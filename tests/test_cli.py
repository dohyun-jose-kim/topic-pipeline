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
    cfg = {"paths": {"input_pmid_csv": str(inp)}}
    # 전체 실행: 각 step 입력은 앞 step 이 생성 → input CSV 만 있으면 통과
    assert cli._validate_preconditions(list(cli.STEPS), tmp_path, cfg) == []


def test_validate_report_alone_missing(tmp_path):
    missing = cli._validate_preconditions(["report"], tmp_path, {})
    files = {f for _, f, _ in missing}
    assert "s2_embeddings.npy" in files
    assert "s5_labels.csv" in files
    # 생성 step 정보가 채워졌는지
    assert all(producer != "?" for _, _, producer in missing)


def test_validate_fetch_missing_input(tmp_path):
    cfg = {"paths": {"input_pmid_csv": str(tmp_path / "nope.csv")}}
    missing = cli._validate_preconditions(["fetch"], tmp_path, cfg)
    assert any(f.endswith("nope.csv") for _, f, _ in missing)


def test_validate_range_satisfied_by_earlier_selected(tmp_path):
    # embed→cluster 연속 실행: cluster 입력(s2_*)은 embed 가 만드므로, s1_meta.csv 만 있으면 통과
    (tmp_path / "s1_meta.csv").write_text("x")
    assert cli._validate_preconditions(["embed", "cluster"], tmp_path, {}) == []


# ── config override / fetch source 인식 (issue #1) ──

def test_validate_report_with_labeled_csv_override(tmp_path):
    # report.labeled_csv/relevance_md/keywords_csv 지정 시 convention 파일 거짓실패 안 남
    for name in ("my_labels.csv", "rel.md", "kw.csv"):
        (tmp_path / name).write_text("x")
    (tmp_path / "s2_embeddings.npy").write_text("x")
    (tmp_path / "s5_labels.csv").write_text("x")
    cfg = {"report": {"labeled_csv": str(tmp_path / "my_labels.csv"),
                      "relevance_md": str(tmp_path / "rel.md"),
                      "keywords_csv": str(tmp_path / "kw.csv")}}
    assert cli._validate_preconditions(["report"], tmp_path, cfg) == []


def test_validate_report_override_missing_reports_override_path(tmp_path):
    # override 경로가 없으면 convention 파일이 아니라 그 override 경로를 누락 보고
    for name in ("s2_embeddings.npy", "s5_labels.csv", "s5_label-relevance.md",
                 "s4_keywords_comparison.csv"):
        (tmp_path / name).write_text("x")
    cfg = {"report": {"labeled_csv": str(tmp_path / "nope.csv")}}
    missing = cli._validate_preconditions(["report"], tmp_path, cfg)
    paths = {f for _, f, _ in missing}
    assert str(tmp_path / "nope.csv") in paths       # override 경로를 보고
    assert "s2_meta_for_embed.csv" not in paths      # convention 파일은 보고 안 함
    assert "s3_labels.csv" not in paths              # 같은 override 가 둘 다 대체


def test_validate_fetch_csv_source_uses_input_csv(tmp_path):
    # source=csv 면 input_pmid_csv 가 아니라 fetch.input_csv 존재를 확인
    (tmp_path / "corpus.csv").write_text("text\nhi\n")
    cfg = {"paths": {"input_pmid_csv": str(tmp_path / "absent.csv")},
           "fetch": {"source": "csv", "input_csv": str(tmp_path / "corpus.csv")}}
    assert cli._validate_preconditions(["fetch"], tmp_path, cfg) == []


def test_validate_fetch_arxiv_no_local_input(tmp_path):
    # source=arxiv 는 네트워크 입력 → 로컬 파일 검증 안 함
    cfg = {"paths": {"input_pmid_csv": str(tmp_path / "absent.csv")},
           "fetch": {"source": "arxiv", "arxiv_query": "cat:cs.CL"}}
    assert cli._validate_preconditions(["fetch"], tmp_path, cfg) == []


# ── serve (issue #7) ──

def test_serve_blocked_logs():
    assert cli._serve_blocked("/logs/run.log")
    assert cli._serve_blocked("logs/")
    assert cli._serve_blocked("/logs")
    assert not cli._serve_blocked("/s7_report.html")
    assert not cli._serve_blocked("/s7_results.json")


def test_serve_blocked_bypass_vectors():
    # translate_path 가 unquote+normpath 한 뒤 logs/ 에 도달하는 우회 경로들도 차단 (issue #8)
    assert cli._serve_blocked("/%6Cogs/run.log")        # 퍼센트 인코딩 ('l')
    assert cli._serve_blocked("/logs%2frun.log")        # %2f → '/'
    assert cli._serve_blocked("/./logs/run.log")        # dot-segment
    assert cli._serve_blocked("/foo/../logs/run.log")   # 상위 참조 정규화
    assert cli._serve_blocked("/Logs/run.log")          # case-insensitive FS
    assert cli._serve_blocked("/exp1/logs/run.log")     # run-id 하위 디렉터리
    # 정상 산출물은 통과
    assert not cli._serve_blocked("/exp1/s7_report.html")
    assert not cli._serve_blocked("/s6_figures/line_absolute.png")


def test_serve_missing_dir_returns_1(tmp_path):
    # 디렉토리 없으면 서버 기동 없이 1 반환 (블로킹 X)
    assert cli._serve(tmp_path / "nope", 8123) == 1
