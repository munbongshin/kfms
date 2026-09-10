# Retail Sales 데이터 임포트 가이드

PostgreSQL 인코딩 문제로 인해 pgAdmin을 통한 수동 임포트를 진행합니다.

## ✅ 준비 완료

- ✅ SQL 스크립트: `create_retail_sales_table.sql`
- ✅ CSV 데이터: `retail_sales_data.csv` (1,000 rows)
- ✅ Backend 실행 중: http://localhost:8000

## 📋 임포트 단계

### 1. pgAdmin 4 실행

### 2. PostgreSQL 서버 연결
- **Host**: localhost
- **Port**: 5433
- **Database**: postgres
- **Username**: postgres
- **Password**: (사용자 비밀번호)

### 3. 테이블 생성
1. 왼쪽 트리에서 **postgres** 데이터베이스 선택
2. 상단 메뉴: **Tools** → **Query Tool**
3. 파일 열기 아이콘 클릭 또는 **File** → **Open**
4. `C:\kfms\scripts\create_retail_sales_table.sql` 선택
5. **Execute** 버튼 (▶) 클릭
6. 결과: "Table created successfully!" 확인

### 4. 데이터 임포트
1. 왼쪽 트리에서 **Tables** → **retail_sales** 우클릭
2. **Import/Export Data...** 선택
3. **Import/Export** 창에서 설정:
   - **Filename**: `C:\kfms\scripts\retail_sales_data.csv` (Browse... 버튼으로 선택)
   - **Format**: CSV
   - **Header**: ✅ Yes (체크)
   - **Delimiter**: , (쉼표)
   - **Quote**: "
   - **Escape**: "
   - **Encoding**: UTF8
4. **OK** 버튼 클릭
5. 진행 상황 확인
6. 완료 메시지: "1000 rows imported"

### 5. 데이터 확인
Query Tool에서 실행:
```sql
-- 전체 레코드 수 확인
SELECT COUNT(*) FROM retail_sales;

-- 샘플 데이터 확인
SELECT * FROM retail_sales LIMIT 10;

-- 카테고리별 집계
SELECT product_category, COUNT(*), SUM(total_amount)
FROM retail_sales
GROUP BY product_category;
```

## 🚀 KFMS로 테스트

데이터 임포트 완료 후, KFMS UI에서 자연어 쿼리 테스트:

### 1. Frontend 시작
```bash
cd c:\kfms\frontend
npm run dev
```

Browser에서 http://localhost:5173 접속

### 2. Database 연결 추가
1. 홈페이지에서 **Database Management** 클릭
2. **Add Connection** 클릭
3. 정보 입력:
   - Name: Retail Sales DB
   - Host: localhost (또는 127.0.0.1)
   - Port: 5433
   - Database: postgres
   - Username: postgres
   - Password: (비밀번호 입력)
   - Read Only: ✅ Yes (안전을 위해)
4. **Test Connection** 클릭하여 연결 확인
5. **Save** 클릭

### 3. 자연어 쿼리 테스트

**Query** 페이지로 이동하여 다음 질문들을 시도해보세요:

#### 기본 질문
- "Show me the first 10 transactions"
- "retail_sales 테이블의 데이터를 보여줘"

#### 집계 쿼리
- "카테고리별 총 매출은?"
- "What are the top 5 products by revenue?"
- "성별로 평균 구매 금액을 알려줘"

#### 시간 분석
- "월별 매출 추이를 보여줘"
- "Show me daily sales for March 2023"

#### 고객 분석
- "30대 고객의 구매 패턴은?"
- "가장 많이 구매한 고객 TOP 10은?"

#### 복잡한 쿼리
- "Electronics 카테고리에서 가장 많이 팔린 날은?"
- "여성 고객의 평균 구매 금액과 남성 고객 비교"

### 4. 시각화 확인

쿼리 실행 후:
- **Table** 탭: 결과 데이터 확인
- **Chart** 탭: 자동 추천된 차트 확인
  - Bar Chart: 카테고리별 비교
  - Line Chart: 시간에 따른 추이
  - Pie Chart: 비율 분석

## 🔧 문제 해결

### 임포트 실패 시
```sql
-- 테이블 삭제 후 재시도
DROP TABLE IF EXISTS retail_sales CASCADE;

-- 그 다음 create_retail_sales_table.sql 재실행
```

### 권한 오류 시
```sql
-- 권한 확인
SELECT grantee, privilege_type 
FROM information_schema.role_table_grants 
WHERE table_name='retail_sales';

-- 권한 부여
GRANT ALL PRIVILEGES ON TABLE retail_sales TO postgres;
```

### CSV 인코딩 문제 시
CSV 파일을 메모장으로 열어서 **다른 이름으로 저장** → 인코딩: **UTF-8** 선택

## 📊 예상 결과

임포트 완료 후:
- **Total Rows**: 1,000
- **Unique Customers**: ~155
- **Product Categories**: 3 (Electronics, Clothing, Beauty)
- **Date Range**: 2023-01-01 ~ 2023-12-31
- **Total Revenue**: $293,155

## 🎯 다음 단계

1. ✅ 데이터 임포트 완료
2. ✅ KFMS Frontend로 자연어 쿼리 테스트
3. ✅ 차트 시각화 확인
4. ✅ Query History에서 실행 기록 확인
5. ✅ Excel 업로드 기능 테스트 (다른 데이터로)

---

**문제가 계속될 경우**:
PostgreSQL의 locale 설정 변경이 필요할 수 있습니다.
(`postgresql.conf`에서 `lc_messages = 'en_US.UTF-8'`로 변경)
