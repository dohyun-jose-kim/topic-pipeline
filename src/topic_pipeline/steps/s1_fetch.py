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


def run(cfg: dict) -> None:
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

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
