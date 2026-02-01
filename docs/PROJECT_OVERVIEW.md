# 👵 프로젝트 마스터 플랜: 똑순이 (Ttok-sun-i)

## 1. 서비스 정의 및 피벗 전략 (Pivot Strategy)

기존의 단순 포털 형식을 탈피하고, **"찾지 마세요, 알려드릴게요"**라는 캐치프레이즈로 **KakaoTalk Push 중심의 알림 서비스**로 전환합니다. 100만 기성 앱(복지로, 워크넷)과 경쟁하지 않고, 그들이 놓치고 있는 **'틈새(Niche)'**를 공략합니다.

### 핵심 가치 (Value Proposition)
- **Deep Narrow**: 전국 대상이 아닌, **"서울 특정 구(예: 종로구) + 65세 이상 + 3040 자녀"**로 타겟 좁힘
- **Push over Pull**: 검색(Pull)이 아닌, 자격 요건에 맞는 혜택만 골라서 **알림(Push)**
- **Family Connection**: 디지털 소외 계층인 부모님을 대신해 **자녀가 구독하고 관리**

### 타겟 유저
- **Primary (User)**: 65세 이상 액티브 시니어 (카카오톡 사용자)
- **Secondary (Admin/Payer)**: 부모님의 복지를 챙기고 싶은 3040 자녀

---

## 2. 단계별 마일스톤 (Milestones)

현실적인 성장 목표를 설정하고 단계별로 접근합니다.

### Phase 1: 시니어 복지 알리미 (카카오 채널)
*목표: 진성 유저 확보 및 '자녀-부모' 연결 모델 검증*
- **기능**:
    - 카카오톡 채널 챗봇
    - 거주지(구 단위) & 연령대 기반 맞춤형 복지 알림
    - 자녀 대리 등록 기능
- **KPI 목표**:
    - **Seed (1~3개월)**: 가입자 **1,000명** (차단율 5% 미만 방어)
    - **Early (4~6개월)**: 가입자 **10,000명** (오픈율 30% 유지)

### Phase 2: 공공 일자리 매칭 (Game Changer) 🔧 구현 중
*목표: 서비스 리텐션 강화 및 본격 수익화*
- **기능**:
    - 공공 일자리(공공근로, 노인일자리) 마감 임박 알림
    - 요양보호사 등 민간 일자리 정보 통합 (크롤링/제휴)
- **KPI 목표**:
    - **Growth (1년 차)**: 가입자 **50,000명+**
    - **수익화**: 지역 광고 및 채용 중개 수수료 모델 도입

**📅 구현 진행 상황 (2026-01-30):**
- ✅ DB 스키마 설계 완료 (`job_postings` 테이블)
- ✅ 벡터 DB 통합 구조 완료 (복지 + 일자리 카테고리 분리)
- ✅ 검색 함수 개발 완료 (`match_job_services`, `get_eligible_jobs`)
- ⏳ 일자리 API 연동 대기 (워크넷, 고용24)
- ⏳ 일자리 데이터 수집기 개발 예정

---

## 3. 기술 스택 (Tech Stack)

비용 효율성과 빠른 개발(Fast MVP)을 위해 Serverless Architecture를 유지합니다.

- **Frontend**: KakaoTalk Chatbot Interface (웹뷰 전환 예정)
- **Backend**: AWS Serverless (Python, Lambda, API Gateway)
- **Database**: Supabase (PostgreSQL + pgvector)
    - **Hybrid Search**: 정형 필터링(지역/조건) + 벡터 검색(의미 유사도)
    - **카테고리별 벡터 인덱스**: 복지/일자리 분리 → 검색 속도 2배 향상 ⚡
- **AI/LLM**: AWS Bedrock
    - **⚠️ Titan Embeddings V2 (1024차원) - 한국어 성능 문제 발견!**
        - "치매" 검색 시 "미숙아", "화장장려금" 등 무관한 결과 (유사도 0.13-0.15)
        - 한국어 의미 이해력 부족 (영어 중심 학습 모델)
        - **임베딩 모델 변경 강력 권장** 🔥
    - Claude 3 Haiku (요약 생성)
- **Data Pipeline**:
    - Phase 1: 공공데이터포털 (지자체복지서비스) ✅ 운영 중
    - Phase 2: 공공 일자리 API (워크넷, 고용24) ⏳ 개발 예정
- **성능 최적화**:
    - **Lambda Cold Start 해결** (2026-01-31) ⚡
        - EventBridge Warming: 5분마다 자동 호출로 항상 Warm 유지
        - 전역 변수 재사용: Supabase 클라이언트 초기화 최적화
        - 응답 속도: 5-10초 → 0.2-0.5초 개선
        - 비용: ~$0.1/월 (거의 무료)

---

## 4. 데이터베이스 설계 핵심 (Supabase)

### 4.1 핵심 테이블 구조 (2026-01-30 업데이트)

```sql
-- [1] 사용자 정보 (Onboarding 시 수집)
create table users (
  id uuid primary key default uuid_generate_v4(),
  kakao_user_id text unique not null,
  
  -- 필수 타겟팅 정보 (DB Filtering용)
  birth_year int not null,         -- 출생연도 (나이 계산)
  ctpv_nm varchar(50) not null,    -- 시도명 (예: 전라남도)
  sgg_nm varchar(50) not null,     -- 시군구명 (예: 진도군)
  
  -- 혜택 필터링 조건 ⭐
  life_cycle text[],               -- 생애주기 ['노년', '중장년']
  target_group text[],             -- 대상 특성 ['저소득', '장애인']
  
  -- 메타 정보
  gender text,                     -- 'M', 'F'
  region_code varchar(10),         -- 법정동코드
  is_active boolean default true,
  created_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul')
);

-- [2] 복지/혜택 마스터 데이터
create table benefits (
  id bigint primary key,
  serv_id varchar(20) unique not null,
  serv_nm varchar(500) not null,
  source_api varchar(20) not null,  -- 'LOCAL', 'NATIONAL'
  
  -- 지역 정보
  ctpv_nm varchar(50),
  sgg_nm varchar(50),
  
  -- 필터링용 배열
  life_nm_array text[],             -- 생애주기 배열
  trgter_indvdl_nm_array text[],    -- 대상 배열
  
  -- RAG용 콘텐츠
  content_for_embedding text,       -- LLM 요약 + 상세정보
  
  -- 기간
  enfc_end_ymd date,
  is_active boolean default true,
  created_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul')
);

-- [3] 공공일자리 마스터 데이터 🆕
create table job_postings (
  id bigserial primary key,
  job_id varchar(50) unique not null,
  title varchar(500) not null,
  company_name varchar(200),
  source_api varchar(20) not null,  -- 'WORKNET', 'GOV_JOB'
  
  -- 지역
  ctpv_nm text,
  sgg_nm text,
  
  -- 일자리 정보
  job_type varchar(50),             -- 공공근로, 노인일자리
  employment_type varchar(50),      -- 정규직, 계약직, 일용직
  salary_type varchar(20),          -- 월급, 시급, 연봉
  salary_amount int,
  
  -- 필터링용 배열
  target_group text[],              -- ['노인', '청년', '장애인']
  age_range text[],                 -- ['20대', '60대이상']
  
  -- 모집 정보
  recruit_end_date date,
  recruit_count int,
  
  -- RAG용 콘텐츠
  content_for_embedding text,
  
  is_active boolean default true,
  is_closed boolean default false,
  created_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul'),
  updated_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul')
);

-- [4] 통합 벡터 임베딩 (복지 + 일자리) 🔥
create table benefit_embeddings (
  id uuid primary key default uuid_generate_v4(),
  
  -- 카테고리 (네임스페이스)
  category varchar(20) not null default 'WELFARE'
    check (category in ('WELFARE', 'JOB')),
  
  -- 원본 참조 (둘 중 하나만)
  benefit_id bigint references benefits(id),
  job_posting_id bigint references job_postings(id),
  
  -- 벡터 데이터
  embedding vector(1024) not null,
  content_chunk text not null,
  chunk_index int default 0,
  
  created_at timestamptz default (now() AT TIME ZONE 'Asia/Seoul'),
  
  constraint check_single_reference check (
    (benefit_id is not null and job_posting_id is null) or
    (benefit_id is null and job_posting_id is not null)
  )
);

-- 카테고리별 Partial HNSW 인덱스 (성능 최적화!) ⚡
create index idx_benefit_embeddings_vector_welfare 
  on benefit_embeddings using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64)
  where category = 'WELFARE';

create index idx_benefit_embeddings_vector_job 
  on benefit_embeddings using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64)
  where category = 'JOB';
```

### 4.2 핵심 설계 포인트

1. **카테고리별 벡터 인덱스**
   - Partial Index로 복지/일자리 검색 범위 분리
   - 검색 속도 2배 향상 (1000개 → 500개 대상)

2. **한국 시간(KST) 저장**
   - 모든 timestamp를 `now() AT TIME ZONE 'Asia/Seoul'`로 저장
   - 서버 위치 변경에도 일관된 시간 기록

3. **유연한 확장성**
   - 교육, 주거 등 추가 카테고리 확장 가능
   - 카테고리별 인덱스만 추가하면 됨

---

## 5. 데이터 수집 및 검색 전략

### 5.1 Data Source

| 카테고리 | API/출처 | 상태 | 수집 범위 |
|---------|---------|------|----------|
| **복지/혜택** | 공공데이터포털 (지자체/중앙부처) | ✅ 운영중 | 전국 |
| **공공일자리** | 워크넷, 고용24 | ⏳ 개발예정 | 전국 |
| **민간일자리** | 크롤링/제휴 | 📅 Phase 2 후반 | - |

### 5.2 Hybrid RAG Search 아키텍처 (2단계 필터링)

```
사용자 쿼리: "저소득층 지원금 있어?"
     ↓
┌─────────────────────────────────────────┐
│ Step 1: Whitelist 조회 (DB 함수)         │
│ - get_eligible_benefits()               │
│ - 지역/생애주기/대상 필터링 (SQL)         │
│ - 결과: 자격요건 100% 충족 혜택         │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ Step 2: Vector Search (의미 유사도)     │
│ - match_welfare_services()              │
│ - 쿼리 임베딩 생성 (Titan V2)            │
│ - 카테고리별 벡터 인덱스 활용 🔥         │
│ - 결과: 의미적으로 관련된 혜택          │
└─────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────┐
│ Step 3: Intersection & Ranking          │
│ - Whitelist ∩ Vector Results            │
│ - 지역 우선순위 (구 > 시/도 > 전국)      │
│ - 혜택 유형 (현금 > 현물)               │
└─────────────────────────────────────────┘
     ↓
    결과 반환 (Top 10)
```

### 5.3 카테고리별 검색 함수

| 함수명 | 용도 | 카테고리 |
|--------|------|----------|
| `get_eligible_benefits()` | 복지 화이트리스트 | WELFARE |
| `match_welfare_services()` | 복지 벡터 검색 | WELFARE |
| `get_eligible_jobs()` | 일자리 화이트리스트 | JOB |
| `match_job_services()` | 일자리 벡터 검색 | JOB |

### 5.4 성능 최적화

- **카테고리별 Partial Index**: 검색 대상 50% 감소 → 속도 2배 향상
- **Regional Pre-filtering**: 지역 필터를 벡터 검색 전에 적용
- **Whitelist First**: 자격요건 필터링을 먼저 수행 (비용 절감)

---

## 6. 수익화 모델 (Business Model)

1.  **Affiliate (초기)**
    - 알림 메시지 하단에 '시니어 추천 상품(지팡이, 영양제)' 쿠팡 파트너스 링크 삽입
2.  **Hyper-Local Ads (중기)**
    - "종로구 할머니들이 자주 가는 정형외과" / "동네 요양병원" 광고
3.  **Recruitment (장기 - Phase 2)**
    - 시니어 인력 파견 업체 매칭 수수료 (헤드헌팅 모델)

---

## 7. 구현 현황 (Implementation Status)

### ✅ 완료된 기능 (Phase 1)

| 구분 | 항목 | 상태 |
|------|------|------|
| **DB** | 복지/혜택 스키마 | ✅ 완료 |
| **DB** | 공공일자리 스키마 | ✅ 완료 (2026-01-30) |
| **DB** | 카테고리별 벡터 인덱스 | ✅ 완료 (2026-01-30) |
| **Backend** | RAG 검색 서비스 | ✅ 완료 (복지 전용) |
| **Backend** | 데이터 수집기 | ✅ 운영중 (복지 전용) |
| **Backend** | 임베딩 생성 | ✅ 운영중 (복지 전용) |
| **Frontend** | 카카오 웹훅 | ✅ 테스트 가능 |

### ⏳ 개발 예정 (Phase 2)

| 구분 | 항목 | 예정일 |
|------|------|--------|
| **Backend** | 일자리 데이터 수집기 | API 확인 후 |
| **Backend** | 일자리 임베딩 생성 | 데이터 수집 후 |
| **Backend** | 일자리 검색 통합 | 데이터 준비 후 |
| **Frontend** | 카카오 웹뷰 | 승인 완료 후 |
| **Frontend** | 메인 메뉴 (복지/일자리 선택) | 웹뷰 전환 시 |

### 📊 기술 부채 (Technical Debt)

1. ✅ **해결됨**: 컬럼명 일관성 (`job_posting_id`)
2. ✅ **해결됨**: 한국 시간(KST) 저장
3. ⚠️ **진행중**: 데이터 수집기 필드 확장 (28개 → 6개만 수집 중)
4. ⏳ **대기중**: 카카오 비즈니스 채널 승인
5. 🔥 **최우선**: 임베딩 모델 변경 (Titan V2 → OpenAI text-embedding-3-small)

---

## 8. 🔥 임베딩 모델 변경 계획 (Embedding Model Migration)

### 8.1 현재 문제 (Titan V2의 한계)

**실제 검색 결과 (2026-01-31 확인):**

| 검색어 | 결과 | 유사도 | 평가 |
|--------|------|--------|------|
| "치매" | 미숙아 및 선천성이상아 의료비 지원 | 0.15 | ❌ 완전 무관 |
| "치매" | 화장장려금 지원 | 0.14 | ❌ 완전 무관 |
| "치매" | 디지털미디어 피해 청소년 지원 | 0.13 | ❌ 완전 무관 |

**결론:** Titan V2는 한국어 의미 이해가 거의 불가능함!

---

### 8.2 모델 비교

| 모델 | 한국어 성능 | 비용 (1M tokens) | Latency | 위치 |
|------|-------------|------------------|---------|------|
| **Titan V2 (현재)** | ⭐⭐ (매우 낮음) | $0.1 | ~100ms | AWS Bedrock (Seoul) |
| **OpenAI text-embedding-3-small** | ⭐⭐⭐⭐⭐ (최고) | $0.02 (5배 저렴!) | ~150-200ms | OpenAI API (US) |
| **Cohere Embed Multilingual** | ⭐⭐⭐⭐ (우수) | $0.1 | ~120ms | Cohere API |

**권장:** OpenAI text-embedding-3-small ✅
- 성능: 최고 (한국어 특화)
- 비용: 5배 저렴
- Latency: 약간 높지만 허용 가능 (50-100ms 차이)

---

### 8.3 Latency 문제 분석

#### **우려사항:**
- OpenAI API는 외부 API (US → Korea 왕복)
- Bedrock은 Seoul Region (ap-northeast-2)
- 예상 Latency 차이: 50-100ms

#### **실제 영향:**
```
Titan V2 (Bedrock):
- Embedding 생성: ~100ms
- 총 응답 시간: ~500ms

OpenAI (text-embedding-3-small):
- Embedding 생성: ~150-200ms
- 총 응답 시간: ~550-600ms

차이: ~50-100ms (체감 어려움)
```

#### **결론:**
- ✅ Lambda 응답 시간은 500-600ms로 충분히 빠름
- ✅ 카카오톡 타임아웃 (5초)에 여유 있음
- ✅ EventBridge Warming으로 Cold Start 해결됨
- ⚠️ 검색 품질 향상이 Latency 증가보다 훨씬 중요!

---

### 8.4 마이그레이션 계획

#### **Step 1: 준비 (30분)**
1. OpenAI API 키 발급
2. `.env`에 `OPENAI_API_KEY` 추가
3. `requirements.txt`에 `openai` 패키지 추가

#### **Step 2: 코드 수정 (1시간)**
1. `backend/common/rag_service.py` 수정
   - `generate_embedding()` 함수를 OpenAI로 변경
   - 벡터 차원: 1024 → 1536 (text-embedding-3-small)
2. `scripts/embeddings/generate_embeddings.py` 수정
   - 임베딩 생성 함수 변경

#### **Step 3: DB 스키마 업데이트 (10분)**
```sql
-- 벡터 차원 변경: 1024 → 1536
ALTER TABLE benefit_embeddings 
  ALTER COLUMN embedding TYPE vector(1536);

-- 기존 임베딩 삭제 (재생성 필요)
DELETE FROM benefit_embeddings;

-- 인덱스 재생성
DROP INDEX idx_benefit_embeddings_vector_welfare;
DROP INDEX idx_benefit_embeddings_vector_job;

CREATE INDEX idx_benefit_embeddings_vector_welfare 
  ON benefit_embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64)
  WHERE category = 'WELFARE';

CREATE INDEX idx_benefit_embeddings_vector_job 
  ON benefit_embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64)
  WHERE category = 'JOB';
```

#### **Step 4: 임베딩 재생성 (1-2시간)**
```bash
cd scripts/embeddings
python generate_embeddings.py
```

**예상 소요 시간:**
- 복지 데이터: ~1,000개 × 0.2초 = ~3-4분
- API Rate Limit 고려: ~10-20분
- 인덱스 생성: ~5분
- **총 소요 시간: 30분 이내**

#### **Step 5: 테스트 및 검증 (30분)**
1. "치매" 검색 테스트
   - 기대 결과: 유사도 0.5+ (치매 관련 서비스만)
2. "효도수당" 검색 테스트
   - 기대 결과: 유사도 0.6+ (정확한 매칭)
3. 다양한 검색어로 품질 확인

---

### 8.5 예상 효과

**검색 품질:**
- Before: 유사도 0.13-0.15 (무관한 결과)
- After: 유사도 0.5-0.7 (관련 결과만)

**비용:**
- Before: $0.1 / 1M tokens
- After: $0.02 / 1M tokens (5배 절감!)

**사용자 경험:**
- Before: "치매" → "미숙아", "화장" (혼란)
- After: "치매" → "치매 돌봄", "인지 재활" (만족)

---

### 8.6 마이그레이션 체크리스트

**준비 단계:**
- [ ] OpenAI API 키 발급
- [ ] 비용 예산 확인 ($0.02/1M tokens)
- [ ] Latency 허용 범위 확인 (50-100ms 증가)

**실행 단계:**
- [ ] 코드 수정 (`rag_service.py`, `generate_embeddings.py`)
- [ ] DB 스키마 변경 (vector(1024) → vector(1536))
- [ ] 임베딩 재생성 (30분 소요)
- [ ] Lambda 배포

**검증 단계:**
- [ ] "치매" 검색 → 관련 서비스만 나옴
- [ ] "효도수당" 검색 → 유사도 0.6+
- [ ] Latency 측정 → 600ms 이내
- [ ] 비용 모니터링

---

## 9. 개발 원칙 (Development Principles)

### 9.1 코딩 철학: "근본적 해결 우선"

> **"임시방편(Workaround)이 아닌, 근본 원인(Root Cause)을 해결하라"**

#### ❌ 나쁜 예시 (임시방편)
```python
# 문제: Lambda Layer에서 common 모듈 import 실패
# 임시방편: try-except로 에러 무시하고 None 처리
try:
    from common.supabase_client import SupabaseClient
except:
    SupabaseClient = None  # ← 문제를 숨김!
```

#### ✅ 좋은 예시 (근본 해결)
```python
# 근본 원인 분석:
# 1. Lambda Layer 구조 문제 (python/ 디렉토리 필요)
# 2. SAM Build가 하위 디렉토리 무시
# 3. BuildMethod 설정 불일치

# 해결책: Flat 구조로 변경 (각 함수에 직접 복사)
from supabase_client import SupabaseClient  # ← 안정적!
```

### 9.2 핵심 원칙

1. **🔍 Root Cause Analysis (RCA)**
   - 에러 발생 시 증상이 아닌 원인을 찾기
   - "왜?"를 5번 질문하기 (5 Whys)
   - 로그와 디버깅으로 정확한 진단

2. **🏗️ Solid Foundation**
   - 빠른 배포보다 안정적인 구조 우선
   - 기술 부채 최소화
   - 확장 가능한 설계 (Scalable Architecture)

3. **📚 Documentation First**
   - 해결 과정을 문서화 (같은 실수 방지)
   - 설계 결정 배경 기록 (ADR: Architecture Decision Records)
   - 코드보다 명확한 주석

4. **🧪 Test & Verify**
   - 임시 수정 후 "일단 돌아간다" ≠ "해결됨"
   - 로컬/스테이징/프로덕션 모두 검증
   - 엣지 케이스(Edge Cases) 고려

5. **🔄 Refactor Over Patch**
   - 패치(Patch)를 반복하지 말고 리팩토링(Refactor)
   - 코드 중복 제거 (DRY: Don't Repeat Yourself)
   - 단순한 구조가 최선 (KISS: Keep It Simple, Stupid)

### 9.3 실제 적용 사례

| 문제 상황 | 임시방편 (❌) | 근본 해결 (✅) |
|----------|-------------|-------------|
| Lambda Layer import 실패 | try-except로 에러 무시 | Flat 구조로 재설계 |
| 벡터 검색 속도 느림 | top_k 값 줄이기 | 카테고리별 Partial Index 생성 |
| 배포 시 코드 미반영 | Description 수정해서 강제 배포 | AutoPublishAlias 설정 |
| 타임스탬프 시간대 불일치 | Python에서 변환 | DB 레벨에서 KST 저장 |
| Lambda Cold Start 타임아웃 | Timeout 값만 늘리기 | EventBridge Warming + 전역 변수 최적화 |

### 9.4 코드 리뷰 체크리스트

- [ ] 이 수정이 근본 원인을 해결하는가?
- [ ] 다른 부분에 부작용(Side Effect)은 없는가?
- [ ] 3개월 후에도 이해할 수 있는 코드인가?
- [ ] 확장 시 변경이 최소화되는 구조인가?
- [ ] 문서화가 충분한가?

---

## 10. 참고 문서

- **설계 문서**: `docs/SERVICE_CATEGORY_DESIGN_V2.md`
- **마이그레이션**: `supabase/MIGRATION_V2_DDL.sql`
- **통합 스키마**: `supabase/schema.sql`
- **데이터 수집 개선**: `docs/DATA_COLLECTOR_TODO.md`
- **백엔드 README**: `backend/README.md`