"""
Stage 5 - Clean CSV exports for Tableau
=======================================

Tableau works best with tidy, row-level files that already have the
cleaning decisions baked in, so Tableau only has to aggregate and draw.
The rows come straight from the SQLite database (Stage 2), so Tableau shows
the same numbers as SQL, pandas and Excel.

  tableau/order_lines_clean.csv     one row per completed order line (Q1 + Q2)
  tableau/orders_delivery_clean.csv one row per completed order (Q3)

Run (after 02_build_database.py):  python scripts/05_export_tableau.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tableau"
OUT.mkdir(exist_ok=True)
con = sqlite3.connect(ROOT / "data" / "ecommerce.db")

# Q1 + Q2: completed lines with corrected profit and discount band (from the view)
lines = pd.read_sql_query("""
    SELECT order_id,
           order_date,
           product_category,
           quantity,
           ROUND(discount_percentage * 100, 1) AS discount_pct,       -- 0-100 scale reads better in Tableau
           discount_band,
           ROUND(gross_sales, 2)               AS gross_sales,
           ROUND(discount_amount, 2)           AS discount_amount,
           ROUND(revenue, 2)                   AS revenue,
           ROUND(product_cost, 2)              AS product_cost,
           ROUND(profit_before_tax, 2)         AS profit_before_tax,
           CASE WHEN profit_before_tax < 0 THEN 'Loss' ELSE 'Profit' END AS line_result
    FROM v_completed_lines
""", con)

# Q3: completed orders with delivery measured against the promise
delivery = pd.read_sql_query("""
    SELECT order_id,
           order_date,
           shipping_method,
           warehouse,
           CAST(delivery_days AS INTEGER)                            AS delivery_days,
           CAST(estimated_delivery_days AS INTEGER)                  AS promised_days,
           CAST(delivery_days - estimated_delivery_days AS INTEGER)  AS days_late,
           delivery_status,
           customer_rating
    FROM orders
    WHERE order_status = 'Completed'
""", con)
con.close()

for name, df in [("order_lines_clean", lines), ("orders_delivery_clean", delivery)]:
    path = OUT / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"{path.relative_to(ROOT)}: {len(df):,} rows, {path.stat().st_size / 1e6:.1f} MB, nulls={df.isna().sum().sum()}")
