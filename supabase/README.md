# Supabase 설정 가이드

## 1. 스키마 설치

### 방법 1: Supabase Dashboard (권장)

1. Supabase 대시보드 접속: https://supabase.com/dashboard
2. 프로젝트 선택: `ttok-sun-i`
3. 왼쪽 메뉴에서 **SQL Editor** 클릭
4. `schema.sql` 파일 내용 전체 복사
5. SQL Editor에 붙여넣기
6. **Run** 버튼 클릭 (또는 Cmd/Ctrl + Enter)

### 방법 2: Supabase CLI

```bash
# Supabase CLI 설치 (없는 경우)
brew install supabase/tap/supabase

# 프로젝트 연결
supabase link --project-ref your-project-id

# 스키마 실행
supabase db push
```

## 2. 설치 확인

SQL Editor에서 다음 쿼리 실행:

```sql
-- 테이블 확인
select tablename from pg_tables where schemaname = 'public';

-- 확장 확인
select * from pg_extension where extname in ('vector', 'uuid-ossp');

-- 카테고리 데이터 확인
select * from category_codes order by display_order;
```

**예상 결과:**
- 테이블 9개 생성 확인
- pgvector, uuid-ossp 확장 활성화
- 카테고리 8개 삽입 확인

## 3. API 키 저장

1. Supabase 대시보드 → **Settings** → **API**
2. 다음 값 복사:
   - `Project URL`
   - `anon public` 키
   - `service_role` 키 (⚠️ 절대 공개 금지)

3. 프로젝트 루트에 `.env` 파일 생성:

```bash
cp .env.example .env
```

4. `.env` 파일 편집하여 실제 값 입력

## 4. 다음 단계

- [ ] 행정동 코드 데이터 수집 (`scripts/sync_region_codes.py`)
- [ ] AWS Lambda 환경 구축
- [ ] 카카오 챗봇 연동

## 문제 해결

### pgvector 확장 오류
```sql
-- 수동으로 확장 활성화
create extension if not exists vector;
```

### RLS 정책 오류
```sql
-- RLS 비활성화 (개발 중에만)
alter table users disable row level security;
```

### 인덱스 생성 실패
```sql
-- HNSW 인덱스는 데이터가 있을 때 생성
-- 초기에는 스킵하고 나중에 생성 가능
```
