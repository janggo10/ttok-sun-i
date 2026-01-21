# 똑순이 개발 TODO

## ✅ 완료된 작업

### 인프라 및 기본 설정
- [x] AWS SAM 프로젝트 구조 설정
- [x] Supabase 데이터베이스 스키마 생성
- [x] Lambda Layer 구조 수정 (`layer/common/`)
- [x] Supabase Service Key 환경 변수 설정
- [x] API Gateway Lambda Proxy 응답 형식 수정
- [x] 카카오 웹훅 기본 응답 작동 확인
- [x] CloudWatch 디버그 로깅 추가

### 데이터 수집 설계 (2026-01-21 완료)
- [x] **복지로 API 연동 테스트**
  - [x] 지자체복지서비스 API 테스트 (`test_local_welfare_api.py`)
  - [x] 중앙부처복지서비스 API 테스트 (`test_bokjiro_api.py`)
  - [x] API 키 발급 및 적용 완료
  - [x] 목록 조회 + 상세 조회 API 연동 완료
  - [x] 데이터 규모 확인 (서울 357개 + 전국 365개 = 총 722개)
- [x] **통합 DB 스키마 설계** (`docs/UNIFIED_SCHEMA_DESIGN.md`)
  - [x] 지자체 + 중앙부처 API 필드 비교 분석
  - [x] benefits 테이블 통합 스키마 설계 (50개 필드)
  - [x] 배열 타입 필드 설계 (life_nm_array, intrs_thema_nm_array 등)
  - [x] 하이브리드 RAG 쿼리 설계 (지역 + 연령대 필터링)
- [x] **연령 필터링 전략 변경**
  - [x] 기존: 나이(숫자) 입력 → target_age_min/max 비교
  - [x] 변경: 관심 연령대(배열) 선택 → life_nm_array && 연산
  - [x] 장점: API 응답과 직접 매칭, 텍스트 파싱 불필요
- [x] **Supabase 스키마 업데이트** (`supabase/schema.sql`)
  - [x] users 테이블: interest_age_groups 배열 필드 추가
  - [x] benefits 테이블: 통합 스키마 반영 (50개 필드)
  - [x] benefit_embeddings 테이블: vector(1024) 설정
  - [x] search_benefits_hybrid() 함수: 배열 필터링 로직 추가
  - [x] GIN 인덱스: 배열 검색 최적화

---

## 🎯 다음 단계 (우선순위 순)

### 1. **Supabase 스키마 실행** 🔥 IMMEDIATE

**목표**: 설계한 통합 스키마를 Supabase에 반영

- [ ] **Supabase SQL Editor에서 스키마 실행**
  - [ ] `supabase/schema.sql` 파일 내용 복사
  - [ ] Supabase 프로젝트 SQL Editor에서 실행
  - [ ] 테이블 생성 확인 (benefits, users, benefit_embeddings 등)
  - [ ] 인덱스 생성 확인 (GIN 인덱스 포함)
  - [ ] 함수 생성 확인 (search_benefits_hybrid 등)
- [ ] **테이블 구조 검증**
  - [ ] benefits 테이블: 50개 필드 확인
  - [ ] users 테이블: interest_age_groups 배열 필드 확인
  - [ ] 제약조건 확인 (UNIQUE, CHECK, FK)

**완료 기준**:
- 모든 테이블, 인덱스, 함수가 정상 생성
- 에러 없이 스키마 실행 완료

---

### 2. **데이터 수집 스크립트 작성** 🔥 HIGH PRIORITY

**목표**: 복지로 API 데이터를 Supabase에 저장

#### 2.1 복지로 API 데이터 수집
- [x] **API 연동 완료**
  - [x] 지자체복지서비스 API 테스트
  - [x] 중앙부처복지서비스 API 테스트
  - [x] API 키 발급 및 검증
- [ ] **데이터 수집 스크립트 작성**
  - [ ] `scripts/data_collection/collect_local_welfare.py` 생성
    - [ ] 목록 API 호출 (서울시 전체, 357개)
    - [ ] 각 servId로 상세 API 호출
    - [ ] 배열 필드 파싱 (lifeNmArray → life_nm_array)
    - [ ] benefits 테이블 INSERT (ON CONFLICT 처리)
  - [ ] `scripts/data_collection/collect_national_welfare.py` 생성
    - [ ] 목록 API 호출 (전국, 365개)
    - [ ] 각 servId로 상세 API 호출
    - [ ] 배열 필드 파싱 (lifeArray → life_nm_array)
    - [ ] benefits 테이블 INSERT (ON CONFLICT 처리)
  - [ ] 공통 유틸리티 함수 작성
    - [ ] `parse_array(value: str) -> list`
    - [ ] `parse_date(value: str) -> date`
    - [ ] `generate_content_for_embedding(...)` 
- [ ] **로컬 테스트**
  - [ ] 소량 데이터 수집 테스트 (10개)
  - [ ] DB 저장 확인
  - [ ] 중복 제거 로직 확인 (serv_id UNIQUE)
- [ ] **전체 데이터 수집**
  - [ ] 서울 지자체 복지 357개 수집
  - [ ] 전국 중앙부처 복지 365개 수집
  - [ ] 총 722개 데이터 저장 확인

#### 2.2 지역코드 수집 (완료)
- [x] 행정안전부(MOIS) API 연동 완료
- [x] Supabase `regions` 테이블 저장 (20,555건)
- [x] 온보딩 파싱용 검색 RPC 함수 구축

**완료 기준**:
- 722개 혜택 데이터 DB 저장 완료
- 모든 필드 정상 매핑 확인
- 배열 필드 (life_nm_array) 정상 저장 확인

---

### 3. **데이터 임베딩 생성**

**목표**: 혜택 데이터를 벡터로 변환하여 RAG 검색 가능하게 만들기

#### 3.1 임베딩 생성 스크립트
- [ ] `scripts/embeddings/generate_embeddings.py` 작성
  - [ ] benefits 테이블에서 content_for_embedding 조회
  - [ ] AWS Bedrock Titan Embeddings V2 API 호출
  - [ ] 벡터 변환 (1024차원)
  - [ ] benefit_embeddings 테이블에 저장
  - [ ] chunk_index 처리 (긴 텍스트 분할)
- [ ] **배치 처리 최적화**
  - [ ] 10개씩 묶어서 API 호출 (비용/속도 최적화)
  - [ ] 에러 핸들링 (재시도 로직)
  - [ ] 진행상황 로깅
- [ ] **로컬 테스트**
  - [ ] 5개 샘플 데이터로 테스트
  - [ ] 벡터 차원 확인 (1024)
  - [ ] 코사인 유사도 검색 테스트

#### 3.2 전체 임베딩 생성
- [ ] 722개 혜택 데이터 전체 임베딩 생성
- [ ] 생성 시간 및 비용 측정
- [ ] 벡터 인덱스 성능 확인

**완료 기준**:
- 722개 혜택 임베딩 생성 완료
- benefit_embeddings 테이블 데이터 확인
- 벡터 검색 정상 작동

---

### 4. **온보딩 로직 구현** ⭐ 변경됨

**목표**: 사용자로부터 지역과 관심 연령대 수집

#### 4.1 지역 설정 (List Card 검색 방식)
- [x] **구현 가이드 문서 작성** (`docs/ONBOARDING_IMPLEMENTATION_GUIDE.md`)
- [ ] **지역 검색 및 목록 카드 구현**
  - [ ] 사용자 입력값으로 `search_regions` RPC 호출
  - [ ] 검색 결과가 없을 경우 재입력 유도 메시지
  - [ ] 검색 결과(최대 5개)를 카카오 List Card 형태로 변환
- [ ] **선택 처리 핸들러 구현**
  - [ ] "지역선택: {코드}" 패턴 인식 및 파싱
  - [ ] `users` 테이블에 `region_code` 업데이트
  - [ ] 완료 후 관심 연령대 선택 단계로 전환

#### 4.2 관심 연령대 선택 ⭐ 새로운 방식
- [ ] **버튼 UI 구현**
  - [ ] 6개 연령대 버튼 제공
    - 영유아 (0~5세)
    - 아동 (6~12세)
    - 청소년 (13~18세)
    - 청년 (19~34세)
    - 중장년 (35~64세)
    - 노년 (65세 이상)
  - [ ] 복수 선택 가능 UI
  - [ ] "선택 완료" 버튼
- [ ] **선택 처리**
  - [ ] 선택된 연령대를 배열로 저장
  - [ ] 예: ['중장년', '노년']
  - [ ] `users.interest_age_groups` 필드 업데이트

#### 4.3 Supabase 업데이트
- [ ] `users` 테이블 업데이트
  - [ ] `region_code` 저장
  - [ ] `interest_age_groups` 배열 저장
- [ ] 온보딩 완료 플래그 설정
- [ ] Slack 알림 (신규 온보딩 완료)
- [ ] `onboarding_logs` 테이블 기록

**완료 기준**:
- 지역 검색 정상 작동
- 관심 연령대 복수 선택 가능
- DB에 배열 형태로 정상 저장
- 온보딩 완료 후 혜택 검색 가능 상태

**변경 사항**:
- ❌ 기존: 출생연도 입력 → 나이 계산 → target_age_min/max 비교
- ✅ 변경: 관심 연령대 선택 → 배열 저장 → life_nm_array && 연산
- 장점: 텍스트 파싱 불필요, API 응답과 직접 매칭

---

### 5. **혜택 검색 엔진 (하이브리드 RAG) 구현** ⭐ 설계 완료

**목표**: 사용자 질문에 맞는 혜택 추천 (지역 + 연령대 필터링 + 벡터 검색)

#### 5.1 하이브리드 RAG 구현
- [ ] **SQL 필터링 (Step 1)**
  - [ ] 사용자 지역 필터링
    - 지자체: `ctpv_nm = '서울특별시' AND sgg_nm = '종로구'`
    - 중앙부처: `ctpv_nm IS NULL AND source_api = 'NATIONAL'`
  - [ ] 연령대 필터링 ⭐
    - `life_nm_array && user_interest_ages`
    - 예: `life_nm_array && ARRAY['중장년', '노년']`
  - [ ] 유효기간 필터링
    - `enfc_end_ymd IS NULL OR enfc_end_ymd >= CURRENT_DATE`
- [ ] **벡터 검색 (Step 2)**
  - [ ] Supabase `pgvector` 활성화 확인
  - [ ] 사용자 질문 → Embedding 변환 (Titan V2)
  - [ ] 필터링된 범위 내에서만 코사인 유사도 검색
  - [ ] TOP 5 결과 반환
- [ ] **search_benefits_hybrid() 함수 활용**
  - [ ] Supabase에 이미 구현된 함수 사용
  - [ ] 파라미터: query_embedding, user_ctpv_nm, user_sgg_nm, user_interest_ages

#### 5.2 LLM 응답 생성
- [ ] Bedrock Nova Lite 연동
- [ ] 프롬프트 엔지니어링
  - [ ] 검색된 혜택 정보 컨텍스트 제공
  - [ ] 사용자 맞춤 설명 생성 (지역, 연령대 고려)
  - [ ] 신청 방법 안내
- [ ] 응답 포맷팅 (카카오 템플릿)

#### 5.3 카카오 템플릿 활용
- [ ] 리스트 카드 (혜택 목록)
- [ ] 상세 카드 (혜택 세부사항)
- [ ] 버튼 (신청 링크, 더보기)

**완료 기준**:
- 자연어 질문 처리 가능
- 지역 + 연령대 필터링 정상 작동
- 관련 혜택 3~5개 추천
- 사용자 맞춤 설명 제공

**설계 완료**:
- ✅ `search_benefits_hybrid()` 함수 설계 완료
- ✅ 배열 기반 연령대 필터링 로직 완료
- ✅ 하이브리드 RAG 쿼리 예시 문서화

---

### 6. **데이터 수집 자동화 및 스케줄링**

**목표**: 매일 자동으로 신규/변경 혜택 데이터 수집

- [ ] **Lambda 함수로 마이그레이션**
  - [ ] `backend/functions/data_collector/` 생성
  - [ ] 로컬 스크립트를 Lambda 함수로 변환
  - [ ] 환경변수 설정 (API 키, Supabase 연결)
- [ ] **EventBridge Rule 설정**
  - [ ] 매일 오전 11시 KST 실행
  - [ ] Cron 표현식: `cron(0 2 * * ? *)`
- [ ] **Slack 알림 연동**
  - [ ] 수집 성공/실패 알림
  - [ ] 신규 데이터 건수 보고
- [ ] **증분 업데이트 로직**
  - [ ] last_mod_ymd 비교
  - [ ] 변경된 데이터만 업데이트
  - [ ] ON CONFLICT 처리

**완료 기준**:
- 매일 자동 실행 확인
- 신규 혜택 자동 수집
- Slack 알림 정상 작동

---

### 7. **Keep-Alive 함수 구현**

**목표**: Supabase Free Tier 프로젝트 활성 상태 유지

- [ ] `KeepAliveFunction` 구현
  - [ ] Supabase 간단한 쿼리 실행 (`SELECT 1`)
  - [ ] CloudWatch 로그 기록
  - [ ] Slack 알림 (주 1회 실행 확인)
- [ ] EventBridge Rule 설정 (주 1회)
- [ ] 테스트 실행 확인

**완료 기준**:
- 주 1회 자동 실행
- Supabase 일시중지 방지

---

## 🔧 향후 개선사항

### 성능 최적화
- [ ] Lambda 메모리 사이즈 튜닝
- [ ] 응답 시간 최적화 (< 3초)
- [ ] 캐싱 전략 (자주 묻는 질문)

### 사용자 경험
- [ ] 대화 히스토리 저장
- [ ] 북마크 기능
- [ ] 알림 설정 (새 혜택 등록 시)

### 모니터링
- [ ] API Gateway 액세스 로그 활성화
- [ ] CloudWatch 대시보드 생성
- [ ] 에러율 모니터링 알람

### 보안
- [ ] API Gateway API Key 추가 (선택)
- [ ] Rate Limiting 설정
- [ ] Secrets Manager로 민감 정보 관리

---

## 📊 완료 기준

### 베타 버전 (MVP)
- [x] 카카오 웹훅 기본 응답
- [x] 데이터 수집 설계 완료 (통합 스키마)
- [x] 하이브리드 RAG 설계 완료
- [ ] Supabase 스키마 실행 ⬅️ 현재 단계
- [ ] 722개 혜택 데이터 수집 (서울 357 + 전국 365)
- [ ] 임베딩 생성 (722개)
- [ ] 온보딩 구현 (지역 + 관심 연령대)
- [ ] 기본 혜택 검색 (하이브리드 RAG)

### 프로덕션 버전
- [ ] 경기도 데이터 추가 (1,193개)
- [ ] 전국 지자체 데이터 확대 (4,550개)
- [ ] 자동 데이터 수집 (매일)
- [ ] 사용자 피드백 수집
- [ ] 북마크 기능
- [ ] 알림 설정 (신규 혜택)

---

## 🛠️ 기술 스택 정리

### 백엔드
- AWS Lambda (Python 3.11)
- AWS SAM
- API Gateway
- EventBridge (스케줄링)

### 데이터베이스
- Supabase (PostgreSQL)
- pgvector (Vector search)

### AI/ML
- AWS Bedrock
  - Amazon Nova Lite (LLM)
  - Titan Embeddings V2 (임베딩)

### 알림
- Slack Webhooks

### 모니터링
- CloudWatch Logs
- CloudWatch Metrics

---

## 📅 예상 일정

**Week 1**: Supabase 스키마 + 데이터 수집 (현재 진행 중)
- Day 1: ✅ 통합 스키마 설계 완료 (2026-01-21)
- Day 2: Supabase 스키마 실행
- Day 3-4: 데이터 수집 스크립트 작성 및 실행
- Day 5: 데이터 검증 및 임베딩 생성 시작

**Week 2**: 임베딩 생성 + 온보딩 로직
- Day 1-2: 722개 혜택 임베딩 생성
- Day 3-4: 온보딩 로직 구현 (지역 + 연령대)
- Day 5: 온보딩 테스트

**Week 3**: 혜택 검색 엔진 (하이브리드 RAG)
- Day 1-2: 하이브리드 RAG 구현
- Day 3-4: LLM 응답 생성 (Bedrock Nova)
- Day 5: 카카오 템플릿 적용

**Week 4**: 자동화 + 최종 테스트
- Day 1-2: Lambda 함수 마이그레이션
- Day 3: EventBridge 스케줄 설정
- Day 4-5: 통합 테스트 및 베타 배포

---

## 💡 참고 자료

### API 문서
- [카카오 i 오픈빌더 API 문서](https://chatbot.kakao.com/docs/skill-response-format)
- [복지로 API - 지자체복지서비스](https://www.data.go.kr/data/15083323/fileData.do)
- [복지로 API - 중앙부처복지서비스](https://www.data.go.kr/data/15083429/fileData.do)
- [행정안전부 지역코드 API](https://www.data.go.kr/data/15063424/openapi.do)

### 프로젝트 문서
- `docs/UNIFIED_SCHEMA_DESIGN.md`: 통합 DB 스키마 설계 ⭐
- `docs/PROJECT_OVERVIEW.md`: 프로젝트 전체 개요
- `docs/BENEFIT_DATA_COLLECTION_DESIGN.md`: 데이터 수집 설계
- `supabase/schema.sql`: Supabase 스키마 정의

### 기술 문서
- [AWS Bedrock 문서](https://docs.aws.amazon.com/bedrock/)
- [Supabase Vector Search](https://supabase.com/docs/guides/ai/vector-search)
- [PostgreSQL 배열 타입](https://www.postgresql.org/docs/current/arrays.html)
- [PostgreSQL GIN 인덱스](https://www.postgresql.org/docs/current/gin.html)
- [AWS SAM 문서](https://docs.aws.amazon.com/serverless-application-model/)

---

**최종 업데이트**: 2026-01-21  
**현재 진행**: 통합 DB 스키마 설계 완료 ✅  
**다음 작업**: Supabase SQL Editor에서 스키마 실행 → 데이터 수집 스크립트 작성

---

## 🎯 주요 변경사항 (2026-01-21)

### 연령 필터링 전략 변경 ⭐
- **기존**: 나이(숫자) 입력 → `target_age_min`/`target_age_max` 비교
- **변경**: 관심 연령대(배열) 선택 → `life_nm_array &&` 연산
- **장점**: 
  - API 응답(`lifeNmArray`, `lifeArray`)과 직접 매칭
  - 텍스트 파싱 불필요 (복잡도 80% 감소)
  - 복수 연령대 선택 가능 (예: ['중장년', '노년'])
  - 향후 확장 용이 (청년, 청소년 등)

### 통합 DB 스키마 완성
- **benefits 테이블**: 50개 필드 (지자체 + 중앙부처 통합)
- **users 테이블**: `interest_age_groups` 배열 필드 추가
- **하이브리드 RAG**: SQL 필터링 (지역 + 연령대) + 벡터 검색
- **GIN 인덱스**: 배열 검색 최적화

### 데이터 규모 확인
- **서울 지자체**: 357개 복지 서비스
- **전국 중앙부처**: 365개 복지 서비스
- **총계**: 722개 (MVP 목표 달성)
