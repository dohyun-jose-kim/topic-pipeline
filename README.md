# topic-pipeline

> 문서(PubMed PMID 또는 일반 CSV) → 임베딩 → BERTopic 클러스터 → LLM 라벨·관련도 rank → 시계열/트렌드 → 종합 HTML + 구조화(JSON) 리포트.

`topic-pipeline` (또는 `python -m topic_pipeline.cli`) 로 **9 step** 순차/선택 실행. PubMed 외 일반 CSV corpus·다국어 stop-words·run 격리·기계판독(JSON) 출력 지원. 설계: [`PLAN-v2.md`](./PLAN-v2.md), 개선 플랜: [`Docs/v3_improvement_plan.md`](./Docs/v3_improvement_plan.md).

---

## 설치

editable 설치 — `pyproject.toml` 의 console-script `topic-pipeline` 제공:

```bash
pip install -e .                          # 일반 설치 (의존성 자동 해결)
# 재현 핀(권장): pip install -r requirements.txt && pip install -e . --no-deps
pip install -e .[test] && pytest          # 테스트 (선택)
topic-pipeline --help                     # 동작 확인
```

이후 사용법 예시는 `topic-pipeline` 엔트리포인트를 사용합니다 (`python -m topic_pipeline.cli` 도 동일).

신규 환경 (다른 머신·CI·배포) 세팅: [`Docs/NEW_ENV_SETUP.md`](./Docs/NEW_ENV_SETUP.md) 참고.

### 환경변수
```bash
export NCBI_API_KEY="..."        # s1 fetch 속도 (10 req/s; 없으면 3 req/s)
export ANTHROPIC_API_KEY="..."   # s5 label / label-relevance (필수)
export NCBI_EMAIL="..."          # NCBI 예의 (선택)
```
시크릿은 환경변수만 — config·코드·로그에 키 저장 금지.

---

## DATA/ — 입력 데이터

이 repo 는 self-contained. `DATA/` 에 PMID CSV 와 수집 스크립트 포함:

| 파일 | 용도 |
|---|---|
| `fetch_pmids.py` | PubMed 쿼리 → 단일 `pmid` 컬럼 CSV |
| `aqua_byproducts-5590.csv` | 수산부산물 기능성 baseline (5,590 건) |
| `sleep_quality-9999.csv` | 수면 질 × 건강 outcome baseline (9,999 건) |

새 PubMed 도메인:
```bash
python DATA/fetch_pmids.py --query '"xyz"[tiab] AND "abc"[tiab]' --output DATA/<name>.csv
```

**비-PubMed corpus**: `fetch.source: csv` + `fetch.columns`(text/doc_id/year/title/keywords 매핑)로 임의 텍스트 CSV 사용 가능 (doc_id 없으면 1..N 정수 pmid 합성, mesh 비움). 상세는 `default_config.yaml` 의 `fetch:` 주석.

---

## 사용법

**기본 실행** (default_config.yaml)
```bash
topic-pipeline                     # 전체 9 step
topic-pipeline fetch               # 특정 step 만
topic-pipeline report              # s7 재렌더 (앞 step 은 cache 사용)
topic-pipeline timeseries report   # 여러 step 연속
```

**시작·step 목록·범위·run 격리**
```bash
topic-pipeline --init my_proj --preset general   # <my_proj>.yaml 스캐폴딩 (general=무키·CSV | biomedical)
topic-pipeline --list-steps                # step별 모듈·필요/생성 산출물 출력
topic-pipeline --from cluster --to label   # 범위 실행 (positional 미지정 시)
topic-pipeline --run-id exp1               # outputs/exp1/ 로 격리 (동시·다도메인 실행 안전)
```

**새 도메인**
```bash
python DATA/fetch_pmids.py --query '"sleep"[tiab]' --output DATA/sleep.csv
topic-pipeline --input-pmid DATA/sleep.csv --relevance-criterion "cognitive function"
# project.주제/데이터 출처 는 파일명·criterion·실제 year 범위로 자동 합성 (config 가 null 이면)
```

**profile 분리**
```bash
cp default_config.yaml my_sleep.yaml   # 편집 후
topic-pipeline --config my_sleep.yaml
```

**재현성·디버깅**
```bash
topic-pipeline --seed 42                    # 동일 시드
topic-pipeline --force-retrain cluster      # s3 캐시 무시
topic-pipeline --umap-dim 5 cluster         # UMAP 5D 실험 (기본 2D)
topic-pipeline --min-topic-size 27 cluster  # sweep 생략 직행
```

**모델 교체**
```bash
topic-pipeline --label-model claude-opus-4-20250514 label label-relevance
topic-pipeline --embed-model sentence-transformers/all-MiniLM-L6-v2 embed   # → s2 재계산
```

**트렌드·리포트 문구**
```bash
topic-pipeline --trend-top-n 10 timeseries report
topic-pipeline --project-theme "운동생리 연구" --project-source "PubMed 2015~2025" report
```

전체 플래그: `topic-pipeline --help`.

---

## 파이프라인 9 step

```
 s1_fetch → [s0_preprocess] → s2_embed → s3_cluster → s4_enrich → s5_label → s5_label-relevance → s6_timeseries → s7_report
  PMID/CSV   abstract_clean    Sentence   BERTopic     4-열         Claude     Claude 2차 호출       연도별           종합 HTML
  meta       (opt-in)          Trans.     sweep+       키워드표     토픽 라벨   relevance md +        + 트렌드          + JSON
  +title                       (.npy)     cutoff                               topic_order.json      (PNG+CSV)        (results.json)
```

| step | 입력 | 출력 | 설명 |
|---|---|---|---|
| `fetch` | `paths.input_pmid_csv` *(또는 `fetch.source: csv`)* | `s1_meta.csv` | PMID efetch **또는 CSV 어댑터** → pmid/title/abstract/year/author_kw/mesh |
| `preprocess` | `s1_meta.csv` | `s0_meta_clean.csv` | **opt-in** (`preprocess.enabled`): abstract → abstract_clean 정제 (기본 off=skip) |
| `embed` | `s1_meta.csv` *(있으면 `s0_meta_clean.csv`)* | `s2_embeddings.npy` + `s2_meta_for_embed.csv` | SentenceTransformer 인코딩 (빈 텍스트 drop; device/batch config) |
| `cluster` | `s2_embeddings.npy` | `s3_model_*/` + `s3_labels.csv` + `s3_metrics.csv` + `sweep/` | BERTopic + mts sweep + cutoff + **tie-break(median_low 기본 \| target-n)** + (opt) guided |
| `enrich` | s3 + s1/s2 merge | `s4_keywords_comparison.csv` | 4열 비교 (c-TF-IDF / KeyBERT / Author KW / MeSH; 메타 없으면 빈 값) |
| `label` | `s4_keywords_comparison.csv` | `s5_labels.csv` | LLM → 토픽별 EN/KR 라벨 + 설명 (도메인·문서수 템플릿) |
| `label-relevance` | `s5_labels.csv` | `s5_label-relevance.md` + `s5_topic_order.json` | LLM 2차 호출 → `relevance_criterion` 기준 rank md (+ md 재파싱 JSON) |
| `timeseries` | s1 + s3 + s5 + relevance md | `s6_topics_over_time.csv` + `s6_trend_stats.csv` + `s6_figures/*` | 연도별 추이 + 트렌드 통계 (MK/Sen/CAGR) |
| `report` | 전 단계 + s2 embeddings | `s7_report.html` + `s7_results.json` + `s7_figures/*` | 종합 HTML (plotly UMAP, 번들 head 1회) + 기계판독 JSON |

**캐시**: s1 (row count), s2 (shape), s3 (md5+params) 일치 시 skip. `--force-retrain` 로 s3 재학습.
**run 격리**: `--run-id NAME` → 모든 산출물이 `outputs/NAME/` 로 (기본 없음 = `outputs/` 직접).

---

## config

기본: [`default_config.yaml`](./default_config.yaml) — CLI 가 자동 로드. 주요 섹션:

- `paths` — input/output 경로 (+ `run_id` 격리)
- `compute` — `device`(cpu 기본/cuda/mps/auto), `embed_batch_size`
- `preprocess` — `enabled`(기본 false): abstract_clean 정제 on/off
- `project` — 주제·데이터 출처 (null 이면 런타임 자동 합성)
- `fetch` — `source`(pubmed 기본/csv), `columns`(csv 매핑), batch_size, NCBI 슬롯(env 우선)
- `embed` — `model_name`(SentenceTransformer), `stop_words`(english 기본/null/리스트)
- `cluster` — `min_topic_size`(auto/숫자), `umap_n_components`(기본 2), `seed_topic_list`(guided), `sweep.tie_break`(median_low/target) + `target_n_topics` + cutoff
- `label` — `provider`(`claude` 기본 | `keywords` 무키·오프라인 | `local` OpenAI호환) + `base_url`(local), 모델, `relevance_criterion`, `domain`, `relevance_taxonomy`(N그룹; 기본 3그룹)
- `timeseries.trend` — top_n_keywords, target_ranks, p_threshold, 이동평균
- `report` — intro / metrics_note / relevance_group_note / summary_comment / `aux_visualizations`

옛 템플릿은 [`depricated/config-v1_template.yaml`](./depricated/config-v1_template.yaml) 에 보존.

---

## 출력 (`outputs/` 또는 `outputs/<run-id>/`)

주요 산출물:
- `s1_meta.csv` — pmid, year, title, abstract, author_keywords, mesh_terms
- `s0_meta_clean.csv` — (opt-in) abstract_clean 추가본
- `s2_embeddings.npy` — (N, D)
- `s3_model_d{dim}_t{mts}_s{seed}_{md5}/` + `s3_labels.csv` + `sweep/`
- `s5_labels.csv` + `s5_label-relevance.md` + `s5_topic_order.json`
- `s6_figures/{line_absolute, stacked_*, trend_keywords_topic*}.png` + `s6_*.csv`
- `s7_report.html` + `s7_results.json` + `s7_figures/umap_{original,relevance}.png`
- `logs/run_{timestamp}.log`

중간 산출물 (`s2_meta_for_embed`, `s3_metrics`, `s7_umap_cache` 등) 은 생략.

---

## 알려진 한계

실행 중 발견·미완 이슈: [`Docs/KNOWN_LIMITATIONS.md`](./Docs/KNOWN_LIMITATIONS.md). 주요:

1. 텍스트 전처리 — `s0_preprocess` **opt-in** 추가(기본 off, 원본 부재로 **근사**) → §6. 기본은 raw abstract.
2. UMAP 기본 차원 **2D** (5D 는 `--umap-dim 5`/config 옵션) → §6. default 플립은 A/B 후.
3. ~~`s5_label-relevance.md` 자동 생성~~ → ✅ 해결 (§C)
4. sweep 선택 — `tie_break: median_low` 기본, **`target` 모드 opt-in** 추가 → §6.
5. ~~UMAP title/outlier 인터랙티브~~ → ✅ 해결 (§B.B1)

> ver3.0.1 개선(범용 corpus·taxonomy·구조화 출력·전처리 등)과 미구현/결정 보류는 [`Docs/KNOWN_LIMITATIONS.md §6`](./Docs/KNOWN_LIMITATIONS.md) · [`Docs/v3_improvement_plan.md`](./Docs/v3_improvement_plan.md). 설계 단계 범위 한계는 [`PLAN-v2.md §9`](./PLAN-v2.md).

---

## 진행 상태 · 라이선스

- 개선 플랜·진행 로그: [`Docs/v3_improvement_plan.md`](./Docs/v3_improvement_plan.md), [`TODO.md`](./TODO.md)
- 작업 정책: [`CLAUDE.md`](./CLAUDE.md)
- 학습·포트폴리오 목적 공개 — 코드 [MIT](./LICENSE). 실제 데이터·API 키·사내 자료는 미포함(코드/소형 예시만).
