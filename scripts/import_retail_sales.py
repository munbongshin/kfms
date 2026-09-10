"""
Excel to PostgreSQL Import Script
Imports retail_sales_dataset.xlsx into PostgreSQL database
"""
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'kfms_meta')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

# Excel file path
EXCEL_FILE = r'C:\Users\신문봉-PC\Desktop\sampledata\retail_sales_dataset.xlsx'

def create_database_engine():
    """Create SQLAlchemy engine for PostgreSQL"""
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?client_encoding=utf8"
    return create_engine(connection_string, pool_pre_ping=True)

def create_table(engine):
    """Create retail_sales table if not exists"""
    create_table_sql = """
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
    """

    with engine.connect() as conn:
        conn.execute(text(create_table_sql))
        conn.commit()
        print("✅ Table 'retail_sales' created successfully")

def import_data(engine):
    """Import data from Excel to PostgreSQL"""
    # Read Excel file
    print(f"📖 Reading Excel file: {EXCEL_FILE}")
    df = pd.read_excel(EXCEL_FILE)

    # Rename columns to match database schema (lowercase, snake_case)
    df.columns = [
        'transaction_id', 'date', 'customer_id', 'gender', 'age',
        'product_category', 'quantity', 'price_per_unit', 'total_amount'
    ]

    # Convert data types
    df['date'] = pd.to_datetime(df['date']).dt.date
    df['transaction_id'] = df['transaction_id'].astype(int)
    df['age'] = df['age'].astype(int)
    df['quantity'] = df['quantity'].astype(int)
    df['price_per_unit'] = df['price_per_unit'].astype(float)
    df['total_amount'] = df['total_amount'].astype(float)

    # Import to PostgreSQL
    print(f"📊 Importing {len(df)} rows to PostgreSQL...")
    df.to_sql(
        'retail_sales',
        engine,
        if_exists='replace',  # Replace existing data
        index=False,
        method='multi',  # Faster bulk insert
        chunksize=500
    )

    print(f"✅ Successfully imported {len(df)} rows")
    return len(df)

def verify_import(engine):
    """Verify data import"""
    with engine.connect() as conn:
        # Count rows
        result = conn.execute(text("SELECT COUNT(*) FROM retail_sales"))
        count = result.scalar()
        print(f"\n📊 Verification:")
        print(f"  - Total rows: {count}")

        # Sample data
        result = conn.execute(text("SELECT * FROM retail_sales LIMIT 5"))
        rows = result.fetchall()
        print(f"\n  First 5 rows:")
        for row in rows:
            print(f"    {row}")

        # Statistics
        stats_sql = """
        SELECT
            COUNT(DISTINCT customer_id) as unique_customers,
            COUNT(DISTINCT product_category) as product_categories,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            SUM(total_amount) as total_revenue
        FROM retail_sales
        """
        result = conn.execute(text(stats_sql))
        stats = result.fetchone()
        print(f"\n  Statistics:")
        print(f"    - Unique Customers: {stats[0]}")
        print(f"    - Product Categories: {stats[1]}")
        print(f"    - Date Range: {stats[2]} to {stats[3]}")
        print(f"    - Total Revenue: ${stats[4]:,.2f}")

def main():
    """Main execution function"""
    try:
        print("🚀 Starting Excel to PostgreSQL import...")
        print("=" * 60)

        # Create database connection
        engine = create_database_engine()
        print("✅ Database connection established")

        # Create table
        create_table(engine)

        # Import data
        row_count = import_data(engine)

        # Verify import
        verify_import(engine)

        print("\n" + "=" * 60)
        print("🎉 Import completed successfully!")
        print("\n💡 Usage Examples:")
        print("  - SELECT * FROM retail_sales WHERE product_category = 'Electronics';")
        print("  - SELECT customer_id, SUM(total_amount) FROM retail_sales GROUP BY customer_id;")
        print("  - SELECT DATE_TRUNC('month', date) as month, SUM(total_amount) FROM retail_sales GROUP BY month;")

    except FileNotFoundError:
        print(f"❌ Error: Excel file not found at {EXCEL_FILE}")
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()
