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


# ── split_ranks / load_taxonomy (T3-7a) ──

def test_split_ranks_sum_and_len():
    for n, k in [(10, 2), (10, 3), (10, 4), (12, 3), (7, 2)]:
        r = colors.split_ranks(n, k)
        assert len(r) == k
        assert sum(r) == n
        assert all(c >= 1 for c in r)


def test_split_ranks_weights():
    r = colors.split_ranks(10, 2, [0.7, 0.3])
    assert sum(r) == 10
    assert r[0] > r[1]


def test_split_ranks_empty():
    assert colors.split_ranks(0, 3) == [0, 0, 0]


def test_load_taxonomy_default_3group():
    tax = colors.load_taxonomy({})
    assert len(tax["groups"]) == 3
    assert tax["groups"][0]["label"] == "직접 관련"
    assert tax["outlier"]["label"] == "Outlier"


def test_load_taxonomy_custom():
    custom = {"label": {"relevance_taxonomy": {
        "groups": [{"label": "high", "start": "#000000", "end": "#ffffff"}],
    }}}
    tax = colors.load_taxonomy(custom)
    assert len(tax["groups"]) == 1
    assert tax["groups"][0]["label"] == "high"
    assert tax["outlier"]["label"] == "Outlier"  # 기본 outlier 유지


# ── build_color_map (T3-7b) ──

def test_build_color_map_default_3group_endpoints():
    order = [5, 4, 1, 2, 7, 9, 8, 6, 3, 0]  # n=10 → relevance_split (3,4,3)
    cm = colors.build_color_map(order)
    assert len(cm) == 10
    assert cm[5] == colors.COLOR_GROUPS[0]["start"]   # rank1 = direct start
    assert cm[0] == colors.COLOR_GROUPS[2]["end"]     # rank10 = low end


def test_build_color_map_custom_2group():
    tax = {"groups": [colors.COLOR_GROUPS[0], colors.COLOR_GROUPS[2]],
           "outlier": colors.COLOR_GROUPS[3]}
    cm = colors.build_color_map([1, 2, 3, 4], tax)
    assert len(cm) == 4
    assert cm[1] == colors.COLOR_GROUPS[0]["start"]
