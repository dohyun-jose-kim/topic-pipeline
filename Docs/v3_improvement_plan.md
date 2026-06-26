# v3 개선 플랜 (2단계 산출물)

> 4개 테마 × **33개 변경**을 실제 코드(파일·라인)에 근거해 설계하고, **② 범용 tool화 기반 우선**으로
> 6개 마일스톤(M1→M6)으로 순서화한 실행 스펙. 4단계(구체적 실행)는 이 문서를 따른다.
>
> 설계 근거: 코드베이스 정밀 분석 워크플로 2회(이해 6 에이전트 + 설계 5 에이전트). 통합 단계에서 인용된
> 모든 파일/라인을 검증함.

## 0. 목표 & 불변 원칙

**4 방향** — ① 토픽모델링 완성도 · ② 범용 tool화(기반) · ③ 다양한 주제(corpus) 대응 · ④ 결과 표현 유연화.

**원칙 (절대 준수):**
- **기본 동작 byte-identical.** 기본 config(biomedical/PubMed/한국어 3그룹/CPU/2D)는 변경 후에도 동일 산출물.
  모든 신규 기능은 **config opt-in**.
- **CLAUDE.md §0 불변 계약 보존** — 시크릿 env-only / 한국어 config 키(`project.주제`,`project['데이터 출처']`)
  / `s5_label-relevance.md`의 **정수 Topic 컬럼**(3곳 regex 재파싱) / `sN_` 파일명 IPC.
- **surgical.** 투기적 추상화 금지 (예: 플러그인 패키지 대신 `cfg.get` 디스패치, Jinja2 신규 의존성 대신
  section-id→fragment dict).

---

## 1. 실행 로드맵 (M1 → M6) — 핵심

| 마일스톤 | 포함 변경 | 산출물 (완료 기준) |
|---|---|---|
| **M1 — 패키징·테스트 기반** | T2-1, T2-2, T2-3, T2-10 | `pip install -e .[test] && pytest` green. 모든 문서에서 절대 conda 경로 제거. 버전 단일화. invariant#3 회귀 테스트(`sample_relevance.md`) 확보 |
| **M2 — CLI/config 골격 안정화** | T2-4(resolver만), T2-5, T2-6, T2-7, T2-8 | `--run-id`로 모든 `sN_` 산출물 네임스페이싱. `--list-steps`/`--from`/`--to`. 누락 선행물 **사전** 실패. 기본(no run-id)은 today와 동일 |
| **M3 — 공유 리팩터 1회** | **LLM-1**(shared/llm.py 추출), T2-9 | 두 s5 호출이 공유 LLM 헬퍼(retry 포함) 사용. device/batch_size config화(기본 cpu 동일) |
| **M4 — 범용 corpus 대응** | T3-1, T3-2, T3-3, T3-4, T3-5, T3-6 | 일반 CSV corpus로 end-to-end 실행(빈 mesh/author-kw, 합성 정수 pmid, embed/stop-words config, 도메인 프롬프트). 기본 PubMed run은 동일 |
| **M5 — 결과 표현 + taxonomy** | T3-7, T4-1, T4-2, T4-3, T4-4, T4-5, T4-6, T4-7 | config 기반 섹션 순서/제목, plotly 번들 1회(순서 무관), N그룹 taxonomy(기본 3그룹 동일), 기계판독 `s5_topic_order.json`+`s7_results.json` |
| **M6 — 토픽모델링 품질** | T1-1, T1-2, T1-3, T1-4, T1-5, T1-7, T1-6, T1-8 | 전처리(approx., A/B 검증), 5D 기본+2D viz 유지, c_v/diversity 지표, target-n 선택, 선택적 guided. 모두 gate되어 baseline 재현 가능 |

> **M6(품질)을 마지막에 두는 이유:** 유일하게 클러스터링 **출력을 바꾸는**(s2/s3 캐시 무효화) 테마이고,
> M2의 run-namespacing이 있어야 전처리/차원 A/B 비교를 충돌 없이 할 수 있다.

---

## 2. 변경 카탈로그 (테마별)

### ② 범용 tool화 / 재사용성 (기반) — T2

| id | 변경 | type | 주요 파일 | risk/effort |
|---|---|---|---|---|
| T2-1 | 버전 단일화: pyproject `dynamic=["version"]` ← `__init__.__version__` | mod | pyproject.toml, `__init__.py` | low/S |
| T2-2 | `pip install -e .` 정규화, docs의 절대 conda 경로 제거 **(+REVISED_PLAN.md 3곳 포함)** | mod | README.md, Docs/NEW_ENV_SETUP.md, Docs/REVISED_PLAN.md | low/S |
| T2-3 | 의존성 상한 캡(requirements 핀 기준) + `[gpu]`·`[test]` extra | mod | pyproject.toml, requirements.txt | med/M |
| T2-4 | `shared/device.py`: `resolve_device`/`setup_torch` + `compute:` config 섹션 | new | shared/device.py, default_config.yaml | low/M |
| T2-5 | run 네임스페이싱: `--run-id`로 effective output_dir, YAML anchor 제거 → `relevance_md_path()` | mod | cli.py, shared/convention.py, default_config.yaml | med/M |
| T2-6 | s6/s7의 relevance_md를 convention helper(null-safe)로 라우팅 | mod | s6_timeseries.py, s7_report.py | low/S |
| T2-7 | cfg in-place 변이 제거 → step마다 deepcopy | mod | cli.py, s7_report.py | low/S |
| T2-8 | `--list-steps`/`--from`/`--to` + `STEP_REQUIRES` + 사전 검증 | mod | cli.py, shared/convention.py | med/L |
| T2-9 | CPU 강제·batch_size를 resolver/config화(중복 device 블록 통합) | mod | s2,s3,s4,s7 | med/M |
| T2-10 | 5개 `_smoke_test`→pytest(fixtures/mock), `sample_relevance.md` 회귀 | new | tests/* , pyproject.toml | low/M |

### 선행 공유 리팩터 — LLM-1 *(통합 단계가 추가한 필수 선행작업)*

| id | 변경 | type | 주요 파일 | risk/effort |
|---|---|---|---|---|
| LLM-1 | byte-identical `_call_claude`(s5_label:85-97 == s5_label_relevance:95-107) → `shared/llm.py call_claude()` (retry/rate-limit/truncation 처리 추가), 두 step 재지정 | refactor | shared/llm.py, s5_label.py, s5_label_relevance.py | med/M |

### ① 토픽모델링 완성도 / 품질 — T1

| id | 변경 | type | 주요 파일 | risk/effort |
|---|---|---|---|---|
| T1-1 | `shared/preprocess.py` — abstract_clean 정제(URL/숫자/인용/소문자). **주의: 원본 v2.4 스크립트 부재 → 근사치, A/B 검증 필수** | new | shared/preprocess.py | med/M |
| T1-2 | `s0_preprocess` step 추가 → `s0_meta_clean.csv`, cli STEPS 등록(fetch→preprocess→embed) | new | s0_preprocess.py, cli.py | med/M |
| T1-3 | s2/s3가 abstract_clean 소비(raw fallback, `preprocess.enabled` gate) | mod | s2_embed.py, s3_cluster.py | high/M |
| T1-4 | `cluster.umap_n_components` 기본 2→5 (s7 viz는 독립 2D — 영향 없음) | mod | default_config.yaml, KNOWN_LIMITATIONS.md | low/S |
| T1-5 | `_measure_metrics`에 c_v coherence + topic diversity(gensim optional, graceful skip) | mod | s3_cluster.py, pyproject.toml | med/M |
| T1-6 | sweep tie-break `median_low`→**target-n** + recommend/confirm gate | mod | s3_cluster.py, default_config.yaml, cli.py | high/L |
| T1-7 | 선택적 guided 모델링(`seed_topic_list`) `_train_one` 경유 | mod | s3_cluster.py, default_config.yaml | med/M |
| T1-8 | report.intro/KNOWN_LIMITATIONS/README 문구 동기화(전처리·5D·신규 지표) | mod | default_config.yaml, Docs/, README.md | low/S |

### ③ 다양한 주제(corpus) 대응 — T3

| id | 변경 | type | 주요 파일 | risk/effort |
|---|---|---|---|---|
| T3-1 | `S1_COLUMNS` 고정 + `fetch.source` 디스패치(PubMed 경로는 그대로) | refactor | s1_fetch.py, shared/pubmed.py, default_config.yaml | low/M |
| T3-2 | CSV-of-text/generic 어댑터(`fetch.columns` 매핑, 합성 정수 pmid) | new | s1_fetch.py, default_config.yaml | med/M |
| T3-3 | embed 모델 config화 + `resolve_embed_model()`(s2/s4 중복 통합) | mod | s2,s4, convention.py, default_config.yaml | low/S |
| T3-4 | `stop_words` 언어/config화 + `resolve_stop_words()`(s3/s4 통합) | mod | s3,s4, convention.py, default_config.yaml | low/S |
| T3-5 | s4 MeSH/Author-KW 컬럼 graceful optional(스키마 불변, 빈 값) | mod | s4_enrich.py, s6_timeseries.py | med/M |
| T3-6 | s5 프롬프트 템플릿화(`수산부산물…5,590편` 리터럴/가짜 카운트 제거, 실제 df 카운트). **rule #2 정수 regex 불가침** | mod | s5_label.py, s5_label_relevance.py, default_config.yaml | med/M |
| T3-7 | relevance taxonomy 일반화(N그룹/라벨/split, 기본 3그룹 동일) | refactor | colors.py, s6, s7, s5_label_relevance.py, default_config.yaml | high/L |

### ④ 결과 표현 유연화 — T4

| id | 변경 | type | 주요 파일 | risk/effort |
|---|---|---|---|---|
| T4-1 | plotly `include_plotlyjs` 순서 결합 버그 수정(번들 1회 head 주입) | mod | s7_report.py | low/S |
| T4-2 | s7 HTML 스켈레톤을 `html_common.render_page` 경유(중복 제거) | refactor | s7_report.py, html_common.py | low/S |
| T4-3 | 섹션 순서/제목/aux 링크를 config화(section-id→fragment dict, 죽은 BERTopic 링크 제거). **Jinja2 미도입** | mod | s7_report.py, default_config.yaml | med/L |
| T4-4 | `s5_topic_order.json` 출력(**md를 재파싱**해 생성 → invariant#3 유지), `parse_relevance_table()` | mod | s5_label_relevance.py, shared/relevance.py | med/M |
| T4-5 | 통합 `s7_results.json`(기계판독 결과 번들) | mod | s7_report.py, default_config.yaml | low/M |
| T4-6 | 선택적 Markdown 리포트(`report.formats`) — PDF는 보류 | mod | s7_report.py, default_config.yaml | low/M |
| T4-7 | 선택적 stdlib http.server serve(output_dir 정적, 127.0.0.1, logs/ 차단) | new | cli.py, s7_report.py | med/M |

---

## 3. 파일 경합 맵 (한 파일을 여러 테마가 수정 — 충돌 방지)

| 파일 | 수정 테마 | 순서 규칙 |
|---|---|---|
| **cli.py** *(최다 경합)* | T2-5/7/8, T1-2/6, T4-7 | flag/STEP 골격을 **M2에서 먼저 안정화**, 이후 append만 |
| **convention.py** | T2-5/8, T3-3/4 | M2에서 resolver home 확립 → M4에서 2개 append |
| **s5_label_relevance.py** | LLM-1, T3-6, T3-7, T4-4 | LLM-1(M3)→T3-6(M4)→T3-7+T4-4(M5). **rule#2(line 80) 불가침** |
| **s2_embed.py** | T2-9(device), T3-3(model), T1-3(text) | 라인 disjoint, 각 reopen 의도적으로 |
| **s4_enrich.py** | T2-9, T3-3, T3-4, T3-5 | T3-3/4/5는 M4에서 한 번에 |
| **s3_cluster.py** | T2-9, T3-4, T1-5/6/7 | M6 cluster 로직 편집은 한 번에 응집 |
| **shared/colors.py** | T3-7(소유), T4-3/5(소비) | T3-7 먼저. `relevance_split(n)` wrapper는 smoke test 위해 유지 |
| **s7_report.py** | T2-6/9, T4-1/2/3/5/6, T3-7(read) | M5 리포트 리팩터를 하나의 응집 패스로 |
| **default_config.yaml** | 전 테마 | 섹션 추가 조율, YAML anchor는 T2-5가 먼저 제거 |

---

## 4. 교차 의존성 (요약)

- **LLM-1 → T3-6, T4-4** (s5 호출 메커니즘을 세 번 다시 쓰지 않도록 M3에서 선행)
- **T2-5 → T2-6, T2-7** (effective output_dir 확정 후 라우팅/deepcopy) · T2-5는 M6 A/B 실험도 unblock
- **T2-4 → T2-9**, 그리고 T3-3/T3-4 resolver의 패턴 템플릿
- **T2-8(STEP_REQUIRES) → T1-2**(preprocess 등록), T1-6/T4-7(신규 flag)
- **T3-1(S1_COLUMNS) → T1-2**(s0_preprocess가 스키마 확장)
- **T3-7(taxonomy) → T4-4/T4-5**(파서/컬러맵이 최종 그룹 모양을 따름)

---

## 5. 전역 리스크 & 완화

1. **invariant#3(정수 Topic)** 이 T3-6/T3-7/T4-4에 의해 건드려짐 → **M1에서 `sample_relevance.md` 회귀
   테스트 선확보**, rule#2 불가침, T4-4는 LLM이 아닌 **md 재파싱**으로 JSON 생성.
2. **T1-1 'v2.4 parity' 불가** (원본 정제 스크립트 부재) → 근사치로 명시, `preprocess.enabled` gate, **경험적
   A/B 후에만** parity 주장. Theme 1을 M6(마지막)에 배치해 blast radius 최소화.
3. **T1-6 interactive y/N**이 dispatcher 루프·CI를 막음 → **비대화형 변형**(sweep 후 추천만 출력, 두 번째
   명시적 `cluster --min-topic-size N` 호출) 권장. M6 전 확정.
4. **의존성 캡(T2-3)** ↔ 재현성 trade-off. 설치된 핀(bertopic==0.16.2 등)이 캡을 만족하는지 M1 설치 시 확인.
5. **캐시 무효화 cascade**(T1-3/T1-4/T3-3) → same-shape 다른-model은 shape check로 안 잡힘. T3-3의
   stale-cache WARNING + text-source/model provenance 로그 필수.
6. **run-id 기본 정책**(T2-5): bare `topic-pipeline`은 flat `./outputs` 유지(무회귀) 권장 vs 자동 timestamp.
7. **serve 노출**(T4-7): output_dir엔 시크릿 없으나 logs/ DEBUG 존재 → logs/ 차단, 127.0.0.1 only.
8. **T2-7 deepcopy**가 s7의 project키 자동합성 변이 의존을 바꿈 → 2-pass in-process run으로 테스트.

---

## 6. 확정 필요 결정 (실행 전/중 owner 입력)

| # | 결정 | 권장 |
|---|---|---|
| D1 | run-id 기본: flat `./outputs` vs 자동 timestamp | **flat(무회귀)** |
| D2 | 의존성: 상한 캡 vs floors-only(+requirements 락) | **캡** (재현성) |
| D3 | `target_n_topics` 기본값 | **10**(v2.4 검증값), tie_break='target' |
| D4 | T1-6 confirm: interactive vs 비대화형 2-step | **비대화형** (CI 친화) |
| D5 | ingest 어댑터 범위: CSV만 vs arXiv/Crossref 추가 | **CSV만**(+계약 문서화) |
| D6 | PDF export | **보류**(heavy dep, AppleGothic headless 취약) |
| D7 | merge key 'pmid' 유지 vs 'doc_id' 리네임 | **'pmid' 유지**(합성 정수) |
| D8 | 전처리 parity 근사치 수용 | **수용 + A/B 검증** |

---

*다음(4단계): M1부터 순차 실행. 각 마일스톤 = 응집 커밋 묶음, 진행 전 검증, `TODO.md` 로그 갱신(CLAUDE.md §2/§4).*
