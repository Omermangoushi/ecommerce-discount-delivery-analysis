# Do Discounts and Delivery Help or Hurt the Business?

*One-page summary · E-Commerce Sales Analytics · **simulated data** (138,116 orders, 2021-2025)*

## Problem
An online retailer wants to know whether its **discounting** and **delivery performance** help or hurt the business.
Three questions: (1) At what discount does a sale stop making money, and does extra volume make up for it?
(2) Which categories sell a lot but earn little? (3) Does slower delivery lead to lower customer ratings?

## Method
1. **Data quality check (Python).** 39 checks on four linked tables (orders, order items, products, customers). The
   data links cleanly, but three issues changed the analysis: the supplied profit counts **sales tax as profit**, 8% of
   order headers **don't match their line items**, and discounts were **wiped on cancelled/returned orders**. So
   profit was recalculated as *revenue after discount − product cost*, all money comes from line items, and only the
   113,559 completed orders were analysed.
2. **SQL (SQLite).** Database with keys and a reusable view; 13 queries using joins, CTEs and window functions.
3. **pandas notebook.** Repeated the analysis, built the charts, and cross-checked against SQL (identical results).
4. **Excel and Tableau** summaries for business readers.

## Findings and recommendations

**1. Discounts above about 30% destroy profit, and extra volume doesn't make up for it.**
A line loses money exactly when its discount is bigger than the product's own margin (true for all 327,028 lines).
Margin falls from 45.5% at 1-10% off to 21.3% at 31-40%, 6.8% at 41-50%, and **−18.8% above 50%** (61% of those lines
lose money). Deep discounts do sell more, about **1.75×** the units per line, but at 41-50% off a line would need
**11.5×** the units to earn what a lightly discounted line earns.
**→ Recommendation:** cap each product's discount below its own margin (with a buffer), and keep blanket promotions at
**30% or less**. Treat 50%+ discounts as a deliberate loss (e.g. clearance), not a growth tool.

**2. Four high-volume categories earn thin margins because of cost, not discounts.**
**Sports & Outdoors** (#1 by units), **Health & Wellness**, **Automotive** and **Home Appliances** sell more than the
average category but earn 32-40% margins, compared with 51-54% for Books and Grocery. Every category gets about the same
19% average discount, so the gap comes from product cost relative to price (correlation with list margin: 1.00).
*Caveat: volumes are fairly even across categories in this simulated data (41k-54k units).*
**→ Recommendation:** renegotiate supplier costs or review prices in these four categories first, and leave them out
of deep promotions, where their thin margins turn into losses fastest.

**3. Late delivery hurts ratings; slow delivery doesn't.**
Late orders (15% of completed orders) average **3.22** stars, compared with **3.73** on time and **4.02** early, and
26.5% of late orders are rated below 3 (vs 3.8% on time). Total delivery time barely matters: **Economy (7.7 days)
rates 3.67, the same as Same Day (0.8 days)**, because both are late about 15% of the time. Being 1 day late hurts as
much as 4 days late. Delays are spread evenly across all 19 warehouses (14-16%).
**→ Recommendation:** promise realistic delivery dates (add a buffer to the estimate), make the **on-time rate** a
tracked KPI, and fix the date-promising process rather than one warehouse. There's no need to pay for faster shipping
methods to protect ratings.

## Limitations
The data is **simulated**, so it shows the method rather than a real company's results. The analysis is
correlational (no A/B test). The effect of discounts on returns can't be measured because discounts were wiped on
returned orders.
