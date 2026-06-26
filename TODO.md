# TODO — 90_CLI 진행 상태

**현재 브랜치**: `week_f-90_cli_v3` (PLAN-v2 Phase 1~8 + v2-pilot 머지 후 분기)
**다음 방향성**: [`Docs/NEXT_PLAN.md`](./Docs/NEXT_PLAN.md) — §A 시계열 재설계 / §B outlier / §C relevance 자동 / §D UMAP 5D / §E guided

## 새 대화창에서 시작할 때 (복붙용 프롬프트)

```
90_CLI v3 작업 이어갈게. 다음 파일을 순서대로 읽어줘:
1. ./TODO.md
2. ./Docs/NEXT_PLAN.md
3. ./Docs/KNOWN_LIMITATIONS.md
4. ./PLAN-v2.md (참고용, 이미 완료)
5. ~/.claude/CLAUDE.md (전역)

현 브랜치: week_f-90_cli_v3.
이전 e2e 결과: 12토픽 (mts=27 수동), outlier 754개, Phase 1~8 완성.
다음 미완 항목은 NEXT_PLAN.md 의 §C(relevance 자동) 또는 §A(시계열 재설계).
§A 착수 시 질문 1~2개 선택 필요 (Q1/Q2/Q3/커스텀).

착수 전:
  (1) 해당 항목의 검증 기준 명시
  (2) 참고할 파일 경로
  (3) 구현 내용 1~2문장 요약
내가 OK 하면 구현 → 검증 → git commit → NEXT_PLAN.md §5 진행 로그 업데이트.
```

## 운영 원칙

- **한 Phase = 한 개의 깔끔한 git commit**
- **각 Phase 검증 기준은 `PLAN-v2.md §8` 의 해당 행 참조**
- **CLAUDE.md 엄수**: ①가정 명시 ②단순성 ③수술적 변경 ④검증 가능 목표
- Phase 단위 완료 후 다음으로 이동. 중간 스킵 금지 (의존성 그래프 `PLAN-v2.md §8` 참조)
- 진행 로그는 아래 표에 일자 + 완료 Phase 기록

---

## Phase 체크리스트

### Phase 1: 스켈레톤
- [x] 패키지 구조 + `pyproject.toml` + `cli.py` 골격 + `config.yaml` 템플릿

### Phase 2: shared/ 모듈 (5개)
- [x] 2a. `shared/colors.py` — COLOR_GROUPS + `get_colors()` RGB 보간 (§13)
- [x] 2b. `shared/relevance.py` — `parse_relevance_order()`
- [x] 2c. `shared/fonts.py` — matplotlib AppleGothic 설정
- [x] 2d. `shared/pubmed.py` — NCBI efetch 래퍼 (재시도 포함)
- [x] 2e. `shared/html_common.py` — CSS/HTML 템플릿

### Phase 3: 잘 정리된 step 먼저 (4개)
- [x] 3a. `steps/s4_enrich.py` — 구 `03_Cluster-to-Topic/enrich_topics_v2.py`
- [x] 3b. `steps/s5_label.py` — 구 `04_Topic_LLM-Assay/label_topics_llm.py`
- [x] 3c. `steps/s6_timeseries.py` 기본 (트렌드 제외) — 구 `05_TimeSeries-Assay/topics_over_time.py`
- [x] 3d. `steps/s7_report.py` — 구 `06_Clustered_Topic_Assay_v3/clustered_topic_report.py`

### Phase 4: s1 수집 통합
- [x] `steps/s1_fetch.py` — PMID → abstract/year + author_kw + MeSH 통합
- 원본 참고: `01_DataFetch/fetch_author_keywords.py` + week_4 abstract fetch 로직

### Phase 5: 클러스터링
- [x] 5a. `steps/s2_embed.py` — SPubMedBERT 임베딩 + 캐시
- [x] 5b. `steps/s3_cluster.py` — BERTopic + sweep + §11 캐시 + §13 outlier 정책
- 원본 참고: `week_7/wk7_Transformer/33_TopicModeling_v3-TopicNumOptimAndUmapD5/`

### Phase 6: End-to-end
- [x] `cli.py` 에서 7 step 순차 호출 + §15 실패 처리 + 로깅

### Phase 7: 트렌드 심화
- [x] `s6_timeseries.py::compute_keyword_trends()` 구현
- [x] `s7_report.py` §5.2 임베드
- 설계 참조: `PLAN-v2-trend.md`

### Phase 8: 마감
- [x] `requirements.txt` / `pyproject.toml` 메타 확정 / `README.md`
- 검증: fresh venv `pip install .` 성공 — 사용자 선택 (TODO: 별도 polish)

### Phase 9: 원본 deprecated
- [x] `01~06` 각 폴더에 `DEPRECATED.md` + 상위 README 포인터 (2026-04-23, commit `9fb5caf`)

---

## 후속 과제

PLAN-v2 의 메인 Phase (1~8) 는 전부 완료. 이후 개선 방향은 새 문서에서 관리:

- [`Docs/NEXT_PLAN.md`](./Docs/NEXT_PLAN.md) — v3 방향성 (시계열 재설계 / Outlier 처리 / s5_label-relevance 자동 / UMAP 5D / guided)
- [`Docs/KNOWN_LIMITATIONS.md`](./Docs/KNOWN_LIMITATIONS.md) — 실행 중 발견 이슈 기록
- [`Docs/v2_pilot_plan.md`](./Docs/v2_pilot_plan.md) / [`v2_pilot_decisions.md`](./Docs/v2_pilot_decisions.md) — v2-pilot 학습 기록

### 남은 항목 (TODO 여기 유지)

- [x] **Phase 9** — 원본 `01~06/` 각 폴더에 `DEPRECATED.md` + 상위 README 포인터 (2026-04-23, `9fb5caf`)

---

## 진행 로그

| 일자 | 완료 Phase | 커밋 해시 | 비고 |
|---|---|---|---|
| 2026-04-21 | Phase 1 | 8ca4f59 | 스켈레톤 + argparse `nargs="*"` + `choices` + `default=[]` 버그 회피 |
| 2026-04-21 | Phase 2a | 4611da7 | COLOR_GROUPS 4그룹 + RGB 선형 보간 |
| 2026-04-21 | Phase 2b | c634290 | parse_relevance_order — md 표 rank→topic_id |
| 2026-04-21 | Phase 2c | d72c099 | setup_mpl (AppleGothic) + matplotlib 의존 추가 |
| 2026-04-21 | Phase 2d | e7d5a5c | efetch_articles iterator + PubMedFetchError + requests 의존 |
| 2026-04-21 | Phase 2e | 9ab32e9 | CSS 상수 + render_page 래퍼 |
| 2026-04-21 | Phase 3a | 8f1165d | s4_enrich 이식 + cli dispatch + bertopic 의존. v2.4 byte-exact 일치 |
| 2026-04-21 | Phase 3b | 60de190 | s5_label 이식 + anthropic 의존. JSON 10토픽×3필드 전부 채움 |
| 2026-04-21 | Phase 3c | 82a4eee | s6_timeseries 기본. CSV + 3 PNG, shared 모듈 통합, outlier 층 경로 |
| 2026-04-21 | Phase 3d | 653bac7 | s7_report. PLAN §5 의 9 섹션, sweep/trend stub, UMAP 캐시, plotly inline |
| 2026-04-21 | Phase 4 | 7a95cc3 | s1_fetch — 5590 PMID → {pmid,year,abstract,author_kw,mesh} 전부 채움 |
| 2026-04-21 | Phase 5a | 25008be | s2_embed — SPubMedBert (5590, 768) float32, 3m40s, NaN 없음 |
| 2026-04-21 | Phase 5b | 37f6dab | s3_cluster — sweep [10,19,37,71,137] → 생존자 [37,71,137] → mts=71 선택. UMAP 2D 로 5토픽 (KNOWN §2). IdentityReducer 로 UMAP 1회만 |
| 2026-04-21 | Phase 6 | 6f5fdd9 | e2e — cli.py loguru+에러처리, convention 헬퍼, s1/s3 캐시, s4~s7 모두 convention 대응. e2e 총 50s (s4 30s + s5 15s + s6 1s + s7 3s) |
| 2026-04-21 | Phase 7 | 69ab2d2 | trend — pymannkendall MK/Sen/CAGR. 20행 stats (2토픽×10kw, 토픽5 부재는 KNOWN §4). s7 §5.2 stub → 임베드 완료 |
| 2026-04-21 | Phase 8 | (자기참조) | 마감 — requirements.txt pin lock, pyproject 메타 (classifiers/authors/keywords), README.md 전체 작성. pip install -e . 재검증 통과 |

---

## v3 진행 로그 (ver3.0.1 — 개선 마일스톤)

ver3.0.1 = v2 정제 복사 베이스라인. 전체 설계: [`Docs/v3_improvement_plan.md`](./Docs/v3_improvement_plan.md) (4테마 × 33변경, M1~M6). 작업 정책: [`CLAUDE.md`](./CLAUDE.md).

| 일자 | 마일스톤 | 커밋 | 비고 |
|---|---|---|---|
| 2026-06-26 | (베이스라인) | `62a8571` | v2 → ver3.0.1 정제 복사 + git init |
| 2026-06-26 | (정책) | `b858846` | CLAUDE.md (GraphRAG 스타일) |
| 2026-06-26 | (플랜) | `0715cba` | v3 개선 플랜 (2단계 산출물) |
| 2026-06-26 | **M1** T2-1/3 | `dd5ce0a` | build: 버전 단일화 + 의존성 캡 + extras. `pip install -e . --no-deps` 로 dynamic 버전 0.1.0 검증 |
| 2026-06-26 | **M1** T2-2 | `e5ff010` | docs: `pip install -e .` 정규화, 절대 conda 경로 제거 (역사적 설계 로그는 provenance 보존) |
| 2026-06-26 | **M1** T2-10 | `e9a056a` | test: shared smoke → pytest 12 (invariant#3 회귀 가드 포함). pytest 12 passed |
| 2026-06-26 | (M1 로그) | `c912f4b` | docs: TODO v3 진행 로그 |
| 2026-06-26 | **M2** T2-4 | `0250dc2` | feat: shared/device.py resolver + compute 섹션 (기본 cpu byte-identical) |
| 2026-06-26 | **M2** T2-5/6/7 | `3ad921a` | feat: --run-id 출력 네임스페이싱 + relevance_md null-safe(anchor 제거) + step별 cfg deepcopy. pytest 18 |
| 2026-06-26 | (별도 요청) | `178c7bd` | docs: CLAUDE_dh_v1.md 범용 작업-방식 템플릿 (백그라운드) |
| 2026-06-26 | **M2** T2-8 | `0dd64b2` | feat: --list-steps/--from/--to + 사전 조건 검증(fail-fast). pytest 26 |
| 2026-06-26 | (M2 로그) | `4745e58` | docs: TODO v3 진행 로그 |
| 2026-06-26 | **M3** LLM-1 | `4b01cbc` | refactor: 중복 _call_claude → shared/llm.py +retry. s5 두 step 재지정 |
| 2026-06-26 | **M3** T2-9 | `32adac4` | refactor: device 강제 → shared/device.setup_torch 통합(s2/s3/s4) + batch_size config화 |
| 2026-06-26 | (M3 로그) | `4a57fd8` | docs: TODO v3 진행 로그 (기반 M1~M3 완료) |
| 2026-06-26 | **M4** T3-1 | `33b6436` | refactor: s1_fetch ingest 소스 디스패치 + S1_COLUMNS 계약 (PubMed byte-identical) |
| 2026-06-26 | **M4** T3-2 | `a7a38b8` | feat: CSV-of-text ingest 어댑터 (합성 정수 pmid, mesh 비움). 순수 pandas 완전 검증 |
| 2026-06-26 | **M4** T3-3 | `35d3337` | refactor: embed 모델 resolve_embed_model 통합 + stale-cache 경고 |
| 2026-06-26 | **M4** T3-4 | `3c95892` | refactor: stop_words resolve_stop_words config화 (english/null/list) |
| 2026-06-26 | (M4 로그) | `94b1096` | docs: TODO v3 진행 로그 (T3-1~4 동기화) |
| 2026-06-26 | **M4** T3-5 | `64f1c51` | feat: s4 MeSH/Author-KW graceful optional (비-PubMed KeyError 방지) |
| 2026-06-26 | **M4** T3-6 | `3ddf795` | feat: s5 프롬프트 도메인 템플릿화(리터럴 제거); rule#2 보존(invariant#3) |

| 2026-06-26 | **M5** T3-7a | `2861e58` | feat: colors split_ranks/load_taxonomy 프리미티브 (기본 3그룹 보존) |
| 2026-06-26 | **M5** T3-7b | `ae56dcd` | refactor: 중복 _build_color_map → colors.build_color_map(taxonomy) 통합 |
| 2026-06-26 | **M5** T3-7c-1 | `6d66632` | refactor: s7 legend·§6 재색상화 taxonomy 일반화 |
| 2026-06-26 | **M5** T3-7c-2 | `cf02435` | refactor: s7 "3그룹" 타이틀 → 그룹 수(n_groups) 기반 |

| 2026-06-26 | **M5** T4-2 | `0020949` | refactor: s7 HTML skeleton → render_page 통합 (head_extra 슬롯 확보) |
| 2026-06-26 | **M5** T4-1 | `2e093b2` | fix: plotly 번들 head 1회 주입 (include_plotlyjs 순서결합 버그) |
| 2026-06-26 | **M5** T4-4 | `8a0d677` | feat: s5_topic_order.json (md 재파싱→invariant#3 유지) + parse_relevance_table |

| 2026-06-26 | **M5** T4-3/T4-5 | `6a6bfcf` | feat: §8 죽은 BERTopic 링크 제거+config화 + s7_results.json |
| 2026-06-26 | **M6** T1-1 | `2d1d44a` | feat: shared/preprocess.py (abstract 정제, 근사·stdlib) |
| 2026-06-26 | **M6** T1-2 | `377f3c9` | feat: s0_preprocess step 등록 (기본 off→skip) |
| 2026-06-26 | **M6** T1-3 | `db91cee` | feat: s2/s3 abstract_clean 우선 소비 + s4 가드 (기본 byte-identical) |
| 2026-06-26 | **M6** T1-6 | `c841e84` | feat: sweep tie-break 옵션 (median_low 기본 \| target-n, KNOWN#4) |
| 2026-06-26 | **M6** T1-7 | `b18c5da` | feat: 선택적 guided 모델링 (seed_topic_list) |
| 2026-06-26 | **M6** T1-8 | (직전) | docs: KNOWN_LIMITATIONS M6 capability·결정 기록 |

> 검증: 스크래치 venv 에서 **pytest 62 passed** (순수 함수·헬퍼·기본경로 단위).
> **M1~M6 핵심 완료** — 모든 신규 기능 opt-in, 기본 config 동작 byte-identical 유지, invariant#3 보존.
> ⚠️ **전체 파이프라인 byte-identical 회귀 + LLM 출력 + M6 활성경로(전처리/target-n/guided)는
> 사용자 실제 env(torch/bertopic+데이터+API키) A/B 검증 필수.**

**잔여(후속·미구현):** T1-5 c_v coherence/diversity 지표, default 플립(전처리 on/5D/target-n — A/B 후),
T4-6 md export·T4-7 serve(optional), cosmetic(s5 요약 bullet·mpl 타이틀), README 전면 동기화.
→ **5단계(검증·리뷰)** 는 사용자 env 에서 실행.

---

## 범용 tool 확장 (2026-06-27, GitHub 이슈 주도 — issues #3~#7 Closed)

발행 후 "쉬운 다목적 범용 tool" 5기능 (baby step + `Closes #N`, push):

| 기능 | 이슈 | 커밋 | 내용 |
|---|---|---|---|
| LLM-optional + 로컬 | #3 | `b7088b9`·`779a049`·`fb53351` | `label.provider` = claude \| **keywords**(무키·오프라인) \| **local**(OpenAI 호환) |
| init + 프리셋 | #4 | `d24cc07` | `--init/--preset`, presets: biomedical·general |
| ingest 어댑터 | #5 | `6fa886c` | jsonl·dir·arxiv (+`_emit_s1_from_df` 공용화) |
| 배포 | #6 | `8b11661` | Dockerfile·.dockerignore·pipx/`build` (presets 패키징 검증) |
| web/serve | #7 | `bf09dfa` | `--serve/--port` (127.0.0.1, logs/ 차단) |

> pytest **86 passed**. 미해결 백로그(should_fix, 이슈 OPEN): #1 `_validate_preconditions` override, #2 sweep `tie_break` 라벨.

---

## 주의사항

- **원본 파일 수정 금지**: `01~06`, `week_7/*` 는 참고만. 복사/재정리만 `90_CLI/src/` 에서.
- **의존성 주의**: 한 Phase 가 깨지면 다음 Phase 에 영향. 검증 기준 통과 못하면 다음으로 넘어가지 않음.
- **테스트 가능 최소 입력**: Phase 4 이후는 `data/pmid_test.csv` (10건) 정도 준비하여 빠르게 검증.
- **Phase 3 먼저 vs Phase 4~5 먼저**: PLAN-v2 에서 "잘 정리된 것부터" 원칙으로 Phase 3 (s4~s7) 먼저. 이때 s1/s2/s3 산출물은 기존 `02_PreviousModelPath/` 의 v2.4 데이터로 대체하여 테스트.
