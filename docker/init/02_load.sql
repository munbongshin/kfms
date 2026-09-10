-- Sample data lives in its own database: the schema the LLM sees must contain
-- only queryable business tables.
CREATE DATABASE retail;

\connect retail

CREATE TABLE retail_sales (
    transaction_id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    gender VARCHAR(10),
    age INTEGER,
    product_category VARCHAR(100),
    quantity INTEGER,
    price_per_unit NUMERIC(10, 2),
    total_amount NUMERIC(10, 2)
);

CREATE INDEX idx_retail_sales_date ON retail_sales(date);
CREATE INDEX idx_retail_sales_customer ON retail_sales(customer_id);
CREATE INDEX idx_retail_sales_category ON retail_sales(product_category);

COPY retail_sales(transaction_id, date, customer_id, gender, age,
                  product_category, quantity, price_per_unit, total_amount)
FROM '/data/retail_sales_data.csv'
WITH (FORMAT csv, HEADER true);
