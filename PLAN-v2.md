# 90_CLI — 토픽 모델링 파이프라인 CLI (v2)

> **v1과의 차이**
> - 스코프: week_f 만 → week_f + week_7(bring pre-trained model + embed) 까지 확장
> - 입력: PMID CSV 한 장 (abstract/year/kw/mesh 는 파이프라인이 수집)
> - 원본 건드림: "무수정 복사" → "충돌 발생 시 리네임 허용"
> - HTML: 두 개(05, 06) → 하나로 통합 (06_v3 기준 + 05 일부)
> - 패키징: Python-level (`pyproject.toml` + `console_scripts`)
> - 원본 `01~06` 폐기: 구동 확인 후 deprecated 표시 (시기는 추후)

---

## 0. 결정 상태

| # | 항목 | 상태 |
|---|---|---|
| 0-1 | UMAP dim / 재학습 정책 — 캐시 기반 β+α 하이브리드 | ✅ 확정 (§11) |
| 0-2 | week_7 base 파일 선정 | ✅ **`33_v3-d5`** (§7) |
| 0-3 | `min_topic_size` 자동 선택 — 5값 기하급수 그리드, cutoff, median_low tie-break | ✅ 확정 (§12) |
| 0-4 | 시계열 심화 — 직접 관련 3토픽의 Author Keywords 추세 | ✅ 확정 ([`PLAN-v2-trend.md`](./PLAN-v2-trend.md)) |
| 0-5 | Outlier 처리 정책 — 재배정 없음, 4번째 그룹으로 시각화 | ✅ 확정 (§13) |
| 0-6 | 참고 문헌 (BERTopic/HDBSCAN) | ✅ 기록 (§14) |
| 0-7 | 운영 정책 — 입력 스키마 / 사전모델 로딩 / 실패 처리 / 로깅 | ✅ 확정 (§15) |

---

## 1. 전체 파이프라인

```
 s1_fetch → s2_embed → s3_cluster → s4_enrich → s5_label → s6_timeseries → s7_report
  PMID→      SPubMed    BERTopic    4-열         Claude     연도별          종합 HTML
  meta       BERT       model+      키워드표     토픽 라벨   + 트렌드통계   (s6 산출물
  +kw+mesh   → .npy     metrics                              (PNG+CSV)      임베드)
```

**s1 단일화**: 기존 "abstract/year 수집" + "author kw/mesh 수집" 2단계를 **PubMed efetch 한 번의 호출**로 통합.

**s6 확장**: 기존 전체 토픽 추이 차트에 더해, **"직접 관련 (1~3위)" 토픽에 대한 정석 트렌드 분석** 결과물(통계표 + 차트)을 추가 산출. → 상세 설계는 [`PLAN-v2-trend.md`](./PLAN-v2-trend.md)

---

## 2. 디렉토리 구조

```
week_f/90_CLI/
├── PLAN-v2.md                  # 이 문서
├── PLAN-v2-trend.md            # 시계열 심화 별도 계획
├── depricated/                 # v1 참고 자료 (구 PLAN.md 등)
├── pyproject.toml              # [project.scripts] topic-pipeline = ...
├── requirements.txt            # 점진적 갱신
├── README.md
├── config.yaml                 # 섹션 네임스페이스 (§4)
├── src/topic_pipeline/
│   ├── __init__.py
│   ├── cli.py                  # argparse 엔트리, step 파싱
│   ├── steps/
│   │   ├── s1_fetch.py         # 구 01 + abstract/year fetch 통합
│   │   ├── s2_embed.py         # 구 week_7/33_d5 의 임베딩 부분
│   │   ├── s3_cluster.py       # 구 week_7/33_d5 의 클러스터링+지표
│   │   ├── s4_enrich.py        # 구 03_Cluster-to-Topic/enrich_topics_v2
│   │   ├── s5_label.py         # 구 04_Topic_LLM-Assay (단일 121줄)
│   │   ├── s6_timeseries.py    # 구 05 + 트렌드 통계 (PLAN-v2-trend.md)
│   │   └── s7_report.py        # 구 06_v3 + s6 산출물 임베드
│   └── shared/
│       ├── colors.py           # COLOR_GROUPS, build_color_map
│       ├── html_common.py      # HTML/CSS 템플릿
│       ├── pubmed.py           # efetch 래퍼
│       ├── fonts.py            # matplotlib 폰트(AppleGothic)
│       └── relevance.py        # parse_relevance_order
└── outputs/                    # 실행 결과 (.gitignore)
    ├── s1_meta.csv
    ├── s2_embeddings.npy
    ├── s3_model_d{N}_t{M}_s{seed}_{md5}/   # 캐시 키로 파라미터+입력해시 인코딩 (§11)
    ├── s3_metrics.csv
    ├── sweep/                    # min_topic_size auto 모드 산출물 (§12)
    │   ├── sweep_metrics.csv
    │   ├── sweep_line.png
    │   ├── sweep_heatmap.png
    │   └── sweep_report.md
    ├── s4_keywords_comparison.csv
    ├── s5_labels.csv, s5_relevance.md
    ├── s6_topics_over_time.csv
    ├── s6_trend_stats.csv       # 트렌드 통계 (MK/Sen/CAGR 등, 상세는 별도 문서)
    ├── s6_figures/              # 전체 + 트렌드 서브 차트
    ├── s7_umap_cache.npy
    ├── s7_report.html
    └── logs/                     # loguru 로그 (§15)
        └── run_{timestamp}.log
```

**경로 재배선 원칙**: 모든 step 은 `outputs/` 중심으로 입출력. 원본의 `02_PreviousModelPath/`, `04_Topic_LLM-Assay/results/` 등 절대경로 참조는 전부 제거.

---

## 3. CLI 사용법 (간소화)

```bash
pip install -e .

# 기본: ./config.yaml 자동 로드, 전체 step 실행
topic-pipeline

# 특정 step (positional, 공백 구분)
topic-pipeline report
topic-pipeline enrich label report

# 다른 config 파일
topic-pipeline --config other.yaml

# 일회성 override
topic-pipeline --umap-dim 5 cluster
```

argparse 스펙:
- `--config` : default `"config.yaml"` (CWD 기준)
- step(s) : positional, `nargs="*"`, 비우면 전체 실행
- `--umap-dim N` : cluster step UMAP 차원 override (고급, 기본 숨김)
- `--force-retrain` : cluster 캐시 무시하고 재학습 (디버그용)

---

## 4. config.yaml (섹션 네임스페이스)

```yaml
project:
  주제: "..."
  데이터 출처: "..."

paths:
  input_pmid_csv: "data/pmid.csv"   # 단일 컬럼 'pmid' CSV (§15)
  output_dir: "./outputs"
  pretrained_from: ""               # 비어있으면 새로 학습. 경로 지정 시 첫 실행에 캐시로 복사 (§15)

fetch:
  ncbi_api_key: ""              # 환경변수 NCBI_API_KEY 우선
  batch_size: 200

embed:
  model_name: "pritamdeka/S-PubMedBert-MS-MARCO"
  cache: true

cluster:
  min_topic_size: auto          # auto = sweep 실행 후 자동 선택 (§12) / 숫자 = 직행
  umap_n_components: 2          # 기본 2D. 2~10 범위. 값 바뀌면 캐시 재학습 (§11)
  seed: 42
  reassign_outliers: false      # 기본 false. outlier(-1) 유지. true 면 reduce_outliers() 호출 (§13)
  sweep:
    grid: null                  # null = 앵커×{0.5,1,2} 자동 생성 (§12)
    cutoff:
      n_topics_min: 4           # 토픽 수 하한
      n_topics_max: 30          # 토픽 수 상한
      silhouette_min: 0.25      # 클러스터 분리도
      imbalance_max: 100        # max(topic_sizes)/min(topic_sizes), outlier(-1) 제외
      min_count_in_topics: 25   # 가장 작은 토픽(outlier 제외)의 문서 수 하한
      # coherence_min: 0.30     # TODO: 논문 근거 확보 후 활성화 예정
      # outlier_max: 0.30       # TODO: 논문 근거 확보 후 활성화 예정

label:
  model: "claude-sonnet-4-20250514"
  relevance_criterion: "생리적 기능성(physiological functionality)"

timeseries:
  summary_comment: |
    (시계열 차트용 코멘트)
  # 트렌드 심화 설정: PLAN-v2-trend.md 에서 정의

report:
  intro: |
    (리포트 도입문)
  metrics_note: |
    (지표 해석)
  relevance_group_note: |
    (3그룹 설명)
  umap_viz:
    seed: 42
    cache: true
  summary_comment: |
    (최종 종합 코멘트)
```

---

## 5. HTML 리포트 섹션 구조 (v3 기준 + TimeSeries 삽입)

```
1. 데이터 개요 (총 N편 / 분류 M편 / outlier K편 투명 표기)
2. UMAP 클러스터링 시각화 (outlier 별도 그룹으로 표시, §13)
3. 모델 품질
   3.1 선택된 모델의 품질 지표                ← 구 §3
   3.2 ★ 하이퍼파라미터 탐색 결과 (NEW)       ← sweep 결과 투명화 (§12)
4. 토픽 라벨링 결과
5. ★ 연도별 추이 (NEW)                        ← 구 topics_over_time_report.html "2. 차트"
   ※ 트렌드 심화 (1~3위 직접 관련) 서브섹션 설계: PLAN-v2-trend.md
   ※ outlier 는 별도 회색 라인 (§13)
6. 생리적 기능성 3그룹 분류                    ← 구 5 (+ outlier 4번째 그룹)
7. 3그룹 재색상화 UMAP                         ← 구 6 (+ outlier 회색x)
8. 보조 시각화                                 ← 구 7
9. 요약 코멘트                                 ← 구 8
```

구 `topics_over_time_report.html` 은 독립 파일로 생성하지 않음. s6 은 차트 PNG + CSV + 트렌드 통계 CSV 만 내고, s7 이 임베드.

---

## 6. 각 step 인터페이스

```python
# src/topic_pipeline/steps/s4_enrich.py
def run(cfg: dict) -> None:
    """cfg 전체를 받되, 필요한 섹션만 사용."""
```

`cli.py` 가 config 로드 + step 파싱 + 선택된 step 의 `run(cfg)` 순차 호출.

---

## 7. week_7 base 파일 선정 근거 (0-2 결정)

| 후보 | 라인 | eval_metrics | UMAP n_components | intertopic 안전체크 |
|---|---:|:---:|:---:|:---:|
| 31_TopicModeling | 371 | ❌ | umap 기본값 | ❌ |
| 32_v2 | 479 | ✅ | umap 기본값 | ❌ |
| **33_v3-d5 (권고)** | 483 | ✅ | **5** (hardcoded) | ✅ |
| 34_v3-d10 | 483 | ✅ | **10** (hardcoded) | ✅ |
| 35_F | — | (heatmap 시각화) | — | 모델링 아님 (선택 보조) |

**실측 diff 결과:**
- `32 → 33`: UMAP `n_components` 명시 + `visualize_topics()` 호출 앞에 "토픽 3개 미만이면 스킵" 안전체크 추가
- `33 → 34`: `n_components` 숫자 하나만 다름

→ **33 은 32 의 상위 호환 (32 + 안전체크 + n_components 명시)**. 34 는 33 에서 숫자만 다른 값.
→ `s3_cluster.py` 에서 `n_components` 를 `cfg["cluster"]["umap_n_components"]` 로 빼면 34 는 파라미터값 5→10 으로 흡수됨.
→ 35_F 는 `metrics_all.csv` + heatmap 기반 "어느 실험 런을 고를지" 선택 보조 도구. PLAN-v2 스코프 외 (향후 `tools/select_run.py` 위치 가능).

---

## 8. 빌드 순서 (16 Phase)

각 Phase 는 **독립 실행/검증 가능** 한 단위. Phase 단위로 git commit. 진행 상태는 [`TODO.md`](./TODO.md) 에서 체크.

| Phase | 작업 | 검증 기준 |
|---|---|---|
| **1** | 패키지 스켈레톤 + `pyproject.toml` + `cli.py` 골격 + `config.yaml` 템플릿 | `pip install -e .` 성공 + `topic-pipeline --help` 출력 |
| **2a** | `shared/colors.py` — COLOR_GROUPS + `get_colors()` RGB 보간 (§13) | 단위 테스트: N=1/3/5/10 에서 보간 결과  검증 |
| **2b** | `shared/relevance.py` — `parse_relevance_order()` | 기존 `topic_physiological_relevance.md` 파싱하여 `[topic_id,...]` 반환 |
| **2c** | `shared/fonts.py` — matplotlib 한글 폰트 (AppleGothic) | import 후 `plt.rcParams["font.family"]` 확인 |
| **2d** | `shared/pubmed.py` — NCBI efetch 래퍼 (재시도 포함) | 10 PMID 배치 호출 성공 |
| **2e** | `shared/html_common.py` — CSS/HTML 템플릿 | 샘플 섹션 렌더 → 브라우저 확인 |
| **3a** | `steps/s4_enrich.py` — 4열 키워드 비교 (구 03) | `outputs/s4_keywords_comparison.csv` 가 기존 v2.4 산출물과 일치 |
| **3b** | `steps/s5_label.py` — Claude API 토픽 라벨 (구 04) | `outputs/s5_labels.csv` 생성, JSON 파싱 성공 |
| **3c** | `steps/s6_timeseries.py` (기본만, 트렌드 제외) — 연도별 집계 + 3종 차트 | CSV + 3 PNG 생성 |
| **3d** | `steps/s7_report.py` — HTML 리포트 (sweep/trend 섹션은 stub) | `outputs/s7_report.html` 브라우저에서 정상 렌더 |
| **4** | `steps/s1_fetch.py` — PMID → abstract/year + author_kw + MeSH 통합 | 10 PMID 테스트 → `outputs/s1_meta.csv` 4 컬럼 확인 |
| **5a** | `steps/s2_embed.py` — SPubMedBERT 임베딩 + 캐시 | `outputs/s2_embeddings.npy` shape 확인 |
| **5b** | `steps/s3_cluster.py` — BERTopic + sweep + §11 캐시 + §13 outlier 정책 | sweep 성공 → `outputs/sweep/` 산출물 + 캐시 디렉토리 생성, 기존 v2.4 결과와 대조 |
| **6** | End-to-end 연결 — `cli.py` 에서 7 step 순차 호출 + §15 실패 처리 + 로깅 | `topic-pipeline` 전체 실행 → `outputs/s7_report.html` 완성 |
| **7** | 트렌드 심화 — `compute_keyword_trends()` + `s7_report.py §5.2` | `outputs/s6_trend_stats.csv` 30행 + 차트 4개, 리포트 §5.2 렌더 ([PLAN-v2-trend.md](./PLAN-v2-trend.md)) |
| **8** | 마감 — `requirements.txt` lock, `pyproject.toml` 메타, `README.md` | fresh venv 에서 `pip install .` 후 `topic-pipeline` 실행 성공 |
| **9** | (추후) 원본 `01~06` deprecated 선언 | 각 폴더에 `DEPRECATED.md` + 상위 README 포인터 |

### 의존성 그래프

```
1 → 2a, 2b, 2c, 2d, 2e (평행 가능, 순차 권장)
         ↓
    3a, 3b, 3c, 3d (의존 shared 각각 다름, 순차 권장)
         ↓
    4 (2d 의존)
         ↓
    5a → 5b
         ↓
    6 (3·4·5 전부 의존)
         ↓
    7 (3c + 3d 확장)
         ↓
    8 (모든 이전 Phase)
```

### 원칙

- **한 Phase = 한 개의 깔끔한 git commit**
- **Phase 완료 시 검증 기준 통과 후 사용자 확인**
- **다음 Phase 착수 전 TODO.md 체크**
- **CLAUDE.md §1~§4 엄수**: 가정 명시 / 단순성 / 수술적 변경 / 검증 가능 목표

---

## 9. 알려진 한계 / 이후 과제

v2 는 **완성도 우선, 일반화는 후속** 기조. 다음은 의도적으로 다루지 않음:

- **HTML 하드코딩**: 섹션 구조가 코드 내 문자열. Jinja2 등 템플릿화는 후속.
- **LLM 로컬 의존**: Claude API 호출. 로컬 LLM 대체 보류.
- **config.yaml 범용화 한계**: `relevance_criterion`, 3그룹 분류 등 도메인 특화 개념 잔존.
- **K 선택 자동화 (0-3)**: `min_topic_size` 자동 선택 전 과정 §12 확정. `coherence` / `outlier_ratio` 컷오프 활성화는 논문 근거 확보 후 (주석 처리 상태). `umap_n_components` 는 §11 의 캐시 기반 수동 탐색으로 해결.
- **웹/API 배포**: 후속. 현재는 `pyproject.toml` 구조만 그 방향에 정렬.

> 현재 파이프라인의 **미완/미정 항목** (전처리, UMAP dim 등 실행 중 발견된 이슈) 은 [`Docs/KNOWN_LIMITATIONS.md`](./Docs/KNOWN_LIMITATIONS.md) 에서 별도 추적.

---

## 10. 원본 `01~06` 처리

- **지금**: 건드리지 않음 (참조/실험 공간)
- **90_CLI 구동 검증 후**: 각 디렉토리 `DEPRECATED.md` + README 이동 공지
- **시점**: 추후 결정

---

## 11. UMAP dim / 재학습 정책 (0-1 상세)

### 핵심
메커니즘은 **β (재학습 가능)**, 결과 캐시로 **α (로드) 효과**. 사용자는 모드 의식하지 않음 (γ UX).

### 동작
```
첫 실행 (umap_n_components=2, 기본값)
  캐시 조회 → 없음 → 학습 → 캐시 저장

두 번째 실행 (같은 값, 같은 입력)
  캐시 조회 → 적중 → 로드만

탐색 실행 (--umap-dim 5)
  캐시 조회 → 없음 (키 다름) → 학습 → 별도 캐시 저장

입력 CSV 교체 (md5 변화)
  캐시 조회 → 없음 (해시 다름) → 자동 재학습
```

### 캐시 키 구조
```
outputs/s3_model_d{umap_n_components}_t{min_topic_size}_s{seed}_{md5_8}/
예: outputs/s3_model_d2_t50_s42_a3f2c8b1/
```

| 키 컴포넌트 | 의미 | 변경 시 동작 |
|---|---|---|
| `d{N}` | UMAP n_components | 값 바뀌면 재학습 |
| `t{M}` | min_topic_size | 값 바뀌면 재학습 |
| `s{seed}` | random seed | 값 바뀌면 재학습 |
| `{md5_8}` | 입력 `pmid.csv` md5 앞 8자 | 입력 바뀌면 재학습 |

### 구현 (세 줄)
```python
import hashlib
md5 = hashlib.md5(Path(cfg["paths"]["input_pmid_csv"]).read_bytes()).hexdigest()[:8]
cache_dir = Path(cfg["paths"]["output_dir"]) / f"s3_model_d{d}_t{t}_s{s}_{md5}"
```

### 수동 무효화
`--force-retrain` 플래그. 디버그/재검증 용도.

### 같은 패턴 확장 여지 (지금은 미구현)
- `s1_fetch`: `pmid.csv` md5 기반 캐시
- `s2_embed`: `s1_meta.csv` md5 + embedding model 이름 기반 캐시
- 지금은 **가장 비싼 s3 만** 적용. 필요해지면 확장.

---

## 12. `min_topic_size` 자동 선택 (0-3 상세)

### 실행 구조 — B (config `auto`)

```yaml
cluster:
  min_topic_size: auto   # ← 이 모드
```

- 첫 실행: sweep 돌려 선택값 결정 → 학습 → 결과 캐시
- 두 번째 실행: 캐시 hit 면 sweep 스킵
- `min_topic_size: 50` (숫자) 로 박으면 sweep 생략, 직행

### 선택 알고리즘

```
1. 그리드 구성 (아래)
2. 각 값으로 학습 + 지표 4종 측정 (silhouette, coherence, outlier_ratio, n_topics)
3. 컷오프 적용 → 생존자만 남김
4. 생존자가 여러 개면 median_low 로 선택 (짝수일 때 더 fine한 쪽)
5. 선택값으로 본 학습 진행
```

### 그리드 구성 — 5값 기하급수, center=sqrt(N)/2 고정

**형태**: `[10, a, C, b, c]` — 하한 10 고정, 중앙값 C = sqrt(N)/2 고정, 5개 값이 **기하급수** (공통비 r).

**도출**:
```
5항 기하급수: [10, 10r, 10r², 10r³, 10r⁴]
grid[2] = 10r² = C = sqrt(N)/2
⟹ r = √(C/10) = √(sqrt(N)/20)
```

```python
def default_grid(N: int) -> list[int]:
    C = max(10, round(N**0.5 / 2))
    if C <= 10:
        return [10]                     # N ≤ 400 축퇴 케이스
    r = (C / 10) ** 0.5
    return [
        10,
        round(10 * r),                  # a = 10r = √(10·C)
        C,                              # center = sqrt(N)/2
        round(C * r),                   # b = 10r³ = C·r
        round(C * r * r),               # c = 10r⁴ = C²/10
    ]
```

### N 스케일별 결과

| N | C | r | 그리드 `[10, a, C, b, c]` | 비고 |
|---:|---:|---:|---|---|
| 1,000 | 16 | 1.27 | `[10, 13, 16, 20, 26]` | r 이 작아 그리드가 압축됨 |
| **5,590** | **37** | **1.92** | **`[10, 19, 37, 71, 137]`** | **사용자 프로젝트 — r≈2 (거의 doubling)** |
| **6,400** | **40** | **2.00** | **`[10, 20, 40, 80, 160]`** | **pivot point — 정확히 doubling (textbook)** |
| 10,000 | 50 | 2.24 | `[10, 22, 50, 112, 250]` | |
| 100,000 | 158 | 3.97 | `[10, 40, 158, 627, 2490]` | |
| 1,000,000 | 500 | 7.07 | `[10, 71, 500, 3536, 25000]` | r 이 커져 그리드가 벌어짐 |

**성질**:
- 하한 **항상 10** (BERTopic 기본값)
- 중앙값 **항상 sqrt(N)/2** (리터러처 암묵적 sweet spot, §14 참조)
- 같은 N 안에서 공통비 r 일정
- **N=6,400 이 자연 pivot point** (r=2 정확히 성립)
- N=6,400 미만: r<2, 그리드 압축 / N=6,400 초과: r>2, 그리드 확장

### cutoff=25 와의 상호작용 (N=5,590 기준)

그리드 `[10, 19, 37, 71, 137]` 에서:
- **10, 19**: 결과 min_count 가 25 미만일 가능성 → 탈락 예상
- **37, 71, 137**: 결과 min_count ≥ 37 → min_count 컷오프 자동 통과

소형 2개는 "경계 탐색" 역할, 실제 선택은 주로 뒤쪽 3개.

### 축퇴 케이스 (N ≤ 400)

`C ≤ 10` 이 되면 그리드가 `[10]` 단일값. 이 경우 경고 메시지 출력 후 config `grid: [...]` 수동 지정 권유.

### config grid 직접 지정 정책

사용자가 `config.yaml` 에 `grid: [15, 25, 40, 60]` 식으로 박으면:
- **자동구성 무시** (공식 호출 안 함)
- **floor 체크 스킵** (사용자가 10 미만 값도 박을 수 있음)
- **cutoff 는 여전히 적용** (품질 필터는 유지)

### 컷오프 (확정)

**활성 5조건 (AND)** — 모두 통과해야 생존자:

| 지표 | 조건 | 의미 |
|---|---|---|
| `n_topics` | `4 ≤ n_topics ≤ 30` | 토픽 수 범위 |
| `silhouette` | `>= 0.25` | 클러스터 분리도 |
| `imbalance_ratio` | `max/min < 100` | 토픽 크기 불균형 방지 (outlier 제외) |
| `min_count_in_topics` | `>= 25` | 가장 작은 토픽도 분석 가능 크기 (outlier 제외) |

**측정만 하고 필터링 안 하는 2지표**:
- `coherence` (C_v 토픽 일관성)
- `outlier_ratio` (미분류 비율)

→ sweep_metrics.csv 와 sweep_line.png 에 **표시하되 생존자 필터에는 사용 안 함**.

**TODO 메모 (논문 근거 확보 후 활성화 예정)**:
```yaml
# coherence_min: 0.30    # C_v >= 0.30 ("양호" 기준 하한 후보)
# outlier_max: 0.30      # outlier 비율 30% 이하
```

→ config.yaml 에 주석으로 박아두고, 근거 확정 시 주석 해제.

### Imbalance / Min-count 계산 세부

둘 다 **outlier 토픽(-1) 을 제외하고** 계산:

```python
non_outlier_sizes = [count for tid, count in topic_counts.items() if tid != -1]
imbalance = max(non_outlier_sizes) / min(non_outlier_sizes)
min_count = min(non_outlier_sizes)
```

### Tie-break — median_low

생존자 중앙값. 짝수 개수일 때 `statistics.median_low()` 로 아래쪽 선택 (더 fine한 클러스터링 보존).

```
생존자: [30, 50, 80, 100]  →  median_low = 50 (not 80)
생존자: [30, 50, 80]       →  median = 50
```

### 산출물 (`outputs/sweep/`)

| 파일 | 내용 |
|---|---|
| `sweep_metrics.csv` | 그리드 전부 + 지표 + 컷오프 통과 + 선택 표시 |
| `sweep_line.png` | x=min_topic_size, y=지표별 subplot. 컷오프 경계 + 선택값 vertical line |
| `sweep_heatmap.png` | 35_F 스타일 heatmap (행=값, 열=지표) |
| `sweep_report.md` | "선택: 50. 생존자 4개 중 median_low" 1줄 해설 |

사용자가 사후에 `outputs/sweep/` 만 보면 "왜 이 값이 뽑혔는지" 납득 가능.

### 실패 처리 — 하드 실패 + 진단 표

생존자 0명이면 파이프라인 중단. 각 grid 값이 **어느 조건을 어떻게 위반했는지** 표로 stdout 에 출력.

**CLI 출력 예** (N=5,590, 그리드 `[10, 19, 37, 71, 137]`):
```
❌ sweep 실패: 그리드 5개 값 모두 컷오프 미통과

  min_topic_size | n_topics | silhouette | imbalance | min_count | status
  ──────────────────────────────────────────────────────────────────────────
              10 |       42 |       0.19 |       234 |        12 | ❌ n_topics>30, silhouette<0.25, imbalance>100, min_count<25
              19 |       28 |       0.22 |        88 |        19 | ❌ silhouette<0.25, min_count<25
              37 |       22 |       0.24 |        75 |        37 | ❌ silhouette<0.25
              71 |       18 |       0.23 |        55 |        71 | ❌ silhouette<0.25
             137 |       14 |       0.22 |        38 |       137 | ❌ silhouette<0.25

해결 방법 (택 1):
  1. config 의 cutoff 값을 조정 (예: silhouette_min 을 0.20 으로)
  2. min_topic_size: 37 같이 숫자로 박아 sweep 건너뛰기
  3. grid: [200, 300, 500] 같이 범위를 달리해서 재실행
  4. 데이터/전처리 재검토 (silhouette 전반이 낮으면 임베딩 품질 의심)
```

같은 내용을 `outputs/sweep/sweep_report.md` 에도 저장하여 사후 추적 가능.

구현: `s3_cluster.py::run()` 에서 `len(survivors) == 0` 이면 `raise SweepFailedError(diagnostic_table)`. `cli.py` 가 이 예외를 받아 포맷해 출력 후 `sys.exit(1)`.

### 리포트 삽입 (성공 시)

sweep 성공 시, 결과를 HTML 리포트 §3.2 "하이퍼파라미터 탐색 결과" 에 삽입:

- **sweep_metrics 표**: 그리드 전체 + 지표 + 컷오프 통과 + 선택값 하이라이트
- **sweep_line.png**: 지표별 subplot + 선택값 vertical line
- **1줄 해설**: "8개 값 중 4개 생존 → median_low = 50 선택"

→ 리포트만 봐도 "왜 `min_topic_size=50` 이 선택됐는지" 투명하게 파악 가능. sweep 은 숨겨진 자동화가 아니라 **문서화된 선택 근거**.

실패 시에는 메인 리포트 생성 자체가 안 됨 (파이프라인 s3 에서 중단). `outputs/sweep/sweep_report.md` 만 남음.

---

## 13. Outlier 처리 정책

### 핵심 방침
- **HDBSCAN 재배정 없음** (`reduce_outliers()` 호출 제거)
- outlier(-1) 는 -1 로 그대로 유지
- 시각화에서는 **4번째 그룹** 으로 별도 표시 (은닉하지 않음)

### Config 토글

```yaml
cluster:
  reassign_outliers: false    # CLI 기본. true 면 reduce_outliers() 호출 (레거시 재현용)
```

### COLOR_GROUPS — Range 기반 동적 보간

**설계 원칙**: 하드코딩된 3/4/3 색상 배열이 아니라, 그룹별 **start/end 색상**을 정의하고 토픽 수 n 에 따라 **RGB 선형 보간**으로 n개 색 생성.

```python
COLOR_GROUPS = [
    {"label": "직접 관련",   "start": "#1b7a3d", "end": "#a8dfc0"},  # 짙은 → 연한 초록
    {"label": "간접 관련",   "start": "#1a5276", "end": "#c5e2f4"},  # 짙은 → 연한 파랑
    {"label": "낮은 관련도", "start": "#b0855a", "end": "#e2c291"},  # 짙은 → 연한 갈색 (약간 노랗게)
    {"label": "Outlier",     "start": "#bdc3c7", "end": "#bdc3c7",   # 단일 톤
                             "marker": "x", "alpha": 0.3},
]

def get_colors(group: dict, n: int) -> list[str]:
    """그룹 내 n개 토픽에 대해 start→end 선형 보간한 n개 색상 반환."""
    if n <= 0:
        return []
    if n == 1:
        return [group["start"]]
    start = hex_to_rgb(group["start"])
    end   = hex_to_rgb(group["end"])
    return [
        rgb_to_hex(tuple(round(s + (i/(n-1)) * (e-s)) for s, e in zip(start, end)))
        for i in range(n)
    ]
```

**장점**:
- 토픽 분포가 3/4/3 가정에서 벗어나도 (예: 1/7/2, 5/5/0, 10/0/0) **자동 대응**
- 각 그룹 내 색상 그라디언트가 토픽 수에 맞춰 균등 분포

### 동작 예시

| 시나리오 | 직접 | 간접 | 낮은 | 설명 |
|---|---|---|---|---|
| 사용자 현재 (3/4/3) | 3단계 초록 | 4단계 파랑 | 3단계 갈색 | 기본 케이스 |
| 편중 (1/7/2) | 단색 초록 | 7단계 파랑 | 2단계 갈색 | 간접이 우세 |
| 극단 (10/0/0) | 10단계 초록 (전체 span) | — | — | 모두 직접 |

### 기존 대비 중간 색상 차이

RGB 선형 보간이라 기존 하드코딩 중간값과 살짝 다름:

| 그룹 | 기존 N=3/4 | 신규 보간 결과 |
|---|---|---|
| 직접 | `#27ae60` (중간) | `#61ab7e` |
| 간접 | `#2e86c1, #5dade2` | `#5c8bb1, #93b5d2` |
| 낮은 | `#c9a375` (중간) | `#c9a375` (거의 동일 — 팔레트 B 끝점 보존) |

시각적으로는 인접 톤이라 구별감은 유지됨.

### 변경 포인트

- 하드코딩 `colors: [hex, hex, hex]` → range 기반 `start/end` + 보간 함수
- "낮은 관련도" 는 순수 갈색 range (구버전은 갈색+회색 혼재)
- Outlier 는 별도 그룹 (start=end 동일로 단일 톤 표현), 구 "낮은 관련도" 회색 `#bdc3c7` 재활용

**시각 구분 규칙**:
- 분류된 토픽: 색상 구분 + 기본 마커 (●)
- Outlier: `#bdc3c7` + `x` 마커 + alpha 0.3 → "분류된 것과 다르다" 즉시 구분

### 범례 포맷

```
■ 직접 관련 (1~3위)   ■ 간접 관련 (4~7위)   ■ 낮은 관련도 (8~10위)   ✕ Outlier (N편)
```

### 영향 받는 산출물

| 대상 | 변경 |
|---|---|
| **s3_cluster** | `reduce_outliers()` 호출하지 않음 (토글 false 시) |
| **s4_enrich** | 4열 키워드 계산 시 `-1` 제외 (기본 동작) |
| **s5_label** | 라벨 생성 대상에서 `-1` 제외 (기본 동작) |
| **s6_timeseries** | stacked/line 차트에 **outlier 레이어 포함** (회색 점선, 맨 아래/위) |
| **s7_report §1** | "총 N편 (outlier M편 포함)" 투명 표기 |
| **s7_report §2 UMAP** | 10개 토픽 색상 + outlier 회색 × 마커 |
| **s7_report §7 재색상화 UMAP** | 3그룹 + outlier 회색 × 마커 |
| **sweep metrics** | `outlier_ratio` 측정만 (컷오프 아님, §12) |

### 리포트 §1 투명성 표기 예시

```
분석 대상: 5,590편 (2000~2026년 PubMed)
├── 분류된 토픽(0~9): 4,419편 (79.05%)
└── Outlier(-1):     1,171편 (20.95%) ← 시각화에 별도 그룹으로 표시

본 리포트의 토픽별 분석은 outlier 를 제외한 4,419편 기준.
연도별 총 논문수 차트(§5.1) 에는 outlier 포함된 5,590편 전부 표시.
```

### 왜 재배정하지 않는가

HDBSCAN 의 outlier 는 "기존 클러스터 어디에도 충분한 밀도로 속하지 않는 문서". 이를 `reduce_outliers()` 로 강제 배정하면:
- **정보 소실**: 어떤 문서가 경계적이었는지 사후 추적 불가
- **토픽 오염**: 이질 문서가 토픽 통계/키워드를 왜곡
- **해석 어려움**: "정말 이 토픽인가 밀려난 것인가" 구분 불가

CLI 는 **투명성 우선** — outlier 를 별도 그룹으로 드러내어 "어떤 문서가 분류 실패했는지" 확인 가능하게 유지.

### 레거시 재현 시나리오

기존 v3 리포트처럼 재배정된 결과를 재현해야 할 때:
```yaml
cluster:
  reassign_outliers: true
```
→ `topic_model.reduce_outliers(strategy="c-tf-idf")` 호출, outlier 가 최근접 토픽으로 흡수됨.

---

## 14. 참고 문헌 (References)

BERTopic/HDBSCAN 파라미터 튜닝, 특히 `min_topic_size` 의 N 의존성에 대한 조사 결과. 공식 수식은 공개 문헌에 없고, Maarten 권고치(1M 문서에 100~500) 를 역산하면 `sqrt(N)/2` 가 가장 잘 부합 — §12 그리드 공식의 근거.

### 공식 문서

- [BERTopic — Parameter Tuning](https://maartengr.github.io/BERTopic/getting_started/parameter%20tuning/parametertuning.html)
- [BERTopic — FAQ](https://maartengr.github.io/BERTopic/faq.html)
- [BERTopic — Best Practices](https://maartengr.github.io/BERTopic/getting_started/best_practices/best_practices.html)
- [BERTopic — API (BERTopic class)](https://maartengr.github.io/BERTopic/api/bertopic.html)
- [HDBSCAN — Parameter Selection](https://hdbscan.readthedocs.io/en/latest/parameter_selection.html)

### GitHub 이슈 (권고치 근거)

- [Issue #1111 — Question about topic size](https://github.com/MaartenGr/BERTopic/issues/1111) (N=2M, min_topic_size=500 사례)
- [Issue #1128 — min_topic_size](https://github.com/MaartenGr/BERTopic/issues/1128)
- [Issue #1642 — Hyperparameter Tuning](https://github.com/MaartenGr/BERTopic/issues/1642)

### 논문 / 관련 도구

- [BERTopic 원 논문 (Grootendorst, 2022) — arXiv:2203.05794](https://arxiv.org/abs/2203.05794)
- [TopicTuner — HDBSCAN Tuning for BERTopic (drob-xx/TopicTuner)](https://github.com/drob-xx/TopicTuner) (내부 그리드 전략은 미공개)

### 핵심 발췌

| 출처 | 발췌 내용 | 암시 공식 |
|---|---|---|
| BERTopic FAQ | "If it nears a million documents, set it much higher than 10, e.g., 100 or 500" | sqrt(1M)/2 ≈ 500 ✓ |
| BERTopic FAQ | "we can set min_topic_size much higher (e.g., 300)" for large datasets | sqrt(90k)/2 ≈ 150, sqrt(360k)/2 ≈ 300 |
| HDBSCAN docs | "set to the smallest size grouping you wish to consider a cluster" | 도메인 기반, 공식 없음 |
| BERTopic 기본값 | 10 | 하한 |

**결론**: `min_topic_size ≈ sqrt(N)/2` 는 공식 문헌에 명시된 수식은 아니지만, Maarten 의 권고치 범위를 가장 잘 설명하는 경험식. §12 그리드는 이 중앙값을 기하급수 공통비 `r = √(C/10)` 로 확장한 구조.

---

## 15. 운영 정책 (Ops)

### 15-1. 입력 CSV 스키마

`data/pmid.csv` (경로는 config `paths.input_pmid_csv`):

```csv
pmid
12345678
23456789
34567890
```

- **필수 컬럼**: `pmid` (한 개)
- **허용 형식**: 정수 또는 문자열, 헤더 필수
- **선택 컬럼**: 지금은 없음. 추후 `query_tag`, `batch_id` 등 추가 여지 있으나 v2 스코프 외
- **검증**: `s1_fetch` 시작 시 컬럼 존재 확인 + PMID 형식 체크 (7~8자리 숫자)

### 15-2. 사전학습 모델 로딩

기존 v2.4 같은 학습 완료 모델을 가져오는 시나리오 지원.

```yaml
paths:
  pretrained_from: "/path/to/topic_model_v2.4"   # 비어있으면 무시
```

**로딩 절차**:
1. 첫 실행 시 `pretrained_from` 경로 읽어 모델의 파라미터 (umap_n_components, min_topic_size, seed) 추출
2. 해당 파라미터 + 입력 pmid.csv md5 로 캐시 키 생성 → `outputs/s3_model_d{N}_t{M}_s{seed}_{md5}/`
3. 원본 모델을 캐시 디렉토리로 복사
4. 캐시 디렉토리 안에 `_provenance.json` 저장:
   ```json
   {"source": "/path/to/topic_model_v2.4", "copied_at": "2026-04-21T12:34:56"}
   ```
5. 이후 실행은 일반 캐시 hit 로 처리됨 (§11 과 동일 경로)

**주의**: 원본 모델의 파라미터와 현재 config 의 `cluster.umap_n_components` / `cluster.min_topic_size` 가 불일치하면 **경고 후 원본 기준으로 override** (원본이 진실).

### 15-3. 실패 처리 — Fail-fast + 명확한 메시지

**기본 원칙**: 예상 가능한 실패는 **명시적으로 알리고 즉시 중단**. 자동 복구보다 사람 개입 우선.

| 지점 | 실패 시 동작 |
|---|---|
| **s1 PubMed fetch** | 기본 재시도 3회 (원본 `fetch_author_keywords.py` 보존). 실패 시 `PubMedFetchError` + exit(1). 수동으로 PMID 나눠 재실행 |
| **s5 LLM (Claude) call** | anthropic SDK 기본 재시도 + CLI 레벨 한 번 더 (총 2 패스). 실패 시 `LLMCallError` + exit(1) |
| **s3 sweep 전체 실패** | 이미 §12 에 정의 — 하드 실패 + 진단 표 |
| **입력 스키마 오류** | s1 시작 직후 `InputSchemaError` + exit(1) |
| **파일 누락** (config 경로) | step 시작 시 `FileNotFoundError` + exit(1) |

**Step 단위 저장 정책**:
- 각 step 은 끝까지 완료되어야 자기 산출물을 `outputs/` 에 저장
- 중간 실패 시 부분 산출물 남기지 않음 (`.tmp` 경로에서 atomic move)
- 하나의 step 내에서 `--resume` 같은 부분 재개 없음
- **Step 간 재개는 지원** — `topic-pipeline enrich label report` 처럼 실패한 step 이후만 재실행

### 15-4. 로깅 / 진행 표시

의존성 2개 추가:
```
tqdm      : 배치 루프 progress bar (PMID fetch, embed 등)
loguru    : stdout + outputs/logs/run_{timestamp}.log 동시 기록
```

**loguru 설정 예**:
```python
from loguru import logger
from pathlib import Path
from datetime import datetime

log_path = Path("outputs/logs") / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
log_path.parent.mkdir(parents=True, exist_ok=True)
logger.add(log_path, rotation=None, retention=None, level="INFO")
```

**로그 레벨 정책**:
- `INFO`: step 시작/완료, 선택된 파라미터, 파일 경로
- `WARNING`: 재시도, 캐시 무효화, outlier 비율 높음 등 "알 필요 있음" 이벤트
- `ERROR`: 실패 지점 + traceback
- `DEBUG`: 상세 (환경변수 `LOGURU_LEVEL=DEBUG` 로 활성화)

**tqdm 적용 지점**:
- `s1_fetch`: PMID 배치 루프
- `s2_embed`: 문서 임베딩 (SentenceTransformer 내부에도 이미 있음)
- `s4_enrich`: KeyBERT 적용
- `s6_timeseries`: 키워드별 연도 집계 (단어 많을 때)

### 15-5. CLI 실행 스코프 — 현재 방식 유지

사용자가 특정 step 들을 선택해 실행:
```bash
topic-pipeline                        # 전체
topic-pipeline fetch embed cluster    # 앞쪽만
topic-pipeline enrich label           # 중간만
topic-pipeline report                 # 마지막만
```

**`--stop-after` / `--from` 플래그 도입 안 함**. 현재 positional step 방식으로 충분 (사용자 확인).
