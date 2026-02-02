-- ============================================
-- 공공 일자리 (100세누리) 데이터베이스 스키마
-- Supabase SQL Editor에서 실행하세요
-- ============================================

-- [0] 기존 테이블 삭제 (초기화)
drop table if exists job_postings cascade;

-- [1] 일자리 공고 테이블
create table if not exists job_postings (
  -- 기본 정보
  id bigint primary key generated always as identity,
  job_id varchar(50) unique not null,               -- RECR_000000000013950 (API 고유 ID)
  
  -- 채용 정보
  title text not null,                              -- 채용 제목 (recrTitle)
  deadline date,                                    -- 마감일 (deadline)
  
  -- 고용 정보
  employment_type_code varchar(10),                 -- 고용형태 코드 (emplymShp: CM0101~CM0105)
  employment_type_nm varchar(100),                  -- 고용형태 명칭 (emplymShpNm: 시간제일자리, 정규직 등)
  
  -- 기관/근무지 정보
  organization_name text,                           -- 기업/기관명 (oranNm)
  workplace_code varchar(10),                       -- 근무지 코드 (workPlc: 010240)
  workplace_nm text,                                -- 근무지명 (workPlcNm: 중구)
  
  -- 연령/자격 정보
  age_limit int,                                    -- 연령 제한 (age: 60)
  age_limit_max int,                                -- 최대 연령 (ageLim: 제한)
  clerk varchar(100),                               -- 담당자 (clerk: 이동윤외2명)
  clerk_contact varchar(50),                        -- 담당자 연락처 (clerkContt: 070-4005-2721)
  
  -- 채용 분류
  job_category_code varchar(10),                    -- 직종 코드 (jobcls: A08009)
  job_category_nm text,                             -- 직종명 (jobclsNm: 기타)
  
  -- 상세 내용
  detail_content text,                              -- 상세 내용 (detCnts: 4000자)
  wanted_title text,                                -- 채용 제목 (상세 API) (wantedTitle)
  wanted_auth_no varchar(50),                       -- 구인등록번호 (wantedAuthNo)
  
  -- 등록/수정 정보
  create_date timestamp with time zone,             -- 생성일자 (createDy)
  update_date timestamp with time zone,             -- 변경일자 (updDy)
  fri_accept_date date,                             -- 시작접수일 (frAcptDd)
  to_accept_date date,                              -- 종료접수일 (toAcptDd)
  
  -- 근무지 상세 주소
  place_detail_address text,                        -- 주소 (plDetAddr)
  place_biz_nm text,                                -- 사업장명 (plbizNm)
  representative varchar(100),                      -- 담당자 (repr)
  
  -- 추가 정보 (JSON)
  extra_info jsonb,                                 -- 기타 정보 (필요시 확장)
  
  -- 시스템
  is_active boolean default true,
  content_hash text,                                -- 중복 제거용
  
  created_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamp with time zone default (now() AT TIME ZONE 'Asia/Seoul')
);

comment on table job_postings is '100세누리 공공 일자리 정보 (SenuriService API 연동)';
comment on column job_postings.job_id is 'API 일자리 고유 ID (중복 방지 키)';
comment on column job_postings.employment_type_code is 'CM0101:정규직, CM0102:계약직, CM0103:시간제일자리, CM0104:일당직, CM0105:기타';
comment on column job_postings.detail_content is '채용 상세 내용 (최대 4000자) - RAG 임베딩용';
comment on column job_postings.deadline is '마감일 (NULL = 상시, 과거 날짜 = 마감)';

-- 인덱스 생성
create index if not exists idx_job_postings_job_id on job_postings(job_id);
create index if not exists idx_job_postings_active on job_postings(is_active) where is_active = true;
create index if not exists idx_job_postings_deadline on job_postings(deadline);  -- WHERE 절 제거 (쿼리 시점에 필터링)
create index if not exists idx_job_postings_employment_type on job_postings(employment_type_code);
create index if not exists idx_job_postings_workplace on job_postings(workplace_code);
create index if not exists idx_job_postings_updated_at on job_postings(updated_at);

-- 전문검색 인덱스 (한글 - simple parser 사용)
create index if not exists idx_job_postings_content_search on job_postings using gin(
  to_tsvector('simple',
    coalesce(title, '') || ' ' ||
    coalesce(organization_name, '') || ' ' ||
    coalesce(job_category_nm, '') || ' ' ||
    coalesce(detail_content, '')
  )
);

-- 중복 제거 인덱스
create index if not exists idx_job_postings_hash on job_postings(content_hash);

-- 자동 updated_at 갱신 트리거 (기존 함수 재사용)
drop trigger if exists update_job_postings_updated_at on job_postings;
create trigger update_job_postings_updated_at before update on job_postings
  for each row execute function update_updated_at_column();

-- 완료 메시지
do $$
begin
  raise notice '✅ 공공 일자리 테이블 생성 완료!';
  raise notice '';
  raise notice '📊 생성된 테이블: job_postings';
  raise notice '  - 채용 정보: 제목, 마감일, 고용형태';
  raise notice '  - 기관 정보: 기업명, 근무지';
  raise notice '  - 상세 정보: 연령, 직종, 상세내용';
  raise notice '';
  raise notice '🔧 생성된 인덱스: 9개';
  raise notice '  - 마감일 필터 (deadline >= current_date)';
  raise notice '  - 고용형태, 근무지 검색';
  raise notice '  - 전문검색 (제목, 기업명, 직종, 상세내용)';
  raise notice '';
  raise notice '다음 단계:';
  raise notice '1. 데이터 수집 (100세누리 API)';
  raise notice '2. 데이터 분석 (임베딩 필드 선정)';
  raise notice '3. 임베딩 생성 (OpenAI text-embedding-3-small)';
end $$;
