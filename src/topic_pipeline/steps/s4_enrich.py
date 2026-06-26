"""steps/s4_enrich.py — 토픽 10개 4열 키워드 비교표 (c-TF-IDF / KeyBERT / Author KW / MeSH).

PLAN-v2 §8 Phase 3a. 원본: 03_Cluster-to-Topic/enrich_topics_v2.py.

입력 (cfg["enrich"]):
  topic_model_dir : BERTopic 모델 디렉토리
  labeled_csv     : pmid, abstract_clean, topic_label 을 가진 CSV
  keywords_csv    : pmid, author_keywords, mesh_terms_v2 을 가진 CSV
출력:
  {paths.output_dir}/s4_keywords_comparison.csv
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from ..shared.convention import load_labeled_convention, read_selected_model_dir, resolve_embed_model

TOP_N = 10


def run(cfg: dict) -> None:
    enrich_cfg = cfg.get("enrich", {}) or {}
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    from ..shared.device import setup_torch

    setup_torch(cfg)

    embed_model_name = resolve_embed_model(cfg)

    if enrich_cfg.get("topic_model_dir"):
        # 명시적 override (Phase 3a 테스트 스타일)
        model_dir = Path(enrich_cfg["topic_model_dir"])
        labeled_csv = Path(enrich_cfg["labeled_csv"])
        keywords_csv = Path(enrich_cfg["keywords_csv"])
        topic_model, docs, labeled_df, kw_df = _load_all_explicit(
            model_dir, labeled_csv, keywords_csv, embed_model_name
        )
    else:
        # Convention (Phase 6 end-to-end)
        topic_model, docs, labeled_df, kw_df = _load_all_convention(
            output_dir, embed_model_name
        )

    topic_model = _apply_keybert(topic_model, docs)
    meta_keywords = _aggregate_meta_keywords(labeled_df, kw_df)

    out_path = output_dir / "s4_keywords_comparison.csv"
    _build_comparison_table(topic_model, meta_keywords, out_path)


def _load_bertopic(model_dir: Path, embed_model_name: str):
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer

    embed_model = SentenceTransformer(embed_model_name)
    return BERTopic.load(str(model_dir), embedding_model=embed_model)


def _load_all_explicit(model_dir, labeled_csv, keywords_csv, embed_model_name):
    """Phase 3a 테스트 — labeled_csv/keywords_csv 명시 + abstract_clean 사용."""
    print("[1] 로드 (explicit)...")
    topic_model = _load_bertopic(model_dir, embed_model_name)
    labeled_df = pd.read_csv(labeled_csv)
    kw_df = pd.read_csv(keywords_csv)

    docs = labeled_df["abstract_clean"].fillna("").tolist()
    n_topics = len(set(labeled_df["topic_label"]) - {-1})
    print(f"  모델: {n_topics} topics, 문서: {len(docs)}")

    return topic_model, docs, labeled_df, kw_df


def _load_all_convention(output_dir: Path, embed_model_name: str):
    """Phase 6 — s2_meta_for_embed + s3_labels merge + s3 selected model 사용."""
    print("[1] 로드 (convention)...")
    model_dir = read_selected_model_dir(output_dir)
    topic_model = _load_bertopic(model_dir, embed_model_name)

    merged = load_labeled_convention(output_dir)
    # 내부 로직이 abstract_clean / mesh_terms_v2 컬럼을 기대 → rename
    labeled_df = merged.rename(columns={
        "abstract": "abstract_clean",
        "mesh_terms": "mesh_terms_v2",
    })
    kw_df = labeled_df  # 동일 df — author_keywords + mesh_terms_v2 둘 다 포함

    docs = labeled_df["abstract_clean"].fillna("").tolist()
    n_topics = len(set(labeled_df["topic_label"]) - {-1})
    print(f"  모델: {n_topics} topics, 문서: {len(docs)}")

    return topic_model, docs, labeled_df, kw_df


def _apply_keybert(topic_model, docs):
    from bertopic.representation import KeyBERTInspired
    from sklearn.feature_extraction.text import CountVectorizer

    print("[2] KeyBERT 적용 중...")

    original_ctfidf = {}
    for tid in topic_model.get_topic_info()["Topic"]:
        if tid == -1:
            continue
        original_ctfidf[tid] = topic_model.get_topic(tid)

    topic_model.update_topics(
        docs,
        representation_model={"KeyBERT": KeyBERTInspired()},
        vectorizer_model=CountVectorizer(stop_words="english", ngram_range=(1, 3)),
    )

    topic_model.topic_aspects_["c-TF-IDF"] = original_ctfidf
    print(f"  topic_aspects_: {list(topic_model.topic_aspects_.keys())}")
    return topic_model


def _aggregate_meta_keywords(labeled_df: pd.DataFrame, kw_df: pd.DataFrame, top_n: int = TOP_N):
    print("[3] Author Keywords / MeSH 빈도 집계 중...")
    merged = labeled_df[["pmid", "topic_label"]].merge(
        kw_df[["pmid", "author_keywords", "mesh_terms_v2"]],
        on="pmid",
        how="left",
    )

    result: dict[int, dict] = {}
    for topic_id in sorted(merged["topic_label"].unique()):
        if topic_id == -1:
            continue
        subset = merged[merged["topic_label"] == topic_id]

        akw_counter: Counter = Counter()
        for kw_str in subset["author_keywords"].dropna():
            for kw in kw_str.split("; "):
                kw = kw.strip().lower()
                if kw:
                    akw_counter[kw] += 1

        mesh_counter: Counter = Counter()
        for m_str in subset["mesh_terms_v2"].dropna():
            for m in m_str.split("; "):
                m = m.strip().lower()
                if m:
                    mesh_counter[m] += 1

        result[int(topic_id)] = {
            "author_kw": akw_counter.most_common(top_n),
            "mesh": mesh_counter.most_common(top_n),
        }

    return result


def _build_comparison_table(topic_model, meta_keywords: dict, out_path: Path, top_n: int = TOP_N) -> None:
    print("[4] 비교표 생성 중...")
    rows = []
    topic_info = topic_model.get_topic_info()

    for _, row in topic_info.iterrows():
        tid = row["Topic"]
        if tid == -1:
            continue

        main_words = topic_model.topic_aspects_.get("c-TF-IDF", {}).get(tid, [])
        main_str = "; ".join([w for w, _ in main_words[:top_n]])

        kb_words = topic_model.topic_aspects_.get("KeyBERT", {}).get(tid, [])
        kb_str = "; ".join([w for w, _ in kb_words[:top_n]])

        akw_top = meta_keywords.get(tid, {}).get("author_kw", [])
        akw_str = "; ".join([f"{kw}({cnt})" for kw, cnt in akw_top])

        mesh_top = meta_keywords.get(tid, {}).get("mesh", [])
        mesh_str = "; ".join([f"{m}({cnt})" for m, cnt in mesh_top])

        rows.append(
            {
                "topic": tid,
                "doc_count": row["Count"],
                "c-TF-IDF": main_str,
                "KeyBERT": kb_str,
                "Author_Keywords_freq": akw_str,
                "MeSH_freq": mesh_str,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 → {out_path}")
