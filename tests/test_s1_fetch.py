"""s1_fetch ingest 디스패치 검증 (네트워크 없이 — 계약/디스패치만)."""

import pytest

from topic_pipeline.steps import s1_fetch


def test_s1_columns_contract():
    # 단계 간 계약: s1_meta.csv 스키마 고정
    assert s1_fetch.S1_COLUMNS == [
        "pmid", "year", "title", "abstract", "author_keywords", "mesh_terms",
    ]


def test_pubmed_source_registered():
    assert "pubmed" in s1_fetch._SOURCES


def test_unknown_source_raises(tmp_path):
    cfg = {"paths": {"output_dir": str(tmp_path)}, "fetch": {"source": "bogus"}}
    with pytest.raises(ValueError, match="bogus"):
        s1_fetch.run(cfg)


# ── csv 어댑터 (T3-2) — 순수 pandas, 네트워크 없이 검증 ──

def test_csv_adapter_basic(tmp_path):
    import pandas as pd

    src = tmp_path / "corpus.csv"
    pd.DataFrame(
        {"id": [10, 20], "body": ["abc", "def"], "pub_year": [2020, 2021], "tags": ["a;b", "c"]}
    ).to_csv(src, index=False)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {
            "source": "csv", "input_csv": str(src),
            "columns": {"text": "body", "doc_id": "id", "year": "pub_year", "keywords": "tags"},
        },
    }
    s1_fetch.run(cfg)

    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert list(out.columns) == s1_fetch.S1_COLUMNS
    assert out["pmid"].tolist() == [10, 20]
    assert out["abstract"].tolist() == ["abc", "def"]
    assert out["mesh_terms"].fillna("").tolist() == ["", ""]


def test_csv_adapter_synthesizes_pmid(tmp_path):
    import pandas as pd

    src = tmp_path / "c.csv"
    pd.DataFrame({"abstract": ["x", "y", "z"]}).to_csv(src, index=False)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {"source": "csv"},
    }
    s1_fetch.run(cfg)

    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert out["pmid"].tolist() == [1, 2, 3]
    assert list(out.columns) == s1_fetch.S1_COLUMNS


def test_csv_adapter_missing_text_raises(tmp_path):
    import pandas as pd

    src = tmp_path / "c.csv"
    pd.DataFrame({"foo": [1]}).to_csv(src, index=False)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {"source": "csv"},
    }
    with pytest.raises(ValueError, match="텍스트"):
        s1_fetch.run(cfg)
