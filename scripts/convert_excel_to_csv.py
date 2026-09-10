"""
Convert Excel to CSV for easy import to PostgreSQL
"""
import pandas as pd
import os

EXCEL_FILE = r'C:\Users\신문봉-PC\Desktop\sampledata\retail_sales_dataset.xlsx'
OUTPUT_CSV = 'retail_sales_data.csv'

def main():
    print("🔄 Converting Excel to CSV...")
    print("=" * 60)

    try:
        # Read Excel
        print(f"📖 Reading: {EXCEL_FILE}")
        df = pd.read_excel(EXCEL_FILE)

        # Rename columns to match database schema
        df.columns = [
            'transaction_id', 'date', 'customer_id', 'gender', 'age',
            'product_category', 'quantity', 'price_per_unit', 'total_amount'
        ]

        # Convert date format
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

        # Save to CSV
        output_path = os.path.join(os.path.dirname(__file__), OUTPUT_CSV)
        df.to_csv(output_path, index=False, encoding='utf-8')

        print(f"✅ CSV created: {output_path}")
        print(f"📊 Rows: {len(df)}")
        print(f"📋 Columns: {len(df.columns)}")

        print("\n" + "=" * 60)
        print("🎉 Conversion completed!")
        print("\n📝 Next Steps:")
        print("  1. Open pgAdmin 4")
        print("  2. Connect to your PostgreSQL server (port 5433)")
        print("  3. Open 'postgres' database")
        print("  4. Tools → Query Tool")
        print("  5. Open and execute: create_retail_sales_table.sql")
        print("  6. Right-click on 'retail_sales' table → Import/Export Data")
        print(f"  7. Select file: {output_path}")
        print("  8. Format: CSV")
        print("  9. Header: Yes")
        print("  10. Click OK to import")

    except FileNotFoundError:
        print(f"❌ File not found: {EXCEL_FILE}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
