"""shared/relevance.py parse_relevance_order 검증 (구 _smoke_test 이관).

개인 절대경로 대신 committed 픽스처 사용. **invariant #3 회귀 가드**:
s5_label-relevance.md 의 정수 Topic 컬럼 파싱이 깨지면 이 테스트가 잡는다.
"""

from pathlib import Path

from topic_pipeline.shared import relevance

FIXTURE = Path(__file__).parent / "fixtures" / "sample_relevance.md"


def test_parse_relevance_order_bare_integer_contract():
    expected = [5, 4, 1, 2, 7, 9, 8, 6, 3, 0]
    assert relevance.parse_relevance_order(FIXTURE) == expected


def test_parse_relevance_table():
    rows = relevance.parse_relevance_table(FIXTURE)
    assert len(rows) == 10
    assert rows[0] == {
        "rank": 1, "topic": 5, "label": "직접 관련 A", "doc_count": 120, "rationale": "근거",
    }
    # 구조화 JSON 의 topic 순서 == parse_relevance_order (단일 소스 일관성)
    assert [r["topic"] for r in rows] == relevance.parse_relevance_order(FIXTURE)


def test_write_topic_order_json(tmp_path):
    import json

    from topic_pipeline.steps import s5_label_relevance

    md = tmp_path / "s5_label-relevance.md"
    md.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    s5_label_relevance._write_topic_order_json(md, tmp_path, "criterion-x", "model-y")

    data = json.loads((tmp_path / "s5_topic_order.json").read_text(encoding="utf-8"))
    assert data["criterion"] == "criterion-x"
    assert data["model"] == "model-y"
    assert data["generated_from"] == "s5_label-relevance.md"
    assert len(data["topics"]) == 10
    assert data["topics"][0]["topic"] == 5
