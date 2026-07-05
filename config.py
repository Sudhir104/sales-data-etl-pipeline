"""Central configuration for the pipeline (paths, DB target, API endpoint)."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RAW_SALES_CSV = os.path.join(BASE_DIR, "data", "raw", "sales_transactions.csv")
PRODUCTS_API_CACHE = os.path.join(BASE_DIR, "data", "raw", "products_api_cache.json")

# Public demo API used for the "REST API extract" step. Falls back to the local
# cache automatically if there's no internet access or the API is unreachable --
# a common real-world resilience pattern for source systems with flaky uptime.
PRODUCTS_API_URL = "https://fakestoreapi.com/products"

OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
CHARTS_DIR = os.path.join(OUTPUT_DIR, "charts")
LOG_FILE = os.path.join(OUTPUT_DIR, "pipeline.log")
QUALITY_REPORT_FILE = os.path.join(OUTPUT_DIR, "data_quality_report.json")

# Database target. Defaults to a local SQLite file so the project runs with zero
# setup. Point DB_URL at a MySQL instance (e.g.
# "mysql+pymysql://user:pass@host:3306/sales_dw") to load into MySQL instead --
# no code changes needed since loading goes through SQLAlchemy.
DB_URL = os.environ.get("DB_URL", f"sqlite:///{os.path.join(OUTPUT_DIR, 'sales_warehouse.db')}")

FACT_TABLE = "fact_sales"
DIM_PRODUCTS_TABLE = "dim_products"
AGG_CATEGORY_TABLE = "agg_revenue_by_category"
AGG_MONTHLY_TABLE = "agg_revenue_by_month"
AGG_REGION_TABLE = "agg_revenue_by_region"
