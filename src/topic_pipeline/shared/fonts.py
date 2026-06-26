"""matplotlib 공통 rcParams (AppleGothic + unicode_minus + dpi).

PLAN-v2 §8 Phase 2c. 원본: 06_Clustered_Topic_Assay_v2/clustered_topic_report.py:158-162.
"""

from __future__ import annotations

import matplotlib.pyplot as plt


def setup_mpl() -> None:
    """한글 폰트 + 마이너스 깨짐 방지 + DPI."""
    plt.rcParams["font.family"] = "AppleGothic"
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150


def _smoke_test() -> None:
    """rcParams 반영 확인 (PLAN-v2 §8 Phase 2c)."""
    setup_mpl()
    fam = plt.rcParams["font.family"]
    assert "AppleGothic" in fam, f"font.family mismatch: {fam}"
    assert plt.rcParams["axes.unicode_minus"] is False
    assert plt.rcParams["figure.dpi"] == 150
    print(f"[OK] setup_mpl 적용: font.family={list(fam)}, dpi={plt.rcParams['figure.dpi']}")


if __name__ == "__main__":
    _smoke_test()
