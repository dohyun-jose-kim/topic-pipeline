# NEXT_PLAN — 90_CLI v3 방향성

새 브랜치 `week_f-90_cli_v3` 에서 진행할 품질 개선 계획. PLAN-v2 의 Phase 1~8 + v2-pilot 의 sweep 개선이 끝난 시점 (2026-04-22 기준).

---

## 0. 배경 · 현 상태

- **파이프라인 완성도**: s1~s7 end-to-end 정상 동작. Phase 6 e2e 50초 (cache hit 기준).
- **클러스터 결과**: `mts=27` 수동 override 로 **12 토픽** 달성. 도메인 라벨 양호 (peptides / collagen / chitosan / scaffolds / wound healing / calcium supplements 등).
- **Outlier**: 754개 (13.5%) 분류됨. `topic_label=-1`. 현재 대부분 분석에서 제외 중.
- **파일럿 결론** ([`v2_pilot_decisions.md`](./v2_pilot_decisions.md)): grid 8값 변경은 효과 있었으나 median_low tie-break 은 여전히 중앙 선호 → 사용자 수동 지정으로 우회. 자동화는 불완전.

---

## 1. 세 줄 요약

1. **시계열 분석** 이 "숫자 나열식" → "보고 싶은 질문 → 산출물" 구조로 재설계
2. **Outlier** 를 눈에 띄게 시각화
3. **`s5_label-relevance.md` 자동 생성** 으로 외부 수동 md 의존 제거 (KNOWN §3)

---

## 2. 항목별 설계

### §A. ❌ 취소됨 (2026-04-22) — 시계열 분석 재설계 — 최우선

**문제**: 토픽당 top10 Author KW × 3 토픽 = 30 시리즈에 MK/Sen/CAGR 라벨링. 숫자 나열만 있고 "무엇을 알고 싶은지" 질문이 없음. 리포트 독자가 스크롤만 내려도 "뭘 보는 건지" 바로 알 수 없음.

**목표**: 사용자가 **1~2 개 분석 질문** 을 먼저 선택. 질문당 CSV 1개 + 대표 그래프 1개를 리포트 §5 **단독 섹션** 으로 배치. 현 MK/Sen 30행 분석은 `<details>` 접기로 강등.

**질문 후보** (구현 전 사용자 결정 필요, **TBD**):

| 코드 | 질문 | 산출물 | 난이도 |
|---|---|---|---|
| Q1 | 최근 5년 (2020–2024) 급성장 키워드 top-10 은? | CAGR(최근5년) 또는 MK-tau(최근5년 sub-window) 기반 랭킹 막대그래프. 토픽 경계 무시, 전체 코퍼스 | 쉬움 |
| Q2 | 시대 구간별 (≤2010 / 2011–2020 / 2021–) 토픽 구성비 변화 | 3 × N_topics 히트맵 + stacked bar | 쉬움 |
| Q3 | 각 토픽의 생명주기 단계 (태동/성장/성숙/쇠퇴) | Gompertz/Logistic curve fitting → 변곡점 연도 + 현재 단계 라벨 | 중간 (fitting 안정성) |
| 사용자 제시 | ... | ... | ? |

**추천 기본 세트**: Q1 + Q2 (Q3 는 후속). 최종 선택 후 착수.

**접근 옵션**:
1. **신규 함수 추가** — `s6_timeseries.py` 에 `_compute_recent_growth()`, `_compute_era_composition()` 추가. 현 `compute_keyword_trends` 는 유지 (하위 호환). 리포트는 세 섹션 병렬.  ← **추천** (작은 diff).
2. 리팩터 — `s6` 를 "질문 → 산출물" 매핑 구조로 재작성. 유연성↑ 복잡도↑.
3. 별도 step `s6b_trend_questions.py` 분리.

**변경 포인트**:
- `src/topic_pipeline/steps/s6_timeseries.py` — 선택된 질문별 compute 함수 신설
- `src/topic_pipeline/steps/s7_report.py::_build_html` — §5 재편: 5.1 전체추이(현) / 5.2 Q1 / 5.3 Q2 / 5.4 키워드 MK/Sen 강등
- `config.yaml::timeseries` — `recent_window: 5`, `eras: [[1990,2010],[2011,2020],[2021,9999]]` 등

**검증 기준**:
- (정량) Q1 CSV top-10 중 ≥7개 를 사용자 육안으로 "실제 최근 뜨는 주제" 인정
- (정량) Q2 히트맵에서 ≥3 토픽이 구간 간 비율 차이 ≥5%p
- (정성) 사용자가 "이 섹션만 봐도 의도 안다" 답

---

### §B. Outlier 다루기

**문제 1 (가시성)**: `s7_report.py:171-172, 202-203` matplotlib 에 `c="lightgray", s=3, alpha=0.3, marker="x"` — 실질 안 보임. plotly (L237-238) 도 `opacity=0.3, size=3`.

**문제 2 (의미 부재)**: outlier 754 (13.5%) 가 c-TF-IDF / Author KW 집계에서 전부 skip (`s4_enrich.py:137` 의 `if tid == -1: continue`). "숨겨진 주제" 가능성.

**목표**:
- **B1**: UMAP 에서 outlier 가 한눈에 구분

**접근**:
- **B1**: alpha 0.3→0.6, size 3→10, color `lightgray → #888` (중간 회색), outline 추가 + 별도 "UMAP — outlier only" PNG

**변경 포인트**:
- `src/topic_pipeline/steps/s7_report.py` L171-172, L197-203, L233-240 — 스타일 파라미터

**검증 기준**:
- 사용자가 렌더된 UMAP PNG 보고 "이제 outlier 보인다" 확인

> §B.B2 (outlier pseudo-topic), §B.B3 (outlier 연도별 비율) 은 2026-04-22 결정으로 **항목 제거**.

---

### §C. `s5_label-relevance.md` 자동 생성 — KNOWN §3 해결

**문제**: 현 외부 수동 md (`04_Topic_LLM-Assay/results/topic_physiological_relevance.md`) 가 v2.4 10토픽 기준 → 우리 12토픽에 silent ID 오류. §6 관련도 표 부분 파손, §5 시계열 타겟 선정 왜곡.

**목표**: s5 가 label 산출과 동시에 `{output_dir}/s5_label-relevance.md` 자동 생성. 외부 md 의존 제거.

**접근**: Claude 2회 호출 분리 — 첫 call = label 생성, 둘째 call = `relevance_criterion` 기준 rank md 생성. 책임·프롬프트 단순, 실패 격리 가능.

**변경 포인트**:
- `src/topic_pipeline/steps/s5_label.py` — `_rank_by_relevance(labels_df, criterion)` 추가, md table writer
- `config.yaml::label.relevance_criterion` (이미 존재) — 프롬프트에 주입
- `config.yaml::timeseries.relevance_md`, `report.relevance_md` default 를 `{output_dir}/s5_label-relevance.md` 로 전환

**검증 기준**:
- 생성된 md 의 topic_id 전체가 `s5_labels.csv` 와 일치 (누락/가공 없음)
- rank 1~N 연속, 중복 없음
- 사용자 육안으로 1~3위 수긍 가능

---

### §E. Guided Topic Modeling — 보류

항목만 기재, §A/§B 결과 후 재검토. 상세 설계는 [`v2_pilot_plan.md §3`](./v2_pilot_plan.md) 참조.

> §D (UMAP 2D → 5D 독립 실험) 은 2026-04-22 결정으로 **항목 자체 제거**. `--umap-dim` CLI 플래그는 남아 있음 (필요 시 수동 실험 가능).

---

## 3. 우선순위 · 의존성

```
§C (relevance 자동) + §B.B1 (UMAP 가시성) → 완료
```

**권장 순서**:
1. **§C** — ✅ 완료 (`27bf7de`)
2. **§B.B1** — ✅ 완료 (`week_f-90_cli_v3_bb1` 브랜치)
3. **§E** — 보류

> §A (시계열 재설계), §D (UMAP 5D), §B.B2 (outlier pseudo-topic), §B.B3 (outlier 연도별 비율) 은 2026-04-22 결정으로 **취소**. 현 §5.2 polish 로 대체 커버.

---

## 4. 사용자 결정 대기 (TBD)

해소됨. §A 취소 (2026-04-22).

---

## 5. 진행 로그

| 일자 | 항목 | 커밋 | 결과 |
|---|---|---|---|
| 2026-04-22 | §C s5_label-relevance 자동 생성 | (자기참조) | label step 분리 (label → label-relevance). Claude 2번째 호출로 md 자동 생성. e2e 통과: label-relevance 17s, timeseries+report 8.2s, trend stats 30행. 부수로 color_map 3+4+3=10 하드코딩 → 동적 split (n=10 하위호환) 교체하여 N≠10 KeyError 해결. |
| 2026-04-22 | §B.B1 UMAP outlier first-class (확장) | `b8af697`, `4b93a3d`, `88eeeef` | 새 브랜치 `week_f-90_cli_v3_bb1`. (A) s1_fetch 에 ArticleTitle inline 파싱 + 재fetch. (B) s7 Plotly outlier 인터랙티브 (hoverinfo=text, `Outlier (754)` legend, title hover) + regular trace NaN 방어 + matplotlib outlier legend count. (C) 폴리시: outlier marker x → 원, 크기/알파 축소, title hover `[:80]...` → textwrap 단어경계 줄바꿈. KNOWN §5 해결. |
