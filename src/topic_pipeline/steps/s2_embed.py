"""steps/s2_embed.py — SPubMedBERT 임베딩 + 캐시.

PLAN-v2 §8 Phase 5a. 원본: week_7/wk7_Transformer/33_TopicModeling_v3-TopicNumOptimAndUmapD5/
topicModeling_v3-d5.py::get_embeddings (L97-116).

입력:
  {output_dir}/s1_meta.csv  — abstract 컬럼
출력:
  {output_dir}/s2_embeddings.npy  — (N, 768) float32
  {output_dir}/s2_meta_for_embed.csv  — abstract 있는 행만 필터링한 meta (pmid 인덱스 보존)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..shared.convention import DEFAULT_EMBED_MODEL, resolve_embed_model


def run(cfg: dict) -> None:
    embed_cfg = cfg.get("embed", {})
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    meta_csv = output_dir / "s1_meta.csv"
    cache_npy = output_dir / "s2_embeddings.npy"
    filtered_meta_csv = output_dir / "s2_meta_for_embed.csv"

    model_name = resolve_embed_model(cfg)
    use_cache = embed_cfg.get("cache", True)
    if model_name != DEFAULT_EMBED_MODEL and use_cache and cache_npy.exists():
        print(f"[s2] ⚠️ 비기본 embed 모델({model_name})인데 기존 임베딩 캐시 존재 — "
              f"모델을 바꿨다면 s2_embeddings.npy 삭제 또는 embed.cache=false 권장 (캐시는 shape 만 비교)")

    df = pd.read_csv(meta_csv)
    print(f"[s2] {len(df)} 행 로드 ← {meta_csv}")

    # abstract 비어있는 행 drop (S3 클러스터 라벨 정합성 위해 meta 재저장)
    df = df.dropna(subset=["abstract"]).reset_index(drop=True)
    df = df[df["abstract"].astype(str).str.strip() != ""].reset_index(drop=True)
    print(f"[s2] abstract 비어있는 행 제거 후 {len(df)} 행")
    df.to_csv(filtered_meta_csv, index=False, encoding="utf-8-sig")

    docs = df["abstract"].astype(str).tolist()

    if use_cache and cache_npy.exists():
        cached = np.load(cache_npy)
        if cached.shape[0] == len(docs):
            print(f"[s2] 캐시 로드: {cache_npy.name} {cached.shape}")
            return
        print(f"[s2] 캐시 shape 불일치 ({cached.shape} vs docs={len(docs)}) — 재계산")

    from ..shared.device import setup_torch

    device = setup_torch(cfg)

    from sentence_transformers import SentenceTransformer

    batch_size = cfg.get("compute", {}).get("embed_batch_size", 16)
    print(f"[s2] 모델 로드: {model_name} (device={device})")
    model = SentenceTransformer(model_name, device=device)
    print(f"[s2] {len(docs)}편 인코딩 시작 (batch_size={batch_size}, device={device})...")
    embeddings = model.encode(docs, show_progress_bar=True, batch_size=batch_size, device=device)
    np.save(cache_npy, embeddings)
    print(f"[s2] 저장 → {cache_npy} {embeddings.shape}")
