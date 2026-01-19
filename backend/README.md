# 똑순이 백엔드

## 개발 환경 설정

### 1. Python 가상환경 생성

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
# .env 파일 생성
cp ../.env.example .env

# .env 파일 편집하여 실제 값 입력
# - SUPABASE_URL
# - SUPABASE_SERVICE_KEY
# - SLACK_WEBHOOK_URL
```

### 3. 로컬 테스트

```bash
# 카카오 웹훅 테스트
cd functions/kakao_webhook
python -c "from app import lambda_handler; print(lambda_handler({'body': '{\"userRequest\": {\"user\": {\"id\": \"test\"}, \"utterance\": \"안녕\"}}'}, {}))"
```

## AWS SAM 배포

### 1. SAM CLI 설치

```bash
brew install aws-sam-cli
```

### 2. 빌드 및 배포

```bash
# 빌드
sam build

# 배포 (처음)
sam deploy --guided

# 배포 (이후)
sam deploy
```

### 3. 배포 시 파라미터

- `SupabaseUrl`: Supabase 프로젝트 URL
- `SupabaseServiceKey`: Supabase 서비스 역할 키
- `SlackWebhookUrl`: Slack 웹훅 URL (선택)
- `Bojogeum24ApiKey`: 보조금24 API 키 (선택)
- `MoisApiKey`: 행정안전부 API 키 (선택)

## 프로젝트 구조

```
backend/
├── template.yaml          # SAM 템플릿
├── requirements.txt       # Python 의존성
├── common/               # 공통 모듈
│   ├── __init__.py
│   ├── slack_notifier.py
│   └── supabase_client.py
├── functions/            # Lambda 함수들
│   ├── kakao_webhook/   # 카카오 챗봇 웹훅
│   ├── data_collector/  # 데이터 수집 (다음 단계)
│   ├── keep_alive/      # Supabase 활성 유지
│   └── notification_sender/  # 알림 발송 (다음 단계)
└── scripts/             # 유틸리티 스크립트
```

## 다음 단계

1. Supabase SQL Editor에서 스키마 실행
2. 로컬에서 가상환경 설정 및 테스트
3. AWS SAM 배포
4. 카카오 개발자 센터에서 웹훅 URL 등록
