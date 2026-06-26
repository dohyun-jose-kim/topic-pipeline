# REVISED PLAN — 90_CLI v3 (2026-04-22 오후 개정, v2)

## Context

`Docs/NEXT_PLAN.md` (오전) 의 §B.B1 (UMAP outlier 가시성) 은 시각 스타일만 다뤘다. 오늘 §C (s5_label-relevance 자동 생성) 완료 (커밋 `27bf7de`) 후 `outputs/s7_report.html` 렌더 검토 중 UMAP 관련 3가지 이슈 발견:

1. **Plotly hover 에 Title 비어 있음** — 튜플팁이 `Title: ...` 로 끝남.
2. **Outlier 점이 non-interactive** — 마우스 올려도 tooltip 안 나옴.
3. **Outlier legend 에 count 없음** — `Outlier` 만, `Outlier (754)` 같은 개수 표기 부재.

3건 모두 §B.B1 의 "UMAP outlier 가 한눈에 구분" 을 "UMAP 의 outlier 가 first-class citizen (가시·인터랙티브·계수)" 로 넓힐 때 함께 해결. Title 은 **s1_fetch 데이터 파이프라인 수정** 필요 — 현재 s1 부터 title 누락이라 s2~s7 어디에도 없음. title 추가 시 **XML 중첩 태그 처리** 가 동반됨 (itertext 평문화 + strip).

**전처리 scope 결정**: title 만 inline 처리. 별도 헬퍼 함수 없음 — 2줄 짜리에 `_clean_title()` 분리는 과함. abstract 전처리는 s2 임베딩 재계산·클러스터 재sweep 을 수반하여 scope 이 훅 커지므로 제외 (KNOWN §1 해결 시 별도 iteration).

---

## 전체 상태 (2026-04-22 오후)

| 항목 | 상태 | 비고 |
|---|---|---|
| §C s5_label-relevance 자동 생성 | ✅ 완료 | 커밋 `27bf7de`. KNOWN §3 해결. color_map 동적 split 부수. |
| **§B.B1 UMAP outlier first-class (확장)** | 🔜 다음 | 원 scope + 데이터 (title + 전처리) + 인터랙티브 + count |
| §E Guided Topic Modeling | 보류 | 후순위. |

> §D (UMAP 2D → 5D) 은 2026-04-22 결정으로 **항목 제거**.

**권장 순서**: §B.B1 완료 → E2E 검증 → Phase 9 (원본 deprecation).

---

## 워크플로우 (사용자 지시 반영)

1. **지금 plan 을 repo 에 문서화** — 이 파일 내용을 `week_f/90_CLI/Docs/REVISED_PLAN.md` 로 저장. 현 브랜치 `week_f-90_cli_v3` 에서 수행.
2. **현 브랜치에 docs commit** — `docs(week_f/90_CLI): REVISED_PLAN v2 (§B.B1 확장 설계)` 같은 의도로 1 커밋.
3. **새 브랜치 분기** — 이름 후보 (사용자 결정): `week_f-90_cli_v3_bb1` / `week_f-90_cli_v3_title-outlier` / 커스텀. 기본 제안: **`week_f-90_cli_v3_bb1`**.
4. **새 브랜치에서 §B.B1 구현** (아래 상세).

---

## §B.B1 확장 — 새 브랜치 상세 계획

### 커밋 구조 (2개)

| 단위 | 단계 | 변경 파일 | 커밋 |
|---|---|---|---|
| A | s1_fetch: ArticleTitle 파싱 inline + `outputs/s1_meta.csv` 재fetch | `steps/s1_fetch.py` | Commit A |
| B-1 | Plotly: outlier 인터랙티브 + legend count + title hover | `steps/s7_report.py` | Commit B |
| B-2 | matplotlib: outlier 스타일 (alpha/size/color/outline) + legend count | `steps/s7_report.py` | Commit B |

2 커밋 근거: 데이터 변경 (외부 PubMed API 재호출, ~3-5분) 과 시각화 변경 (순수 코드) 의 blast radius 분리 → 독립 롤백·검증 가능.

### Commit A — s1_fetch 데이터 선행 (title 만)

**변경**: `src/topic_pipeline/steps/s1_fetch.py::_parse_article` (L64-119) — inline 2 줄 추가.

```python
# _parse_article 내부, L74 이후 (art is None 체크 뒤):
title_elem = art.find("ArticleTitle")
title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""
```

return dict 에 `"title": title,` 추가 (year 다음, abstract 앞).

별도 `_clean_title()` 헬퍼 없음 — 2줄에 함수 분리는 과함. `itertext()` 로 `<i>`, `<sub>` 등 nested 태그 평문화 + `strip()` 만으로 충분. `re.sub` 등 추가 정규화는 speculative feature (CLAUDE.md §2) — 필요 확인 후 추가.

**전처리 적용 범위**:
- **title 만** — itertext + strip (inline).
- abstract 는 **원형 유지** — s2 임베딩 캐시 안정성 우선. KNOWN §1 해결 시 별도 iteration.

**캐시 무효화**: 새 브랜치에서 `rm outputs/s1_meta.csv` 선실행 후 `cli fetch`. `outputs/` 는 gitignored 이므로 `git rm` 불필요 — filesystem `rm` 만. s1_fetch 의 row-count 기반 cache check 가 파일 없으면 자동 재fetch 유도.

**다운스트림 영향**:
- s2 embed cache: **안전**. abstract 만 임베드 (`s2_embed.py:43`). title 추가 영향 없음.
- s3~s7: `shared/convention.py::load_labeled_convention` 이 s2_meta 전체 컬럼 pass-through → title 자동 전파.

### Commit B — s7_report 시각화

**Plotly `_make_plotly_umap` (L227-269)**:

- **outlier 트레이스 (L234-241)**:
  - `hoverinfo="skip"` → `text=outlier_hover_text, hoverinfo="text"`
  - `outlier_hover_text` 를 regular trace 와 동일 shape 로: `f"PMID: {r.pmid}<br>Title: {str(getattr(r, 'title', ''))[:80]}...<br>Topic: Outlier"`
  - `name="outlier"` → `name=f"Outlier ({mask.sum()})"`
  - marker 스타일: `color="lightgray"` → `"#888"`, `size=3` → `10`, `opacity=0.3` → `0.5`
  - **KDE 등고선 없음** (기존대로 outlier 에는 contour 미적용)
- **regular 트레이스 (L249-252)**: `getattr(r, 'title', '') or ''` (NaN 방어). `[:80]` 트런케이션 유지.

**matplotlib outlier scatter (L171-173, L202-204)**:
- `c="lightgray"` → `"#888"`
- `s=3` → `10`
- `alpha=0.3` → `0.6`
- `edgecolors="white", linewidths=0.3` 추가 (outline)
- `label="outlier"` → `f"Outlier ({mask.sum()})"`
- `marker="x"` 유지 (사용자 결정)
- **KDE 등고선 없음** (topic 에는 `_draw_kde_boundary` 호출 유지 L184, L214 — 변경 없음; outlier trace 는 호출 대상 아님, 현재 상태 유지 명시화)

**"UMAP — outlier only" PNG**: 이번 scope **제외**.

### 검증

**Commit A 이후** (~3-5분, 사용자 직접 실행):
```bash
cd /Users/inco/01_Projects/00_Tasks/ifc_ojt_dh.kim/week_f/90_CLI
rm outputs/s1_meta.csv
/Users/inco/01_Projects/00_Tasks/ifc_ojt_dh.kim/week_7/wk7_Transformer/.wk7trf_conda/bin/python \
  -m topic_pipeline.cli fetch --config default_config.yaml
```
체크:
```bash
/Users/inco/01_Projects/00_Tasks/ifc_ojt_dh.kim/week_7/wk7_Transformer/.wk7trf_conda/bin/python -c "
import pandas as pd
df = pd.read_csv('outputs/s1_meta.csv')
assert 'title' in df.columns
print(f'title non-null: {df[\"title\"].notna().sum()}/{len(df)}')
print(f'median len: {df[\"title\"].str.len().median()}')
print(f'blank: {df[\"title\"].eq(\"\").sum()}')
"
```
기대: non-null ~5590/5590, median 80~150, blank 0 근접.

**Commit B 이후** (~5s, API 없음):
```bash
/Users/inco/01_Projects/00_Tasks/ifc_ojt_dh.kim/week_7/wk7_Transformer/.wk7trf_conda/bin/python \
  -m topic_pipeline.cli report --config default_config.yaml
open outputs/s7_report.html
```
육안 체크:
- 일반 토픽 점 hover → Title 실제 값
- outlier 점 hover → tooltip 나타남 (PMID + Title + `Topic: Outlier`)
- Plotly legend 에 `Outlier (754)`
- matplotlib PNG (`umap_original.png`, `umap_relevance.png`): outlier 점 크게·진하게·white outline + legend `Outlier (754)`

### 리스크

1. **Stale cache trap** (최우선): `outputs/s1_meta.csv` 미삭제 시 downstream silent stale. **완화**: Commit A 검증 시 `assert "title" in df.columns`.
2. **Title 없는 PMID**: BookDocument 등. `""` fallback 으로 안전.
3. **XML 중첩 태그**: `itertext()` + `strip()` 로 해결.
4. **Title 트런케이션 80자**: 기존 방식 유지. 잘림 수용.
5. **HTML 용량**: outlier 754점 × ~100자 hover ≈ +75KB. 무시 가능.
6. **matplotlib outline 가독성**: dense 영역에서 시각 부담 가능. 렌더 후 alpha 0.6 → 0.5 등 튜닝 여지.

---

## §A, §B.B2, §D 모두 제거

2026-04-22 결정: §A (시계열 재설계), §B.B2 (outlier pseudo-topic), §D (UMAP 5D) 전부 현 iteration 에서 **항목 취소**. 대체로 §5.2 polish (cf20400) 로 트렌드 리포트 가독성 개선.

---

## Critical files

- `week_f/90_CLI/src/topic_pipeline/steps/s1_fetch.py` — L74, L113-119 (Commit A, inline 2줄)
- `week_f/90_CLI/src/topic_pipeline/steps/s7_report.py` — L170-175, L201-206, L234-260 (Commit B)
- `week_f/90_CLI/src/topic_pipeline/shared/convention.py` — L14-21 (title pass-through 확인용, 변경 없음)
- `week_f/90_CLI/outputs/s1_meta.csv` — 새 브랜치에서 `rm` 대상 (gitignored)
- `week_f/90_CLI/Docs/REVISED_PLAN.md` — 신규 작성 (현 브랜치 docs commit)
- `week_f/90_CLI/Docs/NEXT_PLAN.md` — §B.B1 완료 후 §5 진행 로그 갱신 (새 브랜치)
- `week_f/90_CLI/Docs/KNOWN_LIMITATIONS.md` — (선택) "UMAP title 누락" §5 항목 추가 후 해결 표기

---

## 실행 계획 (체크리스트)

### Phase P1 — 현 브랜치 `week_f-90_cli_v3`
- [ ] 이 plan 을 `week_f/90_CLI/Docs/REVISED_PLAN.md` 로 복사
- [ ] `git add` + `git commit` (docs: REVISED_PLAN v2)
- [ ] 새 브랜치 생성: 기본 `week_f-90_cli_v3_bb1` (사용자 최종 확인)

### Phase P2 — 새 브랜치 Commit A (데이터)
- [ ] `s1_fetch.py::_parse_article` 에 title 추출 inline 2줄 + return dict 에 추가
- [ ] **사용자 수동**: `rm outputs/s1_meta.csv` + `cli fetch` (~3-5분)
- [ ] 검증 스크립트 (title 컬럼 존재 + non-null)
- [ ] `git commit` Commit A

### Phase P3 — 새 브랜치 Commit B (시각화)
- [ ] `s7_report.py` Plotly outlier 트레이스 수정 (hoverinfo, name, marker)
- [ ] `s7_report.py` Plotly regular trace `or ''` 방어
- [ ] `s7_report.py` matplotlib outlier scatter 2곳 수정
- [ ] **사용자 수동**: `cli report` (~5s) + HTML 육안 확인
- [ ] `git commit` Commit B
- [ ] `Docs/NEXT_PLAN.md §5` 진행 로그 + `Docs/KNOWN_LIMITATIONS.md` 항목 추가 — 필요 시 docs commit

### Phase P4 (후속)
- E2E 검증 후 Phase 9 (01~06/ 에 DEPRECATED.md) 진행.

---

## 사용자 확인 대기

- [ ] **새 브랜치 이름**: 기본 제안 `week_f-90_cli_v3_bb1` 로 진행? (또는 alternate 지정)
- [ ] **Phase P1 의 plan 문서 경로**: `week_f/90_CLI/Docs/REVISED_PLAN.md` OK? (다른 위치 희망 시 지정)
