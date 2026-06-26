"""s5_label keyword fallback (provider=keywords) — LLM/API 키 없이 동작."""

import pandas as pd

from topic_pipeline.steps import s5_label


def test_keyword_labels_topwords():
    df = pd.DataFrame({
        "topic": [0, 1],
        "doc_count": [10, 5],
        "c-TF-IDF": ["protein; collagen; peptide; gel", ""],
        "KeyBERT": ["x; y", "sleep; cognition"],
        "Author_Keywords_freq": ["", ""],
        "MeSH_freq": ["", ""],
    })
    labels = s5_label._keyword_labels(df)
    assert labels[0]["label_kr"] == "protein, collagen, peptide"   # 상위 3
    assert labels[1]["label_kr"] == "sleep, cognition"             # c-TF-IDF 비면 KeyBERT
    assert labels[0]["description"].startswith("주요 키워드:")


def test_run_keywords_provider_no_api(tmp_path):
    pd.DataFrame({
        "topic": [0, 1],
        "doc_count": [10, 5],
        "c-TF-IDF": ["a; b; c", "d; e"],
        "KeyBERT": ["", ""],
        "Author_Keywords_freq": ["", ""],
        "MeSH_freq": ["", ""],
    }).to_csv(tmp_path / "s4_keywords_comparison.csv", index=False)

    cfg = {"paths": {"output_dir": str(tmp_path)}, "label": {"provider": "keywords"}}
    s5_label.run(cfg)  # ANTHROPIC_API_KEY 없이 동작해야 한다

    out = pd.read_csv(tmp_path / "s5_labels.csv")
    assert {"topic", "label_en", "label_kr", "description"} <= set(out.columns)
    assert out.loc[out["topic"] == 0, "label_kr"].iloc[0] == "a, b, c"
