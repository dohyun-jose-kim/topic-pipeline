# 90_CLI v2 Pilot — 파일럿 브랜치 목표

**브랜치**: `week_f-90_cli_v2_pilot`
**분기 시점**: `week_f @ 39f95cf` (2026-04-21, Phase 1~8 완료 직후)
**목적**: `week_f` 에 섣불리 반영하기 부담스러운 품질 개선 실험들을 묶어서 돌려보고, 결과가 좋으면 선별 merge, 안 좋으면 learning 기록 후 폐기.

---

## 문제 재정의 (2026-04-21, e2e 1차 실행 후)

**현상**: Phase 6 end-to-end 결과 **5 토픽** 생성, v2.4 수작업 결과 **10 토픽** 과 차이.

**원인 분석** (사용자 관찰 기반):
- UMAP 차원 (2D) 문제 **아님** — 2D 여도 충분히 동작할 수 있음
- 실제 원인: **v2.4 는 `min_topic_size=50` 수작업 지정**, 우리 sweep 은 `median_low` 로 `mts=71` 선택 → 5 토픽
- sweep 결과 표를 보면 `mts=37` 이 **8 토픽** 으로 v2.4 10 토픽에 근접한 "더 나은 후보" 였음. 그러나 median_low 가 "생존자 [37, 71, 137] 의 중앙" 인 71 을 선택 → 도메인적으로 덜 적절한 값.
- 즉 **미세한 파라미터 차이** (50 vs 71) 가 결과를 좌우한 것 — 방법론 자체는 정상

**교훈**: 품질 이슈의 근본 원인은 **§12 의 tie-break 규칙** (median_low). 이 규칙이 "통계적 중간값 선호" 인데, 도메인 기준으로는 "토픽 수가 target 에 가까운 것" 또는 "더 fine-grained 한 것" 이 나음.

→ 우선순위 재조정:
- ~~UMAP 5D 전환~~ → **독립 실험** 으로 유지 (orthogonal 한 개선 여지)
- **sweep tie-break 재설계** → **최우선 목표**
- Guided modeling → optional 추가 트랙

---

## 목표 3종

### 1. UMAP 차원 기본값 2D → 5D  *(독립 실험, 우선순위 낮음)*

**출처**: [`KNOWN_LIMITATIONS.md §2`](./KNOWN_LIMITATIONS.md)

**현 상태**:
- PLAN-v2 §4 config 기본값 `umap_n_components: 2`
- §7 base 파일 33_v3-d5 는 `n_components=5` 로 학습 — 내부 불일치
- v2.4 는 5D 로 학습된 것으로 추정

**변경**:
- `config.yaml` (템플릿) 기본값 `2 → 5`
- `phase6_e2e_config.yaml` 의 명시 `2 → 5` (또는 삭제해서 default 상속)
- PLAN-v2 §4 config 예시의 주석도 같이 업데이트

**가설**:
- 5D 로 바꾸면 밀도 분리 좋아져 HDBSCAN 이 더 세분화된 클러스터 찾음
- 토픽 수 기대: 5 → 10~15 범위

**검증 기준**:
- 재학습 후 토픽 수 `>= 8` (v2.4 의 10 에 근접)
- silhouette 유지 (너무 낮아지지 않음, ≥ 0.25)

---

### 2. `min_topic_size` sweep 그리드·선택 로직 재설계  *(최우선)*

**출처**: [`KNOWN_LIMITATIONS.md §4`](./KNOWN_LIMITATIONS.md)

**현 상태** (PLAN-v2 §12):
- 5값 기하급수 그리드 `[10, a, C, b, c]` with `C = sqrt(N)/2`
- cutoff 5조건 AND → 생존자 → **median_low** 선택
- 실측: N=5590 에서 grid `[10, 19, 37, 71, 137]` → 생존 `[37, 71, 137]`
  - `mts=37` → **8 토픽** (v2.4 의 10 에 근접)
  - `mts=71` → **5 토픽** ← median_low 가 이걸 고름
  - `mts=137` → **5 토픽**
- 결과: **5 토픽** (도메인적으로 부족). `mts=37` 이 있었는데도 못 고름.

**가능한 재설계 방향** (이 pilot 에서 탐색):
1. **"목표 토픽 수" 기반 역산**: 사용자가 `target_n_topics: ~10` 을 주면 이를 만족하는 `min_topic_size` 로 역산. BERTopic 의 `nr_topics` 파라미터 활용 가능성 검토.
2. **grid 확장**: 5값 → 7~10값, 하한을 `max(10, C/4)` 로 조정 (현재 grid 가 중앙값 근처에 몰려있음)
3. **tie-break 변경**: median_low → "n_topics 가 target 에 가장 가까운 값" 선호
4. **cutoff 완화**: `silhouette_min` 을 토픽 수 의존 공식으로 (n 많을 때 자연스럽게 낮아지는 분포 반영)

**검증 기준**:
- 도메인 전문가 (=사용자) 가 "이 정도면 v2.4 대비 유의미한 세분화" 라고 판정
- 정량: 토픽 수 8~15 범위, silhouette ≥ 0.25

**주의**: 목표 1 (UMAP 5D) 이 먼저 적용되면 이 재설계 필요 없을 수도 있음. 순서는 **1 → 재측정 → 2** 가 효율적.

---

### 3. Guided Topic Modeling 트랙 추가  *(optional, 품질 추가 개선)*

**출처**: BERTopic `seed_topic_list` 파라미터 (이미 BERTopic 0.16.2 에 존재)

**현 상태**: 현재 파이프라인은 완전 unsupervised — 도메인 지식 주입 없음

**가설**: 수산부산물 기능성 연구는 도메인이 명확하므로 **seed 키워드 셋** 을 주면 해석 가능한 토픽을 유도할 수 있음:
```python
seed_topic_list = [
    ["peptide", "bioactive", "hydrolysate", "antioxidant"],
    ["chitosan", "chitin", "antimicrobial"],
    ["collagen", "wound", "tissue engineering"],
    ["oxidative stress", "toxicity", "hepatopancreas"],
    ["probiotics", "gut microbiome", "aquaculture"],
    # ...
]
BERTopic(seed_topic_list=seed_topic_list, ...)
```

**변경**:
- `config.yaml` 에 `cluster.seed_topic_list` 섹션 추가 (선택, null 이면 완전 unsupervised)
- `s3_cluster.py` 의 `_train_one` 에 `seed_topic_list=...` 전달
- 문서화: seed 선정은 도메인 지식 기반 (v2.4 의 10토픽 결과에서 대표 키워드 추출 후보)

**검증 기준**:
- seed 있을 때: seed 의도에 맞는 토픽이 형성됨 (예: "peptide" seed → 펩타이드 중심 토픽)
- seed 없을 때: 기존 동작 유지 (regression 없음)

**주의**: guided + UMAP 5D + sweep 재설계 동시 변경 시 **원인 분리 어려움**. 순서 권장:
1. UMAP 5D 단독 → 측정
2. guided 추가 → 측정
3. 그래도 부족 시 sweep 재설계

---

## 진행 순서 (권장, 문제 재정의 반영)

```
(현재) 브랜치 생성 완료 + 계획 문서 — week_f-90_cli_v2_pilot @ 7263669
  ↓
Phase P1: 목표 2 (sweep 재설계) — 최우선
  - tie-break 규칙부터 손보고 재학습 → 토픽 수 변화 확인
  - UMAP 은 현재 2D 유지 (원인이 여기 아니라고 판단됨)
  ↓
Phase P2: 결과 평가
  - 토픽 수가 v2.4 (10) 에 근접하고 도메인적으로 타당하면 → week_f 로 merge 후보
  - 부족하면 → Phase P3 로
  ↓
Phase P3: (optional) 목표 3 (guided) — 시드 주입으로 품질 미세 조정
  ↓
Phase P4: (optional) 목표 1 (UMAP 5D) — 독립 실험. 위 개선으로도 부족한 경우 추가 변수로
  ↓
판정:
  - 좋으면: 선별 merge back to week_f
  - 부분만 좋으면: 채택한 변경만 cherry-pick
  - 별로면: 이 문서에 learning 기록 + 브랜치 보존 (historical)
```

---

## 판정 후 action

**좋은 결과**: week_f 로 merge → `KNOWN_LIMITATIONS.md` §2/§4 을 "해결됨" 마킹, §3 (relevance 자동) 는 별도 추적 유지.

**부분 결과**: 효과 있는 것만 cherry-pick, 나머지는 이 문서에 "시도했으나 효과 미미" 로 기록.

**실패**: 이 문서에 원인 분석 추가. 브랜치는 `git branch -D` 대신 **보존** (나중에 재도전할 때 참조).

---

## 로그 (진행 중 수시 기입)

| 일자 | Phase | 커밋 | 관찰 |
|---|---|---|---|
| 2026-04-21 | 브랜치 생성 | - | week_f @ 39f95cf 에서 분기 |
