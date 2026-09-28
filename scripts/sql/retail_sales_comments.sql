-- Korean business names for retail_sales (database: retail).
-- The query screen shows these as column headers, and the SQL prompt gives
-- them to the LLM so Korean questions map onto the right columns.
-- Re-runnable: COMMENT ON simply replaces the previous text.

COMMENT ON TABLE retail_sales IS '소매 판매 내역';

COMMENT ON COLUMN retail_sales.transaction_id   IS '거래번호';
COMMENT ON COLUMN retail_sales.date             IS '거래일자';
COMMENT ON COLUMN retail_sales.customer_id      IS '고객번호';
COMMENT ON COLUMN retail_sales.gender           IS '성별';
COMMENT ON COLUMN retail_sales.age              IS '나이';
COMMENT ON COLUMN retail_sales.product_category IS '상품 카테고리';
COMMENT ON COLUMN retail_sales.quantity         IS '수량';
COMMENT ON COLUMN retail_sales.price_per_unit   IS '단가';
COMMENT ON COLUMN retail_sales.total_amount     IS '매출액';
