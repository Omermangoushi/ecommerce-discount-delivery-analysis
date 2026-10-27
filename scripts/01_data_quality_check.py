"""
Stage 1 - Data quality check
============================

Before analysing anything we check that the data can be trusted.
Each check below answers one simple question ("are there duplicates?",
"do the numbers add up?") and gets a status:

    PASS  - nothing wrong
    INFO  - something unusual, but expected / harmless
    WARN  - a real problem; the "Decision" column says how we handle it

The results are printed and saved to reports/data_quality_report.md.

Run:  python scripts/01_data_quality_check.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "reports" / "data_quality_report.md"

TOLERANCE = 0.05  # money values are rounded to cents, so allow a few cents of rounding error

results = []  # one row per check: (area, check, status, finding, decision)


def record(area, check, status, finding, decision="-"):
    results.append((area, check, status, finding, decision))
    print(f"[{status:4}] {area:<10} {check}: {finding}")


def pct(x):
    return f"{x:.1%}"


# ---------------------------------------------------------------------------
# Load the four tables
# ---------------------------------------------------------------------------
orders = pd.read_csv(RAW / "orders.csv")
items = pd.read_csv(RAW / "order_items.csv")
products = pd.read_csv(RAW / "product_catalog.csv")
customers = pd.read_csv(RAW / "customer_master.csv")

tables = {"orders": orders, "order_items": items, "products": products, "customers": customers}

# ---------------------------------------------------------------------------
# 1. Size and duplicates
# ---------------------------------------------------------------------------
for name, df in tables.items():
    record("Structure", f"{name} size", "INFO", f"{len(df):,} rows x {df.shape[1]} columns")

for name, df in tables.items():
    dups = df.duplicated().sum()
    record("Duplicates", f"{name} fully duplicated rows",
           "PASS" if dups == 0 else "WARN", f"{dups:,} duplicate rows")

# Primary keys: each ID should appear once in its own table
for name, df, key in [("orders", orders, "order_id"), ("products", products, "product_id"),
                      ("customers", customers, "customer_id")]:
    dups = df[key].duplicated().sum()
    record("Duplicates", f"{name}.{key} is unique", "PASS" if dups == 0 else "WARN", f"{dups:,} repeated IDs")

dups = items.duplicated(["order_id", "product_id"]).sum()
record("Duplicates", "order_items (order_id, product_id) is unique",
       "PASS" if dups == 0 else "INFO",
       f"{dups:,} orders list the same product on two lines (different quantities, not copies)",
       "Keep them; give each line its own line_id in the database")

# ---------------------------------------------------------------------------
# 2. Missing values - and whether they are *expected* to be missing
# ---------------------------------------------------------------------------
for name, df in tables.items():
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if missing.empty:
        record("Missing", f"{name} missing values", "PASS", "no missing values")

missing = orders.isna().sum()
missing = missing[missing > 0]
record("Missing", "orders columns with blanks", "INFO",
       ", ".join(f"{c} ({n:,})" for c, n in missing.items()))

# Delivery and rating fields should only be blank when the order never completed
delivery_cols = ["delivery_days", "estimated_delivery_days", "customer_rating"]
blank = orders[delivery_cols].isna().any(axis=1)
statuses_when_blank = sorted(orders.loc[blank, "order_status"].unique())
completed_blank = (blank & (orders["order_status"] == "Completed")).sum()
record("Missing", "delivery/rating blank only for non-completed orders",
       "PASS" if completed_blank == 0 else "WARN",
       f"blank for statuses {statuses_when_blank}; {completed_blank} completed orders are blank",
       "Delivery and rating analysis uses Completed orders only")

# return_status is only filled in for returned orders (as stated in the data notes)
mismatch = (orders["return_status"].notna() != (orders["order_status"] == "Returned")).sum()
record("Missing", "return_status filled only for Returned orders",
       "PASS" if mismatch == 0 else "WARN",
       f"{orders['return_status'].notna().sum():,} filled, {mismatch} inconsistent rows",
       "Blanks mean 'Not Returned'; filled in that way in the cleaned exports")

record("Missing", "campaign_name / coupon_code blanks", "INFO",
       "Blank simply means no campaign or coupon was used", "Not used in this analysis")

# ---------------------------------------------------------------------------
# 3. Do the tables link up? (referential integrity)
# ---------------------------------------------------------------------------
checks = [
    ("every order_items.order_id exists in orders", ~items["order_id"].isin(orders["order_id"])),
    ("every order has at least one item", ~orders["order_id"].isin(items["order_id"])),
    ("every order_items.product_id exists in products", ~items["product_id"].isin(products["product_id"])),
    ("every orders.customer_id exists in customers", ~orders["customer_id"].isin(customers["customer_id"])),
]
for label, broken in checks:
    record("Joins", label, "PASS" if broken.sum() == 0 else "WARN", f"{broken.sum():,} unmatched rows")

# ---------------------------------------------------------------------------
# 4. Are values in sensible ranges?
# ---------------------------------------------------------------------------
d = items["discount_percentage"]
ok = d.between(0, 1).all()
record("Ranges", "discount_percentage is a 0-1 fraction", "PASS" if ok else "WARN",
       f"min {d.min():.2f}, max {d.max():.2f}, mean {d.mean():.3f} (0.15 = 15% off)",
       "Multiply by 100 only when labelling charts")
record("Ranges", "discount cap", "INFO",
       f"{(d.round(4) == 0.60).sum():,} lines sit exactly at 60% - looks like a maximum-discount cap")

r = orders["customer_rating"].dropna()
record("Ranges", "customer_rating between 1 and 5", "PASS" if r.between(1, 5).all() else "WARN",
       f"min {r.min()}, max {r.max()}, mean {r.mean():.2f}")

for col in ["quantity", "unit_price", "product_cost"]:
    bad = (items[col] <= 0).sum()
    record("Ranges", f"order_items.{col} > 0", "PASS" if bad == 0 else "WARN", f"{bad:,} rows <= 0")

dd = orders["delivery_days"].dropna()
record("Ranges", "delivery_days >= 0", "PASS" if (dd >= 0).all() else "WARN",
       f"range {dd.min():.0f}-{dd.max():.0f} days")

dates = pd.to_datetime(orders["order_date"], errors="coerce")
record("Ranges", "order_date parses as a date", "PASS" if dates.notna().all() else "WARN",
       f"{dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}, {dates.isna().sum()} unparseable")

# ---------------------------------------------------------------------------
# 5. Do the money columns add up? (line level)
# ---------------------------------------------------------------------------
def share_off(actual, expected):
    return ((actual - expected).abs() > TOLERANCE).mean()

record("Maths", "gross_sales = quantity x unit_price",
       "PASS" if share_off(items.gross_sales, items.quantity * items.unit_price) == 0 else "WARN",
       f"{pct(share_off(items.gross_sales, items.quantity * items.unit_price))} of lines off")

off = ((items.discount_amount - items.gross_sales * items.discount_percentage).abs() > 0.5).mean()
record("Maths", "discount_amount = gross_sales x discount_percentage", "PASS" if off == 0 else "WARN",
       f"{pct(off)} of lines off - confirms discount_percentage is a fraction")

net_expected = items.gross_sales - items.discount_amount + items.tax_amount + items.shipping_cost
record("Maths", "net_sales = gross - discount + tax + shipping",
       "PASS" if share_off(items.net_sales, net_expected) == 0 else "WARN",
       f"{pct(share_off(items.net_sales, net_expected))} of lines off - so net_sales INCLUDES tax and shipping")

profit_expected = items.net_sales - items.product_cost - items.shipping_cost
off = share_off(items.profit, profit_expected)
record("Maths", "how the supplied profit column is calculated", "WARN",
       f"profit = net_sales - product_cost - shipping_cost ({pct(1 - off)} of lines match). "
       "Sales tax is therefore counted as profit, but tax is passed on to the government, not kept",
       "Use profit_before_tax = gross_sales - discount_amount - product_cost")

# Catalog prices should match what was charged
j = items.merge(products[["product_id", "unit_price", "product_cost"]], on="product_id", suffixes=("", "_cat"))
price_off = ((j.unit_price - j.unit_price_cat).abs() > 0.01).mean()
cost_off = ((j.product_cost - j.quantity * j.product_cost_cat).abs() > TOLERANCE).mean()
record("Maths", "line unit_price and cost match product_catalog",
       "PASS" if price_off == 0 and cost_off == 0 else "WARN",
       f"price off on {pct(price_off)}, cost off on {pct(cost_off)} of lines")

# ---------------------------------------------------------------------------
# 6. Does the order header agree with its line items?
# ---------------------------------------------------------------------------
line_totals = items.groupby("order_id")[["gross_sales", "quantity"]].sum()
cmp = orders.set_index("order_id")[["gross_sales", "quantity"]].join(line_totals, rsuffix="_lines")
bad = (cmp.gross_sales - cmp.gross_sales_lines).abs() > TOLERANCE
ratio = (cmp.gross_sales[bad] / cmp.gross_sales_lines[bad]).median()
record("Maths", "order header totals = sum of its line items", "WARN",
       f"{bad.sum():,} orders ({pct(bad.mean())}) disagree; on those, the header is a median "
       f"{ratio:.0%} of the line total",
       "Use order_items for every money figure; use orders only for status, delivery and rating")

# ---------------------------------------------------------------------------
# 7. Simulation quirks worth knowing about
# ---------------------------------------------------------------------------
j = items.merge(orders[["order_id", "currency", "order_status"]], on="order_id")
j = j.merge(products[["product_id", "unit_price"]], on="product_id", suffixes=("", "_cat"))
same_price = j.groupby("currency").apply(lambda g: (g.unit_price == g.unit_price_cat).mean(), include_groups=False)
record("Quirks", "currency column", "INFO",
       f"{orders.currency.nunique()} currencies, but prices are identical to the catalog in every one "
       f"(min match {same_price.min():.0%})",
       "Treat currency as a label only; all amounts are in one common unit")

zero_by_status = j.assign(zero=j.discount_percentage == 0).groupby("order_status")["zero"].mean()
record("Quirks", "discounts on cancelled / returned lines", "WARN",
       "share of lines with 0% discount: " + ", ".join(f"{s} {v:.0%}" for s, v in zero_by_status.items()),
       "Discount was wiped on cancelled/returned lines, so discount questions use Completed orders only")

# ---------------------------------------------------------------------------
# Write the markdown report
# ---------------------------------------------------------------------------
summary = pd.Series([r[2] for r in results]).value_counts()
lines = [
    "# Data Quality Report",
    "",
    "Generated by `scripts/01_data_quality_check.py`. Dataset is **simulated** e-commerce data.",
    "",
    f"**Checks run:** {len(results)}  |  " + "  |  ".join(f"**{k}:** {v}" for k, v in summary.items()),
    "",
    "| Area | Check | Status | Finding | Decision |",
    "|---|---|---|---|---|",
]
for area, check, status, finding, decision in results:
    lines.append(f"| {area} | {check} | {status} | {finding} | {decision} |")

lines += [
    "",
    "## What this means for the analysis",
    "",
    "1. **Money comes from `order_items`.** About 8% of order headers don't match their own line items, "
    "so line-level data is the single source of truth for revenue, discount and profit.",
    "2. **Profit is recalculated.** The supplied `profit` column counts sales tax as income. "
    "We use `profit_before_tax = gross_sales - discount_amount - product_cost` "
    "(shipping is charged to the customer and paid to the carrier, so it nets to zero).",
    "3. **Only Completed orders** are used for the discount and category questions (discounts were wiped on "
    "cancelled/returned lines) and for the delivery question (only completed orders have a delivery time and rating).",
    "4. **Blank `return_status` = not returned**, and currency is treated as a label.",
    "",
]
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text("\n".join(lines), encoding="utf-8")
print(f"\nSummary: {summary.to_dict()}")
print(f"Report written to {REPORT.relative_to(ROOT)}")
