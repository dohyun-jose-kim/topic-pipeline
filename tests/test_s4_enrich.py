"""s4_enrich._aggregate_meta_keywords — MeSH/Author-KW optional 검증 (순수 pandas)."""

import pandas as pd

from topic_pipeline.steps import s4_enrich


def test_aggregate_with_columns():
    labeled = pd.DataFrame({"pmid": [1, 2], "topic_label": [0, 0]})
    kw = pd.DataFrame({
        "pmid": [1, 2],
        "author_keywords": ["a; b", "a"],
        "mesh_terms_v2": ["m1", "m1; m2"],
    })
    res = s4_enrich._aggregate_meta_keywords(labeled, kw)
    assert dict(res[0]["author_kw"]).get("a") == 2
    assert dict(res[0]["mesh"]).get("m1") == 2


def test_aggregate_missing_columns_graceful():
    # 비-PubMed corpus: author_keywords / mesh_terms_v2 없음 → KeyError 없이 빈 결과
    labeled = pd.DataFrame({"pmid": [1, 2], "topic_label": [0, 0]})
    kw = pd.DataFrame({"pmid": [1, 2]})
    res = s4_enrich._aggregate_meta_keywords(labeled, kw)
    assert res[0]["author_kw"] == []
    assert res[0]["mesh"] == []
