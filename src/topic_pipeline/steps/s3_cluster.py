"""steps/s3_cluster.py — BERTopic + min_topic_size sweep + 캐시 + outlier 정책.

PLAN-v2:
 - §8 Phase 5b: 검증 (sweep 산출물 + 캐시 디렉토리)
 - §11 cache key: s3_model_d{N}_t{M}_s{seed}_{md5_8}/
 - §12 sweep: 5값 기하급수 그리드 + 4지표 cutoff + median_low tie-break
 - §13 outlier: reassign 안 함 (기본), -1 유지

입력:
  {output_dir}/s2_embeddings.npy     : (N, D)
  {output_dir}/s2_meta_for_embed.csv : abstract 있는 행 (pmid 인덱스)
  {paths.input_pmid_csv}             : md5 hash 용
출력:
  {output_dir}/s3_model_d{n}_t{mts}_s{seed}_{md5}/topic_model/    : BERTopic 모델
  {output_dir}/s3_labels.csv                                       : pmid, topic_label
  {output_dir}/s3_metrics.csv                                      : 선택 모델의 지표
  {output_dir}/sweep/sweep_metrics.csv / sweep_line.png /
                     sweep_heatmap.png / sweep_report.md
"""

from __future__ import annotations

import hashlib
import os
import shutil
from collections import Counter
from pathlib import Path
from statistics import median_low

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..shared.fonts import setup_mpl


class SweepFailedError(Exception):
    """sweep 생존자 0명 (PLAN §12)."""


class IdentityReducer:
    """BERTopic 에 pre-computed UMAP 결과를 주입하기 위한 no-op UMAP 대체.

    BERTopic 내부에서 umap_model.fit_transform(embeddings) 호출 시 재학습 대신
    미리 계산된 축소본을 그대로 반환 → sweep 전체에서 UMAP 1회만 실제 계산.
    """

    def __init__(self, reduced: np.ndarray):
        self._reduced = reduced

    def fit(self, X, y=None):
        return self

    def fit_transform(self, X, y=None):
        return self._reduced

    def transform(self, X):
        return self._reduced


def run(cfg: dict) -> None:
    cluster_cfg = cfg["cluster"]
    paths = cfg["paths"]
    output_dir = Path(paths["output_dir"])
    sweep_dir = output_dir / "sweep"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    seed = cluster_cfg.get("seed", 42)
    umap_n = cluster_cfg.get("umap_n_components", 2)
    force_retrain = cluster_cfg.get("force_retrain", False)
    reassign_outliers = cluster_cfg.get("reassign_outliers", False)
    sweep_cfg = cluster_cfg.get("sweep", {}) or {}
    cutoff_cfg = sweep_cfg.get("cutoff", {}) or {}

    embeddings = np.load(output_dir / "s2_embeddings.npy")
    meta_df = pd.read_csv(output_dir / "s2_meta_for_embed.csv")
    docs = meta_df["abstract"].astype(str).tolist()
    N = len(docs)
    print(f"[s3] 입력: embeddings {embeddings.shape}, docs {N}")

    md5 = hashlib.md5(Path(paths["input_pmid_csv"]).read_bytes()).hexdigest()[:8]

    # 캐시 체크 (PLAN §11): 같은 (d, mts, seed, md5) 산출물이 있으면 skip
    selected_file = output_dir / "s3_selected_model.txt"
    if selected_file.exists() and not force_retrain:
        cached_name = selected_file.read_text(encoding="utf-8").strip()
        cache_dir = output_dir / cached_name
        labels_csv = output_dir / "s3_labels.csv"
        # 이름 파싱: s3_model_d{n}_t{mts}_s{seed}_{md5}
        expected_prefix = f"s3_model_d{umap_n}_"
        expected_suffix = f"_s{seed}_{md5}"
        if (cache_dir.exists() and labels_csv.exists()
                and cached_name.startswith(expected_prefix)
                and cached_name.endswith(expected_suffix)):
            print(f"[s3] 캐시 hit: {cached_name} — skip")
            return
        print(f"[s3] 캐시 불일치 (cached={cached_name}, expected ..._d{umap_n}_..._s{seed}_{md5}) — 재학습")

    grid, skip_sweep = _resolve_grid(cluster_cfg, sweep_cfg, N)
    print(f"[s3] grid: {grid}  (skip_sweep={skip_sweep})")

    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    import torch
    torch.set_default_device("cpu")
    from umap import UMAP

    print(f"[s3] UMAP fit (n_components={umap_n}, seed={seed})...")
    umap_model = UMAP(n_components=umap_n, random_state=seed)
    umap_embeddings = umap_model.fit_transform(embeddings)
    print(f"[s3] UMAP output: {umap_embeddings.shape}")

    sweep_results = []
    for i, mts in enumerate(grid, 1):
        print(f"\n[s3] ({i}/{len(grid)}) fit mts={mts} ...")
        model, topics = _train_one(docs, embeddings, umap_embeddings, mts, reassign_outliers)
        metrics = _measure_metrics(topics, umap_embeddings)
        passed, reasons = (True, []) if skip_sweep else _check_cutoff(metrics, cutoff_cfg)
        sweep_results.append({
            "mts": mts, "metrics": metrics, "passed": passed,
            "reasons": reasons, "model": model, "topics": topics,
        })
        status = "OK" if passed else "FAIL [" + "; ".join(reasons) + "]"
        print(f"[s3] mts={mts}: n_topics={metrics['n_topics']}, "
              f"sil={metrics['silhouette']:.3f}, imb={metrics['imbalance']:.1f}, "
              f"min_count={metrics['min_count']}, outlier={metrics['outlier_ratio']:.2%} → {status}")

    _save_sweep_artifacts(sweep_results, cutoff_cfg, sweep_dir, skip_sweep)

    survivors = [r["mts"] for r in sweep_results if r["passed"]]
    if not survivors:
        table = _build_diagnostic_table(sweep_results)
        raise SweepFailedError(f"생존자 0명. sweep_report.md 참고.\n\n{table}")

    selected_mts = grid[0] if skip_sweep else median_low(survivors)
    print(f"\n[s3] 선택: min_topic_size={selected_mts} "
          f"({'직행' if skip_sweep else f'생존자 {len(survivors)}개 중 median_low'})")

    selected = next(r for r in sweep_results if r["mts"] == selected_mts)

    cache_dir = output_dir / f"s3_model_d{umap_n}_t{selected_mts}_s{seed}_{md5}"
    if force_retrain and cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    model_path = cache_dir / "topic_model"
    selected["model"].save(
        str(model_path),
        serialization="safetensors",
        save_ctfidf=True,
    )
    (output_dir / "s3_selected_model.txt").write_text(cache_dir.name + "\n", encoding="utf-8")
    print(f"[s3] 모델 저장 → {cache_dir}")

    labels_df = pd.DataFrame({
        "pmid": meta_df["pmid"].values,
        "topic_label": selected["topics"],
    })
    labels_df.to_csv(output_dir / "s3_labels.csv", index=False, encoding="utf-8-sig")
    print(f"[s3] 라벨 → s3_labels.csv")

    m = selected["metrics"]
    pd.DataFrame([{
        "min_topic_size": selected_mts,
        "umap_n_components": umap_n,
        "seed": seed,
        "input_md5": md5,
        "n_topics": m["n_topics"],
        "silhouette": m["silhouette"],
        "imbalance": m["imbalance"],
        "min_count": m["min_count"],
        "outlier_ratio": m["outlier_ratio"],
    }]).to_csv(output_dir / "s3_metrics.csv", index=False)
    print(f"[s3] 지표 → s3_metrics.csv")


# ── 그리드 ─────────────────────────────────────────────────────

def _resolve_grid(cluster_cfg: dict, sweep_cfg: dict, N: int) -> tuple[list[int], bool]:
    """min_topic_size 설정 해석 → (grid, skip_sweep 여부)."""
    mts = cluster_cfg.get("min_topic_size", "auto")
    if isinstance(mts, int):
        return [mts], True
    if isinstance(mts, str) and mts.lower() != "auto":
        raise ValueError(f"min_topic_size 는 정수 또는 'auto': {mts!r}")

    user_grid = sweep_cfg.get("grid")
    if user_grid:
        return list(user_grid), False
    return _default_grid(N), False


def _default_grid(N: int) -> list[int]:
    """8값 기하급수 그리드. center = sqrt(N)/2 (index 4).

    v2 pilot (2026-04-21): 기존 5값 (공통비 r≈2) 에서 8값 (r≈1.4) 로 변경.
    10 부터 C 까지 5개 (0~4), C 이후 3개 (5~7) = 총 8값. 중앙값 근처를
    더 촘촘히 탐색해 도메인 sweet spot(예 N=5590 의 50 근처) 이 grid 에
    포함되도록 함. 자세한 배경은 Docs/v2_pilot_plan.md.
    """
    C = max(10, round(N**0.5 / 2))
    if C <= 10:
        return [10]
    r = (C / 10) ** (1 / 4)
    return [round(10 * r**i) for i in range(5)] + [round(C * r**i) for i in range(1, 4)]


# ── 단일 학습 ──────────────────────────────────────────────────

def _train_one(docs, embeddings, umap_reduced, mts, reassign_outliers):
    from bertopic import BERTopic
    from sklearn.feature_extraction.text import CountVectorizer

    vectorizer = CountVectorizer(stop_words="english")
    topic_model = BERTopic(
        umap_model=IdentityReducer(umap_reduced),
        vectorizer_model=vectorizer,
        min_topic_size=mts,
        verbose=False,
    )
    topics, _ = topic_model.fit_transform(docs, embeddings=embeddings)
    topics = list(topics)

    if reassign_outliers:
        new_topics = topic_model.reduce_outliers(docs, topics, strategy="c-tf-idf")
        topic_model.update_topics(docs, topics=new_topics, vectorizer_model=vectorizer)
        topics = list(new_topics)

    return topic_model, topics


# ── 지표 ──────────────────────────────────────────────────────

def _measure_metrics(topics: list[int], umap_embeddings: np.ndarray) -> dict:
    from sklearn.metrics import silhouette_score

    arr = np.array(topics)
    non_outlier_mask = arr != -1
    non_outlier_labels = arr[non_outlier_mask]
    n_topics = len(set(non_outlier_labels.tolist())) if non_outlier_mask.any() else 0

    sil = float("nan")
    if n_topics >= 2 and non_outlier_mask.sum() >= n_topics:
        try:
            sil = float(silhouette_score(umap_embeddings[non_outlier_mask], non_outlier_labels))
        except Exception:
            pass

    sizes = list(Counter(non_outlier_labels.tolist()).values())
    imbalance = (max(sizes) / min(sizes)) if sizes else float("nan")
    min_count = min(sizes) if sizes else 0
    outlier_ratio = float((~non_outlier_mask).sum() / len(arr))

    return {
        "n_topics": n_topics,
        "silhouette": sil,
        "imbalance": float(imbalance),
        "min_count": int(min_count),
        "outlier_ratio": outlier_ratio,
    }


# ── Cutoff (PLAN §12) ──────────────────────────────────────────

def _check_cutoff(metrics: dict, cutoff: dict) -> tuple[bool, list[str]]:
    reasons = []
    n_min = cutoff.get("n_topics_min", 4)
    n_max = cutoff.get("n_topics_max", 30)
    sil_min = cutoff.get("silhouette_min", 0.25)
    imb_max = cutoff.get("imbalance_max", 100)
    count_min = cutoff.get("min_count_in_topics", 25)

    if metrics["n_topics"] < n_min:
        reasons.append(f"n_topics<{n_min}")
    if metrics["n_topics"] > n_max:
        reasons.append(f"n_topics>{n_max}")
    if not (metrics["silhouette"] >= sil_min):  # NaN 도 탈락
        reasons.append(f"silhouette<{sil_min}")
    if metrics["imbalance"] >= imb_max:
        reasons.append(f"imbalance≥{imb_max}")
    if metrics["min_count"] < count_min:
        reasons.append(f"min_count<{count_min}")
    return len(reasons) == 0, reasons


# ── 산출물 ────────────────────────────────────────────────────

def _save_sweep_artifacts(results, cutoff, sweep_dir: Path, skip_sweep: bool):
    rows = []
    for r in results:
        m = r["metrics"]
        rows.append({
            "mts": r["mts"],
            "n_topics": m["n_topics"],
            "silhouette": round(m["silhouette"], 4),
            "imbalance": round(m["imbalance"], 2),
            "min_count": m["min_count"],
            "outlier_ratio": round(m["outlier_ratio"], 4),
            "passed": r["passed"],
            "reasons": "; ".join(r["reasons"]),
        })
    pd.DataFrame(rows).to_csv(sweep_dir / "sweep_metrics.csv", index=False)

    setup_mpl()
    _plot_sweep_line(results, cutoff, sweep_dir / "sweep_line.png")
    _plot_sweep_heatmap(results, sweep_dir / "sweep_heatmap.png")

    survivors = [r["mts"] for r in results if r["passed"]]
    lines = ["# Sweep Report\n"]
    lines.append(f"- 그리드: `{[r['mts'] for r in results]}`")
    if skip_sweep:
        lines.append(f"- 모드: **sweep 생략 (mts 단일값 직행)**")
    if survivors:
        sel = median_low(survivors)
        lines.append(f"- 생존자: `{survivors}`")
        lines.append(f"- **선택: min_topic_size = {sel}** ({'직행' if skip_sweep else 'median_low'})")
    else:
        lines.append("- 생존자: **없음 — 파이프라인 중단**")
    lines.append("")
    lines.append("## 전체 지표")
    lines.append("")
    lines.append(_build_diagnostic_table(results))
    (sweep_dir / "sweep_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[s3] sweep 산출물 → {sweep_dir}")


def _plot_sweep_line(results, cutoff, out_path):
    x = [r["mts"] for r in results]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, key, title, ref in [
        (axes[0, 0], "n_topics", "n_topics",
            [cutoff.get("n_topics_min", 4), cutoff.get("n_topics_max", 30)]),
        (axes[0, 1], "silhouette", "silhouette", [cutoff.get("silhouette_min", 0.25)]),
        (axes[1, 0], "imbalance", "imbalance (max/min)", [cutoff.get("imbalance_max", 100)]),
        (axes[1, 1], "min_count", "min_count", [cutoff.get("min_count_in_topics", 25)]),
    ]:
        y = [r["metrics"][key] for r in results]
        ax.plot(x, y, "o-", markersize=6)
        for rline in ref:
            ax.axhline(rline, ls="--", c="red", alpha=0.4)
        for xi, yi, r in zip(x, y, results):
            if r["passed"]:
                ax.scatter(xi, yi, s=120, marker="o", facecolors="none", edgecolors="green", linewidths=2)
        ax.set_title(title)
        ax.set_xlabel("min_topic_size")
        ax.grid(alpha=0.3)
    fig.suptitle("Sweep metrics (초록 테두리 = 생존자, 빨간 점선 = cutoff)", y=1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _plot_sweep_heatmap(results, out_path):
    metric_names = ["n_topics", "silhouette", "imbalance", "min_count", "outlier_ratio"]
    arr = np.array([[r["metrics"][k] for k in metric_names] for r in results], dtype=float)
    denom = np.nanmax(arr, axis=0) - np.nanmin(arr, axis=0)
    denom[denom == 0] = 1
    norm = (arr - np.nanmin(arr, axis=0)) / denom

    fig, ax = plt.subplots(figsize=(8, 2 + len(results) * 0.4))
    im = ax.imshow(norm, aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(metric_names)))
    ax.set_xticklabels(metric_names, rotation=20)
    ax.set_yticks(range(len(results)))
    ax.set_yticklabels([str(r["mts"]) for r in results])
    ax.set_ylabel("min_topic_size")
    for i, r in enumerate(results):
        for j, k in enumerate(metric_names):
            v = r["metrics"][k]
            txt = f"{v:.2f}" if isinstance(v, float) and not np.isnan(v) else str(v)
            ax.text(j, i, txt, ha="center", va="center", color="w", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _build_diagnostic_table(results) -> str:
    header = "| mts | n_topics | silhouette | imbalance | min_count | outlier% | status |"
    sep = "|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for r in results:
        m = r["metrics"]
        status = "✅ pass" if r["passed"] else "❌ " + ", ".join(r["reasons"])
        lines.append(
            f"| {r['mts']} | {m['n_topics']} | {m['silhouette']:.3f} | "
            f"{m['imbalance']:.1f} | {m['min_count']} | "
            f"{m['outlier_ratio']*100:.1f}% | {status} |"
        )
    return "\n".join(lines)
