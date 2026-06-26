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
