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


def split_ranks(n: int, k: int, weights: list[float] | None = None) -> list[int]:
    """n개 rank 를 k개 연속 그룹 개수로 분할 (합=n; n>=k 면 각 그룹>=1).

    weights(길이 k) 지정 시 비례 분할, 없으면 균등(나머지는 앞 그룹부터).
    relevance_split(3그룹 기본)과 별개의 일반화 함수 — 커스텀 taxonomy(2/4 그룹 등)용.
    """
    if n <= 0 or k <= 0:
        return [0] * k if k > 0 else []
    if weights and len(weights) == k and sum(weights) > 0:
        s = sum(weights)
        counts = [max(1, int(round(n * w / s))) for w in weights]
    else:
        base, rem = divmod(n, k)
        counts = [max(1, base + (1 if i < rem else 0)) for i in range(k)]
    # 합을 정확히 n 에 맞추기
    while sum(counts) > n:
        j = max(range(k), key=lambda i: counts[i])
        if counts[j] <= 1:
            break
        counts[j] -= 1
    while sum(counts) < n:
        counts[min(range(k), key=lambda i: counts[i])] += 1
    return counts


def load_taxonomy(cfg) -> dict:
    """relevance taxonomy: {'groups': [{label,start,end}, ...], 'outlier': {...}}.

    cfg.label.relevance_taxonomy 없으면 현재 3그룹(COLOR_GROUPS[:3]) + Outlier 기본 (byte-identical).
    있으면 {'groups': [...], 'outlier': {...}} 또는 그룹 리스트를 받아들임.
    """
    tax = (cfg.get("label") or {}).get("relevance_taxonomy")
    if not tax:
        return {"groups": COLOR_GROUPS[:3], "outlier": COLOR_GROUPS[3]}
    if isinstance(tax, dict):
        return {"groups": tax.get("groups", COLOR_GROUPS[:3]),
                "outlier": tax.get("outlier", COLOR_GROUPS[3])}
    return {"groups": list(tax), "outlier": COLOR_GROUPS[3]}


def build_color_map(topic_order: list[int], taxonomy: dict | None = None) -> dict[int, str]:
    """관련도 순 topic_order → {topic_id: hex}. s6/s7 의 중복 로직 통합 + N그룹 taxonomy 일반화.

    기본(3그룹)은 relevance_split 분포(예: n=10 → 3/4/3)를 그대로 써서 byte-identical.
    그 외 k그룹은 split_ranks(n, k) 로 분할.
    """
    groups = (taxonomy or load_taxonomy({}))["groups"]
    n = len(topic_order)
    k = len(groups)
    counts = list(relevance_split(n)) if k == 3 else split_ranks(n, k)
    colors: list[str] = []
    for g, c in zip(groups, counts):
        colors += get_colors(g, c)
    return {topic: colors[i] for i, topic in enumerate(topic_order) if i < len(colors)}


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
