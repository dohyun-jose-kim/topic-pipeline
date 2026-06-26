# week_f — 토픽 모델링 Wrap-Up & 패키징

week_7에서 수행한 BERTopic 기반 토픽 모델링 파이프라인을 마무리하고, 재사용 가능한 Python 패키지로 정리하는 프로젝트.

> **⚠️ 현재 진입점: [`90_CLI/`](./90_CLI/)** — 이 폴더의 7개 하위 디렉토리 (`01_DataFetch` ~ `06_Clustered_Topic_Assay_v3`) 는
> `90_CLI/` 내 단일 CLI (`topic-pipeline`) 로 통합되어 각자 `DEPRECATED.md` 표기됨 (2026-04-23). 참조용으로만 유지.

---

## 배경

- **데이터**: 수산부산물 기능성 PubMed 논문 5,590편
- **파이프라인**: S-PubMedBert 임베딩 → UMAP(2D) → HDBSCAN → BERTopic
- **선정 모델**: v2.4 (min_topic_size=50, 10 topics, C_v=0.635, silhouette=0.502)
- **목적**: DB 구축을 위한 사전작업. 토픽모델링으로 연구 주제 지형도를 파악하고, 향후 분석 방향의 출발점으로 삼는다.

## 디렉토리 구조

```
week_f/
├── README.md                  ← 이 파일
├── 00_Plans/                  ← 계획 문서, 의사결정 기록
│   ├── plan.md                   전체 2일 계획
│   ├── todo_day1.md              Day 1 세부 태스크
│   ├── DELETE-MMR-method.md      MMR 제거 결정 근거
│   └── ...
├── 90_CLI/                    ← **★ 현재 진입점** (단일 topic-pipeline CLI)
├── 01_DataFetch/              ← (DEPRECATED → 90_CLI s1) 데이터 수집 & 키워드 보강
│   ├── fetch_author_keywords.py  PubMed efetch → Author Keywords + MeSH 수집
│   ├── data/
│   │   ├── wk3_screened.csv         원본 (week_7에서 복사)
│   │   ├── pmid_keywords.csv        PMID별 author_keywords + mesh_terms_v2
│   │   └── Combine_Keywords_forTM.csv  원본 + 키워드 통합 CSV
│   └── results/
│       └── keyword_stats.md         수집 기초 통계
├── 02_PreviousModelPath/      ← (DEPRECATED) week_7 모델 & 데이터 (참조용 복사본)
│   ├── topic_model_v2.4/         BERTopic 저장 모델
│   ├── topic_labeled_v2.4.csv    5,590편 × 토픽 할당
│   └── embeddings_SPubMedBert.npy  문서 임베딩 캐시
└── 03_Cluster-to-Topic/       ← (DEPRECATED → 90_CLI s4_enrich) 토픽 보강 & 해석
    ├── enrich_topics_v1.py       5열 비교표 (MMR 포함, deprecated)
    ├── enrich_topics_v2.py       4열 비교표 (c-TF-IDF / KeyBERT / Author KW / MeSH)
    └── results/
        └── topic_keywords_comparison.csv
```

## 4열 키워드 비교 방법

| 메트릭 | 후보 풀 | 선택 방식 | 출처 |
|--------|---------|-----------|------|
| c-TF-IDF | 토픽 내 전체 문서 단어 | 빈도 비율 상위 | abstract (비지도) |
| KeyBERT | 대표 문서의 모든 ngram(1~3) | 임베딩 코사인 유사도 | abstract (비지도) |
| Author Keywords | 토픽 내 논문의 저자 키워드 | 단순 빈도 | 저자 명시 (78.2% 커버) |
| MeSH Terms | 토픽 내 논문의 MeSH | 단순 빈도 | NLM 통제어휘 (76.4% 커버) |

## 환경

- conda: `week_7/wk7_Transformer/.wk7trf_conda/`
- Python 3.12, BERTopic 0.16.2, sentence-transformers 2.7.0
- 임베딩 모델: `pritamdeka/S-PubMedBert-MS-MARCO`
