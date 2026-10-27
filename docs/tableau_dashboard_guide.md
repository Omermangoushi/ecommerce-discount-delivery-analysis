# Tableau Public Dashboard: Click-by-Click Guide

You'll build a one-page dashboard with three charts, one per business question:

| # | Sheet name | Answers | Data file |
|---|---|---|---|
| 1 | Discount vs Margin | Q1: at what discount does a sale stop making money? | `tableau/order_lines_clean.csv` |
| 2 | Category Volume vs Margin | Q2: which categories sell a lot but earn little? | `tableau/order_lines_clean.csv` |
| 3 | Lateness vs Rating | Q3: does slower delivery lower ratings? | `tableau/orders_delivery_clean.csv` |

**Before you start:** run `python scripts/05_export_tableau.py` so both CSVs exist, and install the free
**Tableau Public** desktop app (public.tableau.com → *Download the App*). You'll need a free Tableau Public account at
the end to publish.

> **Why pre-cleaned files?** All cleaning (Completed orders only, recalculated profit, discount bands, days late) was
> done in Python/SQL. Tableau only aggregates and draws, so its numbers match the notebook and Excel exactly, and you
> can say so in an interview.

> **Field names:** Tableau turns `profit_before_tax` into **Profit Before Tax**, `discount_band` into
> **Discount Band**, and so on. The guide uses Tableau's names.

---

## Part 1: Connect the data

1. Open Tableau Public. On the start page, in the **Connect** pane on the left, under **To a File**, click
   **Text file**.
2. Browse to the project's `tableau` folder, select **`order_lines_clean.csv`**, and click **Open**.
3. The Data Source page shows a preview. Check that **Discount Pct**, **Revenue** and **Profit Before Tax** show a
   **#** icon (number). If one shows **Abc**, click the icon and choose **Number (decimal)**.
4. Add the second file: top menu **Data → New Data Source → Text file**, then pick **`orders_delivery_clean.csv`**.
5. In the preview, click the **#** icon above **Days Late** and make sure it is **Number (whole)**.
6. Click the **Sheet 1** tab at the bottom left to start building.

You can switch between the two data sources at the top of the **Data** pane on the left.

---

## Part 2: Chart 1 - Discount vs Margin (Q1)

*Goal: one bar per discount band showing profit margin, with the loss-making band in red.*

1. Double-click the **Sheet 1** tab and rename it **Discount vs Margin**.
2. At the top of the Data pane, make sure **order_lines_clean** is selected.
3. Create the margin measure: top menu **Analysis → Create Calculated Field…**
   * Name: `Profit Margin`
   * Formula: `SUM([Profit Before Tax]) / SUM([Revenue])`
   * Click **OK**.

   *Why SUM/SUM?* It gives the margin of the whole band (total profit ÷ total revenue). Averaging each line's own
   margin would give a tiny $5 line the same weight as a $5,000 line.
4. Format it as a percentage: in the Data pane, right-click **Profit Margin → Default Properties → Number Format… →
   Percentage**, set **Decimal places** to 1, then click **OK**.
5. Drag **Discount Band** (under Tables) to the **Columns** shelf.
   The bands sort alphabetically, which is already the right order (0%, 1-10%, 11-20%, …).
6. Drag **Profit Margin** to the **Rows** shelf. You now have a bar chart.
7. Colour the losses:
   * **Analysis → Create Calculated Field…**, name `Margin Result`, formula:
     `IF [Profit Margin] < 0 THEN "Loss" ELSE "Profit" END`, then **OK**.
   * Drag **Margin Result** onto **Color** on the Marks card.
   * Click **Color → Edit Colors…**, then set **Profit** to blue and **Loss** to red. Click **OK**.
8. Add value labels: drag **Profit Margin** onto **Label** on the Marks card.
9. Add context to the tooltip: drag **Quantity** onto **Tooltip**, then right-click that pill → **Measure → Average**.
   (Hovering now shows units per line, the "does volume make up for it?" evidence.)
10. Double-click the sheet title and type: **Profit margin falls with every discount band and turns negative above
    50%**.
11. Right-click the **Margin Result** colour legend → **Hide Card**. The red/blue is explained by the title and labels.

**What it shows:** margin falls from 48% (no discount) to 7% at 41-50% off and -19% at 51-60% off.

---

## Part 3: Chart 2 - Category Volume vs Margin (Q2)

*Goal: a scatter plot with one dot per category, average lines that split it into quadrants, and the "high volume,
low margin" categories highlighted.*

1. Click the **New Worksheet** icon (first icon right of the sheet tabs). Rename it **Category Volume vs Margin**.
2. Make sure **order_lines_clean** is still the selected data source.
3. Drag **Quantity** to **Columns**. It shows as `SUM(Quantity)` (total units sold).
4. Drag **Profit Margin** (from Chart 1) to **Rows**.
5. Drag **Product Category** onto **Detail** on the Marks card, which splits the single dot into 15 dots.
6. Drag **Product Category** onto **Label** as well. If some labels are hidden, click **Label** and tick **Allow labels
   to overlap other marks**.
7. On the Marks card, change the dropdown from **Automatic** to **Circle**. Click **Size** and drag the slider to
   about the middle.
8. Add the quadrant lines: click the **Analytics** tab (next to **Data**, top left), then drag **Average Line** onto
   the chart and drop it on **Table**. You get one line for average units and one for average margin.
9. Highlight the problem quadrant:
   * **Analysis → Create Calculated Field…**, name `Quadrant`, formula:
     ```
     IF SUM([Quantity]) >= WINDOW_AVG(SUM([Quantity]))
        AND [Profit Margin] < WINDOW_AVG([Profit Margin])
     THEN "High volume, low margin"
     ELSE "Other"
     END
     ```
   * Click **OK** and drag **Quadrant** onto **Color**.
   * Right-click the **Quadrant** pill on the Marks card → **Compute Using → Product Category**. This tells the
     `WINDOW_AVG` to average across all categories.
   * **Color → Edit Colors…**, then set "High volume, low margin" to orange and "Other" to grey.
10. Right-click the y-axis → **Edit Axis…**, untick **Include zero**, and close. Repeat for the x-axis. The dots spread
    out instead of bunching in one corner.
11. Title: **Four categories sell above average but earn below-average margins**.

**What it shows:** Sports & Outdoors, Health & Wellness, Automotive and Home Appliances sit in the bottom-right
quadrant.

---

## Part 4: Chart 3 - Lateness vs Rating (Q3)

*Goal: average rating for each "days late" value, with late deliveries in red.*

1. Create a **New Worksheet** and rename it **Lateness vs Rating**.
2. At the top of the Data pane, switch to the **orders_delivery_clean** data source.
3. Days Late needs to act as a category, not a number to add up: right-click **Days Late** in the Data pane →
   **Convert to Dimension**. Right-click it again → **Convert to Discrete**. The pill turns blue.
4. Drag **Days Late** to **Columns**.
5. Drag **Customer Rating** to **Rows**, then right-click the pill → **Measure (Sum) → Average**.
   *(Summing ratings is meaningless; we want the average.)*
6. Colour by lateness:
   * **Analysis → Create Calculated Field…**, name `Delivery Timing`, formula:
     ```
     IF [Days Late] > 0 THEN "Late"
     ELSEIF [Days Late] < 0 THEN "Early"
     ELSE "On time"
     END
     ```
   * Drag **Delivery Timing** onto **Color**. **Edit Colors…**: **Late** = red, **On time** = blue, **Early** = dark blue.
7. Drag **Customer Rating** onto **Label**, set it to **Average** as in step 5, then right-click the label pill →
   **Format…** and set **Numbers** to **Number (custom)** with 2 decimals.
8. Fix the axis: right-click the y-axis → **Edit Axis…** → **Range: Fixed**, Start **1**, End **4.5** (1 is the
   lowest possible rating). Add an axis title: **Average rating (1-5)**.
9. Add the count to the tooltip: drag **Order Id** onto **Tooltip** → right-click → **Measure → Count (Distinct)**.
10. Title: **Ratings drop half a star as soon as an order is late, whatever the delivery speed**.

**Optional extra (strong interview point):** duplicate the sheet (right-click tab → **Duplicate**), replace **Days
Late** on Columns with **Shipping Method**, and remove **Delivery Timing** from Color. All four methods score about 3.68,
even though Economy takes 7.7 days and Same Day 0.8 days. That proves it is lateness, not slowness, that hurts ratings.

**What it shows:** about 4.0 stars when early, 3.73 when on time, and 3.22 at 1, 2, 3 or 4 days late.

---

## Part 5: Assemble the dashboard

1. Click the **New Dashboard** icon (second icon right of the sheet tabs).
2. In the **Dashboard** pane on the left, under **Size**, choose **Fixed size → Generic Desktop (1366 x 768)**.
3. Tick **Show dashboard title** at the bottom of the Dashboard pane. Double-click the title and enter:
   **Do Discounts and Delivery Help or Hurt the Business?**
4. Drag the sheets from the **Sheets** list onto the canvas:
   * **Discount vs Margin** first. It fills the canvas.
   * **Lateness vs Rating**: drop it on the **right half** of the first chart (watch for the grey shaded preview).
   * **Category Volume vs Margin**: drop it along the **bottom edge** so it spans the full width.
5. Tidy up: click each chart's legend on the dashboard, click its **x** to remove it (colours are explained in the
   titles), and keep the Quadrant legend if you like.
6. Add the data note: from **Objects** (bottom left), drag **Text** to the very bottom of the dashboard and type:
   *Simulated e-commerce data (138k orders, 2021-2025). Completed orders only. Profit = revenue after discount minus
   product cost, before tax.*
7. *Optional interactivity:* click **Category Volume vs Margin** on the dashboard, open its drop-down arrow (top right
   of the chart) and choose **Use as Filter**. Clicking a category now filters the discount chart, since both use the
   same data source.
8. Rename the dashboard tab **Discount & Delivery Dashboard**.

---

## Part 6: Publish

1. **File → Save to Tableau Public As…**
2. Sign in with your Tableau Public account when prompted (you do this yourself).
3. Name the workbook **E-Commerce Discount and Delivery Analysis** and click **Save**.
4. Your browser opens the published dashboard. Copy the URL and paste it into the README under **Tableau dashboard**.
5. Optional: on your Tableau Public profile, open the workbook's settings and turn on **Allow others to download** so
   reviewers can inspect your calculated fields.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| A number column shows **Abc** | Data Source page → click the type icon → Number (decimal) |
| Bands appear in a strange order | Right-click **Discount Band** on Columns → **Sort… → Alphabetic, Ascending** |
| Chart 2 colours everything "Other" | Check step 9: the Quadrant pill must use **Compute Using → Product Category** |
| Chart 3 shows one huge bar | **Days Late** is still a measure: Convert to Dimension, then Convert to Discrete |
| Ratings look like thousands | The Customer Rating pill is set to SUM; change it to **Average** |

## Explaining it in an interview

* **Why three charts?** One per business question, so each chart has one clear message, stated in its title.
* **Why calculate margin as SUM ÷ SUM?** It weights each sale by its size. An average of percentages would overweight
  small orders.
* **Why WINDOW_AVG in the quadrant field?** The averages must be across categories, after Tableau has aggregated
  each category. That is exactly what a table calculation does.
* **Why does the rating axis start at 1?** Ratings can't go below 1, so 1 is the true floor of the scale. The labels
  show the exact values.
