"""steps/s5_label.py — Claude API 로 토픽 라벨(en/kr) + 설명 생성.

PLAN-v2 §8 Phase 3b. 원본: 04_Topic_LLM-Assay/label_topics_llm.py.
relevance rank md 자동 생성은 별도 step `s5_label_relevance.py` (NEXT_PLAN §C).

입력:
  {paths.output_dir}/s4_keywords_comparison.csv   (Phase 3a 산출물)
출력:
  {paths.output_dir}/s5_labels.csv
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from ..shared.convention import resolve_domain
from ..shared.llm import generate


def run(cfg: dict) -> None:
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    in_path = output_dir / "s4_keywords_comparison.csv"
    out_path = output_dir / "s5_labels.csv"

    df = pd.read_csv(in_path)
    print(f"[Data] {len(df)} topics 로드 ({in_path})")

    provider = (cfg.get("label") or {}).get("provider", "claude")
    if provider == "keywords":
        print("[s5] provider=keywords — LLM 없이 키워드 상위어로 라벨 생성")
        labels = _keyword_labels(df)
    else:
        labels = _parse_json_labels(generate(_build_prompt(df, resolve_domain(cfg)), cfg))

    labels_df = pd.DataFrame(labels)
    merged = df.merge(labels_df, on="topic", how="left")
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 → {out_path}")

    for _, r in merged.iterrows():
        print(f"\n--- Topic {int(r['topic'])} ({int(r['doc_count'])} docs) ---")
        print(f"  EN: {r.get('label_en', '')}")
        print(f"  KR: {r.get('label_kr', '')}")
        print(f"  설명: {r.get('description', '')}")


def _build_prompt(df: pd.DataFrame, domain: str) -> str:
    topic_blocks = []
    for _, r in df.iterrows():
        block = (
            f"Topic {int(r['topic'])} ({int(r['doc_count'])} docs):\n"
            f"  c-TF-IDF keywords: {r['c-TF-IDF']}\n"
            f"  KeyBERT keywords: {r['KeyBERT']}\n"
            f"  Author Keywords (freq): {r['Author_Keywords_freq']}\n"
            f"  MeSH Terms (freq): {r['MeSH_freq']}"
        )
        topic_blocks.append(block)

    topics_text = "\n\n".join(topic_blocks)
    total = int(df["doc_count"].sum())
    n = len(df)

    return f"""아래는 {domain} 관련 문서 {total:,}편을 BERTopic으로 클러스터링한 {n}개 토픽입니다.
각 토픽에 대해 4가지 관점의 키워드가 주어집니다:
- c-TF-IDF: 토픽 내 빈도 기반 핵심어
- KeyBERT: 임베딩 유사도 기반 핵심어
- Author Keywords: 저자가 직접 명시한 키워드 (빈도 포함)
- MeSH Terms: NLM이 부여한 통제어휘 (빈도 포함)

{topics_text}

각 토픽에 대해 다음을 JSON 배열로 출력해주세요:
[
  {{
    "topic": 0,
    "label_en": "영어 한줄 라벨 (5단어 이내)",
    "label_kr": "한국어 한줄 라벨",
    "description": "이 토픽이 다루는 연구 주제를 2-3문장으로 설명 (한국어)"
  }},
  ...
]

JSON만 출력하세요. 다른 텍스트 없이."""


def _parse_json_labels(text: str) -> list[dict]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"JSON 파싱 실패. 원본 응답:\n{text}")


def _top_keywords(row) -> list[str]:
    """c-TF-IDF(없으면 KeyBERT) 상위어 리스트 ('; ' 구분 파싱)."""
    for col in ("c-TF-IDF", "KeyBERT"):
        val = str(row.get(col, "") or "").strip()
        if val and val.lower() != "nan":
            return [k.strip() for k in val.split(";") if k.strip()]
    return []


def _keyword_labels(df: pd.DataFrame) -> list[dict]:
    """LLM 없이 키워드 상위어로 라벨 생성 (provider=keywords; 무키·오프라인).

    label_en/kr = 상위 3개 키워드, description = 상위 6개. s5_labels.csv 스키마는 동일.
    """
    labels = []
    for _, r in df.iterrows():
        kws = _top_keywords(r)
        label = ", ".join(kws[:3]) if kws else f"Topic {int(r['topic'])}"
        labels.append({
            "topic": int(r["topic"]),
            "label_en": label,
            "label_kr": label,
            "description": ("주요 키워드: " + ", ".join(kws[:6])) if kws else "",
        })
    return labels
