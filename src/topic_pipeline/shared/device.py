"""compute device 해석 + torch 기본 디바이스 설정.

기본은 CPU (기존 동작 유지). cfg.compute.device 로 'cuda'/'mps'/'auto' opt-in.
s2/s3/s4/s7 에 흩어진 `torch.set_default_device('cpu')` 중복 블록을 대체하기 위한 단일 진입점
(배선은 T2-9). torch 는 무거우므로 함수 내부에서 lazy import.
"""

from __future__ import annotations

import os


def resolve_device(cfg: dict) -> str:
    """cfg.compute.device 해석. 'auto' 면 cuda → mps → cpu 순으로 가용 디바이스 선택."""
    dev = (cfg.get("compute") or {}).get("device", "cpu")
    if dev != "auto":
        return dev
    import torch

    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def setup_torch(cfg: dict) -> str:
    """torch 기본 디바이스 설정 + MPS fallback 환경변수. 해석된 device 문자열 반환."""
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    import torch

    dev = resolve_device(cfg)
    torch.set_default_device(dev)
    return dev


def _smoke_test() -> None:
    """torch 없이도 되는 경로만 검증 (cpu/명시)."""
    assert resolve_device({}) == "cpu"
    assert resolve_device({"compute": {"device": "cpu"}}) == "cpu"
    assert resolve_device({"compute": {"device": "cuda"}}) == "cuda"
    print("[OK] resolve_device 기본/명시 검증 통과")


if __name__ == "__main__":
    _smoke_test()
