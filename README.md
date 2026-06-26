# topic-pipeline

> PubMed PMID CSV → 임베딩 → BERTopic 클러스터 → LLM 라벨·관련도 rank → 시계열/트렌드 → 종합 HTML 리포트.

`topic_pipeline.cli` 모듈을 `python -m` 으로 호출해 **8 step** 순차 또는 선택 실행. 설계 문서: [`PLAN-v2.md`](./PLAN-v2.md), [`PLAN-v2-trend.md`](./PLAN-v2-trend.md).

---

## 설치

이 repo 는 `wk7trf_conda` env (week_7 에서 생성) 를 재사용합니다. env 는 **activate 하지 않고** Python 인터프리터 절대경로를 직접 호출합니다.

```bash
PY=/Users/inco/01_Projects/00_Tasks/ifc_ojt_dh.kim/week_7/wk7_Transformer/.wk7trf_conda/bin/python
$PY -m topic_pipeline.cli --help                   # 동작 확인
```

이후 사용법 예시는 위 `$PY` 를 정의했다고 가정합니다.

신규 환경 (다른 머신·CI·배포) 세팅: [`Docs/NEW_ENV_SETUP.md`](./Docs/NEW_ENV_SETUP.md) 참고.

### 환경변수
```bash
export NCBI_API_KEY="..."        # s1 fetch 속도 (10 req/s; 없으면 3 req/s)
export ANTHROPIC_API_KEY="..."   # s5 label / label-relevance (필수)
export NCBI_EMAIL="..."          # NCBI 예의 (선택)
```

---

## DATA/ — 입력 데이터

90_CLI 는 self-contained. `DATA/` 에 PMID CSV 와 수집 스크립트 포함:

| 파일 | 용도 |
|---|---|
| `fetch_pmids.py` | PubMed 쿼리 → 단일 `pmid` 컬럼 CSV |
| `aqua_byproducts-5590.csv` | 수산부산물 기능성 baseline (5,590 건) |
| `sleep_quality-9999.csv` | 수면 질 × 건강 outcome baseline (9,999 건) |

새 도메인:
```bash
$PY DATA/fetch_pmids.py --query '"xyz"[tiab] AND "abc"[tiab]' --output DATA/<name>.csv
```

---

## 사용법

**기본 실행** (default_config.yaml)
```bash
$PY -m topic_pipeline.cli                     # 전체 8 step
$PY -m topic_pipeline.cli fetch               # 특정 step 만
$PY -m topic_pipeline.cli report              # s7 재렌더 (앞 step 은 cache 사용)
$PY -m topic_pipeline.cli timeseries report   # 여러 step 연속
```

**새 도메인**
```bash
$PY DATA/fetch_pmids.py --query '"sleep"[tiab]' --output DATA/sleep.csv
$PY -m topic_pipeline.cli --input-pmid DATA/sleep.csv --relevance-criterion "cognitive function"
# project.주제/데이터 출처 는 파일명·criterion·실제 year 범위로 자동 합성 (config 가 null 이면)
```

**profile 분리**
```bash
cp default_config.yaml my_sleep.yaml   # 편집 후
$PY -m topic_pipeline.cli --config my_sleep.yaml
```

**재현성·디버깅**
```bash
$PY -m topic_pipeline.cli --seed 42                    # 동일 시드
$PY -m topic_pipeline.cli --force-retrain cluster      # s3 캐시 무시
$PY -m topic_pipeline.cli --umap-dim 5 cluster         # UMAP 5D 실험
$PY -m topic_pipeline.cli --min-topic-size 27 cluster  # sweep 생략 직행
```

**모델 교체**
```bash
$PY -m topic_pipeline.cli --label-model claude-opus-4-20250514 label label-relevance
$PY -m topic_pipeline.cli --embed-model sentence-transformers/all-MiniLM-L6-v2 embed   # → s2 재계산
```

**트렌드·리포트 문구**
```bash
$PY -m topic_pipeline.cli --trend-top-n 10 timeseries report
$PY -m topic_pipeline.cli --project-theme "운동생리 연구" --project-source "PubMed 2015~2025" report
```

전체 플래그: `$PY -m topic_pipeline.cli --help`.

---

## 파이프라인 8 step

```
 s1_fetch → s2_embed → s3_cluster → s4_enrich → s5_label → s5_label-relevance → s6_timeseries → s7_report
  PMID→      SPubMed    BERTopic    4-열         Claude     Claude 2차 호출      연도별          종합 HTML
  meta       BERT       sweep +     키워드표     토픽 라벨   relevance rank       + 트렌드        (plotly
  +title     (.npy)     cutoff                               md 자동 생성        (PNG+CSV)       inline)
```

| step | 입력 | 출력 | 설명 |
|---|---|---|---|
| `fetch` | `paths.input_pmid_csv` | `s1_meta.csv` | PMID → title/abstract/year/author_kw/mesh (efetch) |
| `embed` | `s1_meta.csv` | `s2_embeddings.npy` + `s2_meta_for_embed.csv` | SPubMedBERT 인코딩 (빈 abstract drop) |
| `cluster` | `s2_embeddings.npy` | `s3_model_*/` + `s3_labels.csv` + `s3_metrics.csv` + `sweep/` | BERTopic + mts sweep + cutoff + median_low |
| `enrich` | s3 + s1/s2 merge | `s4_keywords_comparison.csv` | 4열 비교 (c-TF-IDF / KeyBERT / Author KW / MeSH) |
| `label` | `s4_keywords_comparison.csv` | `s5_labels.csv` | LLM → 토픽별 EN/KR 라벨 + 설명 |
| `label-relevance` | `s5_labels.csv` | `s5_label-relevance.md` | LLM 2차 호출 → `relevance_criterion` 기준 토픽 rank md |
| `timeseries` | s1 + s3 + s5 + relevance md | `s6_topics_over_time.csv` + `s6_trend_stats.csv` + `s6_figures/*` | 연도별 추이 + 트렌드 통계 (MK/Sen/CAGR) |
| `report` | 전 단계 + s2 embeddings | `s7_report.html` + `s7_figures/*` | 종합 리포트 (plotly UMAP + 이미지 임베드) |

**캐시**: s1 (row count), s2 (shape), s3 (md5) 일치 시 skip. `--force-retrain` 로 s3 재학습.

---

## config

기본: [`default_config.yaml`](./default_config.yaml) — CLI 가 자동 로드.

주요 섹션 (전체 스키마·default 값은 파일 직접 참고):

- `paths` — input/output 경로
- `project` — 주제·데이터 출처 (null 이면 런타임 자동 합성)
- `fetch` — batch_size, NCBI 인증 슬롯 (환경변수 우선)
- `embed` — SentenceTransformer 모델
- `cluster` — min_topic_size (`auto`/숫자), umap_n_components, sweep cutoff
- `label` — LLM 모델, relevance_criterion
- `timeseries.trend` — top_n_keywords, target_ranks, p_threshold, 이동평균
- `report` — intro / metrics_note / relevance_group_note / summary_comment

옛 템플릿은 [`depricated/config-v1_template.yaml`](./depricated/config-v1_template.yaml) 에 보존.

---

## 출력 (`outputs/`)

주요 산출물:
- `s1_meta.csv` — pmid, year, title, abstract, author_keywords, mesh_terms
- `s2_embeddings.npy` — (N, 768)
- `s3_model_d{dim}_t{mts}_s{seed}_{md5}/` + `s3_labels.csv` + `sweep/`
- `s5_labels.csv` + `s5_label-relevance.md`
- `s6_figures/{line_absolute, stacked_*, trend_keywords_topic*}.png` + `s6_*.csv`
- `s7_report.html` + `s7_figures/umap_{original,relevance}.png`
- `logs/run_{timestamp}.log`

중간 산출물 (`s2_meta_for_embed`, `s3_metrics`, `s7_umap_cache` 등) 은 생략.

---

## 알려진 한계

실행 중 발견·미완 이슈: [`Docs/KNOWN_LIMITATIONS.md`](./Docs/KNOWN_LIMITATIONS.md). 주요:

1. 텍스트 전처리 미구현 (raw abstract 사용)
2. UMAP 기본 차원 2D (v2.4 는 5D)
3. ~~`s5_label-relevance.md` 자동 생성~~ → ✅ 해결 (§C)
4. sweep 선택 결과의 도메인적 부적절성 (부분 해결)
5. ~~UMAP title/outlier 인터랙티브~~ → ✅ 해결 (§B.B1)

설계 단계 범위 한계는 [`PLAN-v2.md §9`](./PLAN-v2.md).

---

## 진행 상태 · 라이선스

- 빌드·로드맵: [`TODO.md`](./TODO.md), [`Docs/NEXT_PLAN.md`](./Docs/NEXT_PLAN.md), [`Docs/REVISED_PLAN.md`](./Docs/REVISED_PLAN.md)
- 사내 인턴 과제 산출물 — 외부 배포는 별도 협의
