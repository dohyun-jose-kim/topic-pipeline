# PLAN-v2-trend — 시계열 심화 (Author Keywords 단어 추세)

> [`PLAN-v2.md`](./PLAN-v2.md) 의 §5 (연도별 추이) 서브섹션 설계.
> 메인 플랜과 분리하여 이 문서에서 따로 결정/발전시킨다.
>
> **방향 전환 (2026-04-21)**: 기존 "토픽 단위 논문수 추세" → "토픽 내 Author Keywords 단어 추세" 로 pivot. 이유: 사용자 요구 — "corpus 내 단어의 증감/쇠퇴" 파악이 본질. 토픽 단위 논문수 추세는 이미 §5.1 (기본 차트) 로 커버됨.

---

## 1. 배경

현재 `05_TimeSeries-Assay/topics_over_time.py` 는 **토픽 단위 논문수** 차트만 제공:
- `line_absolute.png` — 토픽별 연도 논문수 꺾은선
- `stacked_absolute.png`, `stacked_relative.png` — stacked area

**부족한 것**: 각 토픽 내부에서 **어떤 단어가 뜨고 지는지** 파악 불가.

프로젝트 맥락:
```
주제: 수산부산물(fishery by-products)의 기능성 관련 연구 동향
초점: 직접 관련 (1~3위) 3개 토픽
기간: 2000~2026 (5,590편)
```

**분석 목표**: 직접 관련 3토픽 각각에 대해 **"어떤 Author Keywords 가 언제 뜨고 언제 지는가"** 를 정량화.

---

## 2. 분석 대상

### 2-1. 토픽 — 직접 관련 3개

`outputs/s5_relevance.md` (구 `topic_physiological_relevance.md`) 에서 1~3위 추출.

### 2-2. 키워드 소스 — Author Keywords 만

4가지 소스 (c-TF-IDF / KeyBERT / Author KW / MeSH) 중 **Author Keywords 만** 사용.

**이유**:
- **출처 명확**: 저자가 명시한 키워드 — 문맥 해석 필요 없음
- **논문 단위 메타**: 연도별 집계 자연스러움 (PMID ↔ 키워드 1:N 매핑)
- **단순성**: c-TF-IDF/KeyBERT 는 토픽 전체 기준 빈도라 연도 분해 어려움, MeSH 는 NLM 부여 통제어휘라 저자 의도와 괴리

예시 (Topic 0 직접 관련 1위, peptides 관련):
```
Author Keywords top 10 (전 기간):
  antioxidant(53), antioxidant activity(51), bioactive peptides(37),
  by-products(19), enzymatic hydrolysis(18), protein hydrolysates(18),
  peptides(18), protein hydrolysate(16), bioactive compounds(15), oxidative stress(15)
```

이 10개 각각에 대해 연도별 빈도 시계열 분석.

### 2-3. 키워드 수 — 토픽당 top 10

- 10개가 차트 가독성 한계
- 각 토픽 × 10 키워드 = **3 × 10 = 30 시계열**

사용자가 config 에서 `top_n: 15` 식으로 조정 가능.

### 2-4. 집계 단위

"해당 Author Keyword 가 부여된 **논문 편수**" (연도별).

즉 한 논문에 "antioxidant" 가 한 번 attached 되든 여러 번 언급되든 **1편으로 카운트**. Author Keywords 가 논문별 메타데이터이기 때문 (각 논문 × 키워드 리스트).

---

## 3. 분석 방법 — 표준 통계 세트

bibliometric 시계열 분석의 정석 조합:

| 방법 | 산출 | 역할 |
|---|---|---|
| **Mann-Kendall 검정** | tau, p-value | 단조 추세 존재 여부 (비모수) |
| **Sen's slope** | 편/년 (robust) | MK 의 짝, 이상치 강함 |
| **CAGR** (year_min → year_max) | % / 년 | 직관적 복리 성장률 |
| **5년 이동평균** | 곡선 | 시각화 보조, 단기 잡음 제거 |

각 (토픽, 키워드) 쌍마다 위 4개 계산.

### 의존성

`pymannkendall` — MK + Sen's slope 제공. `requirements.txt` 에 추가.

---

## 4. 산출물

### 4-1. CSV — `outputs/s6_trend_stats.csv`

| 컬럼 | 의미 |
|---|---|
| `rank` | 관련도 순위 (1~3) |
| `topic_id` | BERTopic ID |
| `label_kr` | 토픽 한국어 라벨 |
| `keyword` | Author Keyword (원문) |
| `total_count` | 전 기간 해당 키워드 부여 논문수 |
| `year_min`, `year_max` | 관측 연도 범위 |
| `mk_tau` | Mann-Kendall tau |
| `mk_p` | Mann-Kendall p-value |
| `sen_slope` | Sen's slope (편/년) |
| `cagr_pct` | CAGR (%) |
| `trend_label` | emerging / stable / declining (자동 분류, §5) |

총 행수: 3 토픽 × 10 키워드 = **30 행**.

### 4-2. 차트 PNG — `outputs/s6_figures/trend_keywords_topic{N}.png`

**토픽당 하나씩, 총 3개 차트** (직접 관련 3토픽).

각 차트 내용:
- x축: 연도 (2000~2026)
- y축: 해당 키워드 부여 논문수
- 10개 키워드 × 연도별 선 그래프 (multi-line)
- 5년 이동평균 덧그림 (굵은 선)
- Sen's slope 회귀선 (점선, 선택적)
- 범례: 키워드 + 총 빈도 + (tau, p) 주석

### 4-3. 통합 비교 차트 — `outputs/s6_figures/trend_comparison_top3.png`

3 토픽의 **top emerging keyword 를 나란히 비교**. 3토픽 간 "어느 토픽이 가장 성장 중인지" 한눈에.

형식 (후보):
- 3×1 subplot, 각 패널 = 한 토픽 (해당 토픽의 top 3 emerging keyword)
- 또는 단일 패널: 3토픽의 top emerging keyword 각 1개씩 (총 3개 라인)

선택은 구현 시 결정 (사용자님 "통합 아님, 그저 최상위 토픽 그룹간 비교").

### 4-4. HTML 섹션 — 리포트 §5.2

```
5.1 전체 토픽 추이 (기존 3종 차트)
5.2 직접 관련 (1~3위) 키워드 트렌드
    ├── 통계 표 (s6_trend_stats.csv 렌더, 30행)
    ├── 토픽별 차트 3개 (trend_keywords_topic{0,1,2}.png)
    └── 비교 차트 1개 (trend_comparison_top3.png)
```

---

## 5. 자동 분류 — `trend_label`

각 (토픽, 키워드) 쌍에 대해 통계 기반 라벨:

| 조건 | 라벨 |
|---|---|
| `mk_p < 0.05` and `sen_slope > 0` | **emerging** |
| `mk_p < 0.05` and `sen_slope < 0` | **declining** |
| `mk_p >= 0.05` | **stable** |

threshold (0.05) 는 config 에서 조정 가능:
```yaml
timeseries:
  trend:
    p_threshold: 0.05
```

---

## 6. 구현 포인트

### 6-1. 코드 위치
`steps/s6_timeseries.py` 내부 함수 추가:

```python
def compute_keyword_trends(
    meta_df: pd.DataFrame,      # s1_meta.csv (pmid, year, author_keywords_list)
    topic_assignments: pd.DataFrame,  # pmid → topic_id
    top_topic_ids: list[int],   # 직접 관련 3개
    top_n_keywords: int = 10,
) -> pd.DataFrame:
    """각 토픽의 top N Author Keywords × 연도별 논문수 집계 + 트렌드 통계."""
```

출력: `outputs/s6_trend_stats.csv` + `outputs/s6_figures/trend_*.png`.

### 6-2. top N 키워드 선정 방식

- 각 토픽에 속한 논문들의 Author Keywords 를 union
- 전 기간 빈도 내림차순 정렬
- 상위 N개 추출

이미 `03_Cluster-to-Topic/enrich_topics_v2.py` 의 `Author_Keywords_freq` 컬럼이 이 형식으로 저장되어 있음. 재활용 가능.

### 6-3. 연도 집계

```python
# meta_df: columns = [pmid, year, author_keywords_list]
# topic_assignments: columns = [pmid, topic_id]

merged = meta_df.merge(topic_assignments, on="pmid")
for topic_id in top_topic_ids:
    topic_docs = merged[merged["topic_id"] == topic_id]
    for kw in top_keywords_for_topic:
        yearly = topic_docs[topic_docs["author_keywords_list"].apply(lambda kws: kw in kws)]
        yearly_counts = yearly.groupby("year").size()
        # yearly_counts → MK, Sen, CAGR 계산
```

### 6-4. 1~3위 식별
`outputs/s5_relevance.md` 에서 상위 3 topic_id 추출 — `shared/relevance.py::parse_relevance_order()` 활용.

---

## 7. Config 통합

`PLAN-v2.md` §4 의 `timeseries` 섹션 확장:

```yaml
timeseries:
  summary_comment: |
    (시계열 차트용 코멘트)
  trend:
    enabled: true                  # false 면 §5.2 스킵
    source: "author_keywords"      # 현재 고정. 추후 "mesh" 등 추가 여지
    top_n_keywords: 10             # 토픽당 상위 N 키워드
    target_ranks: [1, 2, 3]        # 분석 대상 순위 (직접 관련 기본)
    p_threshold: 0.05              # trend_label 판정 기준
    moving_avg_window: 5           # 이동평균 창 (년)
```

---

## 8. 스코프 외 (후속)

- **키워드 정규화**: "antioxidant" vs "antioxidants" vs "antioxidant activity" 를 묶을지 — 현재 문자열 완전 일치. 정규화 원하면 lemmatization 추가 필요
- **예측 (forecasting)**: ARIMA/Prophet 등은 별도 과제
- **변동점 탐지**: ruptures 라이브러리 등 — 후속
- **키워드 간 상관**: "antioxidant 증가" ↔ "bioactive peptides 증가" 공동 변화 분석 — 별도 설계 필요
- **타 소스 통합**: MeSH 나 KeyBERT 로 확장할 경우 — config `source` 로 토글 가능하게 설계되어 있음, 하지만 구현은 v2 스코프 외

---

## 9. 작업 순서 — `PLAN-v2.md` §8 Phase 7 세부

1. `pymannkendall` 의존성 추가 (`requirements.txt`, `pyproject.toml`)
2. `s6_timeseries.py` 에 `compute_keyword_trends()` 추가
3. 토픽×키워드×연도 집계 로직 구현
4. MK/Sen/CAGR 계산 + `trend_label` 자동 분류
5. `trend_keywords_topic{0,1,2}.png` 생성 (3개)
6. `trend_comparison_top3.png` 생성 (비교 뷰)
7. `s7_report.py` §5 를 5.1 / 5.2 로 분할, CSV + PNG 임베드
8. 기존 v2.4 데이터로 검증 — 직접 관련 3토픽의 Author Keywords 추세가 예상(상식적) 추세와 일치하는지 육안 확인
