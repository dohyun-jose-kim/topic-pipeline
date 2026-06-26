"""s5 LLM 프롬프트 템플릿화 검증 (순수 문자열 — 네트워크/키 불필요).

T3-6: 도메인/카운트 하드코딩 제거. invariant#3(정수 Topic regex 지시)는 보존돼야 한다.
"""

import pandas as pd

from topic_pipeline.steps import s5_label, s5_label_relevance


def test_label_prompt_templated_no_hardcoded_literals():
    df = pd.DataFrame({
        "topic": [0, 1], "doc_count": [100, 50],
        "c-TF-IDF": ["x", "y"], "KeyBERT": ["x", "y"],
        "Author_Keywords_freq": ["", ""], "MeSH_freq": ["", ""],
    })
    p = s5_label._build_prompt(df, "운동생리")
    assert "운동생리 관련 문서 150편" in p   # 실제 doc_count 합
    assert "2개 토픽" in p                     # 실제 토픽 수
    assert "수산부산물" not in p               # 도메인 리터럴 제거
    assert "5,590" not in p                    # 카운트 리터럴 제거


def test_rank_prompt_neutral_and_preserves_rule2():
    df = pd.DataFrame({
        "topic": [0, 1], "doc_count": [100, 50],
        "label_en": ["a", "b"], "label_kr": ["가", "나"], "description": ["d", "e"],
    })
    p = s5_label_relevance._build_rank_prompt(df, "항산화 활성")
    assert "PubMed 논문" not in p              # 소스 리터럴 중립화
    assert "항산화 활성" in p                   # criterion 반영
    # invariant #3: 정수 Topic 컬럼 regex 지시 보존 (rule #2)
    assert "정수만" in p
    assert "Topic 5" in p                       # "접두사 붙이지 말 것" 예시 보존