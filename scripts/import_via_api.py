"""
Import retail sales data via KFMS Backend API
Converts Excel to database connection and uploads data
"""
import pandas as pd
import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = 'http://localhost:8000/api/v1'
EXCEL_FILE = r'C:\Users\신문봉-PC\Desktop\sampledata\retail_sales_dataset.xlsx'

# Database connection info
DB_CONNECTION = {
    "name": "Retail Sales Database",
    "host": "127.0.0.1",
    "port": 5433,
    "database": "kfms_meta",
    "username": "postgres",
    "password": "postgres",
    "is_active": True,
    "is_read_only": False  # We need write access to create table
}

def create_database_connection():
    """Create database connection via API"""
    print("📡 Creating database connection via API...")
    response = requests.post(f"{BACKEND_URL}/databases", json=DB_CONNECTION)

    if response.status_code == 200:
        conn_data = response.json()
        print(f"✅ Database connection created: ID = {conn_data['id']}")
        return conn_data['id']
    else:
        print(f"❌ Failed to create connection: {response.text}")
        return None

def upload_excel_file(connection_id):
    """Upload Excel file via API"""
    print(f"📤 Uploading Excel file...")

    with open(EXCEL_FILE, 'rb') as f:
        files = {'file': ('retail_sales_dataset.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {
            'database_id': connection_id,
            'ttl_hours': 24
        }

        response = requests.post(f"{BACKEND_URL}/excel/upload", files=files, data=data)

    if response.status_code == 200:
        upload_data = response.json()
        print(f"✅ Excel uploaded successfully")
        print(f"   Table name: {upload_data['table_name']}")
        print(f"   Rows: {upload_data['row_count']}")
        return upload_data
    else:
        print(f"❌ Failed to upload Excel: {response.text}")
        return None

def test_query(connection_id, table_name):
    """Test query on uploaded data"""
    print(f"\n🔍 Testing query on {table_name}...")

    query_data = {
        "question": f"Show me the first 5 rows from {table_name}",
        "database_id": connection_id,
        "llm_provider": "ollama",
        "auto_approve": True
    }

    response = requests.post(f"{BACKEND_URL}/query/generate-and-execute", json=query_data)

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Query executed successfully")
        print(f"   Generated SQL: {result.get('generated_sql', 'N/A')}")
        print(f"   Rows returned: {len(result.get('results', []))}")

        if result.get('results'):
            print(f"\n   Sample data:")
            for i, row in enumerate(result['results'][:3], 1):
                print(f"     Row {i}: {row}")

        return True
    else:
        print(f"❌ Query failed: {response.text}")
        return False

def main():
    print("🚀 KFMS API-based Excel Import")
    print("=" * 60)

    try:
        # Check backend health
        print("🏥 Checking backend health...")
        response = requests.get(f"{BACKEND_URL}/health")
        if response.status_code != 200:
            print("❌ Backend is not running. Please start the backend first:")
            print("   cd c:\\kfms\\backend")
            print("   python -m app.main")
            return
        print("✅ Backend is healthy")

        # Create database connection
        connection_id = create_database_connection()
        if not connection_id:
            return

        # Upload Excel file
        upload_result = upload_excel_file(connection_id)
        if not upload_result:
            return

        # Test query
        test_query(connection_id, upload_result['table_name'])

        print("\n" + "=" * 60)
        print("🎉 Import completed successfully!")
        print("\n💡 Next Steps:")
        print(f"   1. Open KFMS frontend: http://localhost:5173")
        print(f"   2. Select database: '{DB_CONNECTION['name']}'")
        print(f"   3. Query the table: {upload_result['table_name']}")
        print("\n💡 Example Questions:")
        print(f"   - What are the top 10 products by revenue?")
        print(f"   - Show me sales by category")
        print(f"   - What is the average purchase amount?")

    except requests.ConnectionError:
        print("❌ Cannot connect to backend. Is it running?")
        print("   Start backend with: cd c:\\kfms\\backend && python -m app.main")
    except FileNotFoundError:
        print(f"❌ Excel file not found: {EXCEL_FILE}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()
