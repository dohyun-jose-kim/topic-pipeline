"""NCBI efetch 래퍼 (재시도 + rate limiting).

PLAN-v2 §8 Phase 2d. 원본: 01_DataFetch/fetch_author_keywords.py:38-124 의 네트워크 계층.
파싱(KeywordList / MeshHeadingList / Abstract 등)은 소비자(s1_fetch) 책임.
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from typing import Iterator

import requests

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedFetchError(Exception):
    """efetch 재시도 소진 후에도 실패 (PLAN-v2 §15-3)."""


def _request_with_retry(
    params: dict,
    *,
    max_retries: int,
    backoff: float,
    interval: float,
) -> requests.Response:
    """POST efetch with exponential backoff. 실패 시 PubMedFetchError."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            time.sleep(interval)
            resp = requests.post(EFETCH_URL, data=params, timeout=60)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_exc = e
            wait = backoff * (2**attempt)
            print(f"  [retry {attempt+1}/{max_retries}] {e} — {wait}s 대기")
            time.sleep(wait)
    raise PubMedFetchError(f"efetch 재시도 {max_retries}회 소진: {last_exc}")


def efetch_articles(
    pmids: list[int | str],
    *,
    api_key: str | None = None,
    email: str = "your_email@example.com",
    batch_size: int = 200,
    max_retries: int = 3,
) -> Iterator[ET.Element]:
    """PMID 리스트 → PubmedArticle element iterator (배치별 XML 파싱).

    NCBI_API_KEY 환경변수를 기본값으로 사용 (api_key 인자 명시 시 override).
    """
    key = api_key if api_key is not None else os.environ.get("NCBI_API_KEY", "")
    interval = 0.1 if key else 0.34  # rate limit: 10/s (key) vs 3/s
    backoff = 2.0

    for start in range(0, len(pmids), batch_size):
        batch = pmids[start : start + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(str(p) for p in batch),
            "rettype": "xml",
            "retmode": "xml",
            "email": email,
        }
        if key:
            params["api_key"] = key

        resp = _request_with_retry(
            params, max_retries=max_retries, backoff=backoff, interval=interval
        )

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            raise PubMedFetchError(f"XML 파싱 실패 (batch start={start}): {e}") from e

        yield from root.findall("PubmedArticle")


def _smoke_test() -> None:
    """10 PMID 네트워크 호출 검증 (PLAN-v2 §8 Phase 2d)."""
    test_pmids = [
        41866097, 41863067, 41861927, 41861743, 41861663,
        41857126, 41852833, 41847857, 41833804, 41833395,
    ]
    articles = list(efetch_articles(test_pmids))
    assert len(articles) >= 9, f"expected >=9 articles, got {len(articles)}"
    # 각 article 이 PMID 를 가진 MedlineCitation 을 포함하는지
    pmids_got = [a.findtext("MedlineCitation/PMID", "") for a in articles]
    assert all(p.isdigit() for p in pmids_got), f"non-digit PMID in response: {pmids_got}"
    print(f"[OK] efetch 10 PMID 호출 통과: {len(articles)}개 article, PMIDs={pmids_got[:3]}…")


if __name__ == "__main__":
    _smoke_test()
