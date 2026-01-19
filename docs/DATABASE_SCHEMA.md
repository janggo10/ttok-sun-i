# 🗄️ 똑순이 데이터베이스 스키마 (Supabase PostgreSQL)

## 개요

- **데이터베이스**: Supabase (PostgreSQL 15+)
- **벡터 검색**: pgvector 확장
- **임베딩 모델**: Amazon Titan Embeddings V2 (1024차원)
- **중복 제거 전략**: 2단계 하이브리드 (문자열 유사도 + 벡터 유사도)

---

## 스키마 설치 스크립트

### [1] 확장 및 환경 설정

```sql
-- pgvector 확장 설치
create extension if not exists vector;
comment on extension vector is '시니어 혜택 문맥 검색을 위한 벡터 연산 확장';

-- UUID 생성 함수 활성화
create extension if not exists "uuid-ossp";
```

---

## 마스터 데이터 테이블

### [2] 행정동 코드 마스터 테이블

```sql
create table region_codes (
  code text primary key,                   -- 10자리 행정표준코드
  full_name text not null,                 -- 전체 지명 (예: 서울특별시 은평구 불광제1동)
  si_do text,                             -- 광역 지자체명
  si_gun_gu text,                         -- 기초 지자체명
  is_active boolean default true,         -- 코드 활성화 여부
  deprecated_at timestamp with time zone, -- 코드 폐지 시점 (통폐합 대응)
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table region_codes is '전국 행정표준코드 마스터 데이터 (행정안전부 API 연동)';
comment on column region_codes.deprecated_at is '행정구역 통폐합 시 자동 업데이트';

-- 인덱스
create index idx_region_codes_active on region_codes(is_active) where is_active = true;
create index idx_region_codes_si_do on region_codes(si_do);
create index idx_region_codes_si_gun_gu on region_codes(si_gun_gu);
```

---

### [3] 카테고리 코드 마스터 테이블

```sql
create table category_codes (
  code text primary key,                   -- 카테고리 코드 (예: C01, C02)
  name text not null,                     -- 카테고리 명칭 (예: 의료지원, 생활비지원)
  description text,                       -- 카테고리 설명
  display_order int default 0,            -- 화면 노출 순서
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
```

---

## 사용자 데이터 테이블

### [4] 사용자 정보 테이블

```sql
create table users (
  id uuid primary key default uuid_generate_v4(),
  kakao_user_id text unique not null,      -- 카카오톡 plusfriend_user_key
  region_code text references region_codes(code), -- 사용자의 주 거주지 행정동 코드
  gender text check (gender in ('M', 'F', 'OTHER', null)), -- 성별
  birth_year int check (birth_year between 1900 and 2100), -- 출생 연도
  
  -- 운영 관리 필드
  last_region_check_at timestamp with time zone, -- 거주지 확인 마지막 시점 (6개월 주기)
  is_active boolean default true,                -- 탈퇴/휴면 사용자 관리
  notification_enabled boolean default true,     -- 푸시 알림 수신 동의
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table users is '이용자 프로필 및 개인화 설정 정보';
comment on column users.kakao_user_id is '카카오톡 채널 사용자 고유 식별자 (plusfriend_user_key)';
comment on column users.last_region_check_at is '6개월 주기 거주지 확인 알림용';

-- 인덱스
create index idx_users_region on users(region_code) where is_active = true;
create index idx_users_birth_year on users(birth_year) where is_active = true;
create index idx_users_active on users(is_active);
```

---

## 혜택 데이터 테이블

### [5] 혜택 마스터 테이블

```sql
create table benefits (
  id bigint primary key generated always as identity,
  title text not null,                    -- 혜택 명칭
  category_codes text[],                  -- 적용 카테고리 코드 배열
  
  -- 대상 필터링
  target_age_min int,                     -- 최소 대상 연령
  target_age_max int,                     -- 최대 대상 연령 (제한 없으면 NULL)
  target_gender text check (target_gender in ('M', 'F', 'ALL', null)), -- 성별 제한
  region_codes text[],                    -- 적용 지역 행정동 코드 배열
  
  -- 혜택 내용
  content text,                           -- 혜택 상세 원문 (AI 답변 생성 및 사용자 노출용)
  original_url text,                      -- 공식 공고 연결 링크
  
  -- 신청 기간
  application_start_date date,            -- 신청 시작일
  application_end_date date,              -- 신청 마감일
  
  -- 운영 관리
  source_name text,                       -- 수집 출처 (보조금24, 복지로, 서울시 등)
  is_active boolean default true,         -- 혜택 종료/중단 시 비활성화
  content_hash text,                      -- 중복 제거용 해시값 (title + content 기반)
  
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);

comment on table benefits is '정부 및 지자체 시니어 혜택 통합 마스터';
comment on column benefits.content_hash is '2단계 중복 제거 전략: 1단계 문자열 해시 비교용';
comment on column benefits.application_end_date is '마감 임박 알림 및 자동 아카이빙 기준';

-- 인덱스
create index idx_benefits_active on benefits(is_active) where is_active = true;
create index idx_benefits_region on benefits using gin(region_codes); -- 배열 검색 최적화
create index idx_benefits_category on benefits using gin(category_codes);
create index idx_benefits_dates on benefits(application_end_date) where is_active = true;
create index idx_benefits_hash on benefits(content_hash); -- 중복 제거 성능 향상
create index idx_benefits_source on benefits(source_name);
```

---

## AI/RAG 데이터 테이블

### [6] 벡터 데이터 저장소

```sql
create table benefit_embeddings (
  id uuid primary key default uuid_generate_v4(),
  benefit_id bigint references benefits(id) on delete cascade, -- 부모 혜택 삭제 시 자동 삭제
  embedding vector(1024),                 -- Amazon Titan Embeddings V2 (1024차원)
  content_chunk text,                     -- 벡터화된 실제 텍스트 조각
  chunk_index int default 0,              -- 청크 순서 (긴 문서 분할 시)
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

-- benefit_id 인덱스 (조인 성능)
create index idx_benefit_embeddings_benefit_id on benefit_embeddings(benefit_id);

comment on index idx_benefit_embeddings_vector is 'HNSW 인덱스로 벡터 유사도 검색 속도 10-100배 향상';
```

---

## 사용자 행동 추적 테이블

### [7] 사용자-혜택 상호작용 로그

```sql
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

-- 인덱스
create index idx_interactions_user on user_benefit_interactions(user_id, created_at desc);
create index idx_interactions_benefit on user_benefit_interactions(benefit_id, interaction_type);
create index idx_interactions_type on user_benefit_interactions(interaction_type, created_at desc);
```

---

### [8] 알림 발송 이력

```sql
create table notification_history (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id) on delete cascade,
  benefit_id bigint references benefits(id) on delete set null,
  notification_type text not null check (
    notification_type in ('NEW_BENEFIT', 'DEADLINE_ALERT', 'REGION_CHECK', 'WEEKLY_DIGEST')
  ),
  message_content text,                   -- 발송된 메시지 내용
  sent_at timestamp with time zone default now(),
  is_read boolean default false,
  read_at timestamp with time zone
);

comment on table notification_history is '알림톡 발송 이력 및 중복 방지';
comment on column notification_history.notification_type is 'NEW_BENEFIT: 신규 혜택, DEADLINE_ALERT: 마감 임박, REGION_CHECK: 거주지 확인, WEEKLY_DIGEST: 주간 요약';

-- 인덱스
create index idx_notifications_user on notification_history(user_id, sent_at desc);
create index idx_notifications_benefit on notification_history(benefit_id);
create index idx_notifications_type on notification_history(notification_type, sent_at desc);
```

---

## 운영 관리 테이블

### [9] API 수집 및 동기화 로그

```sql
create table api_sync_logs (
  id uuid primary key default uuid_generate_v4(),
  source_name text not null,              -- 수집 소스 (예: 보조금24, 서울시 복지공고)
  sync_type text check (sync_type in ('API', 'CRAWL', 'MANUAL')), -- 수집 방식
  status text not null check (status in ('SUCCESS', 'PARTIAL', 'FAIL')), -- 작업 상태
  started_at timestamp with time zone default now(),
  finished_at timestamp with time zone,
  rows_affected int default 0,            -- 신규/업데이트 데이터 건수
  duplicates_skipped int default 0,       -- 중복 제거된 건수
  error_log text,                         -- 실패 시 상세 에러 내용
  metadata jsonb                          -- 추가 메타데이터 (API 응답 등)
);

comment on table api_sync_logs is '데이터 수집 자동화 배치 작업 이력 관리 (매일 1회 실행)';
comment on column api_sync_logs.duplicates_skipped is '2단계 중복 제거 전략으로 걸러진 건수';

-- 인덱스
create index idx_sync_logs_source on api_sync_logs(source_name, started_at desc);
create index idx_sync_logs_status on api_sync_logs(status, started_at desc);
```

---

## 유틸리티 함수

### [10] 자동 updated_at 갱신 트리거

```sql
-- updated_at 자동 갱신 함수
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- users 테이블 트리거
create trigger update_users_updated_at before update on users
  for each row execute function update_updated_at_column();

-- benefits 테이블 트리거
create trigger update_benefits_updated_at before update on benefits
  for each row execute function update_updated_at_column();

-- region_codes 테이블 트리거
create trigger update_region_codes_updated_at before update on region_codes
  for each row execute function update_updated_at_column();
```

---

### [11] 만료된 혜택 자동 비활성화 함수

```sql
-- 마감일 지난 혜택 자동 비활성화
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
```

---

## Row Level Security (RLS) 정책

### [12] 사용자 데이터 보호

```sql
-- RLS 활성화
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
```

---

## 중복 제거 전략 구현

### [13] 2단계 하이브리드 중복 제거

```sql
-- 1단계: 문자열 해시 기반 빠른 필터링
create or replace function generate_content_hash(p_title text, p_content text)
returns text as $$
begin
  return md5(lower(regexp_replace(p_title || p_content, '\s+', '', 'g')));
end;
$$ language plpgsql immutable;

comment on function generate_content_hash is '제목+내용 기반 해시 생성 (공백 제거 후 소문자 변환)';

-- 2단계: 벡터 유사도 기반 정밀 검증 (애플리케이션 레벨에서 구현)
-- Python 코드에서 다음과 같이 사용:
-- 1. content_hash로 1차 필터링 (DB 쿼리)
-- 2. 유사 해시 발견 시 벡터 코사인 유사도 계산
-- 3. 유사도 > 0.95 이면 중복으로 판단
```

---

## 데이터 마이그레이션 및 초기화

### [14] 행정동 코드 초기 데이터 로드

```sql
-- 행정안전부 API에서 받아온 데이터를 삽입하는 예시
-- 실제 데이터는 Python 스크립트로 자동 수집 예정
comment on table region_codes is '
초기 데이터 로드 방법:
1. 행정안전부 행정표준코드관리시스템 API 호출
2. Python 스크립트로 JSON 파싱 후 INSERT
3. 매월 1회 자동 업데이트 (Lambda Cron)
';
```

---

## 성능 최적화 가이드

### 벡터 검색 쿼리 예시

```sql
-- 하이브리드 RAG 쿼리 (SQL 필터링 + 벡터 검색)
-- 1단계: 사용자 지역/나이로 필터링
-- 2단계: 필터링된 범위 내에서 벡터 유사도 검색

select 
  b.id,
  b.title,
  b.content,
  b.original_url,
  1 - (be.embedding <=> '[사용자 질문 벡터]'::vector) as similarity
from benefits b
join benefit_embeddings be on b.id = be.benefit_id
where b.is_active = true
  and b.application_end_date >= current_date
  and '[사용자_지역코드]' = any(b.region_codes)
  and (b.target_age_min is null or b.target_age_min <= [사용자_나이])
  and (b.target_age_max is null or b.target_age_max >= [사용자_나이])
  and (b.target_gender is null or b.target_gender in ('ALL', '[사용자_성별]'))
order by be.embedding <=> '[사용자 질문 벡터]'::vector
limit 5;
```

---

## 백업 및 유지보수

### 권장 사항

1. **자동 백업**: Supabase 대시보드에서 일일 자동 백업 활성화
2. **아카이빙**: 마감 3개월 지난 혜택은 별도 테이블로 이동 또는 삭제
3. **인덱스 재구성**: 월 1회 `REINDEX` 실행 (벡터 인덱스 성능 유지)
4. **통계 업데이트**: 주 1회 `ANALYZE` 실행 (쿼리 플래너 최적화)

```sql
-- 정기 유지보수 스크립트 (Lambda Cron으로 실행)
-- 1. 만료 혜택 비활성화
select deactivate_expired_benefits();

-- 2. 3개월 지난 비활성 혜택 삭제
delete from benefits 
where is_active = false 
  and application_end_date < current_date - interval '3 months';

-- 3. 통계 업데이트
analyze benefits;
analyze benefit_embeddings;
```

---

## 다음 단계

1. ✅ Supabase 프로젝트 생성
2. ✅ 위 스키마 SQL 실행
3. ⏭️ 행정동 코드 데이터 수집 스크립트 작성
4. ⏭️ AWS Lambda 함수 개발 (카카오 챗봇 웹훅)
5. ⏭️ 공공 API 수집 파이프라인 구축
