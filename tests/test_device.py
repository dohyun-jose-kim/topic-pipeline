"""shared/device.py resolve_device 검증 (torch 불필요 — cpu/명시 경로만)."""

from topic_pipeline.shared import device


def test_resolve_device_default_cpu():
    assert device.resolve_device({}) == "cpu"
    assert device.resolve_device({"compute": {}}) == "cpu"
    assert device.resolve_device({"compute": None}) == "cpu"


def test_resolve_device_explicit():
    assert device.resolve_device({"compute": {"device": "cpu"}}) == "cpu"
    assert device.resolve_device({"compute": {"device": "cuda"}}) == "cuda"
    assert device.resolve_device({"compute": {"device": "mps"}}) == "mps"
