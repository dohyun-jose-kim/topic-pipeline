"""steps/s6_timeseries.py — 토픽별 연도 추이 (기본, 트렌드 제외).

PLAN-v2 §8 Phase 3c. 원본: 05_TimeSeries-Assay/topics_over_time.py 의 기본 차트 부분.
트렌드 통계(MK/Sen/CAGR)는 Phase 7, HTML 리포트 조립은 s7(§5).

입력:
  {timeseries.labeled_csv}    : pmid, year, topic_label 포함 CSV
  {timeseries.relevance_md}   : 관련도 순위 md (1~10위)
  {output_dir}/s5_labels.csv  : topic → label_kr 매핑 (Phase 3b 산출물)
출력:
  {output_dir}/s6_topics_over_time.csv
  {output_dir}/s6_figures/line_absolute.png
  {output_dir}/s6_figures/stacked_absolute.png
  {output_dir}/s6_figures/stacked_relative.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..shared.colors import COLOR_GROUPS, build_color_map, load_taxonomy
from ..shared.convention import load_labeled_convention, relevance_md_path
from ..shared.fonts import setup_mpl
from ..shared.relevance import parse_relevance_order

OUTLIER_COLOR = COLOR_GROUPS[3]["start"]


def run(cfg: dict) -> None:
    ts_cfg = cfg["timeseries"]
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = output_dir / "s6_figures"
    fig_dir.mkdir(exist_ok=True)

    relevance_md = Path(ts_cfg["relevance_md"]) if ts_cfg.get("relevance_md") else relevance_md_path(output_dir)
    labels_csv = output_dir / "s5_labels.csv"

    if ts_cfg.get("labeled_csv"):
        df = pd.read_csv(ts_cfg["labeled_csv"])
    else:
        df = load_labeled_convention(output_dir)
        df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)
        df = df[df["year"] > 0].reset_index(drop=True)

    labels = pd.read_csv(labels_csv)
    topic_order = parse_relevance_order(relevance_md)

    name_map = dict(zip(labels["topic"], labels["label_kr"]))
    color_map = build_color_map(topic_order, load_taxonomy(cfg))

    freq = df.groupby(["year", "topic_label"]).size().reset_index(name="count")
    pivot = freq.pivot(index="year", columns="topic_label", values="count").fillna(0).astype(int)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    _save_csv(pivot, name_map, output_dir / "s6_topics_over_time.csv")

    setup_mpl()
    _plot_line_absolute(pivot, topic_order, color_map, name_map, fig_dir / "line_absolute.png")
    _plot_stacked(
        pivot, topic_order, color_map, name_map,
        fig_dir / "stacked_absolute.png",
        y_label="Number of Papers", title_suffix="절대량",
    )
    _plot_stacked(
        pivot_pct, topic_order, color_map, name_map,
        fig_dir / "stacked_relative.png",
        y_label="Proportion (%)", title_suffix="비율%", ylim=(0, 100),
    )

    print("[CSV] s6_topics_over_time.csv")
    print("[PNG] s6_figures/{line_absolute, stacked_absolute, stacked_relative}.png")

    # ── 트렌드 심화 (Phase 7, PLAN-v2-trend.md) ──
    trend_cfg = ts_cfg.get("trend", {}) or {}
    if trend_cfg.get("enabled", True):
        _run_trend_analysis(
            df, topic_order, name_map, color_map,
            trend_cfg, ts_cfg, output_dir, fig_dir,
        )


def _save_csv(pivot: pd.DataFrame, name_map: dict, out_path: Path) -> None:
    out = pivot.copy()
    out.columns = [f"T{c}_{name_map.get(c, c)}" for c in out.columns]
    out.to_csv(out_path, encoding="utf-8-sig")


def _plot_line_absolute(pivot, topic_order, color_map, name_map, out_path):
    fig, ax = plt.subplots(figsize=(14, 7))
    for t in topic_order:
        if t in pivot.columns:
            ax.plot(
                pivot.index, pivot[t],
                label=name_map.get(t, f"Topic {t}"),
                color=color_map[t], linewidth=1.8, marker="o", markersize=3,
            )
    if -1 in pivot.columns:
        ax.plot(
            pivot.index, pivot[-1], label="Outlier",
            color=OUTLIER_COLOR, linestyle="--", linewidth=1.2, alpha=0.6,
        )
    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Papers")
    ax.set_title("토픽별 연도 추이 (절대량)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _plot_stacked(pivot, topic_order, color_map, name_map, out_path, *, y_label, title_suffix, ylim=None):
    cols = [t for t in topic_order if t in pivot.columns]
    stack_cols = cols + ([-1] if -1 in pivot.columns else [])
    stack_colors = [color_map[t] for t in cols] + ([OUTLIER_COLOR] if -1 in pivot.columns else [])
    stack_labels = [name_map.get(t, f"Topic {t}") for t in cols] + (["Outlier"] if -1 in pivot.columns else [])

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.stackplot(pivot.index, *[pivot[t] for t in stack_cols],
                 labels=stack_labels, colors=stack_colors, alpha=0.85)
    ax.set_xlabel("Year")
    ax.set_ylabel(y_label)
    ax.set_title(f"토픽별 연도 추이 — Stacked Area ({title_suffix})")
    if ylim:
        ax.set_ylim(*ylim)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# ── 트렌드 심화 (PLAN-v2-trend.md) ──────────────────────────────

def _run_trend_analysis(df, topic_order, name_map, color_map,
                        trend_cfg, ts_cfg, output_dir, fig_dir):
    """직접 관련 N 토픽의 top K Author Keywords 시계열 트렌드 분석."""
    target_ranks = trend_cfg.get("target_ranks", [1, 2, 3])
    top_n = trend_cfg.get("top_n_keywords", 10)
    p_thresh = trend_cfg.get("p_threshold", 0.05)
    ma_window = trend_cfg.get("moving_avg_window", 5)

    # labeled_csv 에 author_keywords 가 없으면 별도 병합 (phase3a_test_config 대응)
    if "author_keywords" not in df.columns:
        kw_csv = ts_cfg.get("author_keywords_csv")
        if not kw_csv:
            print("[s6.trend] author_keywords 컬럼도 author_keywords_csv 설정도 없음 — skip")
            return
        kw_df = pd.read_csv(kw_csv, usecols=["pmid", "author_keywords"])
        df = df.merge(kw_df, on="pmid", how="left")

    actual_topics = set(df["topic_label"].tolist())
    targets = []
    for rank in target_ranks:
        if rank - 1 >= len(topic_order):
            continue
        tid = topic_order[rank - 1]
        if tid in actual_topics:
            targets.append((rank, tid))
        else:
            print(f"[s6.trend] rank={rank} → topic_id={tid} df 에 없음 — skip")

    if not targets:
        print("[s6.trend] target topic 매칭 0건 — skip")
        return

    stats_rows = []
    topic_keyword_data: dict[int, dict[str, pd.Series]] = {}

    for rank, tid in targets:
        top_kws = _top_keywords_for_topic(df, tid, top_n)
        topic_keyword_data[tid] = {}
        for kw in top_kws:
            yearly = _yearly_counts_for_kw(df, tid, kw)
            topic_keyword_data[tid][kw] = yearly
            mk_tau, mk_p, sen, cagr, label = _compute_trend_stats(yearly, p_thresh)
            stats_rows.append({
                "rank": rank,
                "topic_id": int(tid),
                "label_kr": name_map.get(tid, f"Topic {tid}"),
                "keyword": kw,
                "total_count": int(yearly.sum()),
                "year_min": int(yearly.index.min()) if len(yearly) else 0,
                "year_max": int(yearly.index.max()) if len(yearly) else 0,
                "mk_tau": round(mk_tau, 4) if not np.isnan(mk_tau) else None,
                "mk_p": round(mk_p, 4) if not np.isnan(mk_p) else None,
                "sen_slope": round(sen, 4) if not np.isnan(sen) else None,
                "cagr_pct": round(cagr, 2) if not np.isnan(cagr) else None,
                "trend_label": label,
            })

        _plot_trend_topic(
            tid, top_kws, topic_keyword_data[tid],
            name_map.get(tid, f"Topic {tid}"),
            ma_window,
            fig_dir / f"trend_keywords_topic{tid}.png",
        )

    stats_df = pd.DataFrame(stats_rows)
    stats_df.to_csv(output_dir / "s6_trend_stats.csv", index=False, encoding="utf-8-sig")
    print(f"[CSV] s6_trend_stats.csv ({len(stats_df)}행)")
    print("[PNG] s6_figures/trend_keywords_topic*.png")


def _top_keywords_for_topic(df: pd.DataFrame, topic_id: int, top_n: int) -> list[str]:
    from collections import Counter
    sub = df[df["topic_label"] == topic_id]
    counter: Counter = Counter()
    for kw_str in sub["author_keywords"].dropna():
        for kw in str(kw_str).split("; "):
            kw = kw.strip().lower()
            if kw:
                counter[kw] += 1
    return [kw for kw, _ in counter.most_common(top_n)]


def _yearly_counts_for_kw(df: pd.DataFrame, topic_id: int, keyword: str) -> pd.Series:
    sub = df[df["topic_label"] == topic_id]
    mask = sub["author_keywords"].astype(str).apply(
        lambda s: keyword in {k.strip().lower() for k in s.split("; ")}
    )
    return sub[mask].groupby("year").size().sort_index()


def _compute_trend_stats(yearly: pd.Series, p_thresh: float):
    import pymannkendall as mk_mod

    if len(yearly) < 3 or yearly.sum() == 0:
        return float("nan"), float("nan"), float("nan"), float("nan"), "insufficient"

    result = mk_mod.original_test(yearly.values)
    mk_tau = float(result.Tau)
    mk_p = float(result.p)
    sen = float(result.slope)

    y0, yN = float(yearly.iloc[0]), float(yearly.iloc[-1])
    n_years = int(yearly.index[-1]) - int(yearly.index[0])
    if y0 > 0 and yN > 0 and n_years > 0:
        cagr = ((yN / y0) ** (1 / n_years) - 1) * 100
    else:
        cagr = float("nan")

    if mk_p < p_thresh and sen > 0:
        label = "emerging"
    elif mk_p < p_thresh and sen < 0:
        label = "declining"
    else:
        label = "stable"

    return mk_tau, mk_p, sen, cagr, label


def _plot_trend_topic(topic_id, keywords, kw_data, topic_label_kr, ma_window, out_path):
    fig, ax = plt.subplots(figsize=(13, 7))
    cmap = plt.colormaps.get_cmap("tab10").resampled(max(len(keywords), 1))

    for i, kw in enumerate(keywords):
        yearly = kw_data[kw]
        if len(yearly) == 0:
            continue
        color = cmap(i)
        ax.plot(yearly.index, yearly.values, "o-", color=color,
                label=f"{kw} (n={int(yearly.sum())})",
                linewidth=1.2, markersize=3, alpha=0.7)
        if len(yearly) >= ma_window:
            ma = yearly.rolling(window=ma_window, center=True).mean()
            ax.plot(ma.index, ma.values, color=color, linewidth=2.2, alpha=0.9)

    ax.set_title(f"Topic {topic_id}: {topic_label_kr} — Author Keywords 추세 (top {len(keywords)})")
    ax.set_xlabel("Year")
    ax.set_ylabel("Paper count")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight", dpi=120)
    plt.close(fig)


