# ttok-sun-i Backend

똑순이 서버리스 백엔드 (AWS Lambda + Supabase + Bedrock)

## 🚀 빠른 시작

### 🧪 로컬 테스트 (배포 전 필수!)
```bash
# 1. 빌드 (공통 모듈 복사)
cd backend
./build.sh

# 2. 로컬 테스트 실행
cd ../scripts
python test_kakao_local.py

# ✅ 테스트 통과하면 배포 진행!
```

### 배포
```bash
cd backend

# 빌드 + 배포 (한 번에)
./deploy.sh

# 또는 단계별
./build.sh    # 빌드만
sam deploy    # 배포만
```

### 로그 확인
```bash
# 실시간 로그
sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i --tail

# 최근 10분 로그
sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i -s '10min ago'
```

---

## 📁 프로젝트 구조

```
backend/
├── common/                    # 공통 모듈 (✅ Single Source of Truth)
│   ├── supabase_client.py    # Supabase 클라이언트
│   ├── rag_service.py         # RAG 서비스
│   └── slack_notifier.py      # Slack 알림
│
├── functions/                 # Lambda 함수들
│   ├── kakao_webhook/         # 카카오톡 챗봇 웹훅
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   ├── supabase_client.py  ← build.sh가 자동 복사
│   │   ├── rag_service.py      ← build.sh가 자동 복사
│   │   └── slack_notifier.py   ← build.sh가 자동 복사
│   │
│   ├── data_collector/        # 복지 데이터 수집
│   ├── keep_alive/            # Supabase 활성화
│   └── region_updater/        # 지역 코드 업데이트
│
├── build.sh                   # 빌드 스크립트 ⭐
├── deploy.sh                  # 배포 스크립트 ⭐
├── template.yaml              # SAM 템플릿
└── samconfig.toml             # SAM 설정
```

### 🎯 Flat Structure (단순하고 안정적)

**✅ DO (권장)**:
- `common/` 디렉토리의 파일만 수정
- `build.sh`가 자동으로 각 함수에 복사
- 100% 작동 보장
- 디버깅 용이

**❌ DON'T (금지)**:
- `functions/*/supabase_client.py` 등 직접 수정 ❌
- 수동으로 파일 복사 ❌
- 빌드 시마다 `common/`에서 덮어씌워짐!

---

## 🔧 스크립트 설명

### `./build.sh`
- 🧹 빌드 캐시 선택적 삭제 (`.aws-sam/` - `--clean` 옵션)
- 📦 `common/` → `functions/*/` 자동 복사 (Flat structure)
- 🏗️ SAM 빌드 실행

### `./deploy.sh`
- ✅ `build.sh` 자동 실행
- 🚀 AWS에 자동 배포 (confirm 없이)
- 📊 배포 완료 후 유용한 명령어 출력

---

## 🛠️ 개발 워크플로우

### 1. 코드 수정
```bash
# 공통 모듈 수정
vim common/rag_service.py

# 또는 Lambda 함수 수정
vim functions/kakao_webhook/app.py
```

### 2. 로컬 테스트 (선택)
```bash
# RAG 서비스 테스트
cd ..
python scripts/test_rag_cli.py

# 카카오 웹훅 테스트
python scripts/test_kakao_onboarding.py
```

### 3. 배포
```bash
./deploy.sh
```

### 4. 테스트
- 카카오톡에서 메시지 전송
- 로그 확인: `sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i --tail`

---

## 📋 주요 명령어

### 배포 관련
```bash
# 전체 배포 (빌드 + 배포)
./deploy.sh

# 빌드만
./build.sh

# 배포만 (빌드 없이)
sam deploy

# 강제 재배포 (캐시 무시)
rm -rf .aws-sam && ./deploy.sh
```

### 로그 확인
```bash
# 실시간 로그
sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i --tail

# 특정 시간 로그
sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i -s '1hour ago' -e '30min ago'

# 에러만 필터링
sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i --tail | grep ERROR
```

### 스택 정보
```bash
# 전체 스택 정보
aws cloudformation describe-stacks --stack-name ttok-sun-i

# Webhook URL만 출력
aws cloudformation describe-stacks \
  --stack-name ttok-sun-i \
  --query 'Stacks[0].Outputs[?OutputKey==`KakaoWebhookUrl`].OutputValue' \
  --output text
```

### 삭제
```bash
# 전체 스택 삭제
sam delete

# 또는
aws cloudformation delete-stack --stack-name ttok-sun-i
```

---

## ⚡ Cold Start 최적화

### 문제
- Lambda가 휴면 후 첫 실행 시 5-10초 소요
- 카카오톡 타임아웃 (5초) 발생

### 해결
1. **EventBridge Warming** (자동 적용됨)
   - 5분마다 Lambda를 자동 호출하여 Warm 유지
   - 비용: ~$0.1/월 (거의 무료)
   
2. **전역 변수 재사용** (코드에 적용됨)
   - Supabase 클라이언트를 전역 변수로 재사용
   - 초기화 시간 단축

3. **Provisioned Concurrency** (선택, 주석 처리됨)
   - 필요시 `template.yaml`에서 주석 해제
   - 비용: ~$13/월

### 결과
- Cold Start 전: 5-10초
- Cold Start 후: 0.2-0.5초 ⚡

---

## 🔍 트러블슈팅

### Import 에러
```
[ERROR] AttributeError: 'NoneType' object has no attribute 'get_client'
```

**해결**:
```bash
# 빌드 캐시 삭제 후 재배포
rm -rf .aws-sam && ./deploy.sh
```

### Layer 업데이트 안 됨
**해결**: `build.sh`가 자동으로 처리합니다.
```bash
./deploy.sh  # 이것만 실행하면 됨
```

### 환경변수 변경
```bash
# samconfig.toml 수정
vim samconfig.toml

# 재배포
./deploy.sh
```

---

## 📊 배포 흐름

```
./deploy.sh 실행
    ↓
🧹 .aws-sam/ 삭제
    ↓
📦 common/ → layer/python/common/ 복사
    ↓
🏗️ sam build
    ↓
🚀 sam deploy (자동 승인)
    ↓
✅ 배포 완료
```

---

## 💡 팁

1. **매번 `./deploy.sh`만 실행하세요**
   - 빌드 캐시 자동 삭제
   - Layer 자동 동기화
   - 자동 배포

2. **로그는 별도 터미널에서**
   ```bash
   # 터미널 1: 로그 모니터링
   sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i --tail
   
   # 터미널 2: 배포
   ./deploy.sh
   ```

3. **코드 수정 후 바로 배포**
   ```bash
   vim functions/kakao_webhook/app.py
   ./deploy.sh  # 바로 실행!
   ```

---

## 🔗 관련 문서

- [SAM CLI 공식 문서](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)
- [프로젝트 전체 개요](../docs/PROJECT_OVERVIEW.md)
- [서비스 카테고리 설계](../docs/SERVICE_CATEGORY_DESIGN_V2.md)
