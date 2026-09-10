-- KFMS Retail Sales Table
-- Execute this in pgAdmin or psql

-- Create retail_sales table
CREATE TABLE IF NOT EXISTS retail_sales (
    transaction_id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    gender VARCHAR(10),
    age INTEGER,
    product_category VARCHAR(100),
    quantity INTEGER,
    price_per_unit NUMERIC(10, 2),
    total_amount NUMERIC(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_retail_sales_date ON retail_sales(date);
CREATE INDEX IF NOT EXISTS idx_retail_sales_customer ON retail_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_retail_sales_category ON retail_sales(product_category);

-- Grant permissions (adjust user if needed)
GRANT SELECT, INSERT ON retail_sales TO postgres;

-- Verify table creation
SELECT 'Table created successfully!' as status;
