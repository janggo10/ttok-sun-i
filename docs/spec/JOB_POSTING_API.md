# 100세누리 일자리 API 문서

## 📋 개요

**API 제공:** 공공데이터포털 (한국노인력개발원)  
**서비스명:** 100세누리 구인정보  
**API 유형:** REST (XML)  
**인증 방식:** Service Key (URL Parameter)

---

## 🔑 인증

```bash
# 환경변수
PUBLIC_DATA_PORTAL_API_KEY="your_api_key_here"
```

**동일한 키 사용:**
- 복지로 API (지자체/중앙부처 복지서비스)
- 100세누리 API (일자리)
- 행정안전부 API (지역 코드)

---

## 📡 API 엔드포인트

### **Base URL**
```
http://apis.data.go.kr/B552474/SenuriService
```

**⚠️ 주의:** HTTP (not HTTPS)

---

## 🔍 API 목록

### **1. 일자리 목록 조회 (getJobList)**

#### **요청**
```http
GET /getJobList?serviceKey={API_KEY}&pageNo=1&numOfRows=100
```

#### **요청 파라미터**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| serviceKey | String | ✅ | - | 공공데이터포털 인증키 |
| pageNo | Integer | ✅ | 1 | 페이지 번호 |
| numOfRows | Integer | ✅ | 10 | 페이지당 결과 수 (최대 1000) |
| search | String | ❌ | - | 검색어 (직종, 제목 등) |
| emplymShp | String | ❌ | - | 고용형태 (CM0101~CM0105) |
| workPlcNm | String | ❌ | - | 근무지명 (시군구) |

#### **응답 예시**
```xml
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>NORMAL SERVICE.</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <acptMthd>방문</acptMthd>
        <deadline>마감</deadline>
        <emplymShp>CM0105</emplymShp>
        <emplymShpNm>기타</emplymShpNm>
        <frDd>20251111</frDd>
        <jobId>K15163251110006</jobId>
        <oranNm>국립국제교육원</oranNm>
        <organYn>N</organYn>
        <recrTitle>2025년 제9차 국립국제교육원 공무원 근로자(경력직) 채용 공고</recrTitle>
        <stmId>B</stmId>
        <stnNm>하급맥</stnNm>
        <toDd>20251118</toDd>
        <workPlc>030200</workPlc>
      </item>
      <!-- ... more items ... -->
    </items>
    <numOfRows>10</numOfRows>
    <pageNo>1</pageNo>
    <totalCount>18</totalCount>
  </body>
</response>
```

#### **응답 필드 (목록)**

| 필드 | 설명 | 예시 |
|------|------|------|
| jobId | 일자리 ID | K15163251110006 |
| recrTitle | 채용 제목 | 2025년 제9차 ... |
| deadline | 마감 여부 | 마감 / 접수중 |
| emplymShp | 고용형태 코드 | CM0105 |
| emplymShpNm | 고용형태 명칭 | 기타 |
| oranNm | 기관명 | 국립국제교육원 |
| workPlc | 근무지 코드 | 030200 |
| frDd | 시작일 | 20251111 |
| toDd | 종료일 | 20251118 |

---

### **2. 일자리 상세 조회 (getJobInfo)**

#### **요청**
```http
GET /getJobInfo?serviceKey={API_KEY}&id={JOB_ID}
```

#### **요청 파라미터**

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| serviceKey | String | ✅ | 공공데이터포털 인증키 |
| id | String | ✅ | 일자리 ID (jobId) |

#### **응답 예시**
```xml
<response>
  <header>
    <resultCode>00</resultCode>
    <resultMsg>NORMAL SERVICE.</resultMsg>
  </header>
  <body>
    <item>
      <acptMthdCd>CM0804</acptMthdCd>
      <age>60</age>
      <ageLim>제한</ageLim>
      <clerk>이동윤외2명</clerk>
      <clerkContt>070-4005-2721</clerkContt>
      <clltPrnnum>1</clltPrnnum>
      <createDy>2015-05-26T10:56:51+09:00</createDy>
      <detCnts>산후조리원 및 산부인과 주방보조/찻물 주방보조...</detCnts>
      <etcItm>청남우대</etcItm>
      <frAcptDd>20150526</frAcptDd>
      <homepage>http://myb-ob.co.kr</homepage>
      <jobId>K15001150526033</jobId>
      <lnkStmId>B</lnkStmId>
      <organYn>N</organYn>
      <plDetAddr>405~825 안전광역시 남동구 노고개로123번길 17...</plDetAddr>
      <plbizNm>마이비산부인과마이비산후조리원</plbizNm>
      <repr>이동윤외2명</repr>
      <stmId>A</stmId>
      <toAcptDd>20150724</toAcptDd>
      <updDy>2015-07-24T03:11:25+09:00</updDy>
      <wantedAuthNo>K15001150526033</wantedAuthNo>
      <wantedTitle>산후조리원 주방조리사 모집</wantedTitle>
    </item>
  </body>
</response>
```

#### **응답 필드 (상세)**

| 필드 | 설명 | 예시 |
|------|------|------|
| jobId | 일자리 ID | K15001150526033 |
| wantedTitle | 채용 제목 | 산후조리원 주방조리사 모집 |
| detCnts | 상세 내용 (4000자) | 산후조리원 및 산부인과... |
| age | 연령 제한 | 60 |
| ageLim | 연령 제한 여부 | 제한 / 제한 |
| clerk | 담당자 | 이동윤외2명 |
| clerkContt | 담당자 연락처 | 070-4005-2721 |
| createDy | 생성일자 | 2015-05-26T10:56:51+09:00 |
| updDy | 변경일자 | 2015-07-24T03:11:25+09:00 |
| frAcptDd | 시작접수일 | 20150526 |
| toAcptDd | 종료접수일 | 20150724 |
| plDetAddr | 근무지 상세 주소 | 405~825 안전광역시... |
| plbizNm | 사업장명 | 마이비산부인과... |
| homepage | 홈페이지 | http://myb-ob.co.kr |

---

## 📊 고용형태 코드 (emplymShp)

| 코드 | 명칭 |
|------|------|
| CM0101 | 정규직 |
| CM0102 | 계약직 |
| CM0103 | 시간제일자리 |
| CM0104 | 일당직 |
| CM0105 | 기타 |

---

## 🔄 데이터 수집 전략

### **1. 전체 수집 (복지로와 동일)**
```python
page = 1
while True:
    response = fetch_job_list(page)
    if not response['items']:
        break
    save_jobs(response['items'])
    page += 1
```

### **2. 마감일 필터링**
```python
# 수집 시: 마감일 지난 공고 제외 (count만)
expired_count = 0
for job in jobs:
    if job['deadline'] == '마감' or (job['toDd'] and parse_date(job['toDd']) < today):
        expired_count += 1
        continue  # 저장 안 함
    save_job(job)

logger.info(f"Expired jobs excluded: {expired_count}")
```

### **3. 중복 제거**
```python
# content_hash 기반 (복지로와 동일)
content_hash = hashlib.md5(
    f"{job_id}{title}{detail_content}".encode()
).hexdigest()
```

---

## 🎯 RAG 임베딩 필드 (예정)

**데이터 수집 후 확정 예정**

임시 제안:
```python
content_for_embedding = f"""
{title}
{job_category_nm}
{employment_type_nm}
{organization_name}
{workplace_nm}
{detail_content}
"""
```

---

## ⚠️ 주의사항

1. **HTTP 프로토콜**: HTTPS 아님 (공공데이터포털 제공 그대로)
2. **XML 응답**: JSON 아님 (파싱 필요)
3. **마감일**: `deadline` 필드가 "마감" 문자열 or `toDd` 날짜 확인
4. **페이징**: `numOfRows` 최대 1000 권장
5. **API 키**: 복지로 API와 동일 키 사용

---

## 📅 수집 주기

- **주기**: 매일 오전 11시 KST (복지로와 동일)
- **Lambda**: `JobCollectorFunction` (신규 생성 예정)

---

## 🔗 참고 링크

- 공공데이터포털: https://www.data.go.kr/
- API 규격: 첨부된 규격 문서 참조
