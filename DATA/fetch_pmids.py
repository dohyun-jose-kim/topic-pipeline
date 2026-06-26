"""e2eTEST/fetch_pmids.py — PubMed 쿼리 → PMID 리스트 CSV.

원본: week_4/Task1/Task1-v3/01_fetch/collect_pubmed.py (ESearch+EFetch full records).
변형 목적: 90_CLI 파이프라인의 입력 포맷 (단일 컬럼 `pmid`) 생성.
  - ESearch 만 사용 (EFetch 는 s1_fetch.py 가 재수행)
  - 쿼리를 CLI 인자 (--query) 로 주입
  - 대용량 대응 retmax 10000 chunk 페이지네이션

사용법:
    python fetch_pmids.py --query "..." --output pmids.csv
    python fetch_pmids.py --query "..." --count-only
    python fetch_pmids.py --query "..." --limit 1000  # 테스트용 상한

환경변수:
    NCBI_API_KEY (선택)  — 설정 시 10 req/sec, 없으면 3 req/sec
    NCBI_EMAIL  (권장)   — Entrez 예의상 이메일
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
import requests

NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")
EMAIL = os.environ.get("NCBI_EMAIL", "your_email@example.com")
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

REQUEST_INTERVAL = 0.1 if NCBI_API_KEY else 0.34
RETMAX = 10000
MAX_RETRIES = 3


def _post(url: str, params: dict) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(REQUEST_INTERVAL)
            resp = requests.post(url, data=params, timeout=60)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{MAX_RETRIES}] {e} — {wait}s 대기",
                  file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("max retries exceeded")


def esearch_count(query: str) -> int:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": 0,
        "email": EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    resp = _post(ESEARCH_URL, params)
    root = ET.fromstring(resp.text)
    return int(root.findtext("Count", "0"))


def esearch_all_pmids(query: str, total: int, limit: int | None = None) -> list[int]:
    target = min(total, limit) if limit else total
    pmids: list[int] = []
    for start in range(0, target, RETMAX):
        batch_max = min(RETMAX, target - start)
        params = {
            "db": "pubmed",
            "term": query,
            "retstart": start,
            "retmax": batch_max,
            "email": EMAIL,
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY
        print(f"  ESearch {start+1:,}–{start+batch_max:,} / {target:,}")
        resp = _post(ESEARCH_URL, params)
        root = ET.fromstring(resp.text)
        for id_elem in root.findall("IdList/Id"):
            pmids.append(int(id_elem.text))
    return pmids


def main() -> int:
    ap = argparse.ArgumentParser(
        description="PubMed 쿼리 → PMID CSV (90_CLI input 포맷).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--query", required=True,
                    help="PubMed boolean 쿼리 문자열 (따옴표로 감싸기)")
    ap.add_argument("--output", default="./pmids.csv",
                    help="출력 CSV 경로 (default: ./pmids.csv)")
    ap.add_argument("--count-only", action="store_true",
                    help="결과 수만 확인")
    ap.add_argument("--limit", type=int, default=None,
                    help="최대 PMID 수 (테스트용 상한)")
    args = ap.parse_args()

    q_preview = args.query[:200] + ("..." if len(args.query) > 200 else "")
    print(f"쿼리: {q_preview}")
    if not NCBI_API_KEY:
        print("WARNING: NCBI_API_KEY 미설정 — rate limit 3 req/sec",
              file=sys.stderr)

    count = esearch_count(args.query)
    print(f"결과 수: {count:,}")

    if args.count_only:
        return 0
    if count == 0:
        print("결과 0건 — 쿼리 재확인 필요", file=sys.stderr)
        return 1

    pmids = esearch_all_pmids(args.query, count, args.limit)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"pmid": pmids}).to_csv(
        out_path, index=False, encoding="utf-8-sig",
    )
    print(f"\n저장 → {out_path} ({len(pmids):,} 건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
