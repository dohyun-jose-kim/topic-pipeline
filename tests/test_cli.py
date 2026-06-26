"""cli 헬퍼 검증 — run-id 네임스페이싱 (_resolve_output_dir)."""

from pathlib import Path

from topic_pipeline import cli


def test_resolve_output_dir_flat_default():
    cfg = {"paths": {"output_dir": "./outputs"}}
    out = cli._resolve_output_dir(cfg)
    assert out == Path("outputs")
    assert cfg["paths"]["output_dir"] == "outputs"  # today 와 동일 (flat)


def test_resolve_output_dir_with_run_id():
    cfg = {"paths": {"output_dir": "./outputs", "run_id": "demoA"}}
    out = cli._resolve_output_dir(cfg)
    assert out == Path("outputs/demoA")
    assert cfg["paths"]["output_dir"] == "outputs/demoA"


def test_resolve_output_dir_auto_timestamp():
    cfg = {"paths": {"output_dir": "out", "run_id": "auto"}}
    out = cli._resolve_output_dir(cfg)
    assert str(out).startswith("out/run_")
    assert cfg["paths"]["output_dir"].startswith("out/run_")
