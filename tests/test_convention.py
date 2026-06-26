"""shared/convention.py 헬퍼 검증 — relevance_md_path."""

from pathlib import Path

from topic_pipeline.shared import convention


def test_relevance_md_path():
    assert convention.relevance_md_path(Path("/tmp/run1")) == Path("/tmp/run1/s5_label-relevance.md")
    assert convention.relevance_md_path("out") == Path("out/s5_label-relevance.md")
