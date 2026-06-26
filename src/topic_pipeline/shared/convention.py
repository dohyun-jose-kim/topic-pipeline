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
