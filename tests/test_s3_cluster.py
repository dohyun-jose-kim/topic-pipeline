"""s3_cluster._select_mts — sweep tie-break 선택 로직 (순수 로직, bertopic 불필요)."""

from topic_pipeline.steps import s3_cluster


def _rec(mts, n_topics, passed=True):
    return {"mts": mts, "metrics": {"n_topics": n_topics}, "passed": passed}


def test_select_mts_median_low_default():
    sweep = [_rec(10, 5), _rec(20, 8), _rec(30, 12)]
    assert s3_cluster._select_mts(sweep, {"sweep": {}}) == 20  # median_low([10,20,30])


def test_select_mts_default_when_no_tie_break_key():
    sweep = [_rec(10, 5), _rec(30, 12)]
    assert s3_cluster._select_mts(sweep, {}) == 10  # median_low([10,30])


def test_select_mts_target_closest():
    sweep = [_rec(10, 5), _rec(20, 8), _rec(30, 12)]
    cfg = {"sweep": {"tie_break": "target", "target_n_topics": 10}}
    # n_topics 5/8/12 → |·-10| = 5/2/2, 동률(8,12)에서 큰 쪽 12 → mts=30
    assert s3_cluster._select_mts(sweep, cfg) == 30


def test_select_mts_ignores_failed():
    sweep = [_rec(10, 5), _rec(20, 8, passed=False), _rec(30, 12)]
    assert s3_cluster._select_mts(sweep, {"sweep": {}}) == 10  # survivors [10,30]
