"""
Stage 4 - Excel summary workbook
================================

Builds outputs/ecommerce_summary.xlsx for a business reader who doesn't use
Python or SQL. Every table is read from the SQL results produced in Stage 2,
so the workbook always matches the database.

Sheets
  Summary         headline KPIs, the three findings and recommendations
  Discount Bands  Q1 table + a native Excel bar chart of margin by discount band
  Categories      Q2 volume vs margin table
  Delivery        Q3 rating tables

Run (after 02_build_database.py):  python scripts/04_build_excel_summary.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.marker import DataPoint
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "outputs" / "sql_results"
OUT = ROOT / "outputs" / "ecommerce_summary.xlsx"

BLUE, RED, INK, MUTED, LIGHT = "2A78D6", "E34948", "0B0B0B", "52514E", "EEF4FC"
TITLE = Font(size=16, bold=True, color=INK)
H2 = Font(size=12, bold=True, color=INK)
NOTE = Font(size=9, italic=True, color=MUTED)
HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor=BLUE)
BAND_FILL = PatternFill("solid", fgColor=LIGHT)
THIN = Border(bottom=Side(style="thin", color="D9D9D9"))
WRAP = Alignment(wrap_text=True, vertical="top")


def load(name):
    return pd.read_csv(RESULTS / f"{name}.csv")


def write_table(ws, df, top, left=1, formats=None, headers=None):
    """Write a DataFrame as a formatted table; returns the last row used."""
    formats = formats or {}
    for j, col in enumerate(df.columns):
        cell = ws.cell(row=top, column=left + j, value=(headers or {}).get(col, col))
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, (col, value) in enumerate(zip(df.columns, row)):
            cell = ws.cell(row=top + i, column=left + j, value=None if pd.isna(value) else value)
            cell.border = THIN
            if col in formats:
                cell.number_format = formats[col]
    return top + len(df)


def set_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


wb = Workbook()

# ---------------------------------------------------------------------------
# Summary sheet
# ---------------------------------------------------------------------------
ws = wb.active
ws.title = "Summary"
con = sqlite3.connect(ROOT / "data" / "ecommerce.db")
kpi = con.execute("""
    SELECT COUNT(DISTINCT order_id), SUM(revenue), SUM(profit_before_tax), SUM(profit_before_tax) / SUM(revenue)
    FROM v_completed_lines""").fetchone()
rating, delayed = con.execute("""
    SELECT AVG(customer_rating), AVG(delivery_status = 'Delayed') FROM orders WHERE order_status = 'Completed'""").fetchone()
con.close()

ws["A1"] = "E-Commerce Discount & Delivery Analysis"
ws["A1"].font = TITLE
ws["A2"] = "Simulated dataset, 2021-2025. Completed orders only; profit = revenue after discount minus product cost (before tax)."
ws["A2"].font = NOTE

ws["A4"] = "Headline numbers"
ws["A4"].font = H2
kpis = [("Completed orders", kpi[0], "#,##0"), ("Revenue (after discounts)", kpi[1], "$#,##0"),
        ("Profit before tax", kpi[2], "$#,##0"), ("Profit margin", kpi[3], "0.0%"),
        ("Average customer rating (1-5)", rating, "0.00"), ("Orders delivered late", delayed, "0.0%")]
for i, (label, value, fmt) in enumerate(kpis, start=5):
    ws.cell(row=i, column=1, value=label).border = THIN
    c = ws.cell(row=i, column=2, value=value)
    c.number_format, c.font, c.border = fmt, Font(bold=True), THIN

q1 = load("q01_discount_band_summary").set_index("discount_band")
q4 = load("q04_volume_compensation").set_index("discount_band")
q5 = load("q05_category_volume_vs_margin")
q9 = load("q09_rating_by_delivery_status").set_index("delivery_status")
hvlm = ", ".join(q5.loc[q5.quadrant == "High volume, low margin", "product_category"])

ws["A12"] = "Findings and recommendations"
ws["A12"].font = H2
findings = [
    ("Q1. When does a discount stop paying?",
     f"Lines lose money once the discount is bigger than the product's margin (from about 30% off). Margin falls from "
     f"{q1.loc['1-10%', 'margin_pct']:.1f}% at 1-10% off to {q1.loc['41-50%', 'margin_pct']:.1f}% at 41-50% and "
     f"{q1.loc['51-60%', 'margin_pct']:.1f}% above 50%. Lines at 41-50% off sell {q4.loc['41-50%', 'units_actual_x']:.2f}x "
     f"the units of a 1-10% line, but would need {q4.loc['41-50%', 'units_needed_x']:.1f}x to earn the same profit. "
     "Volume does not make up for it.",
     "Cap each product's discount below its own margin, and keep blanket promotions at 30% or less."),
    ("Q2. Which categories sell a lot but earn little?",
     f"{hvlm} sell more units than average but earn below-average margins. Every category gets about a 19% average "
     "discount, so the cause is product cost / pricing, not discounting.",
     "Renegotiate supplier costs or adjust prices in these categories, and leave them out of deep promotions."),
    ("Q3. Does slower delivery lower ratings?",
     f"Lateness does, speed doesn't. Late orders average {q9.loc['Delayed', 'avg_rating']:.2f} stars vs "
     f"{q9.loc['On Time', 'avg_rating']:.2f} on time and {q9.loc['Early', 'avg_rating']:.2f} early. Economy (7.7 days) "
     "rates the same as Same Day (0.8 days).",
     "Build a buffer into promised delivery dates and track the on-time rate as a KPI."),
]
for col, head in enumerate(["Question", "Finding", "Recommendation"], start=1):
    c = ws.cell(row=13, column=col, value=head)
    c.font, c.fill = HEADER_FONT, HEADER_FILL
for i, row in enumerate(findings, start=14):
    for j, text in enumerate(row, start=1):
        c = ws.cell(row=i, column=j, value=text)
        c.alignment, c.border = WRAP, THIN
    ws.cell(row=i, column=1).font = Font(bold=True)
    ws.row_dimensions[i].height = 92
set_widths(ws, [32, 70, 45])

# ---------------------------------------------------------------------------
# Discount Bands sheet (with the chart)
# ---------------------------------------------------------------------------
ws = wb.create_sheet("Discount Bands")
ws["A1"] = "Q1. Profitability by discount band"
ws["A1"].font = TITLE
ws["A2"] = "Source: sql/02_analysis_queries.sql (q01, q04). Margin = profit / revenue after discount."
ws["A2"].font = NOTE

t = load("q01_discount_band_summary").merge(
    load("q04_volume_compensation")[["discount_band", "units_actual_x", "units_needed_x"]], on="discount_band")
t = t[["discount_band", "lines", "units_per_line", "revenue", "profit", "margin_pct", "loss_share_pct",
       "units_actual_x", "units_needed_x"]]
last = write_table(ws, t, top=4, formats={
    "lines": "#,##0", "units_per_line": "0.00", "revenue": "$#,##0", "profit": "$#,##0;[Red]-$#,##0",
    "margin_pct": '0.0"%";[Red]-0.0"%"', "loss_share_pct": '0.0"%"', "units_actual_x": '0.00"x"',
    "units_needed_x": '0.00"x"'}, headers={
    "discount_band": "Discount band", "lines": "Order lines", "units_per_line": "Units per line",
    "revenue": "Revenue", "profit": "Profit", "margin_pct": "Margin %", "loss_share_pct": "% of lines losing money",
    "units_actual_x": "Units sold vs 1-10%", "units_needed_x": "Units needed to match 1-10%"})
ws.cell(row=last + 1, column=9, value="blank = never (loses money on every unit)").font = NOTE
ws.row_dimensions[4].height = 45
set_widths(ws, [14, 12, 10, 14, 14, 10, 13, 13, 15])
ws.freeze_panes = "B5"

chart = BarChart()
chart.type = "col"
chart.title = "Profit margin by discount band"
chart.add_data(Reference(ws, min_col=6, min_row=4, max_row=last), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
series = chart.series[0]
series.graphicalProperties.solidFill = BLUE
series.graphicalProperties.line.noFill = True
series.invertIfNegative = False  # otherwise Excel draws negative bars hollow
for idx, margin in enumerate(t["margin_pct"]):
    if margin < 0:  # colour the loss-making band red
        pt = DataPoint(idx=idx, invertIfNegative=False)
        pt.graphicalProperties.solidFill = RED
        pt.graphicalProperties.line.noFill = True
        series.dPt.append(pt)
series.dLbls = DataLabelList()
series.dLbls.showVal = True
for flag in ("showSerName", "showCatName", "showLegendKey", "showPercent"):
    setattr(series.dLbls, flag, False)
chart.legend = None
chart.gapWidth = 60
chart.x_axis.delete = False
chart.y_axis.delete = False
chart.y_axis.majorGridlines = None
chart.x_axis.tickLblPos = "low"  # keep band labels below the negative bar
chart.height, chart.width = 8, 16
ws.add_chart(chart, f"A{last + 3}")

# ---------------------------------------------------------------------------
# Categories sheet
# ---------------------------------------------------------------------------
ws = wb.create_sheet("Categories")
ws["A1"] = "Q2. Volume vs margin by product category"
ws["A1"].font = TITLE
ws["A2"] = "High volume = more units than the average category; low margin = below the average category margin."
ws["A2"].font = NOTE
cat = load("q05_category_volume_vs_margin").merge(
    load("q06_category_margin_breakdown")[["product_category", "list_margin_pct"]], on="product_category")
cat = cat[["product_category", "units", "volume_rank", "revenue", "profit", "profit_per_unit",
           "list_margin_pct", "avg_discount_pct", "margin_pct", "quadrant"]]
last = write_table(ws, cat, top=4, formats={
    "units": "#,##0", "revenue": "$#,##0", "profit": "$#,##0", "profit_per_unit": "$#,##0.00",
    "list_margin_pct": '0.0"%"', "avg_discount_pct": '0.0"%"', "margin_pct": '0.0"%"'}, headers={
    "product_category": "Category", "units": "Units sold", "volume_rank": "Volume rank", "revenue": "Revenue",
    "profit": "Profit", "profit_per_unit": "Profit per unit", "list_margin_pct": "Margin before discount",
    "avg_discount_pct": "Avg discount", "margin_pct": "Margin earned", "quadrant": "Quadrant"})
for r in range(5, last + 1):
    if ws.cell(row=r, column=10).value == "High volume, low margin":
        for c in range(1, 11):
            ws.cell(row=r, column=c).fill = BAND_FILL
        ws.cell(row=r, column=10).font = Font(bold=True)
ws.row_dimensions[4].height = 32
set_widths(ws, [24, 11, 9, 13, 13, 11, 12, 10, 10, 27])
ws.freeze_panes = "B5"

# ---------------------------------------------------------------------------
# Delivery sheet
# ---------------------------------------------------------------------------
ws = wb.create_sheet("Delivery")
ws["A1"] = "Q3. Delivery performance vs customer rating"
ws["A1"].font = TITLE
ws["A2"] = "Completed orders only (the only orders with a rating). Days late = actual minus promised delivery days."
ws["A2"].font = NOTE

ws["A4"] = "By delivery status"
ws["A4"].font = H2
last = write_table(ws, load("q09_rating_by_delivery_status"), top=5, formats={
    "orders": "#,##0", "share_pct": '0.0"%"', "avg_rating": "0.00", "pct_ratings_below_3": '0.0"%"'}, headers={
    "delivery_status": "Delivery status", "orders": "Orders", "share_pct": "Share of orders",
    "avg_rating": "Avg rating", "pct_ratings_below_3": "% rated below 3"})

top = last + 3
ws.cell(row=top - 1, column=1, value="By days late").font = H2
last = write_table(ws, load("q08_rating_by_days_late"), top=top, formats={"orders": "#,##0", "avg_rating": "0.00"},
                   headers={"days_late": "Days late", "orders": "Orders", "avg_rating": "Avg rating"})

top = last + 3
ws.cell(row=top - 1, column=1, value="By shipping method - slow methods are NOT rated lower").font = H2
write_table(ws, load("q10_rating_by_shipping_method"), top=top, formats={
    "orders": "#,##0", "avg_delivery_days": "0.0", "delayed_pct": '0.0"%"', "avg_rating": "0.00"}, headers={
    "shipping_method": "Shipping method", "orders": "Orders", "avg_delivery_days": "Avg delivery days",
    "delayed_pct": "% delayed", "avg_rating": "Avg rating"})
set_widths(ws, [18, 11, 14, 11, 14])

OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print(f"Saved {OUT.relative_to(ROOT)}")
