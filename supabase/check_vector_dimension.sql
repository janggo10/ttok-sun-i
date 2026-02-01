-- ============================================================
-- 벡터 차원 확인 스크립트
-- ============================================================

-- 1. benefit_embeddings 테이블의 embedding 컬럼 차원 확인
SELECT 
    column_name, 
    data_type,
    udt_name
FROM information_schema.columns 
WHERE table_name = 'benefit_embeddings' 
  AND column_name = 'embedding';

-- 예상 결과: data_type = 'USER-DEFINED', udt_name = 'vector'
-- vector(1536)이어야 함!

-- 2. match_benefits 함수의 파라미터 확인
SELECT 
    routine_name,
    data_type,
    parameter_name,
    parameter_mode
FROM information_schema.parameters
WHERE specific_schema = 'public'
  AND routine_name = 'match_benefits'
  AND parameter_name = 'query_embedding'
ORDER BY ordinal_position;

-- 예상 결과: data_type에 vector(1536) 표시

-- 3. 실제 임베딩 데이터 확인
SELECT 
    COUNT(*) as total_embeddings,
    COUNT(CASE WHEN category = 'WELFARE' THEN 1 END) as welfare_count,
    COUNT(CASE WHEN category = 'JOB' THEN 1 END) as job_count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM benefit_embeddings;

-- 4. 샘플 임베딩 차원 확인 (vector_dims 함수 사용)
SELECT 
    id,
    benefit_id,
    category,
    vector_dims(embedding) as dimension,
    LENGTH(content_chunk) as content_length,
    created_at
FROM benefit_embeddings
LIMIT 5;

-- 예상 결과: dimension = 1536
