-- =============================================================================
-- 02_analysis_queries.sql  -  SQL answers to the three business questions
-- =============================================================================
-- Business problem: does discounting and delivery performance help or hurt
-- the business?
--
-- Each query starts with a "-- name:" line. scripts/02_build_database.py uses
-- that line to run each query and save its result to
-- outputs/sql_results/<name>.csv, so every number here can be reproduced.
--
-- Conventions
--   * Money comes from order_items (line level). About 8% of order headers
--     don't match their own lines (see q00b).
--   * profit_before_tax = gross_sales - discount_amount - product_cost.
--   * Only Completed orders are analysed (via the view v_completed_lines).
--   * Margin = profit / revenue, where revenue = gross_sales - discount.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. SANITY CHECKS
-- -----------------------------------------------------------------------------

-- name: q00a_row_counts
-- How many rows landed in each table? Should match the CSV files.
SELECT 'orders'      AS table_name, COUNT(*) AS row_count FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'products',    COUNT(*) FROM products
UNION ALL SELECT 'customers',   COUNT(*) FROM customers;

-- name: q00b_header_vs_lines
-- Data-quality check written in SQL: compare each order header with the
-- sum of its line items. A CTE ("WITH ...") is a named temporary result
-- we can query like a table.
WITH line_totals AS (
    SELECT order_id, SUM(gross_sales) AS line_gross
    FROM order_items
    GROUP BY order_id
)
SELECT
    COUNT(*)                                                             AS orders,
    SUM(CASE WHEN ABS(o.header_gross_sales - lt.line_gross) > 0.05 THEN 1 ELSE 0 END) AS mismatched_orders,
    ROUND(100.0 * AVG(CASE WHEN ABS(o.header_gross_sales - lt.line_gross) > 0.05 THEN 1 ELSE 0 END), 1) AS pct_mismatched
FROM orders AS o
JOIN line_totals AS lt ON lt.order_id = o.order_id;


-- -----------------------------------------------------------------------------
-- Q1. AT WHAT DISCOUNT LEVEL DOES A SALE STOP MAKING MONEY,
--     AND DOES EXTRA VOLUME MAKE UP FOR IT?
-- -----------------------------------------------------------------------------

-- name: q01_discount_band_summary
-- Profitability of each 10-point discount band.
-- loss_share = share of lines in the band that lost money.
SELECT
    discount_band,
    COUNT(*)                                             AS lines,
    SUM(quantity)                                        AS units,
    ROUND(AVG(quantity), 2)                              AS units_per_line,
    ROUND(SUM(revenue), 0)                               AS revenue,
    ROUND(SUM(profit_before_tax), 0)                     AS profit,
    ROUND(100.0 * SUM(profit_before_tax) / SUM(revenue), 1) AS margin_pct,
    ROUND(SUM(profit_before_tax) / COUNT(*), 2)          AS profit_per_line,
    ROUND(100.0 * AVG(profit_before_tax < 0), 1)         AS loss_share_pct
FROM v_completed_lines
GROUP BY discount_band
ORDER BY MIN(discount_percentage);

-- name: q02_breakeven_5pt_bands
-- Finer 5-point bands to pin down where the average sale crosses zero.
-- CAST(x * 20 AS INTEGER) / 20.0 rounds the discount DOWN to the nearest 5%.
SELECT
    CAST(discount_percentage * 20 AS INTEGER) * 5        AS band_start_pct,
    COUNT(*)                                             AS lines,
    ROUND(100.0 * SUM(profit_before_tax) / SUM(revenue), 1) AS margin_pct,
    ROUND(100.0 * AVG(profit_before_tax < 0), 1)         AS loss_share_pct
FROM v_completed_lines
GROUP BY band_start_pct
ORDER BY band_start_pct;

-- name: q03_loss_rule_check
-- The rule behind the break-even: a line loses money exactly when its
-- discount is larger than the product's own margin. If the rule holds,
-- every row lands on the diagonal (TRUE/TRUE or FALSE/FALSE).
SELECT
    discount_percentage > list_margin   AS discount_exceeds_margin,
    profit_before_tax < 0               AS line_lost_money,
    COUNT(*)                            AS lines
FROM v_completed_lines
GROUP BY 1, 2;

-- name: q04_volume_compensation
-- Does extra volume make up for the lost margin?
-- Compare each band with the typical light discount (1-10%):
--   units_needed_x = how many times more units a line must sell to earn
--                    the same profit as a 1-10% line
--   units_actual_x = how many times more units it actually sells
-- If needed > actual, the extra volume does NOT pay for the discount.
WITH band AS (
    SELECT
        discount_band,
        MIN(discount_percentage)                     AS sort_key,
        AVG(quantity)                                AS units_per_line,
        SUM(profit_before_tax) / SUM(quantity)       AS profit_per_unit
    FROM v_completed_lines
    GROUP BY discount_band
),
baseline AS (
    SELECT units_per_line AS base_units, profit_per_unit AS base_ppu
    FROM band WHERE discount_band = '1-10%'
)
SELECT
    b.discount_band,
    ROUND(b.profit_per_unit, 2)                                  AS profit_per_unit,
    ROUND(b.units_per_line, 2)                                   AS units_per_line,
    ROUND(b.units_per_line / bl.base_units, 2)                   AS units_actual_x,
    CASE WHEN b.profit_per_unit > 0
         THEN ROUND(bl.base_ppu / b.profit_per_unit, 2)
    END                                                          AS units_needed_x,   -- NULL = never (loses money per unit)
    ROUND(b.units_per_line * b.profit_per_unit
          / (bl.base_units * bl.base_ppu) * 100, 0)              AS profit_per_line_vs_baseline_pct
FROM band AS b
CROSS JOIN baseline AS bl
ORDER BY b.sort_key;


-- -----------------------------------------------------------------------------
-- Q2. WHICH PRODUCT CATEGORIES SELL A LOT BUT EARN LITTLE?
-- -----------------------------------------------------------------------------

-- name: q05_category_volume_vs_margin
-- Units sold vs profit margin per category. Window functions
-- (RANK() OVER, AVG() OVER) compare each category with all the others
-- without collapsing the rows.
WITH cat AS (
    SELECT
        product_category,
        SUM(quantity)                                 AS units,
        SUM(revenue)                                  AS revenue,
        SUM(profit_before_tax)                        AS profit,
        SUM(profit_before_tax) / SUM(revenue)         AS margin,
        SUM(discount_amount) / SUM(gross_sales)       AS avg_discount
    FROM v_completed_lines
    GROUP BY product_category
)
SELECT
    product_category,
    units,
    RANK() OVER (ORDER BY units DESC)                 AS volume_rank,
    ROUND(revenue, 0)                                 AS revenue,
    ROUND(profit, 0)                                  AS profit,
    ROUND(profit / units, 2)                          AS profit_per_unit,   -- second meaning of "earns little": $ per item
    ROUND(100 * margin, 1)                            AS margin_pct,
    RANK() OVER (ORDER BY margin ASC)                 AS low_margin_rank,   -- 1 = thinnest margin
    ROUND(100 * avg_discount, 1)                      AS avg_discount_pct,
    CASE
        WHEN units >= AVG(units) OVER () AND margin < AVG(margin) OVER () THEN 'High volume, low margin'
        WHEN units >= AVG(units) OVER ()                                   THEN 'High volume, healthy margin'
        WHEN margin <  AVG(margin) OVER ()                                 THEN 'Low volume, low margin'
        ELSE                                                                    'Low volume, healthy margin'
    END                                               AS quadrant
FROM cat
ORDER BY units DESC;

-- name: q06_category_margin_breakdown
-- WHY is a category's margin thin? Split the gap between list margin
-- (price vs cost, before discounts) and the margin actually earned.
-- A low list margin = cost problem; a big drop = discount problem.
SELECT
    product_category,
    ROUND(100.0 * (1 - SUM(product_cost) / SUM(gross_sales)), 1)          AS list_margin_pct,
    ROUND(100.0 * SUM(profit_before_tax) / SUM(revenue), 1)               AS earned_margin_pct,
    ROUND(100.0 * SUM(discount_amount) / SUM(gross_sales), 1)             AS avg_discount_pct,
    ROUND(100.0 * AVG(discount_percentage > list_margin), 1)              AS pct_lines_discounted_below_cost
FROM v_completed_lines
GROUP BY product_category
ORDER BY earned_margin_pct;


-- -----------------------------------------------------------------------------
-- Q3. DOES SLOWER DELIVERY LEAD TO LOWER CUSTOMER RATINGS?
-- -----------------------------------------------------------------------------
-- Ratings and delivery times only exist for Completed orders, and both live
-- on the orders table, so these queries need no join.

-- name: q07_rating_by_delivery_days
-- Raw delivery time vs rating.
SELECT
    CAST(delivery_days AS INTEGER)       AS delivery_days,
    COUNT(*)                             AS orders,
    ROUND(AVG(customer_rating), 2)       AS avg_rating
FROM orders
WHERE order_status = 'Completed'
GROUP BY 1
ORDER BY 1;

-- name: q08_rating_by_days_late
-- Delivery time measured against the promise:
-- days_late = actual days - promised days (negative = early).
SELECT
    CAST(delivery_days - estimated_delivery_days AS INTEGER) AS days_late,
    COUNT(*)                                                 AS orders,
    ROUND(AVG(customer_rating), 2)                           AS avg_rating
FROM orders
WHERE order_status = 'Completed'
GROUP BY 1
ORDER BY 1;

-- name: q09_rating_by_delivery_status
SELECT
    delivery_status,
    COUNT(*)                                                         AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)               AS share_pct,
    ROUND(AVG(customer_rating), 2)                                   AS avg_rating,
    ROUND(100.0 * AVG(customer_rating < 3), 1)                       AS pct_ratings_below_3
FROM orders
WHERE order_status = 'Completed'
GROUP BY delivery_status
ORDER BY avg_rating DESC;

-- name: q10_rating_by_shipping_method
-- The key test: Economy takes ~3x longer than Express. If slowness itself
-- hurt ratings, Economy would score lower. Compare with delay rate.
SELECT
    shipping_method,
    COUNT(*)                                                 AS orders,
    ROUND(AVG(delivery_days), 1)                             AS avg_delivery_days,
    ROUND(100.0 * AVG(delivery_status = 'Delayed'), 1)       AS delayed_pct,
    ROUND(AVG(customer_rating), 2)                           AS avg_rating
FROM orders
WHERE order_status = 'Completed'
GROUP BY shipping_method
ORDER BY avg_delivery_days;

-- name: q11_delay_rate_by_warehouse
-- Where do delays happen? Joins to customers to show the region mix too.
SELECT
    o.warehouse,
    COUNT(*)                                                 AS orders,
    ROUND(100.0 * AVG(o.delivery_status = 'Delayed'), 1)     AS delayed_pct,
    ROUND(AVG(o.customer_rating), 2)                         AS avg_rating,
    COUNT(DISTINCT c.region)                                 AS regions_served
FROM orders AS o
LEFT JOIN customers AS c ON c.customer_id = o.customer_id   -- LEFT JOIN keeps every order even if a customer were missing
WHERE o.order_status = 'Completed'
GROUP BY o.warehouse
ORDER BY delayed_pct DESC;
