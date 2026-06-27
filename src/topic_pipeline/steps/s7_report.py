"""steps/s7_report.py — 종합 HTML 리포트 (PLAN-v2 §5 섹션 구조).

PLAN-v2 §8 Phase 3d. 원본: 06_Clustered_Topic_Assay_v3/clustered_topic_report.py.
§3.2 sweep 섹션 → Phase 5b 에서 채움 (stub).
§5.2 트렌드 심화 → Phase 7 에서 채움 (stub).

입력 (cfg["report"]):
  labeled_csv       : pmid, year, topic_label 포함 CSV
  embeddings_npy    : 문서 임베딩 .npy
  relevance_md      : 관련도 순위 md
  keywords_csv      : s4 산출물 경로 (선택적 — 기본 {output_dir}/s4_keywords_comparison.csv)
  metrics_csv       : 모델 품질 지표 CSV (선택적, 없으면 §3.1 placeholder)
출력:
  {output_dir}/s7_umap_cache.npy
  {output_dir}/s7_figures/umap_original.png
  {output_dir}/s7_figures/umap_relevance.png
  {output_dir}/s7_report.html
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from textwrap import wrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from ..shared.colors import (
    build_color_map,
    load_taxonomy,
    relevance_split,
    split_ranks,
)
from ..shared.convention import load_labeled_with_year, relevance_md_path
from ..shared.fonts import setup_mpl
from ..shared.html_common import render_page
from ..shared.relevance import parse_relevance_order, parse_relevance_table_text


def _wrap_title(title, width: int = 80) -> str:
    """Plotly hover 용 title 줄바꿈 — width 자 단어경계 기준 <br> 삽입."""
    t = str(title or "")
    return "<br>".join(wrap(t, width)) if t else ""


def _resolve_project_strings(cfg: dict, output_dir: Path) -> None:
    """project.주제 / project.데이터 출처 가 null 이면 자동 합성.

    주제 = "<input_pmid_csv stem> 의 <relevance_criterion> 관련 연구 동향"
    데이터 출처 = "PubMed (<s1_meta.csv year min>~<max>)"
    """
    project = cfg.setdefault("project", {})

    if project.get("주제") is None:
        stem = Path(cfg.get("paths", {}).get("input_pmid_csv", "input")).stem
        criterion = cfg.get("label", {}).get("relevance_criterion", "")
        project["주제"] = f"{stem} 의 {criterion} 관련 연구 동향"

    if project.get("데이터 출처") is None:
        s1_meta = output_dir / "s1_meta.csv"
        src = "PubMed"
        if s1_meta.exists():
            try:
                years = pd.to_numeric(
                    pd.read_csv(s1_meta, usecols=["year"])["year"],
                    errors="coerce",
                ).dropna().astype(int)
                if len(years) > 0:
                    src = f"PubMed ({int(years.min())}~{int(years.max())})"
            except Exception:
                pass
        project["데이터 출처"] = src


def run(cfg: dict) -> None:
    report_cfg = cfg["report"]
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    _resolve_project_strings(cfg, output_dir)
    fig_dir = output_dir / "s7_figures"
    fig_dir.mkdir(exist_ok=True)

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    data = _load_data(cfg, output_dir)

    umap_cfg = report_cfg.get("umap_viz", {"seed": 42, "cache": True})
    embeddings_npy = Path(report_cfg.get("embeddings_npy") or (output_dir / "s2_embeddings.npy"))
    umap_2d = _load_or_compute_umap(
        embeddings_npy,
        output_dir / "s7_umap_cache.npy",
        seed=umap_cfg.get("seed", 42),
        cache=umap_cfg.get("cache", True),
    )

    setup_mpl()
    _plot_umap_original(umap_2d, data["df"]["topic_label"].values,
                        data["name_map"], fig_dir / "umap_original.png")
    _plot_umap_relevance(umap_2d, data["df"]["topic_label"].values,
                         data["color_map"], data["name_map"],
                         data["topic_order"], fig_dir / "umap_relevance.png")

    html = _build_html(data, umap_2d, cfg, fig_dir, output_dir)
    out_path = output_dir / "s7_report.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[HTML] {out_path}")


def _load_data(cfg: dict, output_dir: Path) -> dict:
    r = cfg["report"]
    relevance_md = Path(r["relevance_md"]) if r.get("relevance_md") else relevance_md_path(output_dir)
    keywords_csv = Path(r.get("keywords_csv") or (output_dir / "s4_keywords_comparison.csv"))
    labels_csv = output_dir / "s5_labels.csv"
    metrics_csv = r.get("metrics_csv") or str(output_dir / "s3_metrics.csv")

    if r.get("labeled_csv"):
        df = pd.read_csv(r["labeled_csv"])
    else:
        df = load_labeled_with_year(output_dir)

    labels_df = pd.read_csv(labels_csv)
    keywords_df = pd.read_csv(keywords_csv)
    topic_order = parse_relevance_order(relevance_md)

    color_map = build_color_map(topic_order, load_taxonomy(cfg))
    name_map = dict(zip(labels_df["topic"], labels_df["label_kr"]))
    en_map = dict(zip(labels_df["topic"], labels_df["label_en"]))
    desc_map = dict(zip(labels_df["topic"], labels_df["description"]))

    metrics: dict = {}
    if metrics_csv and Path(metrics_csv).exists():
        metrics = pd.read_csv(metrics_csv).iloc[0].to_dict()

    return {
        "df": df,
        "labels_df": labels_df,
        "keywords_df": keywords_df,
        "relevance_md": relevance_md.read_text(encoding="utf-8"),
        "topic_order": topic_order,
        "color_map": color_map,
        "name_map": name_map,
        "en_map": en_map,
        "desc_map": desc_map,
        "metrics": metrics,
    }


def _load_or_compute_umap(
    embeddings_path: Path, cache_path: Path, *, seed: int, cache: bool
) -> np.ndarray:
    if cache and cache_path.exists():
        umap_2d = np.load(cache_path)
        emb_shape = np.load(embeddings_path, mmap_mode="r").shape
        if umap_2d.shape[0] == emb_shape[0]:
            print(f"[UMAP] 캐시 로드: {cache_path} ({umap_2d.shape})")
            return umap_2d
        print("[UMAP] 캐시 shape 불일치, 재계산")

    from umap import UMAP

    embeddings = np.load(embeddings_path)
    print(f"[UMAP] 임베딩 {embeddings.shape} → 2D 투영 (1~3분)...")
    umap_2d = UMAP(n_components=2, random_state=seed).fit_transform(embeddings)
    np.save(cache_path, umap_2d)
    print(f"[UMAP] 저장: {cache_path}")
    return umap_2d


def _draw_kde_boundary(ax, points, color, level: float = 0.20) -> None:
    from scipy.stats import gaussian_kde

    if len(points) < 10:
        return
    try:
        kde = gaussian_kde(points.T)
        x_min, x_max = points[:, 0].min() - 1, points[:, 0].max() + 1
        y_min, y_max = points[:, 1].min() - 1, points[:, 1].max() + 1
        xx, yy = np.meshgrid(
            np.linspace(x_min, x_max, 100),
            np.linspace(y_min, y_max, 100),
        )
        zz = kde(np.vstack([xx.ravel(), yy.ravel()])).reshape(xx.shape)
        threshold = np.percentile(kde(points.T), level * 100)
        ax.contour(xx, yy, zz, levels=[threshold], colors=[color],
                   linewidths=1.2, alpha=0.7, zorder=3)
    except Exception:
        pass


def _plot_umap_original(umap_2d, labels, name_map, out_path):
    unique_labels = sorted(set(labels))
    n_topics = len([l for l in unique_labels if l != -1])
    cmap = plt.colormaps.get_cmap("tab20").resampled(max(n_topics, 1))

    fig, ax = plt.subplots(figsize=(14, 10))

    if -1 in unique_labels:
        mask = labels == -1
        ax.scatter(umap_2d[mask, 0], umap_2d[mask, 1],
                   c="#888", s=4, alpha=0.4,
                   label=f"Outlier ({int(mask.sum())})",
                   zorder=1)

    color_idx = 0
    for t in unique_labels:
        if t == -1:
            continue
        mask = labels == t
        color = cmap(color_idx)
        label = f"{name_map.get(t, f'T{t}')} ({mask.sum()})"
        ax.scatter(umap_2d[mask, 0], umap_2d[mask, 1],
                   c=[color], s=5, alpha=0.5, label=label, zorder=2)
        _draw_kde_boundary(ax, umap_2d[mask], color=color)
        color_idx += 1

    ax.set_title("UMAP + HDBSCAN Clustering (원본)", fontsize=14)
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7,
              markerscale=3, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[PNG] {out_path}")


def _plot_umap_relevance(umap_2d, labels, color_map, name_map, topic_order, out_path):
    fig, ax = plt.subplots(figsize=(14, 10))

    if -1 in set(labels):
        mask = labels == -1
        ax.scatter(umap_2d[mask, 0], umap_2d[mask, 1],
                   c="#888", s=4, alpha=0.4,
                   label=f"Outlier ({int(mask.sum())})",
                   zorder=1)

    for t in topic_order:
        mask = labels == t
        if not mask.any():
            continue
        color = color_map[t]
        label = f"{name_map.get(t, f'T{t}')} ({mask.sum()})"
        ax.scatter(umap_2d[mask, 0], umap_2d[mask, 1],
                   c=[color], s=5, alpha=0.5, label=label, zorder=2)
        _draw_kde_boundary(ax, umap_2d[mask], color=color)

    ax.set_title("UMAP + HDBSCAN Clustering (생리적 기능성 3그룹 색상)", fontsize=14)
    ax.set_xlabel("UMAP-1")
    ax.set_ylabel("UMAP-2")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=7,
              markerscale=3, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[PNG] {out_path}")


def _make_plotly_umap(
    umap_2d, df, color_map_dict, name_map, topic_order,
    *, title: str, include_plotlyjs: bool = False,
) -> str:
    labels = df["topic_label"].values
    fig = go.Figure()

    mask = labels == -1
    if mask.any():
        outlier_subset = df[mask]
        outlier_hover_text = [
            f"PMID: {r.pmid}<br>Title: {_wrap_title(getattr(r, 'title', ''))}<br>"
            f"Topic: Outlier"
            for _, r in outlier_subset.iterrows()
        ]
        fig.add_trace(go.Scattergl(
            x=umap_2d[mask, 0], y=umap_2d[mask, 1],
            mode="markers", name=f"Outlier ({int(mask.sum())})",
            marker=dict(color="#888", size=4, opacity=0.4),
            text=outlier_hover_text, hoverinfo="text",
        ))

    for t in topic_order:
        mask = labels == t
        if not mask.any():
            continue
        subset = df[mask]
        color = color_map_dict[t]
        hover_text = [
            f"PMID: {r.pmid}<br>Title: {_wrap_title(getattr(r, 'title', ''))}<br>"
            f"Topic: {name_map.get(t, t)}"
            for _, r in subset.iterrows()
        ]
        fig.add_trace(go.Scattergl(
            x=umap_2d[mask, 0], y=umap_2d[mask, 1],
            mode="markers",
            name=f"{name_map.get(t, f'T{t}')} ({mask.sum()})",
            marker=dict(color=color, size=4, opacity=0.6),
            text=hover_text, hoverinfo="text",
        ))

    fig.update_layout(
        title=title,
        xaxis_title="UMAP-1", yaxis_title="UMAP-2",
        legend=dict(font=dict(size=10)),
        hovermode="closest", template="plotly_white",
        height=650, width=900,
    )
    return fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs)


def _img_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _build_color_legend_html(n_topics: int, taxonomy: dict) -> str:
    spans = []
    offset = 1
    groups = taxonomy["groups"]
    k = len(groups)
    splits = list(relevance_split(n_topics)) if k == 3 else split_ranks(n_topics, k)
    for group, n in zip(groups, splits):
        if n <= 0:
            continue
        rep = group["start"]
        spans.append(
            f'<span style="color:{rep}; font-weight:bold;">&#9632; '
            f'{group["label"]} ({offset}~{offset + n - 1}위)</span>'
        )
        offset += n
    # Outlier
    out = taxonomy["outlier"]
    spans.append(
        f'<span style="color:{out["start"]}; font-weight:bold;">&#10005; '
        f'{out["label"]}</span>'
    )
    return " &nbsp; ".join(spans)


def _write_results_json(
    output_dir: Path, project: dict, metrics: dict, topic_order: list,
    name_map: dict, en_map: dict, desc_map: dict, color_map: dict,
    *, total_docs: int, n_classified: int, n_outliers: int,
    n_topics: int, year_min: int, year_max: int,
) -> None:
    """기계판독 결과 번들 s7_results.json (외부/대시보드/corpus 간 비교용). 표·메타만(그림 제외)."""
    def _num(v):
        try:
            f = float(v)
            return int(f) if f.is_integer() else f
        except (TypeError, ValueError):
            return str(v)

    results = {
        "project": {"주제": project.get("주제", ""), "데이터 출처": project.get("데이터 출처", "")},
        "summary": {
            "total_docs": total_docs, "n_classified": n_classified, "n_outliers": n_outliers,
            "n_topics": n_topics, "year_min": year_min, "year_max": year_max,
        },
        "metrics": {k: _num(v) for k, v in (metrics or {}).items()},
        "topics": [
            {
                "topic": int(t),
                "rank": topic_order.index(t) + 1,
                "label_kr": name_map.get(t, ""),
                "label_en": en_map.get(t, ""),
                "description": desc_map.get(t, ""),
                "color": color_map.get(t, ""),
            }
            for t in topic_order
        ],
    }
    path = output_dir / "s7_results.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[results] {path}")


def _build_html(data: dict, umap_2d: np.ndarray, cfg: dict, fig_dir: Path, output_dir: Path) -> str:
    df = data["df"]
    labels_df = data["labels_df"]
    keywords_df = data["keywords_df"]
    topic_order = data["topic_order"]
    color_map = data["color_map"]
    taxonomy = load_taxonomy(cfg)
    n_groups = len(taxonomy["groups"])
    name_map = data["name_map"]
    en_map = data["en_map"]
    desc_map = data["desc_map"]
    metrics = data["metrics"]
    relevance_md_text = data["relevance_md"]

    total_docs = len(df)
    n_outliers = int((df["topic_label"] == -1).sum())
    n_topics_real = len([t for t in df["topic_label"].unique() if t != -1])
    year_min, year_max = int(df["year"].min()), int(df["year"].max())
    n_classified = total_docs - n_outliers
    out_pct = (n_outliers / total_docs * 100) if total_docs else 0.0

    project = cfg.get("project", {})
    report = cfg.get("report", {})
    label_cfg = cfg.get("label", {})

    color_legend = _build_color_legend_html(len(topic_order), taxonomy)

    # §8 보조 시각화: config(report.aux_visualizations) 기반. 기본 [] → 죽은 링크 대신 안내.
    aux_items = report.get("aux_visualizations", []) or []
    if aux_items:
        aux_html = "<ul>\n" + "\n".join(
            f'  <li><code>{a.get("file", "")}</code> — {a.get("desc", "")}</li>'
            for a in aux_items
        ) + "\n</ul>"
    else:
        aux_html = '<p class="interact-hint">(보조 시각화 미설정 — report.aux_visualizations 로 추가)</p>'

    # §1 summary
    summary_items = (
        f'<li><strong>주제</strong>: {project.get("주제", "")}</li>\n'
        f'    <li><strong>데이터 출처</strong>: {project.get("데이터 출처", "")}</li>\n'
        f'    <li><strong>대상 논문</strong>: {year_min}~{year_max}년, 총 <strong>{total_docs:,}</strong>편 '
        f'(분류 {n_classified:,} / outlier {n_outliers:,}, {out_pct:.2f}%)</li>\n'
        f'    <li><strong>토픽 수</strong>: {n_topics_real}</li>\n'
        f'    <li><strong>색상 구분</strong>: {color_legend}</li>'
    )

    year_counts = df["year"].value_counts().sort_index()
    stats_table = "".join(
        f"<tr><td>{y}</td><td style='text-align:right'>{c:,}</td></tr>"
        for y, c in year_counts.items()
    )

    # §3.1 metrics — v2.4 형식과 우리 s3 형식 둘 다 대응
    metrics_html = "<p style='color:#888; font-style:italic;'>(metrics_csv 없음 — s3 완성 후 자동 기입)</p>"
    if metrics:
        sil = float(metrics.get("silhouette", 0))

        out_r_raw = metrics.get("outlier_ratio", 0)
        out_r = float(str(out_r_raw).replace("%", "").strip())
        if out_r <= 1.0:
            out_r *= 100  # 우리 s3: decimal → percentage

        coh = metrics.get("coherence_cv")
        coh_row = f"<tr><td>C_v Coherence</td><td>{float(coh):.4f}</td></tr>" if coh and not pd.isna(coh) else ""

        n_out_m = metrics.get("n_outliers")
        if n_out_m is None or (isinstance(n_out_m, float) and pd.isna(n_out_m)):
            n_out_m = n_outliers  # df 에서 직접 계산한 값
        n_out_m = int(float(n_out_m))

        extra_rows = ""
        if "imbalance" in metrics:
            extra_rows += f"<tr><td>Imbalance (max/min)</td><td>{float(metrics['imbalance']):.2f}</td></tr>"
        if "min_count" in metrics:
            extra_rows += f"<tr><td>min_count</td><td>{int(float(metrics['min_count']))}</td></tr>"

        metrics_html = f"""
<table style="width:auto;">
  <tr><th>지표</th><th>값</th></tr>
  {coh_row}
  <tr><td>Silhouette Score</td><td>{sil:.4f}</td></tr>
  <tr><td>Outlier Ratio</td><td>{out_r:.2f}% ({n_out_m:,}편)</td></tr>
  <tr><td>Topics</td><td>{int(float(metrics.get('n_topics', 0)))}</td></tr>
  <tr><td>min_topic_size</td><td>{int(float(metrics.get('min_topic_size', 0)))}</td></tr>
  {extra_rows}
</table>"""

    # §4 topic table (by doc_count desc)
    topic_by_size = sorted(
        labels_df["topic"].tolist(),
        key=lambda t: int(labels_df[labels_df["topic"] == t].iloc[0]["doc_count"]),
        reverse=True,
    )
    topic_rows_html = ""
    for t in topic_by_size:
        row = labels_df[labels_df["topic"] == t].iloc[0]
        kw_row = keywords_df[keywords_df["topic"] == t]
        kw_detail = ""
        if not kw_row.empty:
            r = kw_row.iloc[0]
            kw_detail = f"""
  <tr>
    <td colspan="4">
      <details style="margin:4px 0;">
        <summary style="cursor:pointer; font-size:0.88em; color:#2e86c1;">키워드 비교 (접기/펼치기)</summary>
        <table style="margin:8px 0; font-size:0.85em; width:100%;">
          <tr><th style="width:120px;">c-TF-IDF</th><td>{r['c-TF-IDF']}</td></tr>
          <tr><th>KeyBERT</th><td>{r['KeyBERT']}</td></tr>
          <tr><th>Author Keywords</th><td>{r['Author_Keywords_freq']}</td></tr>
          <tr><th>MeSH Terms</th><td>{r['MeSH_freq']}</td></tr>
        </table>
      </details>
    </td>
  </tr>"""
        topic_rows_html += f"""
  <tr>
    <td>{t}</td>
    <td>{en_map.get(t, '')}</td>
    <td>{name_map.get(t, '')}</td>
    <td style="text-align:right">{int(row['doc_count']):,}</td>
  </tr>
  <tr>
    <td colspan="4" class="desc-cell">{desc_map.get(t, '')}</td>
  </tr>{kw_detail}"""

    # §6 relevance 표 — parse_relevance_table_text 재사용(콤마 doc_count 안전, invariant#3 단일 문법)
    rel_rows = parse_relevance_table_text(relevance_md_text)
    relevance_rows_html = ""
    for r in rel_rows:
        rc = color_map.get(r["topic"], "#999")
        relevance_rows_html += f"""
  <tr>
    <td style="text-align:center">{r["rank"]}</td>
    <td style="text-align:center"><span style="color:{rc}; font-size:1.2em;">&#9632;</span></td>
    <td style="text-align:center">{r["topic"]}</td>
    <td>{r["label"]}</td>
    <td style="text-align:right">{r["doc_count"]:,}</td>
    <td>{r["rationale"]}</td>
  </tr>"""

    # Plotly UMAP charts
    unique_labels = sorted([t for t in df["topic_label"].unique() if t != -1])
    cmap = plt.colormaps.get_cmap("tab20").resampled(max(len(unique_labels), 1))
    tab20_map = {}
    for i, t in enumerate(unique_labels):
        rgba = cmap(i)
        tab20_map[t] = f"rgb({int(rgba[0]*255)},{int(rgba[1]*255)},{int(rgba[2]*255)})"

    chart_umap_original = _make_plotly_umap(
        umap_2d, df, tab20_map, name_map, unique_labels,
        title="UMAP + HDBSCAN Clustering (원본)",
    )
    chart_umap_relevance = _make_plotly_umap(
        umap_2d, df, color_map, name_map, topic_order,
        title=f"UMAP + HDBSCAN Clustering ({n_groups}그룹)",
    )

    # §5.1 timeseries: embed s6 PNGs if exist
    s6_figs = output_dir / "s6_figures"
    line_png = s6_figs / "line_absolute.png"
    stacked_abs_png = s6_figs / "stacked_absolute.png"
    stacked_rel_png = s6_figs / "stacked_relative.png"
    timeseries_html = ""
    if line_png.exists():
        timeseries_html = f"""
<h3>5.1 전체 토픽 추이</h3>
<img src="{_img_to_b64(line_png)}" alt="Line Absolute" class="chart-img">
<img src="{_img_to_b64(stacked_abs_png)}" alt="Stacked Absolute" class="chart-img">
<img src="{_img_to_b64(stacked_rel_png)}" alt="Stacked Relative" class="chart-img">"""
    else:
        timeseries_html = "<p style='color:#888; font-style:italic;'>(s6_figures 없음 — timeseries step 실행 필요)</p>"

    # §3.2 sweep — outputs/sweep/ 산출물 임베드
    sweep_metrics_csv = output_dir / "sweep" / "sweep_metrics.csv"
    sweep_line_png = output_dir / "sweep" / "sweep_line.png"
    sweep_heatmap_png = output_dir / "sweep" / "sweep_heatmap.png"
    if sweep_metrics_csv.exists():
        sweep_df = pd.read_csv(sweep_metrics_csv)
        selected_mts_for_report = int(metrics.get("min_topic_size", 0)) if metrics else 0

        sweep_rows_html = ""
        for _, r in sweep_df.iterrows():
            is_selected = int(r["mts"]) == selected_mts_for_report
            row_style = ' style="background:#e8f5e9; font-weight:bold;"' if is_selected else ""
            mark = "★" if is_selected else ""
            status = "✅" if r["passed"] else "❌"
            reasons = r.get("reasons", "")
            if pd.isna(reasons):
                reasons = ""
            sweep_rows_html += f"""
  <tr{row_style}>
    <td style="text-align:center">{mark}</td>
    <td style="text-align:right">{int(r['mts'])}</td>
    <td style="text-align:right">{int(r['n_topics'])}</td>
    <td style="text-align:right">{float(r['silhouette']):.3f}</td>
    <td style="text-align:right">{float(r['imbalance']):.1f}</td>
    <td style="text-align:right">{int(r['min_count'])}</td>
    <td style="text-align:right">{float(r['outlier_ratio'])*100:.1f}%</td>
    <td style="text-align:center">{status}</td>
    <td style="font-size:0.85em; color:#666;">{reasons}</td>
  </tr>"""

        line_img_html = (
            f'<img src="{_img_to_b64(sweep_line_png)}" alt="Sweep Line" class="chart-img">'
            if sweep_line_png.exists() else ""
        )
        heatmap_img_html = (
            f'<img src="{_img_to_b64(sweep_heatmap_png)}" alt="Sweep Heatmap" class="chart-img">'
            if sweep_heatmap_png.exists() else ""
        )

        tie_break = ((cfg.get("cluster") or {}).get("sweep") or {}).get("tie_break", "median_low")
        sweep_stub = f"""
<p style="color:#666; font-size:0.92em;">
min_topic_size sweep 결과 (PLAN-v2 §12). 각 그리드 값에서 BERTopic 을 학습,
4지표 측정 후 cutoff 통과 생존자 중 {tie_break} 로 선택. ★ 표시가 최종 선택값.
</p>
<table>
  <thead>
    <tr>
      <th></th><th>mts</th><th>n_topics</th><th>silhouette</th>
      <th>imbalance</th><th>min_count</th><th>outlier%</th>
      <th>통과</th><th>사유</th>
    </tr>
  </thead>
  <tbody>{sweep_rows_html}</tbody>
</table>
{line_img_html}
{heatmap_img_html}
"""
    else:
        sweep_stub = '<p style="color:#888; font-style:italic;">(sweep 산출물 없음 — min_topic_size 단일값 직행 또는 미실행)</p>'

    # §5.2 트렌드 — s6_trend_stats.csv + trend_* PNG 임베드
    trend_csv_path = output_dir / "s6_trend_stats.csv"
    s6_figs = output_dir / "s6_figures"
    trend_cfg = (cfg.get("timeseries", {}) or {}).get("trend", {}) or {}
    trend_criterion = label_cfg.get("relevance_criterion", "(미설정)")
    trend_target_ranks = trend_cfg.get("target_ranks", [1, 2, 3])
    trend_top_n = trend_cfg.get("top_n_keywords", 7)
    if trend_csv_path.exists():
        trend_df = pd.read_csv(trend_csv_path)
        trend_table_rows = ""
        for _, r in trend_df.iterrows():
            trend_table_rows += f"""
  <tr>
    <td style="text-align:center">{r['rank']}</td>
    <td style="text-align:center">{int(r['topic_id'])}</td>
    <td>{r['label_kr']}</td>
    <td>{r['keyword']}</td>
  </tr>"""

        topic_imgs = ""
        for tid in sorted(trend_df["topic_id"].unique()):
            img_path = s6_figs / f"trend_keywords_topic{tid}.png"
            if img_path.exists():
                topic_imgs += (
                    f'<img src="{_img_to_b64(img_path)}" '
                    f'alt="Trend Topic {tid}" class="chart-img">'
                )

        trend_stub = f"""
<p style="color:#666; font-size:0.92em;">
  <strong>분석 기준</strong>:
  관련도 축 <code>{trend_criterion}</code>
  · 타겟 rank <code>{trend_target_ranks}</code>
  · 토픽당 top <code>{trend_top_n}</code> Author Keywords.
  전체 통계 (total / mk_tau / mk_p / sen_slope / cagr% / trend_label) 는 계산되어
  <code>s6_trend_stats.csv</code> 에 저장; 아래 표에서는 가독을 위해 생략.
</p>
<table>
  <thead>
    <tr>
      <th>rank</th><th>topic</th><th>label_kr</th><th>keyword</th>
    </tr>
  </thead>
  <tbody>{trend_table_rows}</tbody>
</table>
{topic_imgs}
"""
    else:
        trend_stub = '<p style="color:#888; font-style:italic;">(s6_trend_stats.csv 없음 — timeseries step 의 trend 분석 실행 필요)</p>'

    body = f"""
<h1>Topic Modeling — 종합 리포트</h1>

<div class="summary">
  <ul style="margin:0; padding-left:20px;">
    {summary_items}
  </ul>
</div>

<div class="note-box">{report.get('intro', '').strip() or '(config.report.intro 에 도입문 작성)'}</div>

<h2>1. 데이터 개요</h2>
<table style="width:auto; min-width:200px;">
  <tr><th>항목</th><th>값</th></tr>
  <tr><td>총 논문 수</td><td style="text-align:right">{total_docs:,}편</td></tr>
  <tr><td>분류된 문서</td><td style="text-align:right">{n_classified:,}편</td></tr>
  <tr><td>Outlier</td><td style="text-align:right">{n_outliers:,}편 ({out_pct:.2f}%)</td></tr>
  <tr><td>발간 년도</td><td>{year_min} ~ {year_max}</td></tr>
  <tr><td>토픽 수</td><td>{n_topics_real}개</td></tr>
</table>
<details style="margin:8px 0;">
  <summary style="cursor:pointer;">연도별 논문 수 (접기/펼치기)</summary>
  <table style="width:auto; min-width:200px;">
    <tr><th>Year</th><th>Count</th></tr>
    {stats_table}
  </table>
</details>

<h2>2. UMAP 클러스터링 시각화</h2>
<img src="{_img_to_b64(fig_dir / 'umap_original.png')}" alt="UMAP Original" class="chart-img">
<h4 style="color:#2e86c1; margin-top:24px;">INTERACTIVE CHART</h4>
<p class="interact-hint">
  마우스를 올리면 논문 정보(PMID, 제목, 토픽)를 확인할 수 있으며,
  드래그로 확대, 범례 클릭으로 토픽 표시/숨김, 더블클릭으로 단독 표시 가능.
</p>
<div class="chart-section">{chart_umap_original}</div>

<h2>3. 모델 품질</h2>
<h3>3.1 선택된 모델의 품질 지표</h3>
{metrics_html}
<div class="note-box">{report.get('metrics_note', '').strip()}</div>
<h3>3.2 하이퍼파라미터 탐색 결과 (sweep)</h3>
{sweep_stub}

<h2>4. 토픽 라벨링 결과</h2>
<p style="margin-bottom:12px;">
  토픽 번호는 BERTopic ID (0~{n_topics_real - 1}). 라벨은 LLM(<em>{label_cfg.get('model', '')}</em>)이
  4가지 키워드 소스(c-TF-IDF/KeyBERT/Author Keywords/MeSH) 를 종합해 생성.
</p>
<table>
  <thead>
    <tr><th>Topic</th><th>Label (EN)</th><th>Label (KR)</th><th>문서수</th></tr>
  </thead>
  <tbody>{topic_rows_html}</tbody>
</table>

<h2>5. 연도별 추이</h2>
{timeseries_html}
<h3>5.2 직접 관련 (1~3위) 키워드 트렌드</h3>
{trend_stub}

<h2>6. 생리적 기능성 {n_groups}그룹 분류</h2>
<div class="note-box">{report.get('relevance_group_note', '').strip()}</div>
<p><strong>색상 구분</strong>: {color_legend}</p>
<table>
  <thead>
    <tr><th>순위</th><th>그룹</th><th>Topic</th><th>Label</th><th>문서수</th><th>관련 근거</th></tr>
  </thead>
  <tbody>{relevance_rows_html}</tbody>
</table>

<h2>7. {n_groups}그룹 재색상화 UMAP</h2>
<img src="{_img_to_b64(fig_dir / 'umap_relevance.png')}" alt="UMAP Relevance" class="chart-img">
<h4 style="color:#2e86c1; margin-top:24px;">INTERACTIVE CHART</h4>
<div class="chart-section">{chart_umap_relevance}</div>

<h2>8. 보조 시각화</h2>
{aux_html}

<h2>9. 요약 코멘트</h2>
<div class="comment-box">
  <p>{report.get('summary_comment', '').strip() or '(config.report.summary_comment 에 요약 작성)'}</p>
</div>
"""

    _write_results_json(
        output_dir, project, metrics, topic_order, name_map, en_map, desc_map, color_map,
        total_docs=total_docs, n_classified=n_classified, n_outliers=n_outliers,
        n_topics=n_topics_real, year_min=year_min, year_max=year_max,
    )

    # plotly.js 번들을 head 에 1회 주입 → 차트 fragment 는 모두 include_plotlyjs=False (순서 무관).
    plotly_head = f"<script>{get_plotlyjs()}</script>"
    return render_page("Topic Modeling — 종합 리포트", body, head_extra=plotly_head)
