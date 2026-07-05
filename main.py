"""
Sales Data ETL Pipeline
=======================
Entry point that runs the full Extract -> Transform -> Validate -> Load flow.

Usage:
    python main.py

Point DB_URL at a MySQL database instead of the SQLite default:
    DB_URL="mysql+pymysql://user:pass@host:3306/sales_dw" python main.py
"""
import json
import logging
import os
import sys
import time

import config

os.makedirs(config.OUTPUT_DIR, exist_ok=True)
os.makedirs(config.CHARTS_DIR, exist_ok=True)

from src import extract, transform, data_quality, load

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(config.LOG_FILE, mode="w")],
)
logger = logging.getLogger("etl.pipeline")


def run() -> dict:
    start = time.time()
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.CHARTS_DIR, exist_ok=True)

    logger.info("=== EXTRACT ===")
    raw_sales = extract.extract_sales_csv(config.RAW_SALES_CSV)
    raw_products = extract.extract_products_api(config.PRODUCTS_API_URL, config.PRODUCTS_API_CACHE)

    logger.info("=== TRANSFORM ===")
    clean_sales = transform.clean_sales(raw_sales)
    products = transform.standardize_products(raw_products)
    fact = transform.join_sales_products(clean_sales, products)

    revenue_by_category = transform.aggregate_revenue_by_category(fact)
    revenue_by_month = transform.aggregate_revenue_by_month(fact)
    revenue_by_region = transform.aggregate_revenue_by_region(fact)

    logger.info("=== DATA QUALITY ===")
    quality_report = data_quality.build_quality_report(clean_sales, fact)
    with open(config.QUALITY_REPORT_FILE, "w") as f:
        json.dump(quality_report, f, indent=2)

    logger.info("=== LOAD ===")
    engine = load.get_engine(config.DB_URL)
    load.load_table(fact.drop(columns=["product_title"], errors="ignore"), config.FACT_TABLE, engine)
    load.load_table(products, config.DIM_PRODUCTS_TABLE, engine)
    load.load_table(revenue_by_category, config.AGG_CATEGORY_TABLE, engine)
    load.load_table(revenue_by_month, config.AGG_MONTHLY_TABLE, engine)
    load.load_table(revenue_by_region, config.AGG_REGION_TABLE, engine)

    elapsed = round(time.time() - start, 2)
    summary = {
        "raw_rows_extracted": len(raw_sales),
        "clean_rows_loaded": len(clean_sales),
        "products_loaded": len(products),
        "total_revenue": round(float(fact.loc[fact["has_valid_product"], "revenue"].sum()), 2),
        "data_quality_status": quality_report["overall_status"],
        "runtime_seconds": elapsed,
        "db_url": config.DB_URL,
    }
    logger.info("=== PIPELINE COMPLETE === %s", summary)
    return summary


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
