import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import transform


def _sample_raw_sales():
    return pd.DataFrame([
        {"transaction_id": "T1", "order_date": "2024-01-01", "customer_id": "C1",
         "product_id": "P1", "quantity": "2", "unit_price": "100.0",
         "region": "North", "payment_method": "UPI"},
        # exact duplicate of T1 -> should be dropped
        {"transaction_id": "T1", "order_date": "2024-01-01", "customer_id": "C1",
         "product_id": "P1", "quantity": "2", "unit_price": "100.0",
         "region": "North", "payment_method": "UPI"},
        # bad quantity -> should be dropped
        {"transaction_id": "T2", "order_date": "2024-01-02", "customer_id": "C2",
         "product_id": "P2", "quantity": "-1", "unit_price": "50.0",
         "region": "South", "payment_method": None},
        # missing customer_id -> should be dropped
        {"transaction_id": "T3", "order_date": "2024-01-03", "customer_id": None,
         "product_id": "P1", "quantity": "1", "unit_price": "20.0",
         "region": "East", "payment_method": "Cash on Delivery"},
        # valid row, missing payment method -> keep with 'Unknown'
        {"transaction_id": "T4", "order_date": "2024-01-04", "customer_id": "C3",
         "product_id": "P2", "quantity": "3", "unit_price": "10.0",
         "region": "West", "payment_method": None},
    ])


def test_clean_sales_drops_duplicates_and_invalid_rows():
    cleaned = transform.clean_sales(_sample_raw_sales())
    # T1 (deduped to 1), T4 survive; T2 (bad qty) and T3 (missing customer) are dropped
    assert set(cleaned["transaction_id"]) == {"T1", "T4"}
    assert len(cleaned) == 2


def test_clean_sales_computes_revenue():
    cleaned = transform.clean_sales(_sample_raw_sales())
    row = cleaned[cleaned["transaction_id"] == "T1"].iloc[0]
    assert row["revenue"] == 200.0


def test_clean_sales_fills_missing_payment_method():
    cleaned = transform.clean_sales(_sample_raw_sales())
    row = cleaned[cleaned["transaction_id"] == "T4"].iloc[0]
    assert row["payment_method"] == "Unknown"


def test_standardize_products_handles_cache_schema():
    raw = pd.DataFrame([
        {"id": "P1", "title": "Widget", "category": "electronics", "price": 9.99, "rating": 4.5, "brand": "Acme"},
    ])
    products = transform.standardize_products(raw)
    assert list(products.columns) == ["product_id", "product_title", "category", "price", "rating", "brand"]
    assert products.iloc[0]["category"] == "Electronics"


def test_standardize_products_handles_live_api_schema():
    # live API shape: no `brand`, nested rating.rate after json_normalize
    raw = pd.DataFrame([
        {"id": "P1", "title": "Widget", "category": "electronics", "price": 9.99, "rating.rate": 4.2, "rating.count": 10},
    ])
    products = transform.standardize_products(raw)
    assert products.iloc[0]["brand"] == "Unknown"
    assert products.iloc[0]["rating"] == 4.2


def test_join_flags_orphaned_product_references():
    sales = pd.DataFrame([
        {"product_id": "P1", "revenue": 100.0, "order_month": "2024-01"},
        {"product_id": "P999", "revenue": 50.0, "order_month": "2024-01"},
    ])
    products = pd.DataFrame([{"product_id": "P1", "category": "Electronics"}])
    fact = transform.join_sales_products(sales, products)
    assert fact.loc[fact["product_id"] == "P1", "has_valid_product"].iloc[0] == True
    assert fact.loc[fact["product_id"] == "P999", "has_valid_product"].iloc[0] == False


def test_aggregate_revenue_by_category_excludes_orphaned_rows():
    fact = pd.DataFrame([
        {"category": "Electronics", "revenue": 100.0, "has_valid_product": True},
        {"category": "Electronics", "revenue": 9999.0, "has_valid_product": False},  # excluded
        {"category": "Books", "revenue": 20.0, "has_valid_product": True},
    ])
    agg = transform.aggregate_revenue_by_category(fact)
    assert agg.set_index("category").loc["Electronics", "revenue"] == 100.0
