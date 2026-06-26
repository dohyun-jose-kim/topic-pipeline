"""steps/s0_preprocess.py — abstract → abstract_clean 정제 (M6 T1-2).

기본 비활성(preprocess.enabled=false) → skip (현행 raw abstract 동작 byte-identical 보존).
활성 시 s1_meta.csv 를 읽어 abstract_clean 컬럼을 추가한 s0_meta_clean.csv 생성.
원본 abstract 는 유지(s7 hover/provenance). 다운스트림 s2 가 s0_meta_clean 있으면 우선 사용(T1-3).

입력:  {output_dir}/s1_meta.csv
출력:  {output_dir}/s0_meta_clean.csv   (enabled 일 때만)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..shared.preprocess import clean_series


def run(cfg: dict) -> None:
    output_dir = Path(cfg["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    if not (cfg.get("preprocess") or {}).get("enabled", False):
        print("[s0] preprocess.enabled=false — skip (raw abstract 사용)")
        return

    in_path = output_dir / "s1_meta.csv"
    out_path = output_dir / "s0_meta_clean.csv"
    df = pd.read_csv(in_path)
    if "abstract" not in df.columns:
        raise ValueError(f"'abstract' 컬럼 없음: {in_path} (columns={list(df.columns)})")

    if out_path.exists():
        try:
            if len(pd.read_csv(out_path, usecols=["pmid"])) == len(df):
                print(f"[s0] 캐시 hit: {out_path} ({len(df)}행) — skip")
                return
        except Exception:
            pass

    df["abstract_clean"] = clean_series(df["abstract"])
    n_empty = int((df["abstract_clean"].str.len() == 0).sum())

    tmp = out_path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    tmp.replace(out_path)
    print(f"[s0] 저장 → {out_path} ({len(df)}행; abstract_clean 빈 값 {n_empty}건)")
