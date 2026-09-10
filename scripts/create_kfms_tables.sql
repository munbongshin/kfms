-- KFMS Metadata Tables
-- Execute this in pgAdmin on 'postgres' database (port 5433)

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

-- Verify
SELECT 'KFMS metadata tables created successfully!' as status;
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('query_history', 'database_connections', 'excel_uploads');
