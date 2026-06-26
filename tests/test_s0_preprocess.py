"""s0_preprocess — enabled/disabled 동작 (순수 pandas, 네트워크 불필요)."""

import pandas as pd

from topic_pipeline.steps import s0_preprocess


def test_s0_disabled_skips(tmp_path):
    (tmp_path / "s1_meta.csv").write_text("pmid,abstract\n1,Hello [1] 5\n", encoding="utf-8")
    cfg = {"paths": {"output_dir": str(tmp_path)}}  # preprocess 없음 → 비활성
    s0_preprocess.run(cfg)
    assert not (tmp_path / "s0_meta_clean.csv").exists()


def test_s0_enabled_produces_clean(tmp_path):
    (tmp_path / "s1_meta.csv").write_text(
        "pmid,abstract\n1,Hello [1] 5\n2,World http://x\n", encoding="utf-8"
    )
    cfg = {"paths": {"output_dir": str(tmp_path)}, "preprocess": {"enabled": True}}
    s0_preprocess.run(cfg)

    out = pd.read_csv(tmp_path / "s0_meta_clean.csv")
    assert "abstract" in out.columns and "abstract_clean" in out.columns  # 원본 유지
    assert out["abstract_clean"].tolist() == ["hello", "world"]
