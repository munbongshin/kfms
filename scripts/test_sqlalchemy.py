"""
Test with SQLAlchemy (same as Backend)
"""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

try:
    print("🔌 Testing SQLAlchemy connection...")

    # Same connection string as Backend
    connection_string = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/postgres?ssl=disable"
    print(f"Connection string: {connection_string}")

    # Try with asyncpg
    print("\n📊 Testing with asyncpg driver...")
    from sqlalchemy.ext.asyncio import create_async_engine
    import asyncio

    async def test_async():
        try:
            engine = create_async_engine(
                connection_string,
                poolclass=NullPool,
                echo=True
            )

            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar()
                print(f"✅ AsyncPG Connection successful!")
                print(f"Version: {version[:80]}")

                # Check tables
                result = await conn.execute(text("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename IN ('query_history', 'database_connections', 'excel_uploads')
                """))
                tables = result.fetchall()
                print(f"\nKFMS Tables: {[t[0] for t in tables]}")

            await engine.dispose()
            return True
        except Exception as e:
            print(f"❌ AsyncPG Error: {type(e).__name__}: {e}")
            return False

    success = asyncio.run(test_async())

    if not success:
        print("\n📊 Trying with psycopg2 driver (sync)...")
        sync_connection = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/postgres"
        engine = create_engine(sync_connection, poolclass=NullPool)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Psycopg2 Connection successful!")
            print(f"Version: {version[:80]}")

except Exception as e:
    print(f"\n❌ Final Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
