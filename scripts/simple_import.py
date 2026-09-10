"""
Simple Excel to PostgreSQL Import (without SQLAlchemy)
"""
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', '5433')),
    'database': os.getenv('DB_NAME', 'kfms_meta'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

EXCEL_FILE = r'C:\Users\신문봉-PC\Desktop\sampledata\retail_sales_dataset.xlsx'

def main():
    print("🚀 Starting simple Excel import...")
    print("=" * 60)

    try:
        # Read Excel
        print(f"📖 Reading Excel file...")
        df = pd.read_excel(EXCEL_FILE)
        print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")

        # Rename columns
        df.columns = [
            'transaction_id', 'date', 'customer_id', 'gender', 'age',
            'product_category', 'quantity', 'price_per_unit', 'total_amount'
        ]

        # Convert date
        df['date'] = pd.to_datetime(df['date']).dt.date

        # Connect to PostgreSQL
        print(f"🔌 Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✅ Connected successfully")

        # Drop existing table
        print("🗑️  Dropping existing table if exists...")
        cur.execute("DROP TABLE IF EXISTS retail_sales CASCADE")

        # Create table
        print("📋 Creating retail_sales table...")
        create_sql = """
        CREATE TABLE retail_sales (
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
        )
        """
        cur.execute(create_sql)
        print("✅ Table created")

        # Insert data
        print(f"📊 Inserting {len(df)} rows...")
        insert_sql = """
        INSERT INTO retail_sales
        (transaction_id, date, customer_id, gender, age, product_category,
         quantity, price_per_unit, total_amount)
        VALUES %s
        """

        # Prepare data
        data = [tuple(row) for row in df.values]

        # Batch insert
        execute_values(cur, insert_sql, data, page_size=500)
        print("✅ Data inserted")

        # Create indexes
        print("🔍 Creating indexes...")
        cur.execute("CREATE INDEX idx_retail_sales_date ON retail_sales(date)")
        cur.execute("CREATE INDEX idx_retail_sales_customer ON retail_sales(customer_id)")
        cur.execute("CREATE INDEX idx_retail_sales_category ON retail_sales(product_category)")
        print("✅ Indexes created")

        # Commit
        conn.commit()

        # Verify
        print("\n📊 Verification:")
        cur.execute("SELECT COUNT(*) FROM retail_sales")
        count = cur.fetchone()[0]
        print(f"  - Total rows: {count}")

        cur.execute("SELECT * FROM retail_sales LIMIT 3")
        rows = cur.fetchall()
        print(f"\n  First 3 rows:")
        for row in rows:
            print(f"    {row[:5]}...")  # Print first 5 columns

        # Statistics
        stats_sql = """
        SELECT
            COUNT(DISTINCT customer_id) as unique_customers,
            COUNT(DISTINCT product_category) as categories,
            MIN(date) as min_date,
            MAX(date) as max_date,
            SUM(total_amount) as total_revenue
        FROM retail_sales
        """
        cur.execute(stats_sql)
        stats = cur.fetchone()
        print(f"\n  Statistics:")
        print(f"    - Unique Customers: {stats[0]}")
        print(f"    - Product Categories: {stats[1]}")
        print(f"    - Date Range: {stats[2]} to {stats[3]}")
        print(f"    - Total Revenue: ${float(stats[4]):,.2f}")

        # Close
        cur.close()
        conn.close()

        print("\n" + "=" * 60)
        print("🎉 Import completed successfully!")
        print("\n💡 Test Query Examples:")
        print("  1. SELECT product_category, COUNT(*) FROM retail_sales GROUP BY product_category;")
        print("  2. SELECT gender, AVG(total_amount) FROM retail_sales GROUP BY gender;")
        print("  3. SELECT DATE_TRUNC('month', date), SUM(total_amount) FROM retail_sales GROUP BY 1;")

    except FileNotFoundError:
        print(f"❌ Excel file not found: {EXCEL_FILE}")
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        if 'conn' in locals():
            conn.rollback()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
