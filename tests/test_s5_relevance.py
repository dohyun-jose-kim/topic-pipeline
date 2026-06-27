"""s5_label_relevance keyword fallback (provider=keywords) — 문서수 순, 무키."""

import json

import pandas as pd

from topic_pipeline.shared import relevance
from topic_pipeline.steps import s5_label_relevance


def test_keyword_rank_md_doc_count_order():
    df = pd.DataFrame({"topic": [0, 1, 2], "doc_count": [5, 30, 12], "label_kr": ["가", "나", "다"]})
    md = s5_label_relevance._keyword_rank_md(df, "테스트기준")
    rows = relevance.parse_relevance_table_text(md)
    assert [r["topic"] for r in rows] == [1, 2, 0]   # 문서수 desc (30,12,5)
    assert rows[0]["doc_count"] == 30


def test_run_keywords_provider_no_api(tmp_path):
    pd.DataFrame({
        "topic": [0, 1], "doc_count": [10, 40],
        "label_kr": ["가", "나"], "label_en": ["a", "b"], "description": ["d", "e"],
    }).to_csv(tmp_path / "s5_labels.csv", index=False)

    cfg = {"paths": {"output_dir": str(tmp_path)},
           "label": {"provider": "keywords", "relevance_criterion": "X"}}
    s5_label_relevance.run(cfg)  # ANTHROPIC_API_KEY 없이 동작

    data = json.loads((tmp_path / "s5_topic_order.json").read_text(encoding="utf-8"))
    assert [t["topic"] for t in data["topics"]] == [1, 0]   # doc_count 40 > 10


# ── LLM 경로 Topic 드리프트 경고 (issue #12) ──

def test_warn_on_topic_drift_fires(capsys):
    df = pd.DataFrame({"topic": [0, 4, 5], "doc_count": [3, 8, 10]})
    drift_md = "| 1 | Topic 5 | a | 10 | r |\n| 2 | 4 | b | 8 | r |\n| 3 | 0 | c | 3 | r |"
    s5_label_relevance._warn_on_topic_drift(drift_md, df)
    out = capsys.readouterr().out
    assert "invariant#3" in out and "5" in out


def test_warn_on_topic_drift_silent_when_clean(capsys):
    df = pd.DataFrame({"topic": [0, 4, 5], "doc_count": [3, 8, 10]})
    clean_md = "| 1 | 5 | a | 10 | r |\n| 2 | 4 | b | 8 | r |\n| 3 | 0 | c | 3 | r |"
    s5_label_relevance._warn_on_topic_drift(clean_md, df)
    assert capsys.readouterr().out == ""
