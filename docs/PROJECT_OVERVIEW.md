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

### Phase 2: 공공 일자리 매칭 (Game Changer)
*목표: 서비스 리텐션 강화 및 본격 수익화*
- **기능**:
    - 공공 일자리(공공근로, 노인일자리) 마감 임박 알림
    - 요양보호사 등 민간 일자리 정보 통합 (크롤링/제휴)
- **KPI 목표**:
    - **Growth (1년 차)**: 가입자 **50,000명+**
    - **수익화**: 지역 광고 및 채용 중개 수수료 모델 도입

---

## 3. 기술 스택 (Tech Stack)

비용 효율성과 빠른 개발(Fast MVP)을 위해 Serverless Architecture를 유지합니다.

- **Frontend**: KakaoTalk Chatbot Interface (별도 앱 개발 보류)
- **Backend**: AWS Serverless (Python, Lambda, API Gateway)
- **Database**: Supabase (PostgreSQL + pgvector)
    - *변경점*: 벡터 검색보다는 **정형 데이터(지역/조건) 필터링** 성능 최적화 우선
- **Data Pipeline**:
    - Phase 1: 공공데이터포털 (지자체복지서비스)
    - Phase 2: 공공 일자리 API + 웹 크롤링 (Selenium/Playwright)

---

## 4. 데이터베이스 설계 핵심 (Supabase)

개인화 알림을 위한 유저 프로필과 필터링 조건이 핵심입니다.

```sql
-- 사용자 정보 (Onboarding 시 수집)
create table users (
  id uuid primary key default uuid_generate_v4(),
  kakao_user_id text unique not null,
  
  -- 필수 타겟팅 정보 (DB Filtering용)
  birth_year integer,      -- 출생년도 (나이 계산)
  region_ctpv text,        -- 시도 (예: 서울특별시)
  region_sgg text,         -- 시군구 (예: 종로구)
  target_group text[],     -- 대상 특성 (예: ['장애인', '저소득', '한부모·조손'])
  
  -- 메타 정보
  relationship text,       -- '본인', '자녀', '기타'
  created_at timestamp with time zone default now()
);

-- 알림 발송 이력 (중복 발송 방지)
create table notification_logs (
  user_id uuid references users(id),
  benefit_id bigint references benefits(id),
  sent_at timestamp default now(),
  status text -- 'SENT', 'FAILED', 'READ'
);
```

---

## 5. 데이터 수집 및 알림 전략

### Data Source
1.  **지자체복지서비스 API**: 서울시 25개 구 데이터 우선 수집
2.  **보조금24 (정부24)**: 전국 단위 대형 혜택 (기초연금 등)

### User Query Processing Strategy (Hybrid Search)
1.  **DB Search (확실한 정보)**
    - 조건: `나이`, `거주지`, `대상특성`이 100% 일치하는 혜택
    - 처리: **즉시 결과에 포함** (LLM 검증 불필요, 비용 0)
2.  **Vector Search (맥락 탐색)**
    - 조건: 사용자 질문(Query)과 의미적으로 유사한 혜택 검색
    - 처리: 검색된 후보군 + User Profile을 **LLM에 전송하여 필터링** (자격요건 검증)
3.  **Result Presentation (UX)**
    - DB 검색 결과 + LLM 필터링 결과를 합쳐서 **서비스 제목 리스트** 먼저 제시
    - 사용자가 제목 클릭 시 **상세 요약 정보(Pre-generated Summary)** 표시

---

## 6. 수익화 모델 (Business Model)

1.  **Affiliate (초기)**
    - 알림 메시지 하단에 '시니어 추천 상품(지팡이, 영양제)' 쿠팡 파트너스 링크 삽입
2.  **Hyper-Local Ads (중기)**
    - "종로구 할머니들이 자주 가는 정형외과" / "동네 요양병원" 광고
3.  **Recruitment (장기 - Phase 2)**
    - 시니어 인력 파견 업체 매칭 수수료 (헤드헌팅 모델)
