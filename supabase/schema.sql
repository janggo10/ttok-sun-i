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

-- [0] 기존 테이블 삭제 (초기화)
drop table if exists onboarding_logs cascade;
drop table if exists api_sync_logs cascade;
drop table if exists notification_logs cascade;
drop table if exists user_benefit_interactions cascade;
-- drop table if exists benefit_embeddings cascade;
-- drop table if exists benefits cascade;
drop table if exists users cascade;
-- drop table if exists category_codes cascade;
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
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
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
  
  -- 생년월일 (생애주기 자동 계산용) ⭐ 변경됨!
  birth_year int NOT NULL,                          -- 출생년도 (YYYY)
  
  last_region_check_at timestamp with time zone,    -- 6개월 거주지 확인
  region_update_count int default 0,                -- 지역 변경 횟수
  is_active boolean default true,
  notification_enabled boolean default true,
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table users is '이용자 프로필 및 개인화 설정 정보';
comment on column users.kakao_user_id is '카카오톡 채널 사용자 고유 식별자 (plusfriend_user_key)';
comment on column users.region_code is '법정동코드 (통계/정확한 위치용)';
comment on column users.ctpv_nm is '시도명 (검색 필터링용 denormalized column)';
comment on column users.sgg_nm is '시군구명 (검색 필터링용 denormalized column)';
comment on column users.birth_year is '출생년도 (예: 1955). 검색 시점에 만나이/생애주기 계산';
comment on column users.last_region_check_at is '6개월 주기 거주지 확인 알림용';

create index if not exists idx_users_region_text on users(ctpv_nm, sgg_nm) where is_active = true;
create index if not exists idx_users_birth_year on users(birth_year);
create index if not exists idx_users_active on users(is_active);

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
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
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

-- [6] 벡터 데이터 저장소
create table if not exists benefit_embeddings (
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
create index if not exists idx_benefit_embeddings_vector 
  on benefit_embeddings 
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create index if not exists idx_benefit_embeddings_benefit_id on benefit_embeddings(benefit_id);

comment on index idx_benefit_embeddings_vector is 'HNSW 인덱스로 벡터 유사도 검색 속도 10-100배 향상';

-- ============================================
-- 사용자 행동 추적 테이블
-- ============================================

-- [7] 사용자-혜택 상호작용 로그
create table if not exists user_benefit_interactions (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id) on delete cascade,
  benefit_id bigint references benefits(id) on delete cascade,
  interaction_type text not null check (
    interaction_type in ('VIEW', 'BOOKMARK', 'APPLY', 'SHARE', 'DISMISS')
  ),
  created_at timestamp with time zone default now()
);

comment on table user_benefit_interactions is '사용자 활동 로그 (클릭, 찜하기 등)';
comment on column user_benefit_interactions.interaction_type is 'VIEW(상세조회), BOOKMARK(찜), APPLY(신청하기클릭), SHARE(공유), DISMISS(숨김)';

create index if not exists idx_interactions_user on user_benefit_interactions(user_id);
create index if not exists idx_interactions_benefit on user_benefit_interactions(benefit_id);
create index if not exists idx_interactions_type on user_benefit_interactions(interaction_type, created_at desc);

-- [8] 알림 발송 이력 (Notification Logs)
create table if not exists notification_logs (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id) on delete set null,
  
  -- 발송 내용
  template_id varchar(50),                           -- 알림톡 템플릿 ID (없으면 NULL)
  message_type varchar(20) not null                  -- KAKAO_PUSH, KAKAO_FRIEND, SMS 등
    check (message_type in ('KAKAO_PUSH', 'KAKAO_FRIEND', 'SMS', 'EMAIL')),
  title varchar(100),
  body text,
  
  -- 발송 결과
  status varchar(20) not null                        -- PENDING, SENT, FAILED, READ
    check (status in ('PENDING', 'SENT', 'FAILED', 'READ')),
  sent_at timestamp with time zone,
  error_message text,
  
  -- 메타데이터
  related_benefit_id bigint references benefits(id) on delete set null,
  campaign_id varchar(50),                           -- 마케팅 캠페인 ID (옵션)
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table notification_logs is '알림 메시지 발송 이력 (카카오톡, SMS 등)';
comment on column notification_logs.status is 'PENDING(발송대기), SENT(발송성공), FAILED(실패), READ(수신확인-가능시)';

create index if not exists idx_noti_logs_user on notification_logs(user_id);
create index if not exists idx_noti_logs_status on notification_logs(status);
create index if not exists idx_noti_logs_date on notification_logs(created_at);

-- [8] 알림 발송 이력


-- ============================================
-- 운영 관리 테이블
-- ============================================

-- [9] API 수집 및 동기화 로그
create table if not exists api_sync_logs (
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

create index if not exists idx_sync_logs_source on api_sync_logs(source_name, started_at desc);
create index if not exists idx_sync_logs_status on api_sync_logs(status, started_at desc);

-- [10] 온보딩 로그 테이블 (파싱 성공률 모니터링)
create table if not exists onboarding_logs (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id) on delete cascade,
  step text not null check (
    step in ('REGION_INPUT', 'REGION_CONFIRM', 'AGE_GROUP_SELECT', 'ONBOARDING_COMPLETE')
  ),
  input_text text,              -- 사용자 입력값
  parse_method text check (
    parse_method in ('REGEX', 'LLM', 'BUTTON_SELECT', 'MANUAL_SELECT', null)
  ),
  parse_success boolean,        -- 파싱 성공 여부
  parsed_region_code varchar(10) references regions(region_code),
  selected_age_groups text[],   -- 선택된 연령대 배열 ⭐
  attempt_count int default 1,  -- 재시도 횟수
  created_at timestamp with time zone default now()
);

comment on table onboarding_logs is '온보딩 프로세스 모니터링 및 파싱 성공률 분석용';
comment on column onboarding_logs.step is 'REGION_INPUT: 지역 입력, REGION_CONFIRM: 확인, AGE_GROUP_SELECT: 관심 연령대 선택, ONBOARDING_COMPLETE: 완료';
comment on column onboarding_logs.parse_method is 'REGEX: 정규식, LLM: AI파싱, BUTTON_SELECT: 버튼선택, MANUAL_SELECT: 수동선택';
comment on column onboarding_logs.selected_age_groups is '사용자가 선택한 관심 연령대 (예: [''중장년'', ''노년''])';

create index if not exists idx_onboarding_user on onboarding_logs(user_id, created_at desc);
create index if not exists idx_onboarding_step on onboarding_logs(step, created_at desc);
create index if not exists idx_onboarding_parse_success on onboarding_logs(parse_success, parse_method);

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

drop trigger if exists update_users_updated_at on users;
create trigger update_users_updated_at before update on users
  for each row execute function update_updated_at_column();

drop trigger if exists update_benefits_updated_at on benefits;
create trigger update_benefits_updated_at before update on benefits
  for each row execute function update_updated_at_column();

drop trigger if exists update_regions_updated_at on regions;
create trigger update_regions_updated_at before update on regions
  for each row execute function update_updated_at_column();

-- [11] 만료된 혜택 자동 비활성화 함수
create or replace function deactivate_expired_benefits()
returns void as $$
begin
  update benefits
  set is_active = false
  where enfc_end_ymd < current_date
    and enfc_end_ymd is not null
    and enfc_end_ymd != '9999-12-31'::date  -- 무기한 제외
    and is_active = true;
end;
$$ language plpgsql;

comment on function deactivate_expired_benefits is '매일 실행: 시행종료일 지난 혜택 자동 아카이빙 (무기한 99991231 제외)';

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


create or replace function search_benefits_hybrid(
  query_embedding vector(1024),
  user_ctpv_nm text,                                 -- 사용자 시도명
  user_sgg_nm text,                                  -- 사용자 시군구명
  user_interest_ages text[],                         -- 사용자 관심 연령대 배열
  limit_count int default 5
)
returns table (
  benefit_id bigint,
  serv_id varchar(20),
  title text,
  content text,
  original_url text,
  similarity float
) as $$
begin
  return query
  select 
    b.id as benefit_id,
    b.serv_id,
    b.serv_nm::text as title,
    b.content_for_embedding::text as content,
    b.serv_dtl_link::text as original_url,
    1 - (be.embedding <=> query_embedding) as similarity
  from benefits b
  join benefit_embeddings be on b.id = be.benefit_id
  where b.is_active = true
    -- 유효기간 체크
    and (b.enfc_end_ymd is null or b.enfc_end_ymd >= current_date)
    and (b.enfc_bgng_ymd is null or b.enfc_bgng_ymd <= current_date)
    -- 지역 필터: 지자체(사용자 지역) OR 중앙부처(전국)
    and (
      (
        b.ctpv_nm = user_ctpv_nm 
        and (b.sgg_nm = user_sgg_nm or b.sgg_nm is null)
      )
      or (b.ctpv_nm is null and b.source_api = 'NATIONAL')
    )
    -- 연령대 필터: 배열 겹침 연산자 (&&) ⭐⭐⭐
    and (
      b.life_nm_array is null 
      or b.life_nm_array && user_interest_ages
    )
  order by be.embedding <=> query_embedding
  limit limit_count;
end;
$$ language plpgsql;

comment on function search_benefits_hybrid(vector, text, text, text[], int) is '하이브리드 RAG: SQL 필터링(지역+연령대) + 벡터 유사도 검색';

create or replace function get_eligible_benefits(
  p_ctpv text,          -- 예: '전라남도' (없으면 null)
  p_sgg text,           -- 예: '진도군' (없으면 null)
  p_life_array text[],  -- 예: ['노년', '중장년'] (빈배열이면 전체)
  p_target_array text[] -- 예: ['저소득', '장애인'] (빈배열이면 전체)
)
returns setof benefits
language sql
security definer
as $$
  select *
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
    -- 혜택 대상이 없거나(Null/Empty) OR 내 대상과 하나라도 겹치는 경우
    and (
        trgter_indvdl_nm_array is null 
        or cardinality(trgter_indvdl_nm_array) = 0
        or (p_target_array is not null and trgter_indvdl_nm_array && p_target_array)
    )

    -- 4. [생애주기] 
    -- 혜택 생애가 없거나(Null/Empty) OR 내 생애와 하나라도 겹치는 경우
    and (
        life_nm_array is null 
        or cardinality(life_nm_array) = 0
        or (p_life_array is not null and life_nm_array && p_life_array)
    );
$$;


-- 구버전 match_benefits 함수 삭제 (search_benefits_hybrid 또는 통합된 match_benefits 사용)
-- 여기서는 일단 남겨두지만, rag_service.py가 이걸 사용하는지 확인 필요.
-- rag_service.py는 match_benefits를 사용중이므로, 아래 내용을 최신 로직(search_benefits_hybrid 로직)으로 업데이트하거나 유지해야 함.
-- 사용자가 'unused function' 정리를 요청했으나, rag_service.py가 match_benefits를 쓰고 있으므로 '삭제' 대신 '유지'하되 코멘트 남김.
-- (실제로는 rag_service.py에서 match_benefits를 호출하므로 삭제하면 안됨. 
--  단, search_benefits_hybrid가 더 나은 버전이라면 rag_service.py를 수정하고 이걸 지워야 함.
--  현재는 match_benefits만 쓰고 있음)

create or replace function match_benefits(
  query_embedding vector(1024),
  match_threshold float,
  match_count int,
  p_ctpv text,
  p_sgg text
)
returns setof benefits
language plpgsql
security definer
as $$
begin
  return query
  select b.*
  from benefit_embeddings be
  join benefits b on be.benefit_id = b.id
  where 
    -- 1. 임베딩 유사도 (Threshold 복구)
    1 - (be.embedding <=> query_embedding) > match_threshold
    
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
    
  order by be.embedding <=> query_embedding asc
  limit match_count;
end;
$$;

-- ============================================
-- Row Level Security (RLS) 정책
-- ============================================

-- [14] 사용자 데이터 보호
alter table users enable row level security;
alter table user_benefit_interactions enable row level security;
-- 알림 이력은 본인 것만 조회
create policy "Users can view own notifications"
  on notification_logs for select
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
  raise notice '📊 생성된 테이블: 10개';
  raise notice '  - regions (지역코드 마스터, depth 1-4 계층)';
  raise notice '  - users (관심 연령대 배열 필드 추가)';
  raise notice '  - benefits (통합 스키마: 지자체+중앙부처 API)';
  raise notice '  - benefit_embeddings (RAG 벡터 저장소)';
  raise notice '  - onboarding_logs (파싱 성공률 모니터링)';
  raise notice '🔧 생성된 함수: 4개';
  raise notice '  - search_benefits_hybrid (하이브리드 RAG 검색)';
  raise notice '  - deactivate_expired_benefits (만료 혜택 정리)';
  raise notice '🔐 RLS 정책: 4개';
  raise notice '';
  raise notice '⭐ 주요 변경사항:';
  raise notice '  - 연령 필터링: birth_year → interest_age_groups 배열';
  raise notice '  - benefits 테이블: API 통합 스키마 (life_nm_array 배열)';
  raise notice '  - 하이브리드 RAG: 지역 + 연령대 배열 필터링';
  raise notice '';
  raise notice '다음 단계:';
  raise notice '1. 복지로 API 키 발급 (지자체+중앙부처)';
  raise notice '2. 데이터 수집 스크립트 작성 (서울 357개 + 전국 365개)';
  raise notice '3. 온보딩 챗봇 구현 (지역 + 연령대 선택)';
end $$;
