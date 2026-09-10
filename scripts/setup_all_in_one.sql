-- ============================================
-- KFMS 전체 설정 SQL (All-in-One)
-- pgAdmin에서 이 파일 하나만 실행하세요
-- ============================================

-- 1. KFMS 메타데이터 테이블 생성
-- ============================================

-- Query execution history
CREATE TABLE IF NOT EXISTS query_history (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    database_id VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    results JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    row_count INTEGER,
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    validation_approved BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_history_database_id ON query_history(database_id);
CREATE INDEX IF NOT EXISTS idx_query_history_status ON query_history(status);

-- Multi-database connection registry
CREATE TABLE IF NOT EXISTS database_connections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    host VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 5432,
    database VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_read_only BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_database_connections_name ON database_connections(name);

-- Uploaded Excel file tracking
CREATE TABLE IF NOT EXISTS excel_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL UNIQUE,
    row_count INTEGER,
    column_count INTEGER,
    schema_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_excel_uploads_expires_at ON excel_uploads(expires_at);
CREATE INDEX IF NOT EXISTS idx_excel_uploads_table_name ON excel_uploads(table_name);


-- 2. Retail Sales 데이터 테이블 생성
-- ============================================

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

CREATE INDEX IF NOT EXISTS idx_retail_sales_date ON retail_sales(date);
CREATE INDEX IF NOT EXISTS idx_retail_sales_customer ON retail_sales(customer_id);
CREATE INDEX IF NOT EXISTS idx_retail_sales_category ON retail_sales(product_category);


-- 3. 데이터베이스 연결 정보 추가
-- ============================================

INSERT INTO database_connections
(name, host, port, database, username, password, is_active, is_read_only, created_at, updated_at)
VALUES
('Retail Sales DB', 'localhost', 5433, 'postgres', 'postgres', 'postgres', true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (name) DO UPDATE SET
    host = EXCLUDED.host,
    port = EXCLUDED.port,
    database = EXCLUDED.database,
    username = EXCLUDED.username,
    password = EXCLUDED.password,
    is_active = EXCLUDED.is_active,
    is_read_only = EXCLUDED.is_read_only,
    updated_at = CURRENT_TIMESTAMP;


-- 4. 확인 쿼리
-- ============================================

-- 생성된 테이블 확인
SELECT '=== 생성된 테이블 ===' as info;
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('query_history', 'database_connections', 'excel_uploads', 'retail_sales')
ORDER BY tablename;

-- 데이터베이스 연결 정보 확인
SELECT '=== 데이터베이스 연결 ===' as info;
SELECT id, name, host, port, database, username, is_active, is_read_only
FROM database_connections;

-- Retail Sales 데이터 확인 (아직 데이터 없음)
SELECT '=== Retail Sales 데이터 ===' as info;
SELECT COUNT(*) as row_count FROM retail_sales;

SELECT '✅ 테이블 생성 완료!' as status;
SELECT '👉 다음 단계: CSV 데이터를 retail_sales 테이블에 Import 하세요' as next_step;
