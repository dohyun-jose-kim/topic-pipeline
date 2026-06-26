"""s1_fetch ingest 디스패치 검증 (네트워크 없이 — 계약/디스패치만)."""

import pandas as pd
import pytest
import responses

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


def test_csv_adapter_duplicate_docid_synthesizes(tmp_path):
    src = tmp_path / "c.csv"
    pd.DataFrame({"id": [100, 100, 200], "abstract": ["a", "b", "c"]}).to_csv(src, index=False)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {"source": "csv", "columns": {"doc_id": "id"}},
    }
    s1_fetch.run(cfg)
    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert out["pmid"].tolist() == [1, 2, 3]  # 중복 → 합성(fan-out 방지)


def test_csv_adapter_nonnumeric_docid_synthesizes(tmp_path):
    src = tmp_path / "c.csv"
    pd.DataFrame({"id": ["PMC1", "x2", "y3"], "abstract": ["a", "b", "c"]}).to_csv(src, index=False)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {"source": "csv", "columns": {"doc_id": "id"}},
    }
    s1_fetch.run(cfg)
    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert out["pmid"].tolist() == [1, 2, 3]


def test_csv_adapter_unique_docid_preserved(tmp_path):
    src = tmp_path / "c.csv"
    pd.DataFrame({"id": [10, 20], "abstract": ["a", "b"]}).to_csv(src, index=False)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {"source": "csv", "columns": {"doc_id": "id"}},
    }
    s1_fetch.run(cfg)
    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert out["pmid"].tolist() == [10, 20]  # 유일 → 보존(회귀 가드)


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


# ── jsonl / dir / arxiv 어댑터 (issue #5) ──

def test_jsonl_adapter(tmp_path):
    src = tmp_path / "c.jsonl"
    src.write_text(
        '{"id": 7, "text": "alpha", "year": 2020}\n{"id": 8, "text": "beta", "year": 2021}\n',
        encoding="utf-8",
    )
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(src)},
        "fetch": {"source": "jsonl", "input_jsonl": str(src),
                  "columns": {"text": "text", "doc_id": "id", "year": "year"}},
    }
    s1_fetch.run(cfg)
    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert list(out.columns) == s1_fetch.S1_COLUMNS
    assert out["pmid"].tolist() == [7, 8]
    assert out["abstract"].tolist() == ["alpha", "beta"]


def test_dir_adapter(tmp_path):
    d = tmp_path / "texts"
    d.mkdir()
    (d / "doc_a.txt").write_text("hello world", encoding="utf-8")
    (d / "doc_b.txt").write_text("foo bar", encoding="utf-8")
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(tmp_path)},
        "fetch": {"source": "dir", "input_dir": str(d)},
    }
    s1_fetch.run(cfg)
    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert len(out) == 2
    assert set(out["title"]) == {"doc_a", "doc_b"}   # 파일명 → title 보존
    assert out["pmid"].tolist() == [1, 2]            # 비숫자 stem → 합성


ARXIV_ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>Paper One</title><summary>Abstract one.</summary><published>2021-05-01T00:00:00Z</published><category term="cs.CL"/></entry>
  <entry><title>Paper Two</title><summary>Abstract two.</summary><published>2022-01-01T00:00:00Z</published><category term="cs.LG"/></entry>
</feed>"""


def test_parse_arxiv_atom():
    rows = s1_fetch._parse_arxiv_atom(ARXIV_ATOM)
    assert len(rows) == 2
    assert rows[0]["title"] == "Paper One"
    assert rows[0]["year"] == "2021"
    assert rows[0]["keywords"] == "cs.CL"


@responses.activate
def test_arxiv_adapter(tmp_path):
    responses.add(responses.GET, "http://export.arxiv.org/api/query", body=ARXIV_ATOM, status=200)
    cfg = {
        "paths": {"output_dir": str(tmp_path), "input_pmid_csv": str(tmp_path / "x")},
        "fetch": {"source": "arxiv", "arxiv_query": "cat:cs.CL"},
    }
    s1_fetch.run(cfg)
    out = pd.read_csv(tmp_path / "s1_meta.csv")
    assert len(out) == 2
    assert out["pmid"].tolist() == [1, 2]
    assert out["abstract"].tolist() == ["Abstract one.", "Abstract two."]
