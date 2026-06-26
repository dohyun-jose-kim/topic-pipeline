"""cli 헬퍼 검증 — run-id 네임스페이싱 + step 선택/사전검증."""

from pathlib import Path
from types import SimpleNamespace

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


# ── _select_steps ────────────────────────────────────────

def test_select_steps_explicit():
    args = SimpleNamespace(steps=["embed", "cluster"], from_step=None, to_step=None)
    assert cli._select_steps(args) == ["embed", "cluster"]


def test_select_steps_range():
    args = SimpleNamespace(steps=[], from_step="cluster", to_step="label")
    assert cli._select_steps(args) == ["cluster", "enrich", "label"]


def test_select_steps_from_only():
    args = SimpleNamespace(steps=[], from_step="timeseries", to_step=None)
    assert cli._select_steps(args) == ["timeseries", "report"]


def test_select_steps_all():
    args = SimpleNamespace(steps=[], from_step=None, to_step=None)
    assert cli._select_steps(args) == list(cli.STEPS)


# ── _validate_preconditions ──────────────────────────────

def test_validate_all_steps_ok_with_input(tmp_path):
    inp = tmp_path / "in.csv"
    inp.write_text("pmid\n1\n")
    # 전체 실행: 각 step 입력은 앞 step 이 생성 → input CSV 만 있으면 통과
    assert cli._validate_preconditions(list(cli.STEPS), tmp_path, str(inp)) == []


def test_validate_report_alone_missing(tmp_path):
    missing = cli._validate_preconditions(["report"], tmp_path, None)
    files = {f for _, f, _ in missing}
    assert "s2_embeddings.npy" in files
    assert "s5_labels.csv" in files
    # 생성 step 정보가 채워졌는지
    assert all(producer != "?" for _, _, producer in missing)


def test_validate_fetch_missing_input(tmp_path):
    missing = cli._validate_preconditions(["fetch"], tmp_path, str(tmp_path / "nope.csv"))
    assert any(f.endswith("nope.csv") for _, f, _ in missing)


def test_validate_range_satisfied_by_earlier_selected(tmp_path):
    # embed→cluster 연속 실행: cluster 입력(s2_*)은 embed 가 만드므로, s1_meta.csv 만 있으면 통과
    (tmp_path / "s1_meta.csv").write_text("x")
    assert cli._validate_preconditions(["embed", "cluster"], tmp_path, None) == []


# ── serve (issue #7) ──

def test_serve_blocked_logs():
    assert cli._serve_blocked("/logs/run.log")
    assert cli._serve_blocked("logs/")
    assert cli._serve_blocked("/logs")
    assert not cli._serve_blocked("/s7_report.html")
    assert not cli._serve_blocked("/s7_results.json")


def test_serve_missing_dir_returns_1(tmp_path):
    # 디렉토리 없으면 서버 기동 없이 1 반환 (블로킹 X)
    assert cli._serve(tmp_path / "nope", 8123) == 1
