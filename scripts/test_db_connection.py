"""
Test PostgreSQL connection
"""
import asyncio
import asyncpg

async def test():
    try:
        print("🔌 Connecting to PostgreSQL...")
        conn = await asyncpg.connect(
            host='127.0.0.1',
            port=5433,
            database='postgres',
            user='postgres',
            password='postgres',
            ssl=False,
            server_settings={
                'client_encoding': 'UTF8',
                'lc_messages': 'C'
            }
        )
        print('✅ Connection successful!')

        # Check version
        version = await conn.fetchval('SELECT version()')
        print(f'\n📊 PostgreSQL version:')
        print(f'  {version[:80]}')

        # Check tables
        print(f'\n🔍 Checking KFMS tables...')
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN ('query_history', 'database_connections', 'excel_uploads')
            ORDER BY tablename
        """)

        if tables:
            print(f'  Found {len(tables)} table(s):')
            for t in tables:
                print(f'    ✅ {t["tablename"]}')
        else:
            print('  ❌ No KFMS tables found!')
            print('  Run create_kfms_tables.sql in pgAdmin')

        # Check retail_sales table
        print(f'\n🔍 Checking retail_sales table...')
        retail_check = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE schemaname = 'public' AND tablename = 'retail_sales'
            )
        """)

        if retail_check:
            count = await conn.fetchval('SELECT COUNT(*) FROM retail_sales')
            print(f'  ✅ retail_sales table exists ({count} rows)')
        else:
            print('  ❌ retail_sales table not found')
            print('  Run create_retail_sales_table.sql in pgAdmin')

        await conn.close()
        print('\n✅ All checks completed!')

    except Exception as e:
        print(f'\n❌ Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
