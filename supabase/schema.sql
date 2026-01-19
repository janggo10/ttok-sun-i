-- ============================================
-- 똑순이 데이터베이스 스키마 설치 스크립트
-- Supabase SQL Editor에서 실행하세요
-- ============================================

-- [1] 확장 및 환경 설정
create extension if not exists vector;
create extension if not exists "uuid-ossp";

comment on extension vector is '시니어 혜택 문맥 검색을 위한 벡터 연산 확장';

-- ============================================
-- 마스터 데이터 테이블
-- ============================================

-- [2] 행정동 코드 마스터 테이블
create table region_codes (
  code text primary key,
  full_name text not null,
  si_do text,
  si_gun_gu text,
  is_active boolean default true,
  deprecated_at timestamp with time zone,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table region_codes is '전국 행정표준코드 마스터 데이터 (행정안전부 API 연동)';
comment on column region_codes.deprecated_at is '행정구역 통폐합 시 자동 업데이트';

create index idx_region_codes_active on region_codes(is_active) where is_active = true;
create index idx_region_codes_si_do on region_codes(si_do);
create index idx_region_codes_si_gun_gu on region_codes(si_gun_gu);

-- [3] 카테고리 코드 마스터 테이블
create table category_codes (
  code text primary key,
  name text not null,
  description text,
  display_order int default 0,
  created_at timestamp with time zone default now()
);

comment on table category_codes is '똑순이 서비스 혜택 카테고리 분류 체계';

-- 기본 카테고리 데이터 삽입
insert into category_codes (code, name, description, display_order) values
  ('C01', '의료지원', '건강검진, 치료비, 의료기기 지원', 1),
  ('C02', '생활비지원', '기초생활비, 난방비, 통신비 지원', 2),
  ('C03', '주거지원', '임대료, 주택개보수, 이사비 지원', 3),
  ('C04', '문화여가', '문화생활, 여행, 체육활동 지원', 4),
  ('C05', '교육지원', '평생교육, 디지털교육, 자격증 지원', 5),
  ('C06', '일자리', '시니어 일자리, 창업 지원', 6),
  ('C07', '돌봄서비스', '요양, 간병, 방문돌봄 서비스', 7),
  ('C08', '기타', '분류되지 않은 혜택', 99);

-- ============================================
-- 사용자 데이터 테이블
-- ============================================

-- [4] 사용자 정보 테이블
create table users (
  id uuid primary key default uuid_generate_v4(),
  kakao_user_id text unique not null,
  region_code text references region_codes(code),
  gender text check (gender in ('M', 'F', 'OTHER', null)),
  birth_year int check (birth_year between 1900 and 2100),
  
  last_region_check_at timestamp with time zone,
  is_active boolean default true,
  notification_enabled boolean default true,
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table users is '이용자 프로필 및 개인화 설정 정보';
comment on column users.kakao_user_id is '카카오톡 채널 사용자 고유 식별자 (plusfriend_user_key)';
comment on column users.last_region_check_at is '6개월 주기 거주지 확인 알림용';

create index idx_users_region on users(region_code) where is_active = true;
create index idx_users_birth_year on users(birth_year) where is_active = true;
create index idx_users_active on users(is_active);

-- ============================================
-- 혜택 데이터 테이블
-- ============================================

-- [5] 혜택 마스터 테이블
create table benefits (
  id bigint primary key generated always as identity,
  title text not null,
  category_codes text[],
  
  target_age_min int,
  target_age_max int,
  target_gender text check (target_gender in ('M', 'F', 'ALL', null)),
  region_codes text[],
  
  content text,
  original_url text,
  
  application_start_date date,
  application_end_date date,
  
  source_name text,
  is_active boolean default true,
  content_hash text,
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table benefits is '정부 및 지자체 시니어 혜택 통합 마스터';
comment on column benefits.content_hash is '2단계 중복 제거 전략: 1단계 문자열 해시 비교용';
comment on column benefits.application_end_date is '마감 임박 알림 및 자동 아카이빙 기준';

create index idx_benefits_active on benefits(is_active) where is_active = true;
create index idx_benefits_region on benefits using gin(region_codes);
create index idx_benefits_category on benefits using gin(category_codes);
create index idx_benefits_dates on benefits(application_end_date) where is_active = true;
create index idx_benefits_hash on benefits(content_hash);
create index idx_benefits_source on benefits(source_name);

-- ============================================
-- AI/RAG 데이터 테이블
-- ============================================

-- [6] 벡터 데이터 저장소
create table benefit_embeddings (
  id uuid primary key default uuid_generate_v4(),
  benefit_id bigint references benefits(id) on delete cascade,
  embedding vector(1024),
  content_chunk text,
  chunk_index int default 0,
  created_at timestamp with time zone default now()
);

comment on table benefit_embeddings is '문맥 검색을 위한 혜택 상세 내용의 벡터 데이터';
comment on column benefit_embeddings.embedding is 'AWS Bedrock Titan Embeddings V2 모델 사용';
comment on column benefit_embeddings.chunk_index is '긴 공고문 분할 시 원본 순서 보존';

-- HNSW 인덱스 (벡터 검색 성능 최적화)
create index idx_benefit_embeddings_vector 
  on benefit_embeddings 
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create index idx_benefit_embeddings_benefit_id on benefit_embeddings(benefit_id);

comment on index idx_benefit_embeddings_vector is 'HNSW 인덱스로 벡터 유사도 검색 속도 10-100배 향상';

-- ============================================
-- 사용자 행동 추적 테이블
-- ============================================

-- [7] 사용자-혜택 상호작용 로그
create table user_benefit_interactions (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id) on delete cascade,
  benefit_id bigint references benefits(id) on delete cascade,
  interaction_type text not null check (
    interaction_type in ('VIEW', 'BOOKMARK', 'APPLY', 'SHARE', 'DISMISS')
  ),
  created_at timestamp with time zone default now()
);

comment on table user_benefit_interactions is '개인화 추천 및 사용자 행동 분석용';
comment on column user_benefit_interactions.interaction_type is 'VIEW: 조회, BOOKMARK: 북마크, APPLY: 신청, SHARE: 공유, DISMISS: 관심없음';

create index idx_interactions_user on user_benefit_interactions(user_id, created_at desc);
create index idx_interactions_benefit on user_benefit_interactions(benefit_id, interaction_type);
create index idx_interactions_type on user_benefit_interactions(interaction_type, created_at desc);

-- [8] 알림 발송 이력
create table notification_history (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id) on delete cascade,
  benefit_id bigint references benefits(id) on delete set null,
  notification_type text not null check (
    notification_type in ('NEW_BENEFIT', 'DEADLINE_ALERT', 'REGION_CHECK', 'WEEKLY_DIGEST')
  ),
  message_content text,
  sent_at timestamp with time zone default now(),
  is_read boolean default false,
  read_at timestamp with time zone
);

comment on table notification_history is '알림톡 발송 이력 및 중복 방지';
comment on column notification_history.notification_type is 'NEW_BENEFIT: 신규 혜택, DEADLINE_ALERT: 마감 임박, REGION_CHECK: 거주지 확인, WEEKLY_DIGEST: 주간 요약';

create index idx_notifications_user on notification_history(user_id, sent_at desc);
create index idx_notifications_benefit on notification_history(benefit_id);
create index idx_notifications_type on notification_history(notification_type, sent_at desc);

-- ============================================
-- 운영 관리 테이블
-- ============================================

-- [9] API 수집 및 동기화 로그
create table api_sync_logs (
  id uuid primary key default uuid_generate_v4(),
  source_name text not null,
  sync_type text check (sync_type in ('API', 'CRAWL', 'MANUAL')),
  status text not null check (status in ('SUCCESS', 'PARTIAL', 'FAIL')),
  started_at timestamp with time zone default now(),
  finished_at timestamp with time zone,
  rows_affected int default 0,
  duplicates_skipped int default 0,
  error_log text,
  metadata jsonb
);

comment on table api_sync_logs is '데이터 수집 자동화 배치 작업 이력 관리 (매일 1회 실행)';
comment on column api_sync_logs.duplicates_skipped is '2단계 중복 제거 전략으로 걸러진 건수';

create index idx_sync_logs_source on api_sync_logs(source_name, started_at desc);
create index idx_sync_logs_status on api_sync_logs(status, started_at desc);

-- ============================================
-- 유틸리티 함수
-- ============================================

-- [10] 자동 updated_at 갱신 트리거
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger update_users_updated_at before update on users
  for each row execute function update_updated_at_column();

create trigger update_benefits_updated_at before update on benefits
  for each row execute function update_updated_at_column();

create trigger update_region_codes_updated_at before update on region_codes
  for each row execute function update_updated_at_column();

-- [11] 만료된 혜택 자동 비활성화 함수
create or replace function deactivate_expired_benefits()
returns void as $$
begin
  update benefits
  set is_active = false
  where application_end_date < current_date
    and is_active = true;
end;
$$ language plpgsql;

comment on function deactivate_expired_benefits is '매일 실행: 마감일 지난 혜택 자동 아카이빙 (3개월 후 삭제)';

-- [12] 중복 제거용 해시 생성 함수
create or replace function generate_content_hash(p_title text, p_content text)
returns text as $$
begin
  return md5(lower(regexp_replace(p_title || p_content, '\s+', '', 'g')));
end;
$$ language plpgsql immutable;

comment on function generate_content_hash is '제목+내용 기반 해시 생성 (공백 제거 후 소문자 변환)';

-- ============================================
-- 하이브리드 RAG 검색 함수
-- ============================================

-- [13] 하이브리드 검색 함수
create or replace function search_benefits_hybrid(
  query_embedding vector(1024),
  user_region text,
  user_age int,
  user_gender text,
  limit_count int default 5
)
returns table (
  benefit_id bigint,
  title text,
  content text,
  original_url text,
  similarity float
) as $$
begin
  return query
  select 
    b.id as benefit_id,
    b.title,
    b.content,
    b.original_url,
    1 - (be.embedding <=> query_embedding) as similarity
  from benefits b
  join benefit_embeddings be on b.id = be.benefit_id
  where b.is_active = true
    and (b.application_end_date is null or b.application_end_date >= current_date)
    and (user_region = any(b.region_codes) or 'ALL' = any(b.region_codes))
    and (b.target_age_min is null or b.target_age_min <= user_age)
    and (b.target_age_max is null or b.target_age_max >= user_age)
    and (b.target_gender is null or b.target_gender in ('ALL', user_gender))
  order by be.embedding <=> query_embedding
  limit limit_count;
end;
$$ language plpgsql;

comment on function search_benefits_hybrid is '하이브리드 RAG: SQL 필터링 + 벡터 유사도 검색';

-- ============================================
-- Row Level Security (RLS) 정책
-- ============================================

-- [14] 사용자 데이터 보호
alter table users enable row level security;
alter table user_benefit_interactions enable row level security;
alter table notification_history enable row level security;

-- 사용자는 본인 데이터만 조회 가능
create policy "Users can view own data"
  on users for select
  using (auth.uid()::text = kakao_user_id);

create policy "Users can update own data"
  on users for update
  using (auth.uid()::text = kakao_user_id);

-- 상호작용 로그는 본인 것만 조회
create policy "Users can view own interactions"
  on user_benefit_interactions for select
  using (user_id = (select id from users where kakao_user_id = auth.uid()::text));

-- 알림 이력은 본인 것만 조회
create policy "Users can view own notifications"
  on notification_history for select
  using (user_id = (select id from users where kakao_user_id = auth.uid()::text));

-- ============================================
-- 설치 완료 확인
-- ============================================

-- 테이블 목록 확인
select 
  schemaname,
  tablename,
  tableowner
from pg_tables
where schemaname = 'public'
order by tablename;

-- 확장 확인
select * from pg_extension where extname in ('vector', 'uuid-ossp');

-- 완료 메시지
do $$
begin
  raise notice '✅ 똑순이 데이터베이스 스키마 설치 완료!';
  raise notice '📊 생성된 테이블: 9개';
  raise notice '🔧 생성된 함수: 4개';
  raise notice '🔐 RLS 정책: 4개';
  raise notice '';
  raise notice '다음 단계:';
  raise notice '1. 행정동 코드 데이터 수집';
  raise notice '2. AWS Lambda 환경 구축';
  raise notice '3. 카카오 챗봇 연동';
end $$;
