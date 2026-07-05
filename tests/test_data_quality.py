import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import data_quality


def test_null_check_counts_correctly():
    df = pd.DataFrame({"a": [1, None, 3], "b": [None, None, 3]})
    result = data_quality.null_check(df, ["a", "b"])
    assert result == {"a": 1, "b": 2}


def test_uniqueness_check_detects_duplicates():
    df = pd.DataFrame({"id": ["T1", "T1", "T2"]})
    result = data_quality.uniqueness_check(df, "id")
    assert result["duplicate_count"] == 1
    assert result["is_unique"] is False


def test_range_check_flags_below_minimum():
    df = pd.DataFrame({"quantity": [1, -1, 0, 5]})
    result = data_quality.range_check(df, "quantity", min_value=0.0001)
    assert result["violations"] == 2  # -1 and 0


def test_referential_integrity_check_computes_orphan_rate():
    df = pd.DataFrame({"has_valid_product": [True, True, False, True]})
    result = data_quality.referential_integrity_check(df)
    assert result["orphaned_rows"] == 1
    assert result["orphan_rate_pct"] == 25.0


def test_build_quality_report_status_pass():
    clean = pd.DataFrame({
        "transaction_id": ["T1", "T2"],
        "order_date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "customer_id": ["C1", "C2"],
        "product_id": ["P1", "P2"],
        "quantity": [1, 2],
        "unit_price": [10.0, 20.0],
    })
    joined = clean.assign(has_valid_product=[True, True])
    report = data_quality.build_quality_report(clean, joined)
    assert report["overall_status"] == "PASS"
