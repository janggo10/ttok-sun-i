# 지역 데이터 아키텍처 설계 검토

## 📋 설계 질문 검토

### 1️⃣ Region 테이블 동기화 주기

**답변**: ✅ **분기 1회 충분**

### 2️⃣ 온보딩 시 저장할 주소 깊이

**최종 결정**: ✅ **읍/면/동 레벨 필수 (depth >= 3)**

**저장 구조**:
- 서울/광역시: **동** (depth=3) - 예: 역삼동
- 경기 대도시: **동** (depth=4) - 예: 서현동
- 경기 중소시: **읍/면** (depth=3) - 예: 공도읍
- 지방: **동/읍/면** (depth=3 or 4)

**Schema 제약**:
```sql
region_code varchar(10) NOT NULL,
region_depth int NOT NULL CHECK (region_depth >= 3)
```

### 3️⃣ 주소 입력 방식

**최종 결정**: ✅ **List Card/Quick Reply 전용**

**이유**:
- 파싱 오류 0%
- 시니어 친화적 (클릭만)
- 카카오톡 네이티브 UI
- 구현 단순

**자유 입력 제거**: 파싱 복잡도 불필요

---

## 🎯 최종 온보딩 플로우

### 단계별 UI 구성

```
1️⃣ 시작
봇: 안녕하세요! 거주 지역을 선택해주세요.

[List Card - 시/도]
- 서울특별시
- 부산광역시
- 대구광역시
- 인천광역시
- 경기도
(최대 5개씩 표시, "더보기" 버튼)

2️⃣ 시/도 선택 후 (예: 서울)
봇: 서울의 어느 구인가요?

[List Card - 구]
- 강남구
- 강동구
- 강북구
- 강서구
- 관악구

3️⃣ 구 선택 후 (예: 강남구)
봇: 강남구의 어느 동인가요?

[List Card - 동]
- 역삼동
- 삼성동
- 대치동
- 청담동
- 논현동

4️⃣ 동 선택 후 (예: 역삼동)
봇: 서울특별시 강남구 역삼동이 맞으신가요?

[Quick Reply]
[확인] [다시 선택]

✅ 완료: region_code='1168010100', depth=3
```

### 경기도 케이스 (구가 있는 시)

```
1️⃣ 경기도 선택
2️⃣ 성남시 선택
3️⃣ [List Card - 구]
   - 분당구
   - 수정구
   - 중원구
4️⃣ 분당구 → [List Card - 동]
   - 서현동
   - 정자동
   - 수내동

✅ 완료: region_code='4113510301', depth=4
```

### 경기도 케이스 (구가 없는 시/군)

```
1️⃣ 경기도 선택
2️⃣ 안성시 선택
3️⃣ [List Card - 읍/면/동]  ← 바로 동 레벨
   - 공도읍
   - 보개면
   - 금광면

✅ 완료: region_code='4415010100', depth=3
```

---

## 📊 구현 상세

### List Card 페이징 전략

**카카오 제한**: 최대 5개 항목

**해결책**:
1. **인기순 정렬** - 서울 25개 구를 인구순으로
2. **더보기 버튼** - 다음 5개 표시
3. **검색 버튼** (선택) - 텍스트 입력으로 필터링

### 데이터 구조

```python
# regions 테이블 쿼리
def get_regions_by_parent(parent_code, offset=0, limit=5):
    return supabase.table('regions')\
        .select('region_code, name, depth')\
        .eq('parent_code', parent_code)\
        .order('order_num')\
        .range(offset, offset + limit - 1)\
        .execute()
```

### 응답 JSON 예시

```json
{
  "version": "2.0",
  "template": {
    "outputs": [{
      "listCard": {
        "header": {"title": "서울의 어느 구인가요?"},
        "items": [
          {
            "title": "강남구",
            "description": "서울특별시 강남구",
            "action": "message",
            "messageText": "강남구",
            "extra": {"region_code": "1168000000"}
          },
          {
            "title": "강동구",
            "description": "서울특별시 강동구",
            "action": "message",
            "messageText": "강동구",
            "extra": {"region_code": "1165000000"}
          }
        ],
        "buttons": [{
          "label": "더보기",
          "action": "message",
          "messageText": "구 더보기"
        }]
      }
    }]
  }
}
```

---

## 🔍 추가 고려사항

### 1. 세션 관리

```python
# 온보딩 상태 저장
onboarding_state = {
    "user_id": "kakao_123",
    "step": "SELECT_DONG",
    "sido_code": "11",
    "sgg_code": "68",
    "page": 0
}
```

### 2. 지역 변경

```sql
-- users 테이블 업데이트
UPDATE users 
SET region_code = '1168010100',
    region_depth = 3,
    region_update_count = region_update_count + 1,
    last_region_check_at = NOW()
WHERE kakao_user_id = 'user123';
```

### 3. 모니터링

```sql
-- onboarding_logs 기록
INSERT INTO onboarding_logs (
  user_id, step, parse_method, parse_success
) VALUES (
  'uuid', 'ONBOARDING_COMPLETE', 'MENU_SELECT', true
);
```

---

## ✅ 최종 결정 요약

| 항목 | 결정 | 이유 |
|------|------|------|
| 입력 방식 | List Card/Quick Reply 전용 | 파싱 불필요, 정확도 100% |
| 저장 Depth | >= 3 (동/읍/면) | 정확한 혜택 매칭 |
| 자유 입력 | 제거 | 복잡도 감소 |
| Schema 제약 | NOT NULL | 서비스 이용 필수 |
| 클릭 횟수 | 3~4번 | 시니어 수용 가능 |

---

**작성일**: 2026-01-20  
**최종 승인**: 사용자  
**다음 단계**: Schema 적용 → 데이터 수집 → 온보딩 로직 구현

---

## 🔍 추가 점검 사항

### 4️⃣ 지역 변경 관리

**고려사항**:
- 사용자가 이사 가는 경우
- 6개월마다 거주지 확인 필요?

**제안**:
```sql
-- users 테이블에 추가
last_region_check_at timestamp  -- 마지막 확인 시점
region_update_count int         -- 변경 횟수 (이상 패턴 감지)
```

**구현**:
- 6개월마다 "거주지가 변경되셨나요?" 알림
- 변경 시 새 지역 기준으로 혜택 재검색
- 변경 이력 로그 (analytics용)

---

### 5️⃣ 전국 단위 혜택 처리

**고려사항**:
- "전국 65세 이상" 같은 전국 단위 혜택

**제안**:
```sql
-- benefits 테이블
region_codes text[] -- ['ALL'] 또는 ['1100000000', '2600000000']
```

**쿼리 예시**:
```sql
WHERE user_region = ANY(region_codes) 
   OR 'ALL' = ANY(region_codes)
```

---

### 6️⃣ 제주특별자치도 등 특수 케이스

**고려사항**:
- 제주도: 시/군/구가 없음 (제주시, 서귀포시)
- 세종특별자치시: 구가 없음

**제안**:
- **시/도 코드를 그대로 사용**
- 제주시 = `5011000000` (depth=2로 간주)
- 세종시 = `3611000000` (depth=1이지만 2로 처리)

---

### 7️⃣ 파싱 실패율 모니터링

**고려사항**:
- 파싱이 자주 실패하면 사용자 이탈

**제안**:
```sql
-- 새 테이블: onboarding_logs
create table onboarding_logs (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid references users(id),
  step text,  -- REGION_INPUT, REGION_CONFIRM, BIRTH_INPUT
  input_text text,
  parse_success boolean,
  attempt_count int,
  created_at timestamp with time zone default now()
);
```

**분석 쿼리**:
```sql
-- 파싱 성공률 확인
SELECT 
  parse_success,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM onboarding_logs
WHERE step = 'REGION_INPUT'
GROUP BY parse_success;
```

---

### 8️⃣ 성능 고려사항

**쿼리 최적화**:
```sql
-- regions 테이블 인덱스
CREATE INDEX idx_regions_name_gin 
  ON regions USING gin(to_tsvector('simple', name));

-- 검색 쿼리
SELECT region_code, name, parent_code
FROM regions
WHERE to_tsvector('simple', name) @@ to_tsquery('simple', '강남')
  AND depth = 2
LIMIT 5;
```

**예상 성능**:
- 전국 35,000개 레코드
- 인덱스로 검색: **< 10ms**
- LLM 파싱: **200-500ms**

---

## ✅ 최종 권장 사항

### Schema 변경

**기존 `region_codes` 테이블 → `regions` 테이블로 교체**:

```sql
-- 삭제
DROP TABLE IF EXISTS region_codes CASCADE;

-- 새로 생성
CREATE TABLE regions (
  id bigint primary key generated always as identity,
  region_code varchar(10) unique not null,
  name text not null,
  parent_code varchar(10),
  sido_code varchar(2),
  sgg_code varchar(3),
  depth int not null,  -- 1:시도, 2:시군구, 3:읍면동, 4:리
  order_num int,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now()
);
```

### Users 테이블 수정

```sql
-- region_code는 시/군/구 레벨만 저장 (depth=2)
ALTER TABLE users 
  ALTER COLUMN region_code 
  TYPE varchar(10);
```

### 동기화 전략

- **분기 1회** 자동 동기화
- EventBridge Cron: `0 0 1 1,4,7,10 ? *` (매 분기 1일 0시)

### 온보딩 UX

1. 자유 입력 허용
2. 정규식 1차 파싱
3. LLM 2차 파싱
4. 선택지 제시 (버튼/리스트)
5. 시/도 → 시/군/구 순차 선택 (최종 폴백)

---

## 📝 TODO 업데이트

기존 TODO에 다음 항목 추가 필요:

```markdown
#### 1.1.5 지역 데이터 아키텍처
- [ ] `regions` 테이블 설계 확정 및 schema.sql 업데이트
- [ ] `onboarding_logs` 테이블 추가 (파싱 성공률 모니터링)
- [ ] 전국 단위 혜택 처리 로직 설계 ('ALL' 코드)
- [ ] 제주/세종 특수 케이스 매핑 정의
```

---

**작성일**: 2026-01-20  
**검토자**: 사용자  
**다음 단계**: schema.sql 업데이트 → API 키 발급 → 데이터 수집
