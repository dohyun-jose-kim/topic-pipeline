"""topic_physiological_relevance.md → rank 순 topic_id 리스트.

PLAN-v2 §8 Phase 2b. 원본: 06_Clustered_Topic_Assay_v2/clustered_topic_report.py:76-79.
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
    """관련도 md 표의 각 행 → dict 리스트 (parse_relevance_order 의 superset).

    | rank | topic | label | doc_count | rationale | 행을 파싱, rank 순 정렬.
    Topic 컬럼은 정수(invariant#3) — 동일 표를 구조화할 뿐, md 가 단일 소스로 유지된다.
    """
    text = Path(md_path).read_text(encoding="utf-8")
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


def _smoke_test() -> None:
    """기존 v2.4 md 파싱 기대값 검증 (PLAN-v2 §8 Phase 2b)."""
    md = Path(
        "/Users/inco/01_Projects/00_Tasks/ifc_ojt_dh.kim/week_f"
        "/04_Topic_LLM-Assay/results/topic_physiological_relevance.md"
    )
    expected = [5, 4, 1, 2, 7, 9, 8, 6, 3, 0]
    got = parse_relevance_order(md)
    assert got == expected, f"mismatch: expected {expected}, got {got}"
    print(f"[OK] parse_relevance_order 검증 통과: {got}")


if __name__ == "__main__":
    _smoke_test()
