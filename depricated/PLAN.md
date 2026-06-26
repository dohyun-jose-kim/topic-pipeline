# 90_CLI — 토픽 모델링 파이프라인 CLI 패키징

## Context

week_7(임베딩/클러스터링)과 week_f(enrichment/라벨링/시각화/리포트)에 걸쳐 개별 스크립트로 수행된 분석 파이프라인을, `week_f/90_CLI/`에 별도 복사+패키징하여 `--step` 인수로 선택적 실행 가능한 CLI로 만든다.

기존 파일은 건드리지 않는다.

## 파이프라인 7단계

| Step | 이름 | 원본 위치 | 하는 일 |
|---:|---|---|---|
| 1 | `embed` | week_7/31_TopicModeling | CSV → SPubMedBERT 임베딩 (.npy) |
| 2 | `cluster` | week_7/32_TopicModeling_v2 | BERTopic 클러스터링 → 모델 + metrics + 시각화 |
| 3 | `fetch_kw` | week_f/01_DataFetch | PubMed API → author keywords + MeSH |
| 4 | `enrich` | week_f/03_Cluster-to-Topic | 4열 키워드 비교표 생성 |
| 5 | `label` | week_f/04_Topic_LLM-Assay | Claude API → 토픽 라벨 |
| 6 | `timeseries` | week_f/05_TimeSeries-Assay | 연도별 추이 분석 + 리포트 |
| 7 | `report` | week_f/06_Clustered_Topic_Assay | UMAP + 종합 리포트 |

## CLI 사용법

```bash
# 전체 실행
python run.py --config config.yaml

# 특정 단계만
python run.py --config config.yaml --step enrich,label,report

# 단일 단계
python run.py --config config.yaml --step report
```

## 디렉토리 구조

```
week_f/90_CLI/
├── PLAN.md                 # 이 문서
├── run.py                  # CLI 엔트리포인트 (argparse)
├── config.yaml             # 모든 경로 + 설정 통합
├── steps/
│   ├── __init__.py
│   ├── s1_embed.py         # week_7/31 로직 복사+정리
│   ├── s2_cluster.py       # week_7/32 로직 복사+정리
│   ├── s3_fetch_kw.py      # week_f/01 로직 복사+정리
│   ├── s4_enrich.py        # week_f/03 로직 복사+정리
│   ├── s5_label.py         # week_f/04 로직 복사+정리
│   ├── s6_timeseries.py    # week_f/05 로직 복사+정리
│   └── s7_report.py        # week_f/06 로직 복사+정리
├── shared/
│   ├── __init__.py
│   ├── colors.py           # COLOR_GROUPS, build_color_map 등 공유 유틸
│   └── html_common.py      # CSS, HTML 공통 템플릿
└── outputs/                # 실행 결과 (gitignore)
```

## config.yaml 통합

```yaml
# ── 입력 경로 ──
paths:
  input_csv: "../../02_PreviousModelPath/topic_labeled_v2.4.csv"
  embeddings: "../../02_PreviousModelPath/embeddings_SPubMedBert.npy"
  model_dir: "../../02_PreviousModelPath/topic_model_v2.4"
  keywords_csv: "..."
  labels_csv: "..."
  relevance_md: "..."
  metrics_csv: "..."
  v24_figures: "..."
  output_dir: "./outputs"

# ── Step별 설정 ──
embed:
  model_name: "pritamdeka/S-PubMedBert-MS-MARCO"
  cache: true

cluster:
  min_topic_size: 50
  seed: 42

fetch_kw:
  ncbi_api_key: ""  # 환경변수 NCBI_API_KEY로도 가능

label:
  model: "claude-sonnet-4-20250514"

umap:
  seed: 42
  cache: true

# ── 리포트 설정 (기존 config.yaml 내용 통합) ──
report_meta:
  주제: "..."
  데이터 출처: "..."
  # ...

topic_overview:
  labeling_model: "..."
  relevance_criterion: "..."

summary_comment: ""
```

## 각 step 모듈 인터페이스

모든 step은 동일한 인터페이스:

```python
# steps/s4_enrich.py
def run(cfg: dict) -> None:
    """cfg는 config.yaml 전체를 dict로 받음. 필요한 키만 사용."""
    ...
```

`run.py`가 config를 로드하고, 선택된 step들을 순서대로 호출.

## 구현 순서

1. `90_CLI/` 구조 생성 + `config.yaml` + `run.py` 골격
2. `shared/colors.py` + `shared/html_common.py` — 공유 코드 추출
3. `steps/s4_enrich.py` — `enrich_topics_v2.py`에서 복사+정리
4. `steps/s5_label.py` — `label_topics_llm.py`에서 복사+정리
5. `steps/s6_timeseries.py` — `topics_over_time.py`에서 복사+정리
6. `steps/s7_report.py` — `clustered_topic_report.py`에서 복사+정리
7. `steps/s3_fetch_kw.py` — `fetch_author_keywords.py`에서 복사+정리
8. `steps/s1_embed.py` + `steps/s2_cluster.py` — week_7에서 복사+정리
9. end-to-end 테스트: `python run.py --step enrich,label,timeseries,report`

## 핵심 원칙

- 기존 파일 수정 없음 — 전부 복사
- 각 step은 독립적으로 실행 가능 (이전 step의 output이 있으면)
- config.yaml 하나로 모든 경로와 설정 관리
- step 간 데이터는 `outputs/` 디렉토리에 저장, 다음 step이 거기서 읽음

## 검증

```bash
cd week_f/90_CLI

# step 4~7만 실행 (이미 모델+임베딩이 있는 경우)
.wk7trf_conda/bin/python run.py --step enrich,label,timeseries,report

# 확인:
# 1. outputs/ 에 각 step의 결과물 생성
# 2. HTML 리포트 브라우저에서 정상 확인
# 3. --step report 단독 실행 시 이전 결과물 참조하여 동작
```

## 주요 복사 대상 파일

| 원본 | 복사 위치 |
|---|---|
| `week_f/03_Cluster-to-Topic/enrich_topics_v2.py` | `steps/s4_enrich.py` |
| `week_f/04_Topic_LLM-Assay/label_topics_llm.py` | `steps/s5_label.py` |
| `week_f/05_TimeSeries-Assay/topics_over_time.py` | `steps/s6_timeseries.py` |
| `week_f/06_Clustered_Topic_Assay/clustered_topic_report.py` | `steps/s7_report.py` |
| `week_f/01_DataFetch/fetch_author_keywords.py` | `steps/s3_fetch_kw.py` |
| `week_7/.../topicModeling.py` | `steps/s1_embed.py` (임베딩 부분만) |
| `week_7/.../topicModeling_v2.py` | `steps/s2_cluster.py` |
| `week_7/.../plot_umap_scatter.py` | `steps/s7_report.py`에 통합 |
