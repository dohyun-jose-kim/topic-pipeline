"""Convention 경로로 이전 step 산출물 로드 헬퍼.

Phase 6 end-to-end 시 각 step 이 explicit override 없이 `{output_dir}` 안의
convention 파일을 찾아 쓰도록 공통화.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_labeled_convention(output_dir: Path) -> pd.DataFrame:
    """s2_meta_for_embed.csv + s3_labels.csv 를 pmid 로 merge.

    반환 df 컬럼: pmid, year, abstract, author_keywords, mesh_terms, topic_label
    """
    s2_meta = pd.read_csv(output_dir / "s2_meta_for_embed.csv")
    s3_labels = pd.read_csv(output_dir / "s3_labels.csv")
    return s2_meta.merge(s3_labels, on="pmid", how="inner")


def read_selected_model_dir(output_dir: Path) -> Path:
    """s3_selected_model.txt 에 기록된 캐시 디렉토리 반환."""
    txt = (output_dir / "s3_selected_model.txt").read_text(encoding="utf-8").strip()
    return output_dir / txt / "topic_model"


def relevance_md_path(output_dir) -> Path:
    """s5_label-relevance step 산출물의 convention 경로 (run 디렉토리 기준).

    config 의 relevance_md 가 null 일 때 s6/s7 이 이 경로로 fallback.
    """
    return Path(output_dir) / "s5_label-relevance.md"


# embed 모델 기본값 단일 소스 (s2_embed / s4_enrich 중복 리터럴 통합).
DEFAULT_EMBED_MODEL = "pritamdeka/S-PubMedBert-MS-MARCO"


def resolve_embed_model(cfg) -> str:
    """embed.model_name (없으면 생의학 기본 모델 DEFAULT_EMBED_MODEL)."""
    return (cfg.get("embed") or {}).get("model_name") or DEFAULT_EMBED_MODEL


def resolve_stop_words(cfg):
    """embed.stop_words: 'english'(기본, sklearn 내장) | None(제거 안 함, CJK/다국어) | [단어,...].

    CountVectorizer 가 셋 다 그대로 받는다. s3/s4 의 하드코딩 'english' 통합.
    """
    return (cfg.get("embed") or {}).get("stop_words", "english")


def resolve_domain(cfg) -> str:
    """LLM 프롬프트용 도메인 서술어: label.domain → label.relevance_criterion → project.주제 → '문서'."""
    label = cfg.get("label") or {}
    project = cfg.get("project") or {}
    return label.get("domain") or label.get("relevance_criterion") or project.get("주제") or "문서"
