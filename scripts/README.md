# Retail Sales Data Import Script

Excel 파일을 PostgreSQL 데이터베이스로 임포트하는 스크립트입니다.

## 📁 데이터 구조

**Source:** `retail_sales_dataset.xlsx` (1,000 rows)

**Columns:**
- `transaction_id` (INTEGER) - 거래 고유 ID
- `date` (DATE) - 거래 날짜
- `customer_id` (VARCHAR) - 고객 ID
- `gender` (VARCHAR) - 성별
- `age` (INTEGER) - 나이
- `product_category` (VARCHAR) - 제품 카테고리
- `quantity` (INTEGER) - 수량
- `price_per_unit` (NUMERIC) - 단가
- `total_amount` (NUMERIC) - 총 금액

## 🚀 사용 방법

### 1. 환경 설정

```bash
# 1. .env 파일 생성
cd C:\kfms\scripts
copy .env.example .env

# 2. .env 파일 수정 (PostgreSQL 접속 정보)
notepad .env
```

### 2. 스크립트 실행

```bash
# scripts 폴더로 이동
cd C:\kfms\scripts

# Python 스크립트 실행
python import_retail_sales.py
```

### 3. 결과 확인

스크립트가 성공적으로 실행되면:
- ✅ `retail_sales` 테이블 생성
- ✅ 1,000개 행 데이터 임포트
- ✅ 인덱스 생성 (date, customer_id, product_category)
- ✅ 통계 정보 출력

## 📊 테스트 쿼리 예제

### 1. 전체 데이터 확인
```sql
SELECT * FROM retail_sales LIMIT 10;
```

### 2. 카테고리별 매출
```sql
SELECT 
    product_category,
    COUNT(*) as transaction_count,
    SUM(total_amount) as total_revenue
FROM retail_sales
GROUP BY product_category
ORDER BY total_revenue DESC;
```

### 3. 월별 매출 추이
```sql
SELECT 
    DATE_TRUNC('month', date) as month,
    SUM(total_amount) as monthly_revenue,
    COUNT(*) as transaction_count
FROM retail_sales
GROUP BY month
ORDER BY month;
```

### 4. 고객 성별 분석
```sql
SELECT 
    gender,
    COUNT(DISTINCT customer_id) as customer_count,
    AVG(age) as avg_age,
    SUM(total_amount) as total_spent
FROM retail_sales
GROUP BY gender;
```

### 5. 최고 구매 고객 TOP 10
```sql
SELECT 
    customer_id,
    gender,
    age,
    COUNT(*) as purchase_count,
    SUM(total_amount) as total_spent
FROM retail_sales
GROUP BY customer_id, gender, age
ORDER BY total_spent DESC
LIMIT 10;
```

## 🔍 KFMS Text-to-SQL 테스트

이 데이터로 KFMS의 Text-to-SQL 기능을 테스트할 수 있습니다:

### 자연어 질문 예제

1. **"카테고리별 매출을 보여줘"**
   - 예상 SQL: `SELECT product_category, SUM(total_amount) FROM retail_sales GROUP BY product_category`

2. **"2023년 3월 매출이 가장 높은 날은?"**
   - 예상 SQL: `SELECT date, SUM(total_amount) FROM retail_sales WHERE date BETWEEN '2023-03-01' AND '2023-03-31' GROUP BY date ORDER BY SUM(total_amount) DESC LIMIT 1`

3. **"30대 고객의 평균 구매 금액은?"**
   - 예상 SQL: `SELECT AVG(total_amount) FROM retail_sales WHERE age BETWEEN 30 AND 39`

4. **"가장 인기있는 제품 카테고리는?"**
   - 예상 SQL: `SELECT product_category, COUNT(*) FROM retail_sales GROUP BY product_category ORDER BY COUNT(*) DESC LIMIT 1`

5. **"남성과 여성의 구매 패턴 차이는?"**
   - 예상 SQL: `SELECT gender, AVG(total_amount), AVG(quantity), COUNT(*) FROM retail_sales GROUP BY gender`

## 📈 시각화 테스트

이 데이터로 차트 추천 기능을 테스트할 수 있습니다:

- **Bar Chart**: 카테고리별 매출, 성별 분석
- **Line Chart**: 월별 매출 추이, 날짜별 거래량
- **Pie Chart**: 카테고리별 매출 비중, 성별 분포

## 🛠️ 문제 해결

### PostgreSQL 연결 실패
```bash
# PostgreSQL 서비스 상태 확인
pg_ctl status

# PostgreSQL 시작
pg_ctl start
```

### 테이블 재생성
```sql
-- 기존 테이블 삭제 후 재실행
DROP TABLE IF EXISTS retail_sales;
```

### 데이터 확인
```sql
-- 테이블 존재 확인
SELECT tablename FROM pg_tables WHERE tablename = 'retail_sales';

-- 레코드 수 확인
SELECT COUNT(*) FROM retail_sales;
```

## 📝 참고사항

- 스크립트는 기존 데이터를 **덮어씁니다** (`if_exists='replace'`)
- 총 1,000개의 샘플 거래 데이터가 임포트됩니다
- 인덱스가 자동으로 생성되어 쿼리 성능이 최적화됩니다
- 날짜 범위: 2023년 전체
