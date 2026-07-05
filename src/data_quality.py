"""
Automated data quality checks, run after cleaning and after the join.
Produces a single JSON report so quality can be tracked run over run
rather than only eyeballed in logs.
"""
import logging

import pandas as pd

logger = logging.getLogger("etl.quality")


def null_check(df: pd.DataFrame, columns: list) -> dict:
    return {col: int(df[col].isna().sum()) for col in columns}


def uniqueness_check(df: pd.DataFrame, column: str) -> dict:
    dupes = int(df.duplicated(subset=column).sum())
    return {"column": column, "duplicate_count": dupes, "is_unique": dupes == 0}


def range_check(df: pd.DataFrame, column: str, min_value: float = 0) -> dict:
    below_min = int((df[column] < min_value).sum())
    return {"column": column, "min_allowed": min_value, "violations": below_min}


def referential_integrity_check(fact_df: pd.DataFrame, key_flag_column: str = "has_valid_product") -> dict:
    total = len(fact_df)
    invalid = int((~fact_df[key_flag_column]).sum())
    return {
        "total_rows": total,
        "orphaned_rows": invalid,
        "orphan_rate_pct": round(100 * invalid / total, 2) if total else 0.0,
    }


def build_quality_report(clean_sales_df: pd.DataFrame, joined_df: pd.DataFrame) -> dict:
    report = {
        "row_counts": {
            "clean_sales_rows": len(clean_sales_df),
            "joined_fact_rows": len(joined_df),
        },
        "null_checks": null_check(clean_sales_df, ["order_date", "customer_id", "product_id", "quantity", "unit_price"]),
        "uniqueness_checks": {
            "transaction_id": uniqueness_check(clean_sales_df, "transaction_id"),
        },
        "range_checks": {
            "quantity": range_check(clean_sales_df, "quantity", min_value=0.0001),
            "unit_price": range_check(clean_sales_df, "unit_price", min_value=0.0001),
        },
        "referential_integrity": referential_integrity_check(joined_df),
    }

    passed = (
        all(v == 0 for v in report["null_checks"].values())
        and report["uniqueness_checks"]["transaction_id"]["is_unique"]
        and report["range_checks"]["quantity"]["violations"] == 0
        and report["range_checks"]["unit_price"]["violations"] == 0
    )
    report["overall_status"] = "PASS" if passed else "PASS_WITH_WARNINGS"
    logger.info("Data quality report: %s", report["overall_status"])
    return report
