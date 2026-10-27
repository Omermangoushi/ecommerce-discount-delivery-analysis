"""
Stage 2 - Build the SQLite database and run the SQL analysis
============================================================

1. Creates data/ecommerce.db using the table design in sql/01_schema.sql
   (primary keys, foreign keys, indexes and a reusable view).
2. Loads the four raw CSV files into those tables.
3. Runs every query in sql/02_analysis_queries.sql and saves each result
   to outputs/sql_results/<query name>.csv.

SQLite is a full SQL database stored in a single file - no server needed,
and it ships with Python.

Run:  python scripts/02_build_database.py
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "ecommerce.db"
SQL = ROOT / "sql"
RESULTS = ROOT / "outputs" / "sql_results"

# Columns kept from the wide raw orders file (customer details live in customers;
# sales/marketing channel columns are out of scope)
ORDER_COLUMNS = {
    "order_id": "order_id", "order_date": "order_date", "order_status": "order_status",
    "customer_id": "customer_id", "customer_type": "customer_type", "payment_status": "payment_status",
    "currency": "currency", "shipping_method": "shipping_method", "warehouse": "warehouse",
    "delivery_days": "delivery_days", "estimated_delivery_days": "estimated_delivery_days",
    "delivery_status": "delivery_status", "return_status": "return_status", "return_reason": "return_reason",
    "customer_rating": "customer_rating", "review_sentiment": "review_sentiment",
    "gross_sales": "header_gross_sales", "quantity": "header_quantity",
}

# --- 1. Create the empty tables -------------------------------------------
DB.unlink(missing_ok=True)
con = sqlite3.connect(DB)
con.executescript((SQL / "01_schema.sql").read_text(encoding="utf-8"))

# --- 2. Load the CSVs (parents first, so foreign keys are satisfied) -------
products = pd.read_csv(RAW / "product_catalog.csv")
customers = pd.read_csv(RAW / "customer_master.csv", dtype={"customer_postal_code": str})
orders = pd.read_csv(RAW / "orders.csv", usecols=list(ORDER_COLUMNS)).rename(columns=ORDER_COLUMNS)
items = pd.read_csv(RAW / "order_items.csv")
items.insert(0, "line_id", range(1, len(items) + 1))

for name, df in [("products", products), ("customers", customers), ("orders", orders), ("order_items", items)]:
    df.to_sql(name, con, if_exists="append", index=False)  # append = keep the table design from schema.sql
    print(f"Loaded {name:<12} {len(df):>8,} rows")

broken = con.execute("PRAGMA foreign_key_check").fetchall()
print(f"Foreign key violations: {len(broken)}")
con.commit()

# --- 3. Run each named query and save the result ---------------------------
text = (SQL / "02_analysis_queries.sql").read_text(encoding="utf-8")
blocks = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
queries = dict(zip(blocks[1::2], blocks[2::2]))  # {name: sql}

RESULTS.mkdir(parents=True, exist_ok=True)
for name, sql in queries.items():
    sql = sql.split("-- ----")[0]  # stop at the next section divider
    result = pd.read_sql_query(sql, con)
    result.to_csv(RESULTS / f"{name}.csv", index=False)
    print(f"\n== {name}\n{result.to_string(index=False)}")

con.close()
print(f"\nDatabase: {DB.relative_to(ROOT)}  |  {len(queries)} query results in {RESULTS.relative_to(ROOT)}")
