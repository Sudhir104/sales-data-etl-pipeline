"""
Streamlit dashboard for the Sales Data ETL Pipeline.

Deploy this file on Streamlit Community Cloud (streamlit.io) connected to
your GitHub repo -- on first load, if the warehouse database doesn't exist
yet (it's gitignored, since generated artifacts shouldn't live in git), the
app runs the pipeline itself against the committed sample raw data, then
serves the dashboard from the freshly-built warehouse.

Run locally:
    streamlit run streamlit_app.py
"""
import json
import os
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

import config

st.set_page_config(page_title="Sales Data ETL Pipeline", page_icon="📊", layout="wide")


@st.cache_resource(show_spinner="Running the ETL pipeline for the first time...")
def ensure_warehouse_built():
    """Build the warehouse on first load if it isn't already there."""
    db_path = config.DB_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        import main as pipeline
        pipeline.run()
    return db_path


@st.cache_data(show_spinner=False)
def load_tables(db_path: str):
    conn = sqlite3.connect(db_path)
    tables = {
        "fact": pd.read_sql(f"SELECT * FROM {config.FACT_TABLE}", conn),
        "by_category": pd.read_sql(f"SELECT * FROM {config.AGG_CATEGORY_TABLE}", conn),
        "by_month": pd.read_sql(f"SELECT * FROM {config.AGG_MONTHLY_TABLE}", conn),
        "by_region": pd.read_sql(f"SELECT * FROM {config.AGG_REGION_TABLE}", conn),
        "products": pd.read_sql(f"SELECT * FROM {config.DIM_PRODUCTS_TABLE}", conn),
    }
    conn.close()
    return tables


db_path = ensure_warehouse_built()
tables = load_tables(db_path)

with open(config.QUALITY_REPORT_FILE) as f:
    quality = json.load(f)

# ---------------------------------------------------------------- header ---
st.title("📊 Sales Data ETL Pipeline — Live Dashboard")
st.caption(
    "CSV + REST API sources → Python/Pandas/PySpark cleaning → data quality checks → "
    "SQL warehouse. This dashboard reads directly from the pipeline's output tables."
)

# ------------------------------------------------------------------ KPIs ---
fact = tables["fact"]
total_revenue = fact.loc[fact["has_valid_product"] == 1, "revenue"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"₹{total_revenue:,.0f}")
c2.metric("Clean Transactions Loaded", f"{len(fact):,}")
c3.metric("Products in Catalog", f"{len(tables['products']):,}")
c4.metric("Data Quality Status", quality["overall_status"])

st.divider()

# --------------------------------------------------------------- charts ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Revenue by Category")
    fig = px.bar(
        tables["by_category"], x="category", y="revenue",
        color_discrete_sequence=["#1F3864"],
    )
    fig.update_layout(xaxis_title="", yaxis_title="Revenue (₹)")
    st.plotly_chart(fig, width='stretch')

with col2:
    st.subheader("Revenue by Region")
    fig = px.bar(
        tables["by_region"], x="region", y="revenue",
        color_discrete_sequence=["#2E5090"],
    )
    fig.update_layout(xaxis_title="", yaxis_title="Revenue (₹)")
    st.plotly_chart(fig, width='stretch')

st.subheader("Monthly Revenue Trend")
fig = px.line(
    tables["by_month"], x="order_month", y="revenue", markers=True,
    color_discrete_sequence=["#1F3864"],
)
fig.update_layout(xaxis_title="Month", yaxis_title="Revenue (₹)")
st.plotly_chart(fig, width='stretch')

st.divider()

# --------------------------------------------------------- data quality ---
st.subheader("🔍 Data Quality Report")
qc1, qc2, qc3 = st.columns(3)
qc1.write("**Null checks**")
qc1.json(quality["null_checks"])
qc2.write("**Range checks**")
qc2.json(quality["range_checks"])
qc3.write("**Referential integrity**")
qc3.json(quality["referential_integrity"])

st.divider()

# ------------------------------------------------------------ raw table ---
st.subheader("Fact Table Sample")
st.dataframe(fact.head(200), width='stretch')

st.caption(
    "Source code: extract.py (CSV + REST API w/ cache fallback) → transform.py "
    "(cleaning, dedup, join) → data_quality.py (validation) → load.py (SQLAlchemy warehouse load)."
)
