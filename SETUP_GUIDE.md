# 똑순이 프로젝트 설정 가이드

## ✅ 완료된 작업

### 1. 프로젝트 구조 생성
```
ttok-sun-i/
├── docs/                    # 문서
│   ├── PROJECT_OVERVIEW.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── DATABASE_SCHEMA.md
│   └── NEXT_STEPS.md
├── supabase/               # Supabase 설정
│   ├── schema.sql
│   └── README.md
├── backend/                # AWS Lambda 백엔드
│   ├── template.yaml
│   ├── requirements.txt
│   ├── venv/              # Python 가상환경 ✅
│   ├── common/            # 공통 모듈
│   │   ├── slack_notifier.py
│   │   └── supabase_client.py
│   └── functions/         # Lambda 함수들
│       ├── kakao_webhook/
│       └── keep_alive/
└── .env.example           # 환경 변수 템플릿
```

### 2. Python 가상환경 설정 완료 ✅
- 가상환경 생성: `backend/venv/`
- 의존성 설치 완료:
  - ✅ supabase (2.27.2)
  - ✅ boto3 (1.42.30)
  - ✅ requests (2.32.5)
  - ✅ python-dotenv (1.2.1)

---

## 📋 다음 단계

### Step 1: Supabase 스키마 설치

1. Supabase 대시보드 접속
2. **SQL Editor** 메뉴 선택
3. `supabase/schema.sql` 파일 내용 복사
4. SQL Editor에 붙여넣고 **Run** 실행

**확인:**
```sql
-- 테이블 확인
select tablename from pg_tables where schemaname = 'public';

-- 카테고리 데이터 확인
select * from category_codes order by display_order;
```

### Step 2: 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
nano .env
```

**필수 값:**
- `SUPABASE_URL`: Supabase 프로젝트 URL
- `SUPABASE_SERVICE_KEY`: Supabase 서비스 역할 키

**선택 값:**
- `SLACK_WEBHOOK_URL`: Slack 알림 (나중에 설정 가능)
- `PUBLIC_DATA_PORTAL_API_KEY`: 공공데이터포털 인증키 (복지로, 일자리, 행정안전부 등 통합)

### Step 3: 로컬 테스트

```bash
cd backend
source venv/bin/activate

# 환경 변수 로드
export $(cat ../.env | xargs)

# Supabase 연결 테스트
python3 -c "from common.supabase_client import SupabaseClient; client = SupabaseClient.get_client(); print('✅ Supabase 연결 성공!')"
```

### Step 4: AWS SAM 배포 (선택)

```bash
# SAM CLI 설치
brew install aws-sam-cli

# 빌드
cd backend
sam build

# 배포
sam deploy --guided
```

---

## 🎯 현재 상태

| 항목 | 상태 |
|------|------|
| Supabase 프로젝트 | ✅ 생성 완료 |
| 데이터베이스 스키마 | ⏳ 설치 대기 |
| Python 가상환경 | ✅ 설정 완료 |
| 환경 변수 | ⏳ 설정 대기 |
| Lambda 함수 | ✅ 코드 작성 완료 |
| AWS 배포 | ⏳ 배포 대기 |

---

## 💡 다음에 할 일

1. **Supabase 스키마 설치** (5분)
2. **환경 변수 설정** (2분)
3. **로컬 테스트** (3분)
4. **카카오 개발자 센터 설정** (10분)
5. **AWS Lambda 배포** (선택, 15분)

---

## 🆘 문제 해결

### Python 가상환경 재설정
```bash
cd backend
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Supabase 연결 오류
- `.env` 파일에서 `SUPABASE_URL`과 `SUPABASE_SERVICE_KEY` 확인
- Supabase 대시보드 → Settings → API에서 키 재확인

---

## 📞 다음 액션

어떤 것부터 진행하시겠어요?

1. **Supabase 스키마 설치** - SQL 실행
2. **환경 변수 설정** - `.env` 파일 작성
3. **로컬 테스트** - Supabase 연결 확인
4. **카카오 챗봇 설정** - 개발자 센터 설정

말씀해주시면 바로 도와드리겠습니다! 🚀
