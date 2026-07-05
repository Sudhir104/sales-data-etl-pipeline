"""
Transform layer: cleaning, deduplication, schema standardization,
referential-integrity join, and business aggregations.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("etl.transform")


def clean_sales(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the raw sales export:
      - drop exact duplicate rows (retry / re-sync artifacts)
      - coerce order_date, quantity, unit_price to proper types (bad values -> NaN)
      - drop rows missing a required key field (customer_id, product_id, order_date)
      - drop rows with non-positive quantity or unit_price (data entry errors)
      - fill missing payment_method with 'Unknown' (non-critical field)
      - compute a `revenue` column
    """
    df = raw_df.copy()
    before = len(df)

    df = df.drop_duplicates()
    after_dedupe = len(df)

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")

    df["payment_method"] = df["payment_method"].fillna("Unknown")

    required = ["order_date", "customer_id", "product_id", "quantity", "unit_price"]
    df = df.dropna(subset=required)
    after_required = len(df)

    df = df[(df["quantity"] > 0) & (df["unit_price"] > 0)]
    after_positive = len(df)

    df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["order_month"] = df["order_date"].dt.to_period("M").astype(str)

    logger.info(
        "clean_sales: %d raw -> %d after dedupe -> %d after required-field check -> %d after positive-value check",
        before, after_dedupe, after_required, after_positive,
    )
    return df.reset_index(drop=True)


def standardize_products(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize the product master to a consistent schema regardless of whether
    it came from the live public API (nested `rating.rate`, no `brand`) or the
    cached snapshot (flat `rating`, includes `brand`).
    """
    df = raw_df.copy()
    df = df.rename(columns={"id": "product_id", "title": "product_title"})

    if "rating.rate" in df.columns:
        df["rating"] = df["rating.rate"]

    if "brand" not in df.columns:
        df["brand"] = "Unknown"

    df["category"] = df["category"].astype(str).str.strip().str.title()
    df["product_id"] = df["product_id"].astype(str)

    keep = ["product_id", "product_title", "category", "price", "rating", "brand"]
    df = df[[c for c in keep if c in df.columns]].drop_duplicates(subset="product_id")
    return df.reset_index(drop=True)


def join_sales_products(sales_df: pd.DataFrame, products_df: pd.DataFrame) -> pd.DataFrame:
    """
    Left-join sales facts to the product dimension. Rows whose product_id
    has no match (referential-integrity issue -- e.g. a discontinued or
    mistyped product code) are flagged rather than silently dropped, so
    they can be reported on and investigated instead of skewing revenue.
    """
    merged = sales_df.merge(products_df, on="product_id", how="left", indicator=True)
    unmatched = int((merged["_merge"] == "left_only").sum())
    if unmatched:
        logger.warning("%d sales rows reference a product_id not found in the product master", unmatched)
    merged["has_valid_product"] = merged["_merge"] == "both"
    merged = merged.drop(columns=["_merge"])
    return merged


def aggregate_revenue_by_category(fact_df: pd.DataFrame) -> pd.DataFrame:
    valid = fact_df[fact_df["has_valid_product"]]
    agg = (
        valid.groupby("category", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .round(2)
    )
    return agg.reset_index(drop=True)


def aggregate_revenue_by_month(fact_df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        fact_df.groupby("order_month", as_index=False)["revenue"]
        .sum()
        .sort_values("order_month")
        .round(2)
    )
    return agg.reset_index(drop=True)


def aggregate_revenue_by_region(fact_df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        fact_df.groupby("region", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
        .round(2)
    )
    return agg.reset_index(drop=True)
