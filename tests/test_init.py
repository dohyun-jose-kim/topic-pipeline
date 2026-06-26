"""topic-pipeline --init / 프리셋 스캐폴딩 (issue #4)."""

import yaml

from topic_pipeline import cli


def test_list_presets():
    presets = cli._list_presets()
    assert "general" in presets and "biomedical" in presets


def test_init_writes_general(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli._init("myproj", "general") == 0
    p = tmp_path / "myproj.yaml"
    assert p.exists()
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert d["fetch"]["source"] == "csv"
    assert d["label"]["provider"] == "keywords"   # 무키 프리셋


def test_init_default_preset_is_general(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli._init("p2", None) == 0
    d = yaml.safe_load((tmp_path / "p2.yaml").read_text(encoding="utf-8"))
    assert d["fetch"]["source"] == "csv"


def test_init_unknown_preset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli._init("x", "nonexistent") == 1


def test_init_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.yaml").write_text("existing", encoding="utf-8")
    assert cli._init("x", "general") == 1
