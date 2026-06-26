"""steps/s5_label_relevance.py — s5_labels.csv 를 relevance_criterion 기준으로 rank.

NEXT_PLAN §C (KNOWN §3 해결). s5_label 의 2번째 LLM 호출을 별도 step 으로 분리.

입력:
  {paths.output_dir}/s5_labels.csv                (s5_label 산출물)
출력:
  {paths.output_dir}/s5_label-relevance.md              (parse_relevance_order 호환 md)

config:
  label.model                — Claude 모델 (s5_label 과 공용)
  label.relevance_criterion  — rank 기준 문자열
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..shared.llm import generate
from ..shared.relevance import parse_relevance_table


def run(cfg: dict) -> None:
    output_dir = Path(cfg["paths"]["output_dir"])
    labels_path = output_dir / "s5_labels.csv"
    out_path = output_dir / "s5_label-relevance.md"

    model = (cfg.get("label") or {}).get("model", "")
    criterion = cfg["label"]["relevance_criterion"]
    provider = (cfg.get("label") or {}).get("provider", "claude")

    labels_df = pd.read_csv(labels_path)
    print(f"[Data] {len(labels_df)} topics 로드 ({labels_path})")

    if provider == "keywords":
        print("[s5] provider=keywords — 문서수 내림차순 랭킹 (LLM 없음)")
        rank_md = _keyword_rank_md(labels_df, criterion)
    else:
        rank_md = _rank_by_relevance(labels_df, criterion, cfg)
    out_path.write_text(rank_md + "\n", encoding="utf-8")
    print(f"저장 → {out_path}")
    _write_topic_order_json(out_path, output_dir, criterion, model)


def _build_rank_prompt(labels_df: pd.DataFrame, criterion: str) -> str:
    topic_blocks = []
    for _, r in labels_df.iterrows():
        block = (
            f"Topic {int(r['topic'])} ({int(r['doc_count'])} docs):\n"
            f"  label_en: {r.get('label_en', '')}\n"
            f"  label_kr: {r.get('label_kr', '')}\n"
            f"  설명: {r.get('description', '')}"
        )
        topic_blocks.append(block)
    topics_text = "\n\n".join(topic_blocks)
    n = len(labels_df)

    return f"""아래는 문서를 BERTopic 클러스터링한 결과의 {n}개 토픽 라벨입니다.

{topics_text}

이 {n}개 토픽 전체를 **{criterion}** 관련도 순으로 정렬하여 아래 형식의 마크다운 문서를 반환해주세요.

---출력 형식 (아래 본문만 반환, 주변 설명·코드펜스 금지)---

# 토픽별 {criterion} 관련도 분석

{n}개 토픽을 **{criterion}** 관련도 순으로 정리한 결과입니다.

## 관련도 순위

| 순위 | Topic | Label | 문서수 | 관련 근거 |
|---:|:---:|---|---:|---|
| 1 | 5 | <label_kr> | <doc_count> | <한줄 근거> |
| 2 | 4 | <label_kr> | <doc_count> | <한줄 근거> |
...
| {n} | 0 | <label_kr> | <doc_count> | <한줄 근거> |

## 요약

- **직접 관련 (1~a위)**: ...
- **간접 관련 (a+1~b위)**: ...
- **낮은 관련도 (b+1~{n}위)**: ...

---규칙---
1. rank 1~{n} 연속, 중복/생략 없음
2. **Topic 컬럼에는 topic 번호 정수만 (예: `5`). "Topic 5" 처럼 접두사 붙이지 말 것** — 이 값은 정규식 `\\d+` 로 파싱됨
3. 문서수는 주어진 doc_count 정수 그대로
4. Label 컬럼은 label_kr 사용
5. 관련 근거는 한국어 15~40자, 판단 이유 핵심만
6. 요약 그룹 경계 (a, b) 는 LLM 판단에 맡김
"""


def _rank_by_relevance(labels_df: pd.DataFrame, criterion: str, cfg: dict) -> str:
    prompt = _build_rank_prompt(labels_df, criterion)
    print(f"[LLM] relevance rank 호출 (criterion: {criterion})")
    return generate(prompt, cfg).strip()


def _keyword_rank_md(labels_df: pd.DataFrame, criterion: str) -> str:
    """LLM 없이 문서수 내림차순으로 랭킹 md 생성 (provider=keywords).

    Topic 컬럼은 정수만(invariant#3) — parse_relevance_order/table 와 동일 포맷 유지.
    """
    df = labels_df.sort_values("doc_count", ascending=False).reset_index(drop=True)
    lines = [
        f"# 토픽별 {criterion} 관련도 (키워드 기반)",
        "",
        "LLM 없이 문서수 내림차순으로 정렬했습니다 (provider=keywords).",
        "",
        "## 관련도 순위",
        "",
        "| 순위 | Topic | Label | 문서수 | 관련 근거 |",
        "|---:|:---:|---|---:|---|",
    ]
    for i, r in df.iterrows():
        lines.append(
            f"| {i + 1} | {int(r['topic'])} | {r.get('label_kr', '')} | {int(r['doc_count'])} | 문서수 순 |"
        )
    return "\n".join(lines)


def _write_topic_order_json(md_path: Path, output_dir: Path, criterion: str, model: str) -> None:
    """방금 쓴 md 를 재파싱해 구조화 JSON(s5_topic_order.json) 도 emit.

    md 가 단일 소스(LLM 이 JSON 을 직접 만들지 않음) → 정수 Topic 컬럼/표 포맷(invariant#3) 유지.
    외부/API 소비자용 추가 산출물.
    """
    rows = parse_relevance_table(md_path)
    payload = {
        "criterion": criterion,
        "model": model,
        "generated_from": md_path.name,
        "topics": rows,
    }
    json_path = output_dir / "s5_topic_order.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 → {json_path} ({len(rows)} topics)")
