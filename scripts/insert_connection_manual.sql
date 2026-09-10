-- pgAdmin에서 실행: 데이터베이스 연결 정보 수동 추가
-- Python 클라이언트의 한글 인코딩 문제를 우회하는 방법

-- 1. KFMS 테이블이 있는지 확인
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
AND tablename = 'database_connections';

-- 2. 테이블이 없으면 먼저 create_kfms_tables.sql 실행!

-- 3. 기존 연결 확인
SELECT * FROM database_connections;

-- 4. 새 연결 추가 (비밀번호는 평문으로 저장 - Backend가 암호화함)
INSERT INTO database_connections
(name, host, port, database, username, password, is_active, is_read_only, created_at, updated_at)
VALUES
('Retail Sales DB', 'localhost', 5433, 'postgres', 'postgres',
 'postgres',  -- 실제 비밀번호로 변경하세요
 true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (name) DO UPDATE SET
    host = EXCLUDED.host,
    port = EXCLUDED.port,
    database = EXCLUDED.database,
    username = EXCLUDED.username,
    password = EXCLUDED.password,
    is_active = EXCLUDED.is_active,
    is_read_only = EXCLUDED.is_read_only,
    updated_at = CURRENT_TIMESTAMP;

-- 5. 확인
SELECT id, name, host, port, database, username, is_active, is_read_only
FROM database_connections
ORDER BY id DESC;

-- 6. 연결 ID 확인 (Frontend에서 사용)
SELECT id, name FROM database_connections WHERE name = 'Retail Sales DB';
