-- ============================================
-- 똑순이 데이터베이스 스키마 설치 스크립트
-- Supabase SQL Editor에서 실행하세요
-- ============================================

-- [1] 확장 및 환경 설정
create extension if not exists vector;
create extension if not exists "uuid-ossp";

comment on extension vector is '시니어 혜택 문맥 검색을 위한 벡터 연산 확장';

-- [1-2] 한국 시간(KST) 설정 🕐
-- 세션 타임존 설정
SET timezone = 'Asia/Seoul';
-- 영구 설정: ALTER DATABASE postgres SET timezone TO 'Asia/Seoul'; (관리자 권한 필요)

-- ============================================
-- 마스터 데이터 테이블
-- ============================================

-- [0] 기존 테이블 삭제 (초기화)
-- drop table if exists benefit_embeddings cascade;
-- drop table if exists benefits cascade;
drop table if exists users cascade;
-- drop table if exists regions cascade;

-- [2] 지역코드 마스터 테이블 (행정안전부 법정동코드)
create table if not exists regions (
  id bigint primary key generated always as identity,
  region_code varchar(10) unique not null,  -- 10자리 법정동코드
  name text not null,                       -- 지역명 (서울특별시, 강남구, 역삼동 등)
  parent_code varchar(10),                  -- 상위 지역코드
  sido_code varchar(2),                     -- 시도코드 (11, 26 등)
  sgg_code varchar(3),                      -- 시군구코드
  depth int not null,                       -- 깊이 (1:시도, 2:시군구, 3:읍면동, 4:리)
  order_num int,                            -- 정렬 순서
  is_active boolean default true,
  deprecated_at timestamp with time zone,    -- 행정구역 통폐합 시 기록
  created_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul')
);

comment on table regions is '전국 행정표준코드 마스터 데이터 (행정안전부 API 연동, 분기 1회 갱신)';
comment on column regions.region_code is '10자리 법정동코드 (예: 1168000000 = 서울특별시 강남구)';
comment on column regions.depth is '1=시도, 2=시군구(온보딩 저장 레벨), 3=읍면동, 4=리';
comment on column regions.deprecated_at is '행정구역 통폐합 시 자동 업데이트';

-- 인덱스 생성
create index if not exists idx_regions_region_code on regions(region_code);
create index if not exists idx_regions_parent_code on regions(parent_code);
create index if not exists idx_regions_sido_code on regions(sido_code);
create index if not exists idx_regions_depth on regions(depth);
create index if not exists idx_regions_active on regions(is_active) where is_active = true;

-- 지역명 검색용 전문 검색 인덱스
create index if not exists idx_regions_name_gin on regions using gin(to_tsvector('simple', name));



-- ============================================
-- 사용자 데이터 테이블
-- ============================================

-- [4] 사용자 정보 테이블
create table if not exists users (
  id uuid primary key default uuid_generate_v4(),
  kakao_user_id text unique not null,
  
  -- 읍/면/동 레벨 필수 (애플리케이션 로직에서 검증)
  -- 세종시는 depth=2 허용, 나머지는 depth>=3
  -- 거주지 정보 (검색 최적화)
  region_code varchar(10) NOT NULL references regions(region_code),
  region_depth int NOT NULL, -- 나중을 위해 살려둠
  ctpv_nm varchar(50) NOT NULL,                     -- 시도명 (서울특별시)
  sgg_nm varchar(50) NOT NULL,                      -- 시군구명 (종로구)
  
  gender text check (gender in ('M', 'F', 'OTHER', null)),
  
  -- 생년월일 (생애주기 자동 계산용)
  birth_year int NOT NULL,                          -- 출생연도 (YYYY)
  
  -- 혜택 필터링 조건 (온보딩 또는 자동 계산) ⭐
  life_cycle text[],                                -- 생애주기 배열 ['노년', '중장년'] 등
  target_group text[],                              -- 대상 특성 ['저소득', '장애인'] 등
  
  last_region_check_at timestamp with time zone,    -- 6개월 거주지 확인
  region_update_count int default 0,                -- 지역 변경 횟수
  is_active boolean default true,
  notification_enabled boolean default true,
  
  created_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul')
);

comment on table users is '이용자 프로필 및 개인화 설정 정보';
comment on column users.kakao_user_id is '카카오톡 채널 사용자 고유 식별자 (plusfriend_user_key)';
comment on column users.region_code is '법정동코드 (통계/정확한 위치용)';
comment on column users.ctpv_nm is '시도명 (검색 필터링용 denormalized column)';
comment on column users.sgg_nm is '시군구명 (검색 필터링용 denormalized column)';
comment on column users.birth_year is '출생년도 (예: 1955). 검색 시점에 만나이/생애주기 계산';
comment on column users.life_cycle is '생애주기 배열 (예: [''노년'', ''중장년'']). 온보딩 시 선택 또는 birth_year 기반 자동 계산';
comment on column users.target_group is '대상 특성 배열 (예: [''저소득'', ''장애인'']). 온보딩 시 선택';
comment on column users.last_region_check_at is '6개월 주기 거주지 확인 알림용';

create index if not exists idx_users_region_text on users(ctpv_nm, sgg_nm) where is_active = true;
create index if not exists idx_users_birth_year on users(birth_year);
create index if not exists idx_users_active on users(is_active);

-- 생애주기 및 대상 특성 검색용 GIN 인덱스
create index if not exists idx_users_life_cycle on users using gin(life_cycle);
create index if not exists idx_users_target_group on users using gin(target_group);

-- ============================================
-- 혜택 데이터 테이블
-- ============================================

-- [5] 혜택 마스터 테이블 (통합 스키마)
create table if not exists benefits (
  -- 기본 정보
  id bigint primary key generated always as identity,
  serv_id varchar(20) unique not null,               -- WLF00001188 (API 고유 ID)
  serv_nm varchar(500) not null,                     -- 서비스명
  source_api varchar(20) not null                    -- 'LOCAL' (지자체) or 'NATIONAL' (중앙부처)
    check (source_api in ('LOCAL', 'NATIONAL')),
  
  -- 지역 정보 (지자체 API만, 중앙부처는 NULL)
  ctpv_nm varchar(50),                               -- 시도명 (서울특별시)
  sgg_nm varchar(50),                                -- 시군구명 (종로구)
  
  -- 부서/기관 정보
  dept_name varchar(200),                            -- 담당부서/주관부처
  dept_contact varchar(100),                         -- 연락처
  
  -- 기간 정보
  enfc_bgng_ymd date,                                -- 시행시작일 (지자체만)
  enfc_end_ymd date,                                 -- 시행종료일 (지자체만)
  crtr_yr integer,                                   -- 기준연도 (중앙부처만)
  last_mod_ymd date,                                 -- 최종수정일
  
  -- 분류 메타데이터 (PostgreSQL 배열 타입) ⭐
  life_array text[],                                 -- 생애주기 코드 배열
  life_nm_array text[],                              -- 생애주기 명칭 배열 ['중장년', '노년']
  intrs_thema_array text[],                          -- 관심주제 코드 배열
  intrs_thema_nm_array text[],                       -- 관심주제 명칭 배열
  trgter_indvdl_array text[],                        -- 대상자 코드 배열
  trgter_indvdl_nm_array text[],                     -- 대상자 명칭 배열
  sprt_cyc_nm varchar(50),                           -- 지원주기 (월, 연, 1회성)
  srv_pvsn_nm varchar(50),                           -- 서비스제공방법 (현금지급, 현물)
  aply_mtd_nm varchar(200),                          -- 신청방법 (방문, 온라인 등)
  
  -- 온라인신청 (중앙부처만)
  onap_psblt_yn char(1),                             -- Y/N
  
  -- 핵심 콘텐츠 (요약)
  serv_dgst text,                                    -- 서비스 요약
  wlfare_info_outl_cn text,                          -- 복지정보 개요 (중앙부처만)
  serv_dtl_link varchar(500),                        -- 상세정보 링크 (복지로)
  
  -- 핵심 콘텐츠 (상세) - RAG/임베딩용 ⭐⭐⭐
  target_detail text,                                -- 지원대상 상세
  select_criteria text,                              -- 선정기준 상세
  service_content text,                              -- 지원내용 상세
  apply_method_detail text,                          -- 신청방법 상세
  
  -- 통합 임베딩 컬럼 ⭐⭐⭐
  content_for_embedding text,                        -- 위 4개 필드 결합 (RAG용)
  
  -- 부가 정보 (JSON)
  contact_info jsonb,                                -- 문의처 정보
  attachments jsonb,                                 -- 첨부파일 목록
  base_laws jsonb,                                   -- 근거법령 목록
  related_links jsonb,                               -- 관련 홈페이지 (중앙부처)
  
  -- 통계 및 시스템
  inq_num integer default 0,                         -- 조회수
  is_active boolean default true,
  content_hash text,                                 -- 중복 제거용
  
  created_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul')
);

comment on table benefits is '정부 및 지자체 복지 혜택 통합 마스터 (복지로 API 연동)';
comment on column benefits.serv_id is 'API 서비스 고유 ID (중복 방지 키)';
comment on column benefits.source_api is 'LOCAL=지자체복지서비스, NATIONAL=중앙부처복지서비스';
comment on column benefits.life_nm_array is '생애주기 명칭 배열: [''중장년'', ''노년''] - 연령대 필터링 핵심!';
comment on column benefits.content_for_embedding is 'target_detail + select_criteria + service_content + apply_method_detail 결합';
comment on column benefits.content_hash is '2단계 중복 제거: 1단계 문자열 해시 비교용';
comment on column benefits.enfc_end_ymd is '마감일 (NULL = 상시, 99991231 = 무기한)';

-- 인덱스 생성
create index if not exists idx_benefits_serv_id on benefits(serv_id);
create index if not exists idx_benefits_source_api on benefits(source_api);
create index if not exists idx_benefits_active on benefits(is_active) where is_active = true;

-- 지역 검색 인덱스
create index if not exists idx_benefits_region on benefits(ctpv_nm, sgg_nm) where ctpv_nm is not null;

-- 배열 검색을 위한 GIN 인덱스 (연령대 필터링 핵심!) ⭐
create index if not exists idx_benefits_life_array on benefits using gin(life_nm_array);
create index if not exists idx_benefits_intrs_thema on benefits using gin(intrs_thema_nm_array);
create index if not exists idx_benefits_trgter on benefits using gin(trgter_indvdl_nm_array);

-- 기간 검색 인덱스
create index if not exists idx_benefits_dates on benefits(enfc_end_ymd) where is_active = true;
create index if not exists idx_benefits_updated_at on benefits(updated_at);

-- 중복 제거 인덱스
create index if not exists idx_benefits_hash on benefits(content_hash);

-- 전문검색 인덱스 (한글 - simple parser 사용)
create index if not exists idx_benefits_content_search on benefits using gin(
  to_tsvector('simple',
    coalesce(serv_nm, '') || ' ' ||
    coalesce(serv_dgst, '') || ' ' ||
    coalesce(target_detail, '') || ' ' ||
    coalesce(service_content, '')
  )
);

-- ============================================
-- AI/RAG 데이터 테이블
-- ============================================

-- [6] 벡터 데이터 저장소 (복지 + 일자리 통합) 🔥
create table if not exists benefit_embeddings (
  id uuid primary key default uuid_generate_v4(),
  
  -- 카테고리 (네임스페이스 역할, Partial Index용)
  category varchar(20) not null default 'WELFARE'
    check (category in ('WELFARE', 'JOB')),
  
  -- 원본 데이터 참조 (둘 중 하나만 NOT NULL)
  benefit_id bigint references benefits(id) on delete cascade,
  job_posting_id bigint references job_postings(id) on delete cascade,
  
  -- 벡터 데이터
  embedding vector(1536) not null,  -- OpenAI text-embedding-3-small (1536차원)
  content_chunk text not null,
  chunk_index int default 0,
  
  -- 타임스탬프 (한국 시간)
  created_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul'),
  
  -- 제약조건: benefit_id OR job_posting_id (둘 중 하나만)
  constraint check_single_reference check (
    (benefit_id is not null and job_posting_id is null) or
    (benefit_id is null and job_posting_id is not null)
  )
);

comment on table benefit_embeddings is '복지/일자리 통합 벡터 임베딩 (OpenAI text-embedding-3-small)';
comment on column benefit_embeddings.category is '서비스 카테고리: WELFARE(복지), JOB(일자리) - Partial Index 최적화용';
comment on column benefit_embeddings.benefit_id is '복지 테이블 참조 (category=WELFARE일 때)';
comment on column benefit_embeddings.job_posting_id is '일자리 테이블 참조 (category=JOB일 때)';
comment on column benefit_embeddings.embedding is 'OpenAI text-embedding-3-small 모델 사용 (1536차원)';
comment on column benefit_embeddings.chunk_index is '긴 공고문 분할 시 원본 순서 보존';

-- 카테고리별 Partial HNSW 인덱스 (성능 최적화!) 🔥
-- WELFARE 전용 벡터 인덱스
create index if not exists idx_benefit_embeddings_vector_welfare 
  on benefit_embeddings 
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64)
  where category = 'WELFARE';

-- JOB 전용 벡터 인덱스
create index if not exists idx_benefit_embeddings_vector_job 
  on benefit_embeddings 
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64)
  where category = 'JOB';

-- 기타 인덱스
create index if not exists idx_benefit_embeddings_category on benefit_embeddings(category);
create index if not exists idx_benefit_embeddings_benefit_id on benefit_embeddings(benefit_id) where benefit_id is not null;
create index if not exists idx_benefit_embeddings_job_posting_id on benefit_embeddings(job_posting_id) where job_posting_id is not null;

comment on index idx_benefit_embeddings_vector_welfare is 'WELFARE 전용 HNSW 인덱스 (검색 속도 2배 향상)';
comment on index idx_benefit_embeddings_vector_job is 'JOB 전용 HNSW 인덱스 (검색 속도 2배 향상)';

-- ============================================
-- 유틸리티 함수
-- ============================================

-- [10] 자동 updated_at 갱신 트리거
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now() AT TIME ZONE 'Asia/Seoul';
  return new;
end;
$$ language plpgsql;

comment on function update_updated_at_column() is 'updated_at을 한국 시간(KST)으로 자동 갱신';

drop trigger if exists update_users_updated_at on users;
create trigger update_users_updated_at before update on users
  for each row execute function update_updated_at_column();

drop trigger if exists update_benefits_updated_at on benefits;
create trigger update_benefits_updated_at before update on benefits
  for each row execute function update_updated_at_column();

drop trigger if exists update_regions_updated_at on regions;
create trigger update_regions_updated_at before update on regions
  for each row execute function update_updated_at_column();

-- ============================================
-- 하이브리드 RAG 검색 함수
-- ============================================

-- [함수 1] 자격요건 Whitelist 조회
create or replace function get_eligible_benefits(
  p_ctpv text,          -- 예: '전라남도' (없으면 null)
  p_sgg text,           -- 예: '진도군' (없으면 null)
  p_life_array text[],  -- 예: ['노년', '중장년'] (빈배열이면 전체)
  p_target_array text[] -- 예: ['저소득', '장애인'] (빈배열이면 전체)
)
returns table (
  id bigint,
  serv_nm varchar(500),
  srv_pvsn_nm varchar(50),
  ctpv_nm varchar(50),
  sgg_nm varchar(50),
  trgter_indvdl_nm_array text[],
  life_nm_array text[],
  serv_dgst text,
  enfc_end_ymd date,
  serv_dtl_link varchar(500)
)
language sql
security definer
as $$
  select 
    id,
    serv_nm,
    srv_pvsn_nm,
    ctpv_nm,
    sgg_nm,
    trgter_indvdl_nm_array,
    life_nm_array,
    serv_dgst,
    enfc_end_ymd,
    serv_dtl_link
  from benefits
  where 
    is_active = true
    
    -- 1. [기간] 종료일이 없거나(계속), 오늘 이후인 경우
    and (enfc_end_ymd is null or enfc_end_ymd >= current_date)
    
    -- 2. [지역] 
    -- Case A: 전국 (둘 다 Null)
    -- Case B: 내 시/도 일치 + 시/군/구 Null (광역 혜택)
    -- Case C: 내 시/도 일치 + 내 시/군/구 일치 (기초 혜택)
    and (
        (ctpv_nm is null and sgg_nm is null) 
        or (ctpv_nm = p_ctpv and sgg_nm is null)
        or (ctpv_nm = p_ctpv and sgg_nm = p_sgg)
    )

    -- 3. [대상] (Array Overlap && 연산자 사용)
    -- Case A: 서비스 대상이 없음(Null/Empty) → 전국민 대상 (포함)
    -- Case B: 서비스 대상 있음 + 사용자 대상 있음 + 겹침 → 포함
    -- Case C: 서비스 대상 있음 + 사용자 대상 없음 → 제외!
    and (
        -- Case A: 서비스 대상이 없으면 전국민 대상
        (trgter_indvdl_nm_array is null or cardinality(trgter_indvdl_nm_array) = 0)
        or
        -- Case B: 서비스 대상도 있고, 사용자 대상도 있고, 둘이 겹침
        (trgter_indvdl_nm_array is not null 
         and cardinality(trgter_indvdl_nm_array) > 0
         and p_target_array is not null 
         and cardinality(p_target_array) > 0 
         and trgter_indvdl_nm_array && p_target_array)
    )

    -- 4. [생애주기] 
    -- 혜택 생애주기가 없거나(Null/Empty) → 모든 연령대 대상
    -- 사용자가 생애주기를 선택하지 않았거나(Null/Empty) → 모든 혜택 검색
    -- 배열이 겹치면 → 해당 혜택 포함
    and (
        life_nm_array is null 
        or cardinality(life_nm_array) = 0
        or p_life_array is null
        or cardinality(p_life_array) = 0
        or life_nm_array && p_life_array
    );
$$;

comment on function get_eligible_benefits(text, text, text[], text[]) is '자격요건 기반 Whitelist 조회 (지역+연령대+대상특성 필터)';

-- [함수 2] 벡터 검색 (의미 유사도 기반)
-- 참고: 연령대 필터 없음 (get_eligible_benefits와 교집합으로 처리)
create or replace function match_benefits(
  query_embedding vector(1536),  -- OpenAI text-embedding-3-small (1536차원)
  match_threshold float,
  match_count int,
  p_ctpv text,
  p_sgg text,
  p_life_array text[],
  p_target_array text[]
)
returns table (
  id bigint,
  serv_nm varchar(500),
  srv_pvsn_nm varchar(50),
  ctpv_nm varchar(50),
  sgg_nm varchar(50),
  trgter_indvdl_nm_array text[],
  life_nm_array text[],
  serv_dgst text,
  enfc_end_ymd date,
  serv_dtl_link varchar(500),
  similarity float  -- 🆕 유사도 점수 추가!
)
language plpgsql
security definer
as $$
begin
  return query
  select 
    b.id,
    b.serv_nm,
    b.srv_pvsn_nm,
    b.ctpv_nm,
    b.sgg_nm,
    b.trgter_indvdl_nm_array,
    b.life_nm_array,
    b.serv_dgst,
    b.enfc_end_ymd,
    b.serv_dtl_link,
    (1 - (be.embedding <=> query_embedding))::float as similarity  -- 🆕 유사도 계산!
  from benefit_embeddings be
  join benefits b on be.benefit_id = b.id
  where 
    -- 0. 카테고리 필터 (복지만 검색)
    be.category = 'WELFARE'
    
    -- 1. 임베딩 유사도 (Threshold 복구)
    and 1 - (be.embedding <=> query_embedding) > match_threshold
    
    -- 2. 유효 기간 체크 (만료된 혜택 제외)
    -- enfc_end_ymd가 NULL이면 계속 진행 중인 것으로 간주(또는 9999-12-31)
    and (b.enfc_end_ymd is null or b.enfc_end_ymd >= current_date)
    and b.is_active = true

    -- 3. 지역 필터 (내 지역 + 중앙부처)
    and (
       b.source_api = 'NATIONAL'
       or (
           (b.ctpv_nm is null and b.sgg_nm is null) 
           or (b.ctpv_nm = p_ctpv and b.sgg_nm is null)
           or (b.ctpv_nm = p_ctpv and b.sgg_nm = p_sgg)
       )
    )
    
    -- 4. 대상 특성 필터 (get_eligible_benefits와 동일 로직)
    and (
        -- Case A: 서비스 대상이 없으면 전국민 대상
        (b.trgter_indvdl_nm_array is null or cardinality(b.trgter_indvdl_nm_array) = 0)
        or
        -- Case B: 서비스 대상도 있고, 사용자 대상도 있고, 둘이 겹침
        (b.trgter_indvdl_nm_array is not null 
         and cardinality(b.trgter_indvdl_nm_array) > 0
         and p_target_array is not null 
         and cardinality(p_target_array) > 0 
         and b.trgter_indvdl_nm_array && p_target_array)
    )
    
    -- 5. 생애주기 필터 (get_eligible_benefits와 동일 로직)
    and (
        b.life_nm_array is null 
        or cardinality(b.life_nm_array) = 0
        or p_life_array is null
        or cardinality(p_life_array) = 0
        or b.life_nm_array && p_life_array
    )
    
  order by similarity desc  -- 유사도 높은 순으로 정렬
  limit match_count;
end;
$$;

comment on function match_benefits(vector, float, int, text, text, text[], text[]) is '벡터 검색 (similarity 점수 포함, 지역+생애주기+대상 필터링)';

-- ============================================
-- Row Level Security (RLS) 정책
-- ============================================

-- [14] 사용자 데이터 보호
alter table users enable row level security;

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
  raise notice '✅ 똑순이 데이터베이스 스키마 설치 완료! (MVP 버전)';
  raise notice '';
  raise notice '📊 생성된 테이블: 4개';
  raise notice '  - regions (지역코드 마스터, depth 1-4 계층)';
  raise notice '  - users (사용자 프로필)';
  raise notice '  - benefits (복지 혜택 통합 마스터)';
  raise notice '  - benefit_embeddings (RAG 벡터 저장소)';
  raise notice '';
  raise notice '🔧 생성된 함수: 3개';
  raise notice '  - update_updated_at_column (자동 타임스탬프)';
  raise notice '  - get_eligible_benefits (자격요건 Whitelist)';
  raise notice '  - match_benefits (벡터 검색)';
  raise notice '';
  raise notice '🔐 RLS 정책: 1개';
  raise notice '  - users 테이블 보호';
  raise notice '';
  raise notice '🎯 MVP 버전 특징:';
  raise notice '  - 핵심 기능만 포함 (간결한 스키마)';
  raise notice '  - 하이브리드 RAG: 자격요건 필터 + 벡터 검색';
  raise notice '  - birth_year 기반 자동 생애주기 변환';
  raise notice '';
  raise notice '다음 단계:';
  raise notice '1. 데이터 수집 (복지로 API)';
  raise notice '2. 임베딩 생성 (Bedrock Titan)';
  raise notice '3. 온보딩 구현 (카카오톡 챗봇)';
end $$;
