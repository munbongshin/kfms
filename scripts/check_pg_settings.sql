-- PostgreSQL 설정 확인 및 조정

-- 1. 현재 설정 확인
SELECT name, setting, context
FROM pg_settings
WHERE name IN (
    'listen_addresses',
    'port',
    'max_connections',
    'lc_messages',
    'lc_ctype',
    'client_encoding',
    'server_encoding'
)
ORDER BY name;

-- 2. 세션별 로케일 설정 (임시)
SET lc_messages TO 'C';
SET lc_ctype TO 'C';
SET client_encoding TO 'UTF8';

-- 3. 연결 확인
SELECT
    datname,
    usename,
    application_name,
    client_addr,
    state
FROM pg_stat_activity
WHERE datname = 'postgres';

-- 4. 테이블 확인
SELECT tablename, schemaname
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

SELECT '✅ 설정 확인 완료' as status;
