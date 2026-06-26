"""s5_label-relevance.md 파싱 — rank 순 topic_id 리스트 / 표 전체 dict.

PLAN-v2 §8 Phase 2b. 회귀 검증은 tests/test_relevance.py (fixtures/sample_relevance.md).
"""

from __future__ import annotations

import re
from pathlib import Path


def parse_relevance_order(md_path: Path) -> list[int]:
    """관련도 순위 표의 | rank | topic | 쌍을 뽑아 rank 순 topic_id 리스트로 반환."""
    text = Path(md_path).read_text(encoding="utf-8")
    rows = re.findall(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|", text)
    return [int(topic) for _, topic in sorted(rows, key=lambda x: int(x[0]))]


_TABLE_ROW = re.compile(
    r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\|\s*([\d,]+)\s*\|\s*(.*?)\s*\|"
)


def parse_relevance_table(md_path: Path) -> list[dict]:
    """관련도 md 파일 → dict 리스트 (parse_relevance_table_text 의 파일경로 버전)."""
    return parse_relevance_table_text(Path(md_path).read_text(encoding="utf-8"))


def parse_relevance_table_text(text: str) -> list[dict]:
    """관련도 md 표 텍스트의 각 행 → dict 리스트 (parse_relevance_order 의 superset).

    | rank | topic | label | doc_count | rationale | 행을 파싱(doc_count 천단위 콤마 허용), rank 순 정렬.
    Topic 컬럼은 정수(invariant#3). s5_topic_order.json 과 s7 §6 표가 **이 단일 파서**를 공유한다.
    """
    rows = []
    for m in _TABLE_ROW.finditer(text):
        rank, topic, label, doc_count, rationale = m.groups()
        rows.append({
            "rank": int(rank),
            "topic": int(topic),
            "label": label.strip(),
            "doc_count": int(doc_count.replace(",", "")),
            "rationale": rationale.strip(),
        })
    rows.sort(key=lambda r: r["rank"])
    return rows
