"""shared/convention.py 헬퍼 검증 — relevance_md_path."""

from pathlib import Path

import pandas as pd
import pytest

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


# ── load_labeled_with_year (issue #11) ──

def _write_labeled(tmp_path, years):
    n = len(years)
    pd.DataFrame({"pmid": range(1, n + 1), "year": years, "abstract": ["x"] * n}).to_csv(
        tmp_path / "s2_meta_for_embed.csv", index=False)
    pd.DataFrame({"pmid": range(1, n + 1), "topic_label": [0] * n}).to_csv(
        tmp_path / "s3_labels.csv", index=False)


def test_load_labeled_with_year_filters(tmp_path):
    _write_labeled(tmp_path, [2020, "", 2022])   # 빈 year 행은 drop
    df = convention.load_labeled_with_year(tmp_path)
    assert df["year"].tolist() == [2020, 2022]


def test_load_labeled_with_year_empty_raises(tmp_path):
    _write_labeled(tmp_path, ["", "", ""])       # 연도 없는 코퍼스(dir 등) → 명확한 에러
    with pytest.raises(ValueError, match="year"):
        convention.load_labeled_with_year(tmp_path)
