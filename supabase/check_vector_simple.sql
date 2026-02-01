-- ============================================================
-- 간단한 벡터 차원 확인 (에러 수정)
-- ============================================================

-- 1. 실제 임베딩 차원 확인 ⭐ (가장 중요!)
SELECT 
    id,
    benefit_id,
    category,
    vector_dims(embedding) as dimension,
    LENGTH(content_chunk) as content_length,
    created_at
FROM benefit_embeddings
LIMIT 5;

-- 예상 결과: dimension = 1536 (OpenAI)
-- 만약 1024이면: migrate_to_openai_embeddings.sql 실행 필요!

-- 2. 임베딩 데이터 통계
SELECT 
    COUNT(*) as total_embeddings,
    COUNT(CASE WHEN category = 'WELFARE' THEN 1 END) as welfare_count,
    COUNT(CASE WHEN category = 'JOB' THEN 1 END) as job_count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM benefit_embeddings;

-- 3. embedding 컬럼 타입 확인
SELECT 
    table_name,
    column_name, 
    data_type,
    udt_name
FROM information_schema.columns 
WHERE table_name = 'benefit_embeddings' 
  AND column_name = 'embedding';
