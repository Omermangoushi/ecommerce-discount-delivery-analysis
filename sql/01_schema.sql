-- =============================================================================
-- 01_schema.sql  -  Database design for the e-commerce analysis (SQLite)
-- =============================================================================
-- Four tables, linked by ID columns (a simple "star-like" design):
--
--     customers 1 ──< orders 1 ──< order_items >── 1 products
--
--   * one customer places many orders
--   * one order contains many line items
--   * each line item is one product
--
-- PRIMARY KEY  = the column that uniquely identifies a row.
-- FOREIGN KEY  = a column that must match a primary key in another table,
--                which stops "orphan" rows (e.g. an item for an order that
--                does not exist).
-- This file is run by scripts/02_build_database.py.
-- =============================================================================

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_completed_lines;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

-- Product master list (one row per product)
CREATE TABLE products (
    product_id          TEXT PRIMARY KEY,
    product_name        TEXT,
    product_category    TEXT NOT NULL,
    product_subcategory TEXT,
    brand               TEXT,
    supplier            TEXT,
    unit_price          REAL NOT NULL,   -- list price per unit
    product_cost        REAL NOT NULL,   -- what the retailer pays per unit
    product_rating      REAL
);

-- Customer master list (one row per customer)
CREATE TABLE customers (
    customer_id               TEXT PRIMARY KEY,
    customer_name             TEXT,
    customer_age              INTEGER,
    gender                    TEXT,
    customer_segment          TEXT,
    customer_city             TEXT,
    customer_state            TEXT,
    customer_country          TEXT,
    region                    TEXT,
    customer_postal_code      TEXT,
    customer_acquisition_cost REAL
);

-- Order header (one row per order).
-- The raw orders file repeats customer details on every row; those live in
-- the customers table instead, so only order-level columns are kept here.
-- Sales/marketing channel columns are left out: they showed no real
-- differences and are out of scope.
CREATE TABLE orders (
    order_id                TEXT PRIMARY KEY,
    order_date              TEXT NOT NULL,   -- ISO format YYYY-MM-DD
    order_status            TEXT NOT NULL,   -- Completed / Returned / Cancelled / Pending
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    customer_type           TEXT,
    payment_status          TEXT,
    currency                TEXT,            -- label only (prices are identical in every currency)
    shipping_method         TEXT,
    warehouse               TEXT,
    delivery_days           REAL,            -- blank unless the order was completed
    estimated_delivery_days REAL,            -- the delivery time promised to the customer
    delivery_status         TEXT,            -- Early / On Time / Delayed / Cancelled
    return_status           TEXT,            -- only filled for returned orders
    return_reason           TEXT,
    customer_rating         REAL,            -- 1-5, only for completed orders
    review_sentiment        TEXT,
    -- header totals: kept only to demonstrate the header-vs-lines check;
    -- order_items is the trusted source for money
    header_gross_sales      REAL,
    header_quantity         INTEGER
);

-- Order lines (one row per product in an order)
CREATE TABLE order_items (
    line_id             INTEGER PRIMARY KEY,  -- surrogate key: the same product can appear twice in an order
    order_id            TEXT NOT NULL REFERENCES orders(order_id),
    product_id          TEXT NOT NULL REFERENCES products(product_id),
    quantity            INTEGER NOT NULL,
    unit_price          REAL NOT NULL,
    discount_percentage REAL NOT NULL,        -- 0-1 fraction: 0.25 = 25% off
    discount_amount     REAL NOT NULL,
    gross_sales         REAL NOT NULL,        -- quantity x unit_price, before discount
    tax_amount          REAL,
    shipping_cost       REAL,
    net_sales           REAL,                 -- includes tax and shipping (see quality report)
    product_cost        REAL NOT NULL,
    profit              REAL                  -- supplied figure; counts tax as profit, so not used
);

-- Indexes make joins and filters on these columns fast
CREATE INDEX idx_items_order   ON order_items(order_id);
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_orders_status ON orders(order_status);

-- -----------------------------------------------------------------------------
-- View: v_completed_lines
-- A saved query that every analysis query can reuse. It joins the three
-- tables, keeps Completed orders only, recalculates profit correctly and
-- puts each line into a discount band.
-- -----------------------------------------------------------------------------
CREATE VIEW v_completed_lines AS
SELECT
    oi.line_id,
    oi.order_id,
    o.order_date,
    oi.product_id,
    p.product_category,
    oi.quantity,
    oi.discount_percentage,
    oi.gross_sales,
    oi.discount_amount,
    oi.gross_sales - oi.discount_amount                      AS revenue,            -- what the customer actually paid for goods
    oi.product_cost,
    oi.gross_sales - oi.discount_amount - oi.product_cost    AS profit_before_tax,  -- corrected profit
    (p.unit_price - p.product_cost) / p.unit_price           AS list_margin,        -- product margin before any discount
    CASE
        WHEN oi.discount_percentage = 0     THEN '0%'
        WHEN oi.discount_percentage <= 0.10 THEN '1-10%'
        WHEN oi.discount_percentage <= 0.20 THEN '11-20%'
        WHEN oi.discount_percentage <= 0.30 THEN '21-30%'
        WHEN oi.discount_percentage <= 0.40 THEN '31-40%'
        WHEN oi.discount_percentage <= 0.50 THEN '41-50%'
        ELSE                                     '51-60%'
    END AS discount_band
FROM order_items AS oi
JOIN orders      AS o ON o.order_id   = oi.order_id      -- INNER JOIN: line must belong to an order
JOIN products    AS p ON p.product_id = oi.product_id    -- ...and to a product
WHERE o.order_status = 'Completed';
