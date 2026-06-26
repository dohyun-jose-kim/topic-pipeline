"""COLOR_GROUPS + get_colors — RGB 선형 보간 (PLAN-v2 §13).

그룹별 start/end hex 를 정의하고 토픽 수 n 에 따라 n개 색을 선형 보간으로 생성.
"""

from __future__ import annotations

COLOR_GROUPS = [
    {"label": "직접 관련",   "start": "#1b7a3d", "end": "#a8dfc0"},
    {"label": "간접 관련",   "start": "#1a5276", "end": "#c5e2f4"},
    {"label": "낮은 관련도", "start": "#b0855a", "end": "#e2c291"},
    {"label": "Outlier",     "start": "#bdc3c7", "end": "#bdc3c7",
                             "marker": "x", "alpha": 0.3},
]


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def get_colors(group: dict, n: int) -> list[str]:
    """그룹 내 n개 토픽에 대해 start→end 선형 보간한 n개 색상 반환."""
    if n <= 0:
        return []
    if n == 1:
        return [group["start"]]
    start = hex_to_rgb(group["start"])
    end = hex_to_rgb(group["end"])
    return [
        rgb_to_hex(tuple(round(s + (i / (n - 1)) * (e - s)) for s, e in zip(start, end)))
        for i in range(n)
    ]


def relevance_split(n: int) -> tuple[int, int, int]:
    """Rank 기반 3등분 (직접/간접/낮은) 개수. n=10 → (3,4,3) 하위호환."""
    if n <= 0:
        return 0, 0, 0
    n_direct = max(1, n // 3)
    n_low = max(1, n // 3)
    n_indirect = max(1, n - n_direct - n_low)
    return n_direct, n_indirect, n_low


def _smoke_test() -> None:
    """N=1/3/5/10 보간 검증 (PLAN-v2 §8 Phase 2a 기준)."""
    direct = COLOR_GROUPS[0]
    outlier = COLOR_GROUPS[3]

    assert get_colors(direct, 0) == []
    assert get_colors(direct, -1) == []
    assert get_colors(direct, 1) == [direct["start"]]

    for n in (3, 5, 10):
        c = get_colors(direct, n)
        assert len(c) == n, f"N={n} 길이 mismatch: {len(c)}"
        assert c[0] == direct["start"], f"N={n} c[0] mismatch: {c[0]}"
        assert c[-1] == direct["end"], f"N={n} c[-1] mismatch: {c[-1]}"

    assert get_colors(outlier, 5) == [outlier["start"]] * 5

    for g in COLOR_GROUPS:
        c4 = get_colors(g, 4)
        assert len(c4) == 4
        assert c4[0] == g["start"]
        assert c4[-1] == g["end"]

    print("[OK] N=1/3/5/10 보간 검증 통과")
    for n in (1, 3, 5, 10):
        print(f"  direct N={n}: {get_colors(direct, n)}")
    print(f"  outlier N=5:  {get_colors(outlier, 5)}")


if __name__ == "__main__":
    _smoke_test()
