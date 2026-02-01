-- ============================================================
-- OpenAI text-embedding-3-small 마이그레이션
-- ============================================================
-- 목적: Titan V2 (1024차원) → OpenAI (1536차원) 전환
-- 작성일: 2026-01-31
-- 실행 순서:
--   1. 기존 HNSW 인덱스 삭제
--   2. embedding 컬럼 차원 변경
--   3. 기존 임베딩 데이터 전체 삭제
--   4. 새 HNSW 인덱스 생성
--   5. Python 스크립트로 재임베딩: scripts/embeddings/generate_embeddings.py
-- ============================================================

BEGIN;

-- Step 1: 기존 HNSW 인덱스 삭제
DROP INDEX IF EXISTS idx_benefit_embeddings_welfare_hnsw;
DROP INDEX IF EXISTS idx_benefit_embeddings_job_hnsw;

-- Step 2: embedding 컬럼 차원 변경 (1024 → 1536)
-- PostgreSQL의 vector 타입은 ALTER COLUMN으로 직접 변경 불가
-- 임시 컬럼 생성 → 기존 컬럼 삭제 → 컬럼명 변경 → 데이터 삭제 → NOT NULL 추가

-- 2-1. 임시 컬럼 생성 (NOT NULL 없이)
ALTER TABLE benefit_embeddings ADD COLUMN embedding_new vector(1536);

-- 2-2. 기존 컬럼 삭제 (어차피 재임베딩할 예정)
ALTER TABLE benefit_embeddings DROP COLUMN embedding;

-- 2-3. 새 컬럼을 기존 이름으로 변경
ALTER TABLE benefit_embeddings RENAME COLUMN embedding_new TO embedding;

-- Step 3: 기존 임베딩 데이터 전체 삭제
-- (재임베딩을 위해 데이터를 지우되, 테이블 구조는 유지)
TRUNCATE TABLE benefit_embeddings;

-- Step 3-2: 데이터 삭제 후 NOT NULL 제약조건 추가
ALTER TABLE benefit_embeddings ALTER COLUMN embedding SET NOT NULL;

-- Step 4: 새 HNSW 인덱스 생성 (1536차원)
-- Partial Index for WELFARE category
CREATE INDEX idx_benefit_embeddings_welfare_hnsw
ON benefit_embeddings USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
WHERE category = 'WELFARE';

-- Partial Index for JOB category (준비용)
CREATE INDEX idx_benefit_embeddings_job_hnsw
ON benefit_embeddings USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
WHERE category = 'JOB';

COMMIT;

-- ============================================================
-- 실행 결과 확인
-- ============================================================
-- 1. 컬럼 차원 확인:
--    SELECT column_name, data_type 
--    FROM information_schema.columns 
--    WHERE table_name = 'benefit_embeddings' AND column_name = 'embedding';
--    → vector(1536)이어야 함
--
-- 2. 인덱스 확인:
--    SELECT indexname, indexdef 
--    FROM pg_indexes 
--    WHERE tablename = 'benefit_embeddings';
--    → idx_benefit_embeddings_welfare_hnsw, idx_benefit_embeddings_job_hnsw 존재 확인
--
-- 3. 데이터 확인:
--    SELECT COUNT(*) FROM benefit_embeddings;
--    → 0이어야 함 (재임베딩 전)
-- ============================================================

-- ============================================================
-- 다음 단계: Python 스크립트로 재임베딩
-- ============================================================
-- cd /Users/a1102028/Documents/ttok-sun-i
-- source backend/venv/bin/activate
-- python scripts/embeddings/generate_embeddings.py
-- ============================================================
