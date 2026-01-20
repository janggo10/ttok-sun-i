# 👵 프로젝트 마스터 플랜: 똑순이 (Ttok-sun-i)

## 1. 서비스 정의 및 타겟

- **서비스명**: 똑순이 - 시니어 혜택 알리미
- **핵심 가치**: 복잡한 공공 혜택을 시니어 눈높이에서 해석하고 맞춤형으로 푸시 알림 제공
- **타겟 유저**: 5070 액티브 시니어 및 부모님 복지를 챙기는 3040 자녀 세대
- **플랫폼**: 카카오톡 채널 (API형 챗봇)

## 2. 기술 스택 (Tech Stack)

- **Frontend**: KakaoTalk Chatbot Interface
- **Backend**: AWS Serverless (Python, Lambda, API Gateway)
- **Database**: Supabase (PostgreSQL + pgvector)
- **AI/LLM**: Gemini Pro / GPT-4o-mini (RAG 구현 및 문서 요약)
- **Infrastructure**: AWS SAM CLI, S3 (문서 임시 저장)

## 3. 데이터베이스 설계 (Supabase SQL)

이 스키마를 Supabase SQL Editor에서 실행하여 뼈대를 만듭니다.

```sql
-- 확장 설치
create extension if not exists vector;

-- 사용자 정보 (이사 대응 및 개인화)
create table users (
  id uuid primary key default uuid_generate_v4(),
  kakao_user_id text unique not null,
  region_si_do text,
  region_si_gun_gu text,
  birth_year int,
  created_at timestamp with time zone default now()
);

-- 혜택 마스터 (정형 데이터)
create table benefits (
  id bigint primary key generated always as identity,
  title text not null,
  category text,
  target_age_min int,
  region_filter text,
  content text,
  original_url text,
  created_at timestamp with time zone default now()
);

-- 비정형 데이터 벡터 저장소
create table benefit_embeddings (
  id uuid primary key default uuid_generate_v4(),
  benefit_id bigint references benefits(id) on delete cascade,
  embedding vector(1536),
  content_chunk text
);
```

## 4. 핵심 로직 및 기능 명세

### 하이브리드 RAG
유저의 지역/나이로 SQL 필터링을 먼저 수행한 뒤, 해당 범위 내에서만 벡터 검색을 실행하여 할루시네이션(환각) 방지

### 데이터 파이프라인
1. 공공데이터 API 수집
2. 지자체 공고(PDF, HWP, Excel) 다운로드 및 텍스트 추출
3. LLM을 활용한 핵심 3요소(대상, 금액, 방법) 요약 및 벡터화

### 사용자 관리
IP 기반 위치 추정 및 6개월 단위 거주지 확인 알림을 통한 데이터 동기화

## 5. 수익 및 마케팅 전략

### 수익화
- **초기**: 쿠팡/알리 어필리에이트 API 연동
- **성장기**: 가입자 확보 후 고단가 CPA(병원, 보험 상담 연결) 도입

### 마케팅
- 숏폼 자동 생성 파이프라인(서울시 25개 구 타겟)
- 자녀 세대 대상 '효도 마케팅' 전개

---

## 6. AI 코딩 유의사항

> **중요**: AI가 코드를 작성할 때 반드시 준수해야 할 원칙

### ⚠️ 필수 원칙

1. **명확하게 이해하지 못했으면 코딩하기 전에 질문을 먼저**
   - 요구사항이 애매하거나 불명확한 경우 즉시 질문
   - 추측으로 코드를 작성하지 말 것
   - 여러 해석이 가능한 경우 모든 옵션을 제시하고 확인 요청

2. **Fallback 하지 말고 에러 처리**
   - 에러 발생 시 조용히 fallback 하지 말 것
   - 명시적인 에러 처리 및 로깅 필수
   - Slack 알림을 통한 에러 모니터링
   - 사용자에게 명확한 에러 메시지 제공

3. **로컬 테스트 우선 개발**
   - AWS 배포 및 테스트는 시간이 많이 소요됨
   - 가능한 모든 기능을 **로컬에서 먼저 구현 및 테스트**
   - Supabase는 Docker로 로컬 실행 (`supabase start`)
   - Lambda 함수는 `sam local invoke`로 로컬 테스트
   - AWS 배포는 로컬 테스트 완료 후 최종 검증 단계에서만
   - 개발 사이클: **코드 작성 → 로컬 테스트 → 디버깅 → AWS 배포**

4. **클린 코드: 파일 분리**
   - 파일의 내용이 많아지면 **여러 파일로 분리**
   - 단일 책임 원칙 (Single Responsibility Principle) 준수
   - 각 파일은 하나의 명확한 목적을 가져야 함
   - 예: `app.py`가 500줄 이상이면 → `handlers/`, `utils/`, `models/` 등으로 분리
   - 모듈화를 통한 재사용성 및 테스트 용이성 향상

### 예시

**❌ 나쁜 예 (Fallback)**
```python
def get_user_region(user_id):
    try:
        region = supabase.table('users').select('region_code').eq('id', user_id).execute()
        return region.data[0]['region_code']
    except:
        return 'ALL'  # 조용히 fallback - 나쁨!
```

**✅ 좋은 예 (명시적 에러 처리)**
```python
def get_user_region(user_id):
    try:
        result = supabase.table('users').select('region_code').eq('id', user_id).execute()
        if not result.data:
            raise ValueError(f'User not found: {user_id}')
        return result.data[0]['region_code']
    except Exception as e:
        notify_error('get_user_region 실패', {
            '사용자 ID': user_id,
            '에러': str(e)
        })
        raise  # 에러를 상위로 전파
```

