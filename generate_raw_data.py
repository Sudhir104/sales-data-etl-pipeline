"""
Generates a realistic, intentionally-messy raw sales transactions CSV
(duplicates, nulls, bad types, negative values) so the pipeline has
real cleaning/validation work to do -- exactly like real-world source data.

Run once: python generate_raw_data.py
"""
import numpy as np
import pandas as pd
import random
import json

random.seed(42)
np.random.seed(42)

N = 3000
regions = ["North", "South", "East", "West", "Central"]
payment_methods = ["Credit Card", "Debit Card", "UPI", "Net Banking", "Cash on Delivery", None]
product_ids = [f"P{str(i).zfill(4)}" for i in range(1, 61)]
customer_ids = [f"C{str(i).zfill(5)}" for i in range(1, 901)]

dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")

rows = []
for i in range(1, N + 1):
    txn_id = f"TXN{str(i).zfill(6)}"
    order_date = str(random.choice(dates).date())
    customer_id = random.choice(customer_ids)
    product_id = random.choice(product_ids)
    quantity = random.choice([1, 1, 2, 2, 3, 4, 5, -1, 0])  # -1/0 are bad data
    unit_price = round(random.uniform(99, 4999), 2)
    region = random.choice(regions)
    payment_method = random.choice(payment_methods)  # includes None ~1/6 of the time

    rows.append([txn_id, order_date, customer_id, product_id, quantity, unit_price, region, payment_method])

df = pd.DataFrame(rows, columns=[
    "transaction_id", "order_date", "customer_id", "product_id",
    "quantity", "unit_price", "region", "payment_method"
])

# Inject duplicate rows (real pipelines see these from retries / re-syncs)
dupes = df.sample(120, random_state=1)
df = pd.concat([df, dupes], ignore_index=True)

# Inject a few rows with missing critical fields
missing_idx = df.sample(40, random_state=2).index
df.loc[missing_idx, "unit_price"] = np.nan

missing_idx2 = df.sample(25, random_state=3).index
df.loc[missing_idx2, "customer_id"] = None

# Inject a few malformed dates and prices (as raw strings would look from a bad export)
malformed_idx = df.sample(15, random_state=4).index
df.loc[malformed_idx, "order_date"] = "N/A"

malformed_price_idx = df.sample(10, random_state=5).index
df["unit_price"] = df["unit_price"].astype(object)
df.loc[malformed_price_idx, "unit_price"] = "unknown"

# Inject product_ids that don't exist in the product master (referential integrity issue)
bad_product_idx = df.sample(20, random_state=6).index
df.loc[bad_product_idx, "product_id"] = "P9999"

df = df.sample(frac=1, random_state=7).reset_index(drop=True)  # shuffle
df.to_csv("data/raw/sales_transactions.csv", index=False)
print(f"Wrote data/raw/sales_transactions.csv with {len(df)} rows")

# ---- Cached "REST API" product master (mirrors a public products API response shape) ----
categories = ["Electronics", "Home & Kitchen", "Fashion", "Sports", "Books", "Beauty"]
brands = ["Nova", "Zentra", "Uplift", "Ember", "Wayfound", "Lumo"]

products = []
for i in range(1, 61):
    products.append({
        "id": f"P{str(i).zfill(4)}",
        "title": f"{random.choice(brands)} {random.choice(['Pro', 'Max', 'Air', 'Lite', 'Plus'])} {i}",
        "category": random.choice(categories),
        "price": round(random.uniform(99, 4999), 2),
        "rating": round(random.uniform(2.5, 5.0), 1),
        "brand": random.choice(brands),
    })

with open("data/raw/products_api_cache.json", "w") as f:
    json.dump(products, f, indent=2)
print(f"Wrote data/raw/products_api_cache.json with {len(products)} products")
