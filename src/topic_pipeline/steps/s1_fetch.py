"""steps/s1_fetch.py — PMID CSV → {year, abstract, author_keywords, mesh_terms} 통합.

PLAN-v2 §8 Phase 4. 네트워크 계층은 shared/pubmed.py 재사용.
원본 파싱 로직: week_4/Task1-v3/01_fetch/collect_pubmed.py::parse_article (abstract/year)
             + 01_DataFetch/fetch_author_keywords.py::parse_keywords (author_kw/mesh).

입력:
  {paths.input_pmid_csv}  — 'pmid' 컬럼을 가진 CSV (다른 컬럼 무시)
출력:
  {paths.output_dir}/s1_meta.csv
    pmid, year, abstract, author_keywords, mesh_terms
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from ..shared.pubmed import efetch_articles

# s1_meta.csv 스키마 = 단계 간 계약(invariant). 모든 ingest 어댑터가 이 컬럼을 emit 해야 한다.
S1_COLUMNS = ["pmid", "year", "title", "abstract", "author_keywords", "mesh_terms"]


def run(cfg: dict) -> None:
    """fetch.source 에 따라 ingest 어댑터를 골라 s1_meta.csv 생성. 기본 'pubmed'."""
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    source = (cfg.get("fetch", {}) or {}).get("source", "pubmed")
    runner = _SOURCES.get(source)
    if runner is None:
        raise ValueError(f"알 수 없는 fetch.source: {source!r} (지원: {sorted(_SOURCES)})")
    runner(cfg, output_dir)


def _run_pubmed(cfg: dict, output_dir: Path) -> None:
    """PubMed efetch 어댑터 — s1_meta.csv(S1_COLUMNS) 생성. (기존 동작 그대로)"""
    fetch_cfg = cfg.get("fetch", {})
    pmid_csv = Path(cfg["paths"]["input_pmid_csv"])

    pmids_df = pd.read_csv(pmid_csv)
    if "pmid" not in pmids_df.columns:
        raise ValueError(f"'pmid' 컬럼 없음: {pmid_csv} (columns={list(pmids_df.columns)})")
    pmids = pmids_df["pmid"].dropna().astype(int).tolist()
    print(f"[s1] {len(pmids)} PMIDs 로드 ← {pmid_csv}")

    out_path = output_dir / "s1_meta.csv"
    if out_path.exists() and not fetch_cfg.get("force_refetch", False):
        cached_rows = len(pd.read_csv(out_path, usecols=["pmid"]))
        if cached_rows == len(pmids):
            print(f"[s1] 캐시 hit: {out_path} ({cached_rows}편) — skip")
            return
        print(f"[s1] 캐시 행수 불일치 ({cached_rows} vs 기대 {len(pmids)}) — 재수집")

    records = []
    for article in tqdm(
        efetch_articles(
            pmids,
            api_key=fetch_cfg.get("ncbi_api_key") or None,
            batch_size=fetch_cfg.get("batch_size", 200),
        ),
        total=len(pmids),
        desc="[s1] parsing",
    ):
        rec = _parse_article(article)
        if rec:
            records.append(rec)

    pd.DataFrame(records).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 → {out_path} ({len(records)} 편)")


def _run_csv(cfg: dict, output_dir: Path) -> None:
    """일반 CSV 어댑터 — 임의 텍스트 CSV → s1_meta.csv(S1_COLUMNS).

    fetch.input_csv(없으면 paths.input_pmid_csv) 를 읽고 fetch.columns 매핑(s1 스키마 ← 사용자
    컬럼명)으로 변환. 본문 텍스트(text/abstract)는 필수. doc_id 없으면 1..N 정수를 pmid 로 합성
    (병합키 계약 유지). mesh_terms 는 항상 빈 값(PubMed 전용 메타).
    """
    fetch_cfg = cfg.get("fetch", {}) or {}
    csv_path = Path(fetch_cfg.get("input_csv") or cfg["paths"]["input_pmid_csv"])
    colmap = fetch_cfg.get("columns", {}) or {}

    df = pd.read_csv(csv_path)
    print(f"[s1] CSV 어댑터: {len(df)} 행 로드 ← {csv_path}")

    def pick(schema_name: str):
        """schema_name 에 매핑된 사용자 컬럼 Series (매핑 없으면 동명 컬럼). 없으면 None."""
        user = colmap.get(schema_name, schema_name)
        return df[user] if user in df.columns else None

    text = pick("text")
    if text is None:
        text = pick("abstract")
    if text is None:
        raise ValueError(
            f"본문 텍스트 컬럼 없음 — fetch.columns.text 로 지정하세요 (가용: {list(df.columns)})"
        )

    n = len(df)
    doc_id = pick("doc_id")
    if doc_id is None:
        doc_id = pick("pmid")
    if doc_id is not None:
        pmid = pd.to_numeric(doc_id, errors="coerce")
        if pmid.isna().any():
            pmid = pd.Series(range(1, n + 1))
    else:
        pmid = pd.Series(range(1, n + 1))

    year = pick("year")
    title = pick("title")
    keywords = pick("keywords")

    out = pd.DataFrame({
        "pmid": pmid.astype(int).to_numpy(),
        "year": year.to_numpy() if year is not None else "",
        "title": title.astype(str).to_numpy() if title is not None else "",
        "abstract": text.astype(str).to_numpy(),
        "author_keywords": keywords.astype(str).to_numpy() if keywords is not None else "",
        "mesh_terms": "",
    })[S1_COLUMNS]

    out_path = output_dir / "s1_meta.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 → {out_path} ({len(out)} 행; mesh_terms 비움)")


_SOURCES = {"pubmed": _run_pubmed, "csv": _run_csv}


def _parse_article(article: ET.Element) -> dict | None:
    medline = article.find("MedlineCitation")
    if medline is None:
        return None
    pmid = medline.findtext("PMID", "")
    if not pmid:
        return None

    art = medline.find("Article")
    if art is None:
        return None

    # Title (nested 태그 <i>, <sub> 등 평문화)
    title_elem = art.find("ArticleTitle")
    title = "".join(title_elem.itertext()).strip() if title_elem is not None else ""

    # Abstract (여러 AbstractText 합치기, Label 있으면 "Label: ..." prefix)
    abstract_parts = []
    abs_elem = art.find("Abstract")
    if abs_elem is not None:
        for at in abs_elem.findall("AbstractText"):
            label = at.get("Label", "")
            text = "".join(at.itertext())
            abstract_parts.append(f"{label}: {text}" if label else text)
    abstract = " ".join(abstract_parts)

    # Year (PubDate/Year, 없으면 MedlineDate 앞 4자리)
    year = ""
    pub_date = art.find("Journal/JournalIssue/PubDate")
    if pub_date is not None:
        year = pub_date.findtext("Year", "")
        if not year:
            medline_date = pub_date.findtext("MedlineDate", "")
            if medline_date:
                year = medline_date[:4]

    # Author Keywords
    author_kws = []
    for kw_list in medline.findall("KeywordList"):
        for kw in kw_list.findall("Keyword"):
            text = "".join(kw.itertext()).strip()
            if text:
                author_kws.append(text)

    # MeSH Terms
    mesh_terms = []
    mesh_list = medline.find("MeshHeadingList")
    if mesh_list is not None:
        for mh in mesh_list.findall("MeshHeading"):
            desc = mh.findtext("DescriptorName", "")
            if desc:
                mesh_terms.append(desc)

    return {
        "pmid": int(pmid),
        "year": year,
        "title": title,
        "abstract": abstract,
        "author_keywords": "; ".join(author_kws),
        "mesh_terms": "; ".join(mesh_terms),
    }
