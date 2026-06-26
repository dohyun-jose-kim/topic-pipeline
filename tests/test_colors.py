"""shared/colors.py 색상 보간 검증 (구 _smoke_test 이관)."""

from topic_pipeline.shared import colors


def test_get_colors_edge_counts():
    direct = colors.COLOR_GROUPS[0]
    assert colors.get_colors(direct, 0) == []
    assert colors.get_colors(direct, -1) == []
    assert colors.get_colors(direct, 1) == [direct["start"]]


def test_get_colors_interpolation_endpoints():
    direct = colors.COLOR_GROUPS[0]
    for n in (3, 5, 10):
        c = colors.get_colors(direct, n)
        assert len(c) == n
        assert c[0] == direct["start"]
        assert c[-1] == direct["end"]


def test_outlier_constant_color():
    outlier = colors.COLOR_GROUPS[3]
    assert colors.get_colors(outlier, 5) == [outlier["start"]] * 5


def test_all_groups_endpoints():
    for g in colors.COLOR_GROUPS:
        c4 = colors.get_colors(g, 4)
        assert len(c4) == 4
        assert c4[0] == g["start"]
        assert c4[-1] == g["end"]


def test_relevance_split_3group():
    assert colors.relevance_split(10) == (3, 4, 3)
    assert colors.relevance_split(0) == (0, 0, 0)
