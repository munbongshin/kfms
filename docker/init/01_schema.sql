-- KFMS metadata tables. These live in their own database so they never appear
-- in the schema context handed to the LLM.
CREATE TABLE query_history (
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
    is_bookmarked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_history_created_at ON query_history(created_at DESC);
CREATE INDEX idx_query_history_database_id ON query_history(database_id);
CREATE INDEX idx_query_history_status ON query_history(status);
CREATE INDEX idx_query_history_bookmarked ON query_history(is_bookmarked, created_at DESC)
    WHERE is_bookmarked;

CREATE TABLE anomaly_review (
    id           SERIAL PRIMARY KEY,
    database_id  VARCHAR(255) NOT NULL,
    finding_key  VARCHAR(200) NOT NULL,
    rule_code    VARCHAR(40)  NOT NULL,
    status       VARCHAR(20)  NOT NULL,
    fingerprint  VARCHAR(64)  NOT NULL,
    note         TEXT,
    reviewed_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (database_id, finding_key)
);

CREATE INDEX idx_anomaly_review_lookup ON anomaly_review(database_id, rule_code);

CREATE TABLE llm_settings (
    id          INTEGER PRIMARY KEY,
    provider    VARCHAR(40),                -- ollama, lmstudio, vllm, openai_compatible, groq
    profiles    JSON NOT NULL DEFAULT '{}', -- per-platform settings; api_key Fernet-encrypted
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE eval_cases (
    id           SERIAL PRIMARY KEY,
    question     TEXT NOT NULL,
    expected_sql TEXT NOT NULL,
    database_id  VARCHAR(255) NOT NULL,
    created_by   VARCHAR(60) NOT NULL DEFAULT '',
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE eval_runs (
    id          SERIAL PRIMARY KEY,
    database_id VARCHAR(255) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, done, error
    provider    VARCHAR(60) NOT NULL DEFAULT '',
    model       VARCHAR(200) NOT NULL DEFAULT '',
    total       INTEGER NOT NULL DEFAULT 0,
    passed      INTEGER NOT NULL DEFAULT 0,
    seconds     DOUBLE PRECISION,
    error       TEXT,
    details     JSON,
    started_by  VARCHAR(60) NOT NULL DEFAULT '',
    started_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE saved_reports (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(200) NOT NULL,
    question       TEXT NOT NULL DEFAULT '',
    sql            TEXT NOT NULL,
    database_id    VARCHAR(255) NOT NULL,
    frequency      VARCHAR(20) NOT NULL DEFAULT 'daily',   -- daily, weekly, monthly
    run_hour       INTEGER NOT NULL DEFAULT 9,
    run_weekday    INTEGER,                                 -- 0 = Monday, for weekly
    run_day        INTEGER,                                 -- 1-28, for monthly
    is_active      BOOLEAN NOT NULL DEFAULT true,
    next_run_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    last_run_at    TIMESTAMP WITH TIME ZONE,
    last_status    VARCHAR(20),
    last_error     TEXT,
    last_row_count INTEGER,
    last_results   JSON,
    created_by     VARCHAR(60) NOT NULL DEFAULT '',
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_saved_reports_due ON saved_reports(next_run_at);

CREATE TABLE anomaly_settings (
    id         INTEGER PRIMARY KEY,
    params     JSON NOT NULL DEFAULT '{}',  -- edited thresholds per rule template
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE app_users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(60) NOT NULL UNIQUE,
    display_name  VARCHAR(100) NOT NULL DEFAULT '',
    password_hash VARCHAR(300) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'viewer',  -- admin, auditor, viewer
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE audit_log (
    id       SERIAL PRIMARY KEY,
    at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    username VARCHAR(60) NOT NULL DEFAULT '',
    role     VARCHAR(20) NOT NULL DEFAULT '',
    action   VARCHAR(60) NOT NULL,
    target   VARCHAR(500) NOT NULL DEFAULT '',
    detail   JSON NOT NULL DEFAULT '{}',
    ip       VARCHAR(64) NOT NULL DEFAULT ''
);

CREATE INDEX idx_audit_log_at ON audit_log(at);

CREATE TABLE glossary_terms (
    id          SERIAL PRIMARY KEY,
    term        VARCHAR(100) NOT NULL UNIQUE,
    definition  TEXT NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE database_connections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    host VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 5432,
    database VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_read_only BOOLEAN DEFAULT true,
    excluded_tables JSON NOT NULL DEFAULT '[]',  -- tables left out of analysis
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_database_connections_name ON database_connections(name);

CREATE TABLE excel_uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL UNIQUE,
    row_count INTEGER,
    column_count INTEGER,
    schema_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_excel_uploads_expires_at ON excel_uploads(expires_at);
CREATE INDEX idx_excel_uploads_table_name ON excel_uploads(table_name);
