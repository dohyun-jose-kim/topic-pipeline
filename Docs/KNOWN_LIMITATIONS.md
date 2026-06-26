# Known Limitations / Pending Items

파이프라인 구현 중 발견된 **미완/미정 항목**. PLAN-v2 §9 는 설계 단계 한계, 이 문서는 **실행 중 발견된 이슈 + 후속 작업 트래커**.

---

## 1. 텍스트 전처리 미구현

**발견 시점**: 2026-04-21 (Phase 5b 착수 전 검토)

**현 상태**:
- `s1_fetch` 는 PubMed 원본 abstract 를 그대로 저장 (`s1_meta.csv.abstract`)
- `s2_embed` 는 이 raw abstract 를 SPubMedBERT 에 바로 투입
- 전처리 step 없음

**v2.4 비교**:
- v2.4 모델은 `abstract_clean` 으로 학습됨
- 전처리 로직 위치: `week_4/Task1/Task1-v3/03_abstract-text_preprocessing/tokenize_pipeline.py` (+ `build_dicts.py`)
- 적용된 변환 (추정): lowercasing / citation·URL 제거 / 약어 정규화 / 특수문자 처리

**영향**:
- 우리 파이프라인 클러스터 결과는 **v2.4 와 byte-exact 불일치**
- 파이프라인 self-consistent 일 뿐 — 끝까지 돌릴 수 있고 내부 정합성은 유지됨
- 클러스터 품질에 영향 (c-TF-IDF 에 URL 토큰·숫자 등이 섞여 핵심어 오염 가능)

**개선 경로** (아직 안 함):
1. `week_4/Task1-v3/03_abstract-text_preprocessing/tokenize_pipeline.py` 계열 로직을 `shared/preprocess.py` 로 이식
2. s1_fetch 내부에 cleaning 추가 (한 step 증가 없이 완결) **또는** 별도 `s0_preprocess` step 도입
3. 이식 전후 클러스터 품질 비교 (silhouette, c-TF-IDF 육안 검토)

**착수 권장 시점**: Phase 8 마감 직전 polish 단계. Phase 5b/6 의 파이프라인 검증을 먼저 완료하고, 품질 이슈가 실제로 관찰되면 그때.

---

## 2. UMAP 차원 PLAN 내부 불일치

**발견 시점**: 2026-04-21 (Phase 5b 설계 검토)

**모순 지점**:
| 위치 | 내용 |
|---|---|
| PLAN-v2 §4 config | `umap_n_components: 2  # 기본 2D` |
| PLAN-v2 §7 base 선정 | 33_v3-d5 (`n_components=5` hardcoded) 권고 |

**추정**: v2.4 는 5D 로 학습됐을 가능성 높음 (33_d5 네이밍, `n_components=5` hardcoded 원본에서). §4 default `2` 는 설계 당시 오타 가능.

**영향**:
- 현재 default (`umap_n_components: 2`) 로 돌리면 2D 클러스터링 → v2.4 와 구조 자체가 다름
- BERTopic 에서 2D 는 비표준 (보통 5D 가 권장값)
- HDBSCAN 이 2D 에서 밀도 계산하면 클러스터 분리도 저하 가능성

**Phase 5b 처리 방침**:
- 최초 실행은 현 default (2D) 로 **sweep 메커니즘 동작만 검증**
- 이후 `umap_n_components: 5` 로 전환 — 방법 두 가지:
  - (a) PLAN §4 default 수정 → config 기본값 변경
  - (b) test config 에서만 override → PLAN default 유지

**판정 필요**: §4 default 가 의도적이면 유지 (다만 §7 과 의도 명확화), 오타면 5 로 수정.

---

## 3. ✅ 해결됨 — `s5_label-relevance.md` 자동 생성 (2026-04-22)

**발견 시점**: 2026-04-21 (Phase 6 설계 중)
**해결**: NEXT_PLAN §C. `s5_label_relevance.py` 신설 step 이 `s5_labels.csv` 를 읽어 Claude 2번째 호출로 `relevance_criterion` 기준 rank md 를 자동 생성. `default_config.yaml` (구 `phase6_e2e_config.yaml`) 의 `relevance_md` 도 `./outputs/s5_label-relevance.md` 로 전환. 외부 수동 md 의존 제거.

**현 상태**:
- PLAN-v2 §2 는 `s5_label-relevance.md` 를 s5 산출물로 명시 (`relevance_criterion` 기준 토픽 랭킹 md)
- PLAN-v2 §4 config 에 `label.relevance_criterion: "생리적 기능성(physiological functionality)"` 슬롯 존재
- Phase 3b 구현 당시 scope-out — 현재 s5_label.py 는 `s5_labels.csv` 만 생성, relevance md 는 미생성

**영향**:
- s6/s7 이 관련도 순위 표를 필요로 함 → **외부 수동작성 `topic_physiological_relevance.md`** 로 대체 사용 중
- 외부 md 는 v2.4 의 10 토픽 기준으로 작성됨. 우리 s3 결과 (5 토픽, 0~4) 와 **rank → topic_id 매핑 중 일부 미스매치**
- Phase 6 end-to-end 리포트는 렌더 가능하지만, §6 관련도 표 일부 topic_id 가 실제 우리 토픽에 없어 의미 깨짐

**개선 경로** (아직 안 함):
1. `s5_label.py` 에 두 번째 Claude 호출 추가: "위 10개(또는 N개) 토픽을 `{relevance_criterion}` 기준으로 순위 매기고 | rank | topic | label | doc_count | 근거 | 마크다운 표로 반환"
2. 또는 단일 호출로 label + rank 둘 다 한 번에 — 토큰 절약
3. 출력: `outputs/s5_label-relevance.md` (PLAN §2 네이밍)
4. s6/s7 config 의 `relevance_md` default 를 외부 경로 → `{output_dir}/s5_label-relevance.md` 로 전환

**착수 권장 시점**: Phase 7 직후 또는 Phase 8 polish 단계.

**임시 대응**: Phase 6 test config 는 외부 md 경로 명시. s6/s7 의 `parse_relevance_order()` 는 외부 md 의 topic_id 중 실제 df 에 없는 건 자연스럽게 skip (`if t in pivot.columns`).

---

## 4. sweep 선택 결과의 도메인적 부적절성 — 부분 해결

**발견 시점**: 2026-04-21 (Phase 6 e2e 리포트 육안 검토)

**2026-04-22 업데이트**: pilot 에서 grid 5→8값 변경 + `--min-topic-size` 플래그 도입. 자동 sweep 은 `mts=51 → 7토픽` 까지 개선됐으나 median_low tie-break 은 여전히 중앙값 선호. 사용자가 `--min-topic-size 27` 수동 override 로 **12토픽** 달성 (도메인적으로 양호). 근본 해결은 후속 — relevance 자동 생성 및 시계열 재설계 먼저 (`Docs/NEXT_PLAN.md §A, §C`).

**현 상태** (원래 기록):
- PLAN-v2 §12 sweep (5값 기하급수 그리드 + cutoff 5조건 + median_low) 로 `min_topic_size=71` 선택됨
- 결과 토픽 수: **5개** (0~4)
- 비교: v2.4 모델은 같은 N=5590 에서 **10 토픽** 생성, 도메인 전문가 수작업 검토 후 "적절하다" 판정됨

**의심 원인 (복합)**:
1. 2D UMAP 사용 (KNOWN §2) — 저차원이라 밀도 구분 저하 → 과도한 병합
2. raw abstract 사용 (KNOWN §1) — 노이즈 단어가 임베딩 다양성 저하
3. **§12 cutoff 규칙 자체의 적절성** — 예:
   - `n_topics_max: 30` 은 상한만 규정, 하한이 `n_topics_min: 4` 로 낮음
   - `silhouette_min: 0.25` 컷오프가 "토픽 수 많은 후보" 를 불리하게 만들 수 있음 (많을수록 sil 평균 낮아지는 경향)
   - median_low 는 보수적 선택 — 생존자 중 더 fine-grained 쪽 선호하지만, 3개 survivors `[37, 71, 137]` 에서 71 이 중간이라 v2.4 의 실제 좋은 선택(~50 근처 추정) 과 어긋남
4. 도메인 판단 부재: sweep 은 "통계적 cutoff" 뿐 — 생리적 기능성 연구 맥락의 "적당한 토픽 수" 감각이 없음

**Phase 6 영향**:
- end-to-end 파이프라인 **자체는 정상 동작** — sweep/cutoff 메커니즘 작동 증명됨
- 그러나 **클러스터의 의미론적 품질은 부족** — 5 토픽은 "해양 바이오폴리머 응용" 에 다양한 소재·응용 주제가 한꺼번에 묶임, 세분화 부족

**개선 경로** (아직 안 함):
1. **우선 KNOWN §1, §2 먼저 해결** — 전처리 + 5D UMAP 으로 재실행 → 토픽 수 10~15 범위 나오는지 확인
2. 그래도 부적절하면 §12 cutoff 재튜닝:
   - `n_topics_min: 4 → 7~10` 로 상향 (도메인 지식 기반)
   - `silhouette_min` 을 토픽 수 의존 공식으로 (n 많을수록 허용선 낮춤)
   - tie-break 을 median_low → 중앙값/최대 토픽수 선호로 검토
3. 또는 **PLAN-v2 §0-3 (결정 0-3) 자체를 재검토** — "자동 선택" 을 포기하고 "추천값 제시 + 사용자 수동 결정" 으로 downgrade

**착수 권장 시점**: KNOWN §1, §2 먼저 해결 → 재검증 → 그래도 문제면 Phase 9 이후 별도 iteration.

---

## 5. ✅ 해결됨 — UMAP 인터랙티브에서 Title 누락 / outlier non-interactive / legend count 부재 (2026-04-22)

**발견 시점**: 2026-04-22 오후 (§C 완료 후 `s7_report.html` 렌더 검토 중)

**현 상태** (발견 당시):
- Plotly UMAP hover 에 `Title: ...` 로 비어 있음 — `s1_fetch.py::_parse_article` (L64-119) 가 ArticleTitle 을 파싱하지 않아 s1_meta.csv 부터 title 컬럼 없음. `s7_report.py::_make_plotly_umap` L250 의 `getattr(r, 'title', '')` 가 항상 `''` 반환.
- Plotly outlier 트레이스가 `hoverinfo="skip"` 하드코딩 (s7_report.py:240) 으로 인터랙티브 불가.
- Plotly·matplotlib outlier legend 에 count 없음 (`name="outlier"` / `label="outlier"` 하드코딩).

**해결**: NEXT_PLAN §B.B1 확장 iteration (브랜치 `week_f-90_cli_v3_bb1`, 커밋 `b8af697`, `4b93a3d`, `88eeeef`).
- Commit A `b8af697`: `s1_fetch.py` 에 `ArticleTitle` inline 파싱 + `itertext()` 평문화 + return dict 에 title 필드. `outputs/s1_meta.csv` 재fetch (사용자 수동).
- Commit B `4b93a3d`: s7 Plotly outlier 트레이스를 인터랙티브로 (`hoverinfo="text"` + PMID/Title/Topic="Outlier" 템플릿) + legend `Outlier (754)` + regular trace title NaN 방어. matplotlib outlier 도 `c=#888`, `label=f"Outlier ({N})"` 개선.
- Fix `88eeeef`: outlier marker x → 기본 원형 (s 10→4, alpha 0.6→0.4, regular 점을 덮던 문제 해결). title hover 에 `textwrap.wrap(width=80)` 로 단어경계 `<br>` 삽입 (전체 내용 + 가로폭 통제).

**영향 없는 downstream**: s2 embed cache (abstract 기반, title 추가 무관). 단 `s2_meta_for_embed.csv` 재생성 필요 — s2 step 재실행 (embed cache hit, ~2s) 로 s7 convention df 에 title 전파.

---

## 6. ver3.0.1 M6 — 품질 개선 capability (opt-in) 추가 (2026-06-26)

ver3.0.1 개선 플랜(`Docs/v3_improvement_plan.md`) M6. #1/#2/#4 에 대해 **knob 을 추가하되 기본값은 현행 유지**
(byte-identical). 출력을 바꾸는 default 플립은 사용자 실제 env 의 **경험적 A/B 검증 후** 결정한다
(이 환경엔 torch/bertopic·데이터·API키 부재로 클러스터 출력 검증 불가 — 순수 함수/기본경로만 단위 검증).

- **#1 전처리** → *부분 해결*. `shared/preprocess.py`(clean_abstract/clean_series — **근사**: 원본
  tokenize_pipeline.py 부재 verified) + `s0_preprocess` step 신설. `preprocess.enabled`(기본 false)=true 시
  s0 가 `s0_meta_clean.csv`(abstract_clean) 생성, s2/s3 가 우선 소비(s4 rename 충돌 가드 포함).
  **parity 는 가정 금지 — A/B 검증 대상.** (커밋 `2d1d44a`/`377f3c9`/`db91cee`)
- **#4 sweep tie-break** → *부분 해결*. `cluster.sweep.tie_break`('median_low' 기본·현행 | 'target') +
  `target_n_topics`(기본 10). target 모드는 n_topics 가 목표에 가장 가까운 후보 선택. (커밋 `c841e84`)
  interactive confirm gate 는 dispatcher/CI 비친화로 **미구현**(비대화형 권장).
- **#2 UMAP 차원** → *결정 보류*. `--umap-dim 5`/config 로 5D 사용 가능(기존). 기본 default 는 **2D 유지**
  (5D 플립은 출력 변경 → A/B 후 결정). 캐시 키 d{dim} 으로 2D/5D 모델 비충돌.
- **guided 모델링** 신설(plan §E): `cluster.seed_topic_list`(기본 미설정=비지도→byte-identical). (커밋 `b18c5da`)

**M6 잔여(미구현):** c_v coherence / topic diversity 지표(추가형이나 s3 내부·gensim optional — 후속);
default 플립(전처리 on / 5D / target-n)은 실 env A/B 후. cosmetic: s5 요약 bullet taxonomy화, s7 mpl 타이틀(L254).

---

## 문서 운영 원칙

- 새 이슈 발견 시 **section 번호 매겨 append**
- 해결되면 section 에 `## ✅ 해결됨` 표기 + 해결 경위 간단 기록
- 이 문서는 "알지만 아직 안 고친 것" 트래커 — PLAN-v2 의 설계 한계 (§9) 와 구분
