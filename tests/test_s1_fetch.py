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
