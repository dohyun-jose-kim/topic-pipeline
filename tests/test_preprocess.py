"""shared/preprocess.py — abstract 정제 (순수 stdlib, 네트워크 불필요)."""

import pandas as pd

from topic_pipeline.shared import preprocess


def test_clean_abstract_strips():
    out = preprocess.clean_abstract("See https://x.org [12] and 42% at DOI 10.1234/abc.")
    assert "http" not in out
    assert "[12]" not in out
    assert "42" not in out
    assert out == out.lower()


def test_clean_abstract_nonstring():
    assert preprocess.clean_abstract(None) == ""
    assert preprocess.clean_abstract(3.14) == ""


def test_clean_series():
    s = pd.Series(["AAA http://x", None, "B [1] 5"])
    out = preprocess.clean_series(s)
    assert list(out) == ["aaa", "", "b"]
