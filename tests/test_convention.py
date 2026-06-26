"""shared/convention.py 헬퍼 검증 — relevance_md_path."""

from pathlib import Path

from topic_pipeline.shared import convention


def test_relevance_md_path():
    assert convention.relevance_md_path(Path("/tmp/run1")) == Path("/tmp/run1/s5_label-relevance.md")
    assert convention.relevance_md_path("out") == Path("out/s5_label-relevance.md")


def test_resolve_embed_model_default():
    assert convention.resolve_embed_model({}) == convention.DEFAULT_EMBED_MODEL
    assert convention.resolve_embed_model({"embed": {}}) == convention.DEFAULT_EMBED_MODEL
    assert convention.resolve_embed_model({"embed": None}) == convention.DEFAULT_EMBED_MODEL


def test_resolve_embed_model_override():
    assert convention.resolve_embed_model({"embed": {"model_name": "foo/bar"}}) == "foo/bar"


def test_resolve_stop_words():
    assert convention.resolve_stop_words({}) == "english"
    assert convention.resolve_stop_words({"embed": {}}) == "english"
    assert convention.resolve_stop_words({"embed": {"stop_words": None}}) is None
    assert convention.resolve_stop_words({"embed": {"stop_words": ["a", "b"]}}) == ["a", "b"]
