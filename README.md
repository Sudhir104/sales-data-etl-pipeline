# Sales Data ETL Pipeline

An end-to-end batch ETL pipeline that ingests raw, messy multi-source sales
data, cleans and validates it, joins it against a product catalog pulled
from a REST API, and loads curated fact/dimension/aggregate tables into a
SQL data warehouse — with an analysis notebook on top.

> Built to be genuinely runnable in under a minute: `pip install -r requirements.txt && python main.py`

---

## Problem

Retail sales exports are rarely clean. In this project the raw source data
(`data/raw/sales_transactions.csv`, ~3,100 rows) has the same problems a real
CRM/POS export has: duplicate rows from retries, missing customer/price
fields, non-numeric price values, negative/zero quantities, and product IDs
that don't exist in the catalog. Meanwhile the product catalog itself lives
in a separate system, reachable only via a REST API.

The goal: build a pipeline that reliably turns that raw mess into a trusted,
query-ready warehouse — with every cleaning decision logged and every
quality issue measured, not just quietly fixed and forgotten.

## Technologies & tools

| Layer | Tool |
|---|---|
| Extraction | `pandas` (CSV), `requests` (REST API, with local-cache fallback) |
| Transformation | `pandas`, `numpy` |
| Data quality | custom validation module (`src/data_quality.py`) + JSON report |
| Loading | `SQLAlchemy` → SQLite by default, MySQL-compatible via connection string |
| Testing | `pytest` (12 unit tests on transform + quality logic) |
| Analysis | Jupyter Notebook, `matplotlib` |

## Approach

The pipeline follows a standard **Extract → Transform → Validate → Load**
structure, split into small, independently-testable modules under `src/`:

1. **Extract** (`src/extract.py`)
   - Reads the raw sales CSV as-is (everything as strings — no data loss
     from premature type-casting).
   - Pulls the product catalog from a public REST API
     (`fakestoreapi.com/products`), and **transparently falls back to a
     cached JSON snapshot** (`data/raw/products_api_cache.json`) if the API
     is unreachable, rate-limited, or times out. This is the same fallback
     pattern you'd want against a flaky third-party/vendor API in production.

2. **Transform** (`src/transform.py`)
   - Drops exact duplicates (retry artifacts).
   - Coerces `order_date`, `quantity`, `unit_price` to proper types —
     malformed values (e.g. `"unknown"`, `"N/A"`) become `NaN` instead of
     crashing the pipeline.
   - Drops rows missing a required key field, and rows with non-positive
     quantity/price (bad data, not real transactions).
   - Standardizes the product schema whether it came from the live API
     (nested `rating.rate`, no `brand` field) or the cached snapshot (flat
     schema, includes `brand`) — one consistent shape either way.
   - Left-joins sales to products and **flags** (rather than silently
     drops) rows whose `product_id` has no match — a referential-integrity
     issue that gets reported, not buried.
   - Produces three business aggregates: revenue by category, by month,
     and by region.

3. **Validate** (`src/data_quality.py`)
   - Null checks, uniqueness checks (on `transaction_id`), range checks
     (quantity/price > 0), and a referential-integrity check (orphan rate).
   - All checks are written to `outputs/data_quality_report.json` after
     every run, so quality is a tracked artifact, not just a log line.

4. **Load** (`src/load.py`)
   - Loads `fact_sales`, `dim_products`, and the three aggregate tables via
     SQLAlchemy. Defaults to a local SQLite file
     (`outputs/sales_warehouse.db`) so the project runs with zero setup;
     pointing `DB_URL` at a MySQL instance loads into MySQL instead with
     **no code changes**.

5. **Analyze** (`notebooks/sales_analysis.ipynb`)
   - Reads the warehouse tables back out and answers: which categories
     drive revenue, how revenue trends month-over-month, and which regions
     are strongest — plus surfaces the data quality report inline.

## Key outcomes

A single run against the sample data:

| Metric | Value |
|---|---|
| Raw rows extracted | 3,120 |
| Rows after dedupe | 3,001 |
| Rows after required-field check | 2,911 |
| Clean rows loaded to warehouse | 2,267 |
| Products loaded | 60 |
| Orphaned sales rows (no matching product) | 17 (0.7%) |
| Total valid revenue | ₹1,47,46,818.23 |
| Data quality status | **PASS** |
| Runtime | ~0.4s |

(Exact numbers are reproducible — the raw data is generated with a fixed
random seed by `generate_raw_data.py`.)

## Key learnings

- **Fail loud on structure, fail soft on values.** A missing column should
  crash the pipeline; a malformed price in one row shouldn't — it should be
  coerced to null, counted, and reported.
- **Referential-integrity issues are information, not noise.** Dropping
  orphaned rows silently would have understated the real severity of a
  catalog sync problem; flagging them and excluding them only from revenue
  aggregates (while keeping them queryable) makes the issue visible.
- **A cache fallback for external APIs isn't optional in production ETL.**
  Third-party APIs go down or rate-limit; a pipeline that can't run without
  them isn't reliable enough to depend on for daily loads.
- **Swapping databases should be a config change, not a rewrite.** Going
  through SQLAlchemy instead of hand-rolled SQLite calls means the exact
  same load code targets MySQL in production.

## How to run it

```bash
pip install -r requirements.txt

# (optional) regenerate the raw sample data — a fixed seed means this is
# reproducible, so you don't need to re-run it; a copy is already committed
python generate_raw_data.py

# run the full pipeline
python main.py

# run the test suite
pytest tests/ -v

# open the analysis notebook
jupyter notebook notebooks/sales_analysis.ipynb
```

To load into MySQL instead of the default SQLite:

```bash
pip install pymysql
DB_URL="mysql+pymysql://user:password@host:3306/sales_dw" python main.py
```

## Project structure

```
sales-data-etl-pipeline/
├── main.py                     # pipeline orchestrator (extract -> transform -> validate -> load)
├── streamlit_app.py            # live dashboard on top of the pipeline output (deploy to Streamlit Cloud)
├── config.py                   # paths, DB target, API endpoint
├── generate_raw_data.py        # generates the intentionally-messy sample raw data
├── src/
│   ├── extract.py              # CSV + REST API (with cache fallback) extraction
│   ├── transform.py            # cleaning, standardization, join, aggregation
│   ├── data_quality.py         # validation checks + JSON quality report
│   └── load.py                 # SQLAlchemy-based warehouse loading
├── data/raw/                   # sample raw sales CSV + cached product API snapshot
├── tests/                      # pytest unit tests (12 tests)
├── notebooks/
│   └── sales_analysis.ipynb    # post-load analysis + charts (pre-executed)
└── outputs/                    # generated: warehouse db, quality report, charts, logs
```

## Live dashboard (Streamlit)

`streamlit_app.py` is a dashboard on top of the pipeline's output tables —
KPIs, revenue-by-category/month/region charts, and the data quality report.
On first load it automatically runs the pipeline against the committed
sample data if the warehouse doesn't exist yet, so it works out of the box
on Streamlit Community Cloud with zero manual setup steps.

Run it locally:

```bash
streamlit run streamlit_app.py
```

### Deploying to Streamlit Community Cloud (free)

1. Push this repo to GitHub (see below).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. Click **New app** → pick this repo → set **Main file path** to `streamlit_app.py` → **Deploy**.
4. Streamlit installs `requirements.txt`, runs the app, and the pipeline
   auto-builds the warehouse on first load. You'll get a public URL like
   `https://<your-app>.streamlit.app` — that's your live link.

## Live link

GitHub repository: **[add your GitHub repo URL here after pushing]**
Live dashboard: **[add your Streamlit Community Cloud URL here after deploying]**

