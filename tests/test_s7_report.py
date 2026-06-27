"""s7_report._build_color_legend_html — taxonomy 기반 legend 검증."""

import pandas as pd

from topic_pipeline.shared import colors
from topic_pipeline.steps import s7_report


# ── _read_trend_stats: 빈/없는 trend_stats 가드 (issue #14) ──

def test_read_trend_stats_missing(tmp_path):
    assert s7_report._read_trend_stats(tmp_path / "nope.csv") is None


def test_read_trend_stats_empty_bom_only(tmp_path):
    # s6 가 트렌드 0건일 때 쓰는 BOM-only(컬럼 없음) 파일 → EmptyDataError 흡수 → None
    p = tmp_path / "s6_trend_stats.csv"
    p.write_bytes(b"\xef\xbb\xbf\n")
    assert s7_report._read_trend_stats(p) is None


def test_read_trend_stats_header_only(tmp_path):
    # 헤더만(행 0) → None (df.empty)
    p = tmp_path / "s6_trend_stats.csv"
    p.write_text("rank,topic_id,label_kr,keyword\n", encoding="utf-8-sig")
    assert s7_report._read_trend_stats(p) is None


def test_read_trend_stats_populated(tmp_path):
    p = tmp_path / "s6_trend_stats.csv"
    pd.DataFrame({"rank": [1], "topic_id": [0], "label_kr": ["가"], "keyword": ["k"]}).to_csv(
        p, index=False, encoding="utf-8-sig")
    df = s7_report._read_trend_stats(p)
    assert df is not None and len(df) == 1


def test_legend_default_3group():
    tax = colors.load_taxonomy({})
    html = s7_report._build_color_legend_html(10, tax)
    assert "직접 관련" in html and "간접 관련" in html and "낮은 관련도" in html
    assert "Outlier" in html
    # 기본 3그룹 분포 relevance_split(10)=(3,4,3) → 1~3 / 4~7 / 8~10위
    assert "(1~3위)" in html and "(4~7위)" in html and "(8~10위)" in html


def test_legend_custom_2group():
    tax = {
        "groups": [colors.COLOR_GROUPS[0], colors.COLOR_GROUPS[2]],
        "outlier": colors.COLOR_GROUPS[3],
    }
    html = s7_report._build_color_legend_html(10, tax)
    # 2그룹 split_ranks(10,2)=[5,5] → 1~5 / 6~10위
    assert "(1~5위)" in html and "(6~10위)" in html
    assert html.count("위)") == 2  # outlier 제외 2 그룹


def test_write_results_json(tmp_path):
    import json

    s7_report._write_results_json(
        tmp_path, {"주제": "T", "데이터 출처": "S"}, {"silhouette": 0.3},
        [5, 4], {5: "가", 4: "나"}, {5: "a", 4: "b"}, {5: "d5", 4: "d4"},
        {5: "#111", 4: "#222"},
        total_docs=10, n_classified=8, n_outliers=2, n_topics=2, year_min=2020, year_max=2021,
    )
    data = json.loads((tmp_path / "s7_results.json").read_text(encoding="utf-8"))
    assert data["summary"]["total_docs"] == 10
    assert data["project"]["주제"] == "T"
    assert data["topics"][0] == {
        "topic": 5, "rank": 1, "label_kr": "가", "label_en": "a",
        "description": "d5", "color": "#111",
    }
