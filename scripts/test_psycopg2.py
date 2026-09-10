"""
Test PostgreSQL connection with psycopg2 (sync)
"""
import psycopg2

try:
    print("🔌 Connecting to PostgreSQL (psycopg2)...")
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=5433,
        database='postgres',
        user='postgres',
        password='postgres'
    )
    print('✅ Connection successful!')

    cur = conn.cursor()

    # Check version
    cur.execute('SELECT version()')
    version = cur.fetchone()[0]
    print(f'\n📊 PostgreSQL version:')
    print(f'  {version[:80]}')

    # Check tables
    print(f'\n🔍 Checking KFMS tables...')
    cur.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename IN ('query_history', 'database_connections', 'excel_uploads')
        ORDER BY tablename
    """)
    tables = cur.fetchall()

    if tables:
        print(f'  Found {len(tables)} table(s):')
        for t in tables:
            print(f'    ✅ {t[0]}')
    else:
        print('  ❌ No KFMS tables found!')
        print('  👉 Run create_kfms_tables.sql in pgAdmin')

    # Check retail_sales table
    print(f'\n🔍 Checking retail_sales table...')
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'retail_sales'
        )
    """)
    retail_exists = cur.fetchone()[0]

    if retail_exists:
        cur.execute('SELECT COUNT(*) FROM retail_sales')
        count = cur.fetchone()[0]
        print(f'  ✅ retail_sales table exists ({count} rows)')
    else:
        print('  ❌ retail_sales table not found')
        print('  👉 Run create_retail_sales_table.sql and import CSV in pgAdmin')

    cur.close()
    conn.close()
    print('\n✅ All checks completed!')

except Exception as e:
    print(f'\n❌ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
