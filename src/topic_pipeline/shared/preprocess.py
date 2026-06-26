"""abstract 텍스트 정제 (M6 T1-1).

KNOWN_LIMITATION #1: v2.4 참조 모델은 abstract_clean(week_4 tokenize_pipeline) 으로 학습됨.
원본 정제 스크립트는 이 트리에 **부재(verified absent)** — 따라서 이는 문서화된 transform 의
**근사 재구성**이다. "v2.4 parity" 는 경험적 A/B 로 검증해야 하며 가정하지 않는다.
순수 stdlib `re` 만 사용(heavy NLP 미도입 — speculative).
"""

from __future__ import annotations

import re

_URL = re.compile(r"https?://\S+|www\.\S+")
_DOI = re.compile(r"\b10\.\d{4,}/\S+")
_BRACKET_CITE = re.compile(r"\[\s*\d+(?:\s*[-,]\s*\d+)*\s*\]")  # [12], [3-5], [1, 2]
_NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
_WS = re.compile(r"\s+")


def clean_abstract(text: str) -> str:
    """URL/DOI/대괄호 인용/독립 숫자 제거 + 소문자화 + 공백 정규화 (근사)."""
    if not isinstance(text, str):
        return ""
    t = _URL.sub(" ", text)
    t = _DOI.sub(" ", t)
    t = _BRACKET_CITE.sub(" ", t)
    t = _NUM.sub(" ", t)
    t = t.lower()
    return _WS.sub(" ", t).strip()


def clean_series(s):
    """pandas Series 에 clean_abstract 벡터 적용 (NaN → '')."""
    return s.fillna("").astype(str).map(clean_abstract)


def _smoke_test() -> None:
    dirty = "Study of X (see https://x.org and [12]) showed 42% increase. DOI 10.1234/abc"
    out = clean_abstract(dirty)
    assert "http" not in out and "[12]" not in out and "42" not in out
    assert out == out.lower()
    print(f"[OK] clean_abstract → {out!r}")


if __name__ == "__main__":
    _smoke_test()
