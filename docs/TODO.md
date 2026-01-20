# 똑순이 개발 TODO

## ✅ 완료된 작업

- [x] AWS SAM 프로젝트 구조 설정
- [x] Supabase 데이터베이스 스키마 생성
- [x] Lambda Layer 구조 수정 (`layer/common/`)
- [x] Supabase Service Key 환경 변수 설정
- [x] API Gateway Lambda Proxy 응답 형식 수정
- [x] 카카오 웹훅 기본 응답 작동 확인
- [x] CloudWatch 디버그 로깅 추가

---

## 🎯 다음 단계 (우선순위 순)

### 1. **데이터 수집 파이프라인 구현** 🔥 HIGH PRIORITY

**목표**: 실제 혜택 데이터 수집하여 DB에 저장

#### 1.1 보조금24 API 연동
- [ ] API 키 발급 (https://www.bokjiro.go.kr)
- [ ] API 스펙 확인 (혜택 목록 조회)
- [ ] **로컬 환경 변수 로드 구현**
  - [x] `python-dotenv` 패키지 추가 (requirements.txt)
  - [x] 각 Lambda 함수에 `.env` 로드 코드 추가
  - [ ] 로컬/AWS 환경 자동 감지 로직 (AWS Lambda는 환경변수 주입됨)
- [x] **지역코드 수집 및 저장**
  - [x] 행정안전부(MOIS) API 연동 완료 (`load_region_codes.py`)
  - [x] Supabase `regions` 테이블 생성 (region_code, name, parent_code)
  - [x] 17개 시/도 + 시/군/구 데이터 저장 (20,555건)
  - [x] 온보딩 파싱용 검색 RPC 함수 구축 (`search_regions.sql`)
- [ ] `DataCollectorFunction` 구현
  - [ ] 보조금24 API 호출
  - [ ] 응답 파싱 (JSON → Dict)
  - [ ] 데이터 정제 (null 제거, 필드 매핑)
- [ ] Supabase `benefits` 테이블에 저장
- [ ] 로컬 테스트 (sample 데이터)
- [ ] CloudWatch 로그 확인

#### 1.2 행정안전부 API 연동 (완료)
- [x] API 키 발급 및 적용
- [x] API 스펙 확인 (행정구역 코드 조회)
- [x] 데이터 수집 로직 추가 (`RegionUpdaterFunction`)
- [x] **자동화 및 스케줄링**
  - [x] AWS Lambda 마이그레이션 (`backend/functions/region_updater`)
  - [x] 분기별 자동 실행 (3, 6, 9, 12월 말일)
  - [x] Slack 알림 연동 (성공/실패 채널 분리)

#### 1.3 데이터 임베딩 생성
- [ ] Bedrock Titan Embeddings V2 연동
- [ ] 혜택 설명 → Vector 변환
- [ ] Supabase `benefit_embeddings` 테이블에 저장
- [ ] Vector 차원 확인 (1024차원)

#### 1.4 스케줄 설정
- [ ] EventBridge Rule 활성화 (매일 오전 11시 KST)
- [ ] 첫 실행 후 수집 데이터 확인
- [ ] Slack 알림 확인

**완료 기준**:
- 최소 100개 이상의 혜택 데이터 수집
- 임베딩 생성 완료
- 자동 스케줄 작동 확인

---

### 2. **온보딩 로직 구현**

**목표**: 사용자로부터 지역과 출생연도 수집

#### 2.1 지역 설정 (List Card 검색 방식)
- [x] **구현 가이드 문서 작성** (`docs/ONBOARDING_IMPLEMENTATION_GUIDE.md`)
- [ ] **지역 검색 및 목록 카드 구현**
  - [ ] 사용자 입력값으로 `search_regions` RPC 호출
  - [ ] 검색 결과가 없을 경우 재입력 유도 메시지
  - [ ] 검색 결과(최대 5개)를 카카오 List Card 형태로 변환
- [ ] **선택 처리 핸들러 구현**
  - [ ] "지역선택: {코드}" 패턴 인식 및 파싱
  - [ ] `users` 테이블에 `region_code` 업데이트
  - [ ] 완료 후 출생연도 입력 단계로 전환

#### 2.2 출생연도 파싱
- [ ] 4자리 숫자 추출 (예: "1955", "1960")
- [ ] 2자리 변환 (예: "55년생" → 1955)
- [ ] 유효성 검증 (1900~현재년도)

#### 2.3 Supabase 업데이트
- [ ] `users` 테이블 `region_code`, `birth_year` 업데이트
- [ ] 온보딩 완료 플래그 설정
- [ ] Slack 알림 (신규 온보딩 완료)

**완료 기준**:
- 다양한 주소 형식 처리 가능
- 95% 이상 정확도
- 온보딩 완료 후 혜택 검색 가능 상태

---

### 3. **혜택 검색 엔진 (RAG) 구현**

**목표**: 사용자 질문에 맞는 혜택 추천

#### 3.1 Vector Search
- [ ] Supabase `pgvector` 활성화 확인
- [ ] 사용자 질문 → Embedding 변환
- [ ] Cosine similarity 검색 (TOP 5)
- [ ] 지역 필터링 (사용자 지역 매칭)
- [ ] 나이 필터링 (출생연도 → 만나이 계산)

#### 3.2 LLM 응답 생성
- [ ] Bedrock Nova Lite 연동
- [ ] 프롬프트 엔지니어링
  - [ ] 검색된 혜택 정보 컨텍스트 제공
  - [ ] 사용자 맞춤 설명 생성
  - [ ] 신청 방법 안내
- [ ] 응답 포맷팅 (카카오 템플릿)

#### 3.3 카카오 템플릿 활용
- [ ] 리스트 카드 (혜택 목록)
- [ ] 상세 카드 (혜택 세부사항)
- [ ] 버튼 (신청 링크, 더보기)

**완료 기준**:
- 자연어 질문 처리 가능
- 관련 혜택 3~5개 추천
- 사용자 맞춤 설명 제공

---

### 4. **Keep-Alive 함수 구현**

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
- [ ] 100개 이상 혜택 데이터
- [ ] 온보딩 완료
- [ ] 기본 혜택 검색

### 프로덕션 버전
- [ ] 1000개 이상 혜택 데이터
- [ ] 자동 데이터 수집 (매일)
- [ ] 고급 검색 (필터, 정렬)
- [ ] 사용자 피드백 수집

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

**Week 1**: 데이터 수집 파이프라인
- Day 1-2: 보조금24 API 연동
- Day 3-4: 데이터 임베딩
- Day 5: 테스트 및 디버깅

**Week 2**: 온보딩 로직
- Day 1-2: 지역 파싱
- Day 3: 출생연도 파싱
- Day 4-5: 통합 테스트

**Week 3**: 혜택 검색 엔진
- Day 1-2: Vector Search
- Day 3-4: LLM 응답 생성
- Day 5: 카카오 템플릿 적용

**Week 4**: 최종 테스트 및 배포
- Day 1-2: 통합 테스트
- Day 3: 성능 최적화
- Day 4-5: 베타 테스트

---

## 💡 참고 자료

- [카카오 i 오픈빌더 API 문서](https://chatbot.kakao.com/docs/skill-response-format)
- [보조금24 API](https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/openapi/OpenApiInfoUserGuide.do)
- [AWS Bedrock 문서](https://docs.aws.amazon.com/bedrock/)
- [Supabase Vector Search](https://supabase.com/docs/guides/ai/vector-search)
- [AWS SAM 문서](https://docs.aws.amazon.com/serverless-application-model/)

---

**최종 업데이트**: 2026-01-19  
**다음 작업**: 데이터 수집 파이프라인 구현
