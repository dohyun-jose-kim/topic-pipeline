"""shared/fonts.py rcParams 검증 (구 _smoke_test 이관)."""

from topic_pipeline.shared import fonts


def test_setup_mpl_rcparams():
    import matplotlib.pyplot as plt

    fonts.setup_mpl()
    assert "AppleGothic" in plt.rcParams["font.family"]
    assert plt.rcParams["axes.unicode_minus"] is False
    assert plt.rcParams["figure.dpi"] == 150
