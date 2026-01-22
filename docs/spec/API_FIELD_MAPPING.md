# 복지로 API 필드 매핑 명세서

## 📋 개요

이 문서는 복지로(bokjiro.go.kr) API의 응답 필드와 Supabase `benefits` 테이블 컬럼 간의 매핑을 정의합니다.

**API 종류**:
1. **중앙부처복지서비스** (National Welfare)
2. **지자체복지서비스** (Local Government Welfare)

**각 API는 2개의 엔드포인트 제공**:
- 목록 조회 (List API)
- 상세 조회 (Detail API)

---

## 1. 중앙부처복지서비스 API

### 1.1 API 기본 정보

| 항목 | 내용 |
|------|------|
| API명 | 한국사회보장정보원_중앙부처복지서비스 |
| 버전 | V001 |
| 목록 API | `NationalWelfarelistV001` |
| 상세 API | `NationalWelfaredetailedV001` |
| 공공데이터포털 | https://www.data.go.kr/data/15083429/fileData.do |
| 응답 형식 | XML |

### 1.2 목록 API 응답 필드 (`servList`)

| 필드명 | 타입 | 설명 | 예시 값 | DB 컬럼 | 비고 |
|--------|------|------|---------|---------|------|
| `servId` | String | 서비스 고유 ID | WLF00001188 | `serv_id` | Primary Key |
| `servNm` | String | 서비스명 | 산모·신생아 건강관리 지원사업 | `serv_nm` | |
| `servDgst` | String | 서비스 요약 | 출산가정에 건강관리사를... | `serv_dgst` | 짧은 설명 |
| `servDtlLink` | String | 상세정보 링크 (복지로) | https://www.bokjiro.go.kr/... | `serv_dtl_link` | |
| `jurMnofNm` | String | 주관부처명 | 보건복지부 | `dept_name` | 부처명만 |
| `jurOrgNm` | String | 부서명 | 출산정책과 | `dept_name` | ⭐ jurMnofNm과 조합 |
| `rprsCtadr` | String | 대표 연락처 | 129 | `dept_contact` | |
| `svcfrstRegTs` | String | 최초 등록일 | 20210903 | `enfc_bgng_ymd` | YYYYMMDD 형식 |
| `onapPsbltYn` | Char(1) | 온라인 신청 가능 여부 | Y / N | `onap_psblt_yn` | |
| `inqNum` | Integer | 조회수 | 1416063 | `inq_num` | |
| **서비스 메타데이터** |
| `sprtCycNm` | String | 지원주기 | 1회성 | `sprt_cyc_nm` | ⭐ 목록 API에도 있음 |
| `srvPvsnNm` | String | 서비스 제공방법 | 현지비지원(바우처) | `srv_pvsn_nm` | ⭐ 목록 API에도 있음 |
| **생애주기** |
| `lifeArray` | String | 생애주기 **명칭** (쉼표 구분) | 영유아,임신 · 출산 | `life_nm_array` | ⚠️ 코드 아닌 이름 |
| **관심주제** |
| `intrsThemaArray` | String | 관심주제 **명칭** (쉼표 구분) | 신체건강,임신·출산 | `intrs_thema_nm_array` | ⚠️ 코드 아닌 이름 |
| **대상자** |
| `trgterIndvdlArray` | String | 대상자 **명칭** (쉼표 구분) | 다자녀,장애인,저소득 | `trgter_indvdl_nm_array` | ⚠️ 코드 아닌 이름 |

### 1.3 상세 API 응답 필드 (`wantedDtl`)

| 필드명 | 타입 | 설명 | 예시 값 | DB 컬럼 | 비고 |
|--------|------|------|---------|---------|------|
| **기본 정보** (목록 API와 중복) |
| `servId` | String | 서비스 ID | WLF00000024 | - | 중복 |
| `servNm` | String | 서비스명 | 아이돌봄 서비스 | - | 중복 |
| `jurMnofNm` | String | 주관부처명 (상세) | 성평등가족부 가족문화과 | `dept_name` | ⭐ 목록보다 상세함 |
| **핵심 콘텐츠** (상세 API만 제공) |
| `wlfareInfoOutlCn` | Text | 복지정보 개요 | 맞벌이 가정 아동 돌봄... | `wlfare_info_outl_cn` | RAG용 |
| `tgtrDtlCn` | Text | 대상자 상세 | 만 12세 이하 자녀를 둔... | `target_detail` | ⭐ RAG 핵심 |
| `slctCritCn` | Text | 선정기준 상세 | 소득인정액이 전국가구... | `select_criteria` | ⭐ RAG 핵심 |
| `alwServCn` | Text | 지원내용 상세 | 시간당 1만원 지원... | `service_content` | ⭐ RAG 핵심 |
| **문의처 목록** (JSON 변환) |
| `inqplCtadrList` | XML List | 문의처 정보 리스트 | - | `contact_info` (JSONB) | 아래 상세 참고 |
| ㄴ `servSeDetailLink` | String | 연락처/링크 | 1577-8136 | | |
| ㄴ `servSeDetailNm` | String | 문의처명 | 아이돌봄 지원사업 | | |
| **첨부파일 목록** |
| `basfrmList` | XML List | 첨부파일 리스트 | - | `attachments` (JSONB) | |
| ㄴ `servSeDetailLink` | String | 파일 URL | https://bokjiro.go.kr/... | | |
| ㄴ `servSeDetailNm` | String | 파일명 | 2025년 아이돌봄 안내.pdf | | |
| **근거법령 목록** |
| `baslawList` | XML List | 근거법령 리스트 | - | `base_laws` (JSONB) | |
| ㄴ `servSeDetailNm` | String | 법령명 | 아이돌봄지원법 | | |
| **관련 홈페이지** |
| `inqplHmpgReldList` | XML List | 관련 홈페이지 리스트 | - | `related_links` (JSONB) | |
| ㄴ `servSeDetailLink` | String | URL | https://idolbom.go.kr/ | | |
| ㄴ `servSeDetailNm` | String | 홈페이지명 | 아이돌봄 지원사업 | | |
| **신청방법 목록** ⭐ |
| `applmetList` | XML List | 신청방법 리스트 (형제 노드 반복) | - | `apply_method_detail` (Text) | 포맷팅해서 저장 |
| ㄴ `servSeDetailLink` | String | 신청방법 | 방문 신청 | | |
| ㄴ `servSeDetailNm` | String | 신청처 | 사용관리기관 | | |
| **배열 필드** (상세 API에도 있음) |
| `lifeArray` | String | 생애주기 명칭 | 아동,영유아,청소년 | `life_nm_array` | 목록 API와 동일/다를 수 있음 |
| `intrsThemaArray` | String | 관심주제 명칭 | 보호·돌봄,보육 | `intrs_thema_nm_array` | |
| `trgterIndvdlArray` | String | 대상자 명칭 | 영아민,다자녀-예비맘 | `trgter_indvdl_nm_array` | |
| **서비스 메타** (상세 API에도 있음) |
| `sprtCycNm` | String | 지원주기 | 수시 | `sprt_cyc_nm` | 목록 API와 동일/다를 수 있음 |
| `srvPvsnNm` | String | 서비스 제공방법 | 기타 | `srv_pvsn_nm` | |

### 1.4 XML 구조 특징 (중앙부처) ⚠️ 주의

상세 API의 XML 구조는 **형제 노드로 반복**되는 특이한 구조를 가집니다.

**형태 1: 단일 항목 구조**:
```xml
<inqplCtadrList>
    <servSeDetailLink>1577-8136</servSeDetailLink>
    <servSeDetailNm>아이돌봄 지원사업</servSeDetailNm>
</inqplCtadrList>
```

**형태 2: 다중 항목 - 형제 노드로 반복** ⭐ (실제 구조):
```xml
<applmetList>
    <servSeCode>070</servSeCode>
    <servSeDetailLink>방문 신청</servSeDetailLink>
    <servSeDetailNm>사용관리기관</servSeDetailNm>
</applmetList>
<applmetList>
    <servSeCode>070</servSeCode>
    <servSeDetailLink>전화 신청</servSeDetailLink>
    <servSeDetailNm>사용관리기관</servSeDetailNm>
</applmetList>
```

**형태 3: 다중 항목 - child 태그 반복** (일부 필드):
```xml
<basfrmList>
    <basfrm>
        <servSeCode>040</servSeCode>
        <servSeDetailLink>https://...</servSeDetailLink>
        <servSeDetailNm>2025년 아이돌봄 안내.pdf</servSeDetailNm>
    </basfrm>
</basfrmList>
```

**파싱 전략**:
- `findall(parent_tag)`로 모든 형제 노드 찾기
- 각 노드에서 child가 있으면 child 순회, 없으면 직접 필드 추출

---

## 2. 지자체복지서비스 API

### 2.1 API 기본 정보

| 항목 | 내용 |
|------|------|
| API명 | 한국사회보장정보원_지자체복지서비스 |
| 목록 API | `LcgvWelfarelist` |
| 상세 API | `LcgvWelfaredetailed` |
| 공공데이터포털 | https://www.data.go.kr/data/15083323/fileData.do |
| 응답 형식 | XML |

### 2.2 목록 API 응답 필드 (`servList`)

| 필드명 | 타입 | 설명 | 예시 값 | DB 컬럼 | 비고 |
|--------|------|------|---------|---------|------|
| `servId` | String | 서비스 고유 ID | LCG00001234 | `serv_id` | Primary Key |
| `servNm` | String | 서비스명 | 서울시 어르신 건강검진 | `serv_nm` | |
| `servDtlLink` | String | 상세정보 링크 | https://bokjiro.go.kr/... | `serv_dtl_link` | |

### 2.3 상세 API 응답 필드

| 필드명 | 타입 | 설명 | 예시 값 | DB 컬럼 | 비고 |
|--------|------|------|---------|---------|------|
| **기본 정보** |
| `servId` | String | 서비스 ID | LCG00001234 | `serv_id` | |
| `servNm` | String | 서비스명 | 서울시 어르신 건강검진 | `serv_nm` | |
| `servDgst` | String | 서비스 요약 | 만 65세 이상... | `serv_dgst` | |
| **지역 정보** (⭐ 중앙부처와 차이점) |
| `ctpvNm` | String | 시도명 | 서울특별시 | `ctpv_nm` | 중앙부처는 NULL |
| `sggNm` | String | 시군구명 | 종로구 | `sgg_nm` | 중앙부처는 NULL |
| **부서 정보** |
| `bizChrDeptNm` | String | 업무담당부서명 | 서울시 복지정책과 | `dept_name` | |
| **기간 정보** (⭐ 중앙부처와 차이점) |
| `enfcBgngYmd` | String | 시행시작일 | 20240101 | `enfc_bgng_ymd` | YYYYMMDD |
| `enfcEndYmd` | String | 시행종료일 | 20241231 | `enfc_end_ymd` | YYYYMMDD, NULL 가능 |
| `lastModYmd` | String | 최종수정일 | 20240620 | `last_mod_ymd` | YYYYMMDD |
| **생애주기** (슬래시 또는 쉼표 구분) |
| `lifeNmArray` | String | 생애주기 명칭 | 중장년/노년 | `life_nm_array` | 배열 변환 |
| **관심주제** |
| `intrsThemaNmArray` | String | 관심주제 명칭 | 건강/의료 | `intrs_thema_nm_array` | 배열 변환 |
| **대상자** |
| `trgterIndvdlNmArray` | String | 대상자 명칭 | 노인 | `trgter_indvdl_nm_array` | 배열 변환 |
| **서비스 메타데이터** |
| `sprtCycNm` | String | 지원주기 | 월 | `sprt_cyc_nm` | 월/연/1회성 등 |
| `srvPvsnNm` | String | 서비스제공방법 | 현금지급 | `srv_pvsn_nm` | 현금/현물/서비스 등 |
| `aplyMtdNm` | String | 신청방법 | 방문, 온라인 | `aply_mtd_nm` | |
| **핵심 콘텐츠** |
| `sprtTrgtCn` | Text | 지원대상 상세 | 만 65세 이상 서울시민 | `target_detail` | ⭐ RAG 핵심 |
| `slctCritCn` | Text | 선정기준 상세 | 소득인정액 하위 70% | `select_criteria` | ⭐ RAG 핵심 |
| `alwServCn` | Text | 지원내용 상세 | 건강검진 비용 전액 지원 | `service_content` | ⭐ RAG 핵심 |
| `aplyMtdCn` | Text | 신청방법 상세 | 주민센터 방문 또는... | `apply_method_detail` | ⭐ RAG 핵심 |
| **문의처 목록** ⚠️ |
| `inqplCtadrList` | XML List | 문의처 정보 리스트 | - | `contact_info` (JSONB) | ⚠️ 필드명 중앙과 다름 |
| ㄴ `wlfareInfoReldCn` | String | 연락처 | 02-120 | | ⚠️ 중앙은 servSeDetailLink |
| ㄴ `wlfareInfoReldNm` | String | 문의처명 | 서울시 다산콜센터 | | ⚠️ 중앙은 servSeDetailNm |
| **근거법령 목록** ⚠️ |
| `baslawList` | XML List | 근거법령 리스트 | - | `base_laws` (JSONB) | ⚠️ 필드명 중앙과 다름 |
| ㄴ `wlfareInfoReldCn` | String | 법령 URL | https://www.law.go.kr/... | | ⭐ 지자체도 URL 제공 |
| ㄴ `wlfareInfoReldNm` | String | 법령명 | 서울시 복지조례 | | |
| **첨부파일 목록** ⚠️ |
| `basfrmList` | XML List | 첨부파일 리스트 | - | `attachments` (JSONB) | ⚠️ 필드명 중앙과 다름 |
| ㄴ `wlfareInfoReldCn` | String | 파일 URL | https://... | | |
| ㄴ `wlfareInfoReldNm` | String | 파일명 | 신청서.pdf | | |
| **관련 홈페이지** ⭐ |
| `inqplHmpgReldList` | XML List | 관련 홈페이지 리스트 | - | `related_links` (JSONB) | ⭐ 지자체도 있음! |
| ㄴ `wlfareInfoReldCn` | String | URL | http://www.129.go.kr | | |
| ㄴ `wlfareInfoReldNm` | String | 홈페이지명 | 보건복지상담센터 | | |
| **통계** |
| `inqNum` | Integer | 조회수 | 5432 | `inq_num` | |

---

## 3. DB 컬럼 매핑 요약

### 3.1 benefits 테이블 구조

```sql
CREATE TABLE benefits (
    -- 기본 정보
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    serv_id VARCHAR(20) UNIQUE NOT NULL,           -- servId (양쪽 공통)
    serv_nm VARCHAR(500) NOT NULL,                  -- servNm (양쪽 공통)
    source_api VARCHAR(20) NOT NULL,                -- 'LOCAL' or 'NATIONAL'
    
    -- 지역 정보 (지자체만, 중앙부처는 NULL)
    ctpv_nm VARCHAR(50),                            -- ctpvNm (지자체만)
    sgg_nm VARCHAR(50),                             -- sggNm (지자체만)
    
    -- 부서/기관 정보
    dept_name VARCHAR(200),                         -- jurMnofNm (중앙) / bizChrDeptNm (지자체)
    dept_contact VARCHAR(100),                      -- rprsCtadr (중앙) / contact_info에서 추출 (지자체)
    
    -- 기간 정보
    enfc_bgng_ymd DATE,                             -- svcfrstRegTs (중앙) / enfcBgngYmd (지자체)
    enfc_end_ymd DATE,                              -- NULL (중앙) / enfcEndYmd (지자체)
    crtr_yr INTEGER,                                -- 중앙부처만
    last_mod_ymd DATE,                              -- lastModYmd (지자체만)
    
    -- 분류 메타데이터 (배열 - 이름만 저장)
    life_nm_array TEXT[],                           -- lifeArray (중앙) / lifeNmArray (지자체)
    intrs_thema_nm_array TEXT[],                    -- intrsThemaArray (중앙) / intrsThemaNmArray (지자체)
    trgter_indvdl_nm_array TEXT[],                  -- trgterIndvdlArray (중앙) / trgterIndvdlNmArray (지자체)
    sprt_cyc_nm VARCHAR(50),                        -- sprtCycNm (양쪽 모두)
    srv_pvsn_nm VARCHAR(50),                        -- srvPvsnNm (양쪽 모두)
    aply_mtd_nm VARCHAR(200),                       -- aplyMtdNm (지자체)
    
    -- 온라인신청 (중앙부처만)
    onap_psblt_yn CHAR(1),                          -- onapPsbltYn (중앙만)
    
    -- 요약 콘텐츠
    serv_dgst TEXT,                                 -- servDgst (양쪽)
    wlfare_info_outl_cn TEXT,                       -- wlfareInfoOutlCn (중앙만)
    serv_dtl_link VARCHAR(500),                     -- servDtlLink (양쪽)
    
    -- 핵심 콘텐츠 (RAG용)
    target_detail TEXT,                             -- tgtrDtlCn (중앙) / sprtTrgtCn (지자체)
    select_criteria TEXT,                           -- slctCritCn (양쪽)
    service_content TEXT,                           -- alwServCn (양쪽)
    apply_method_detail TEXT,                       -- applmetList (중앙) / aplyMtdCn (지자체)
    
    -- 통합 임베딩 컬럼
    content_for_embedding TEXT,                     -- 위 4개 필드 결합
    
    -- JSON 필드
    contact_info JSONB,                             -- inqplCtadrList
    attachments JSONB,                              -- basfrmList
    base_laws JSONB,                                -- baslawList
    related_links JSONB,                            -- inqplHmpgReldList (중앙만)
    
    -- 통계
    inq_num INTEGER DEFAULT 0,                      -- inqNum (양쪽)
    
    -- 시스템 필드
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 필드별 매핑 비교표

| DB 컬럼 | 중앙부처 API | 지자체 API | 데이터 타입 | 변환 로직 |
|---------|------------|-----------|------------|----------|
| `serv_id` | servId | servId | String | 직접 매핑 |
| `serv_nm` | servNm | servNm | String | 직접 매핑 |
| `source_api` | - | - | String | 고정값: 'NATIONAL' / 'LOCAL' |
| `ctpv_nm` | NULL | ctpvNm | String | 지자체만 |
| `sgg_nm` | NULL | sggNm | String | 지자체만 |
| `dept_name` | jurMnofNm + jurOrgNm | bizChrDeptNm | String | 중앙: 부처+부서 조합 |
| `dept_contact` | rprsCtadr | contact_info에서 추출 | String | |
| `enfc_bgng_ymd` | svcfrstRegTs | enfcBgngYmd | Date | YYYYMMDD → Date |
| `enfc_end_ymd` | NULL | enfcEndYmd | Date | YYYYMMDD → Date |
| `last_mod_ymd` | - | lastModYmd | Date | YYYYMMDD → Date |
| `life_nm_array` | lifeArray | lifeNmArray | Array | ⚠️ 중앙은 코드 아닌 이름 |
| `intrs_thema_nm_array` | intrsThemaArray | intrsThemaNmArray | Array | ⚠️ 중앙은 코드 아닌 이름 |
| `trgter_indvdl_nm_array` | trgterIndvdlArray | trgterIndvdlNmArray | Array | ⚠️ 중앙은 코드 아닌 이름 |
| `sprt_cyc_nm` | sprtCycNm | sprtCycNm | String | 양쪽 모두 제공 |
| `srv_pvsn_nm` | srvPvsnNm | srvPvsnNm | String | 양쪽 모두 제공 |
| `onap_psblt_yn` | onapPsbltYn | NULL | Char(1) | 중앙만 |
| `serv_dgst` | servDgst | servDgst | Text | 직접 매핑 |
| `wlfare_info_outl_cn` | wlfareInfoOutlCn | NULL | Text | 중앙만 |
| `target_detail` | tgtrDtlCn | sprtTrgtCn | Text | ⭐ RAG 핵심 |
| `select_criteria` | slctCritCn | slctCritCn | Text | ⭐ RAG 핵심 |
| `service_content` | alwServCn | alwServCn | Text | ⭐ RAG 핵심 |
| `apply_method_detail` | applmetList | aplyMtdCn | Text | ⭐ RAG 핵심 |
| `contact_info` | inqplCtadrList | inqplCtadrList | JSONB | XML → JSON |
| `attachments` | basfrmList | basfrmList | JSONB | XML → JSON |
| `base_laws` | baslawList | baslawList | JSONB | XML → JSON |
| `related_links` | inqplHmpgReldList | inqplHmpgReldList | JSONB | ⭐ 양쪽 모두 제공 |
| `inq_num` | inqNum | inqNum | Integer | 직접 매핑 |

---

## 4. 데이터 변환 로직

### 4.1 배열 변환

**중앙부처** (쉼표 구분, 이름만 제공):
```python
# Input (주의: 코드가 아닌 이름이 들어있음)
lifeArray = "영유아,임신 · 출산"
intrsThemaArray = "신체건강,임신·출산"
trgterIndvdlArray = "다자녀,장애인,저소득"

# Output
life_nm_array = ["영유아", "임신 · 출산"]
intrs_thema_nm_array = ["신체건강", "임신·출산"]
trgter_indvdl_nm_array = ["다자녀", "장애인", "저소득"]
```

**지자체** (슬래시 또는 쉼표 구분):
```python
# Input
lifeNmArray = "중장년/노년"

# Output
life_nm_array = ["중장년", "노년"]
```

**변환 함수**:
```python
def parse_array(value):
    """쉼표 또는 슬래시로 구분된 문자열을 배열로 변환"""
    if not value:
        return []
    # 중앙부처: 쉼표 구분
    if ',' in value:
        return [x.strip() for x in value.split(',')]
    # 지자체: 슬래시 구분
    elif '/' in value:
        return [x.strip() for x in value.split('/')]
    else:
        return [value.strip()]
```

### 4.2 날짜 변환

```python
def parse_date(date_str):
    """YYYYMMDD → YYYY-MM-DD"""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date().isoformat()
    except ValueError:
        return None

# Example
"20240101" → "2024-01-01"
```

### 4.3 XML → JSON 변환

**형태 1: 단일 항목 구조**:
```xml
<inqplCtadrList>
    <servSeDetailLink>1577-8136</servSeDetailLink>
    <servSeDetailNm>아이돌봄 지원사업</servSeDetailNm>
</inqplCtadrList>
```

**변환 결과**:
```json
[
  {
    "servSeDetailLink": "1577-8136",
    "servSeDetailNm": "아이돌봄 지원사업"
  }
]
```

**형태 2: 다중 항목 - 형제 노드 반복** ⭐:
```xml
<applmetList>
    <servSeDetailLink>방문 신청</servSeDetailLink>
    <servSeDetailNm>사용관리기관</servSeDetailNm>
</applmetList>
<applmetList>
    <servSeDetailLink>전화 신청</servSeDetailLink>
    <servSeDetailNm>사용관리기관</servSeDetailNm>
</applmetList>
```

**변환 결과**:
```json
[
  {
    "servSeDetailLink": "방문 신청",
    "servSeDetailNm": "사용관리기관"
  },
  {
    "servSeDetailLink": "전화 신청",
    "servSeDetailNm": "사용관리기관"
  }
]
```

**형태 3: 다중 항목 - child 태그 반복**:
```xml
<basfrmList>
    <basfrm>
        <servSeDetailLink>https://...</servSeDetailLink>
        <servSeDetailNm>안내서.pdf</servSeDetailNm>
    </basfrm>
    <basfrm>
        <servSeDetailLink>https://...</servSeDetailLink>
        <servSeDetailNm>신청서.hwp</servSeDetailNm>
    </basfrm>
</basfrmList>
```

**변환 결과**:
```json
[
  {
    "servSeDetailLink": "https://...",
    "servSeDetailNm": "안내서.pdf"
  },
  {
    "servSeDetailLink": "https://...",
    "servSeDetailNm": "신청서.hwp"
  }
]
```

**변환 함수** (3가지 형태 모두 지원):
```python
def parse_xml_list_auto(root, parent_tag, possible_child_tag, fields):
    """
    XML 리스트를 JSON 배열로 변환
    - 형태1: 단일 항목
    - 형태2: 형제 노드 반복 (applmetList, basfrmList 등)
    - 형태3: child 태그 반복
    """
    results = []
    
    # 형제로 반복되는 parent_tag들 모두 찾기
    parents = root.findall(f'.//{parent_tag}')
    if not parents:
        return json.dumps([], ensure_ascii=False)
    
    # 각 parent에서 데이터 추출
    for parent in parents:
        # child_tag가 있는지 확인
        children = parent.findall(possible_child_tag)
        if children:
            # child가 있는 경우
            for child in children:
                data = {field: safe_find_text(child, field) for field in fields}
                if any(data.values()):
                    results.append(data)
        else:
            # parent 안에 직접 필드가 있는 경우
            data = {field: safe_find_text(parent, field) for field in fields}
            if any(data.values()):
                results.append(data)
    
    return json.dumps(results, ensure_ascii=False)
```

**신청방법 텍스트 변환**:
```python
def format_apply_methods(apply_methods_json):
    """JSON 리스트를 텍스트로 포맷팅"""
    if apply_methods_json == '[]':
        return None
    
    methods_list = json.loads(apply_methods_json)
    formatted_methods = []
    
    for method in methods_list:
        link = method.get('servSeDetailLink', '')
        name = method.get('servSeDetailNm', '')
        if link and name:
            formatted_methods.append(f"{link} ({name})")
        elif link:
            formatted_methods.append(link)
        elif name:
            formatted_methods.append(name)
    
    return ', '.join(formatted_methods) if formatted_methods else None

# 예시
# Input: [{"servSeDetailLink":"방문 신청","servSeDetailNm":"사용관리기관"},...]
# Output: "방문 신청 (사용관리기관), 전화 신청 (사용관리기관)"
```

### 4.4 content_for_embedding 생성

**목적**: RAG를 위한 통합 임베딩 생성

**중앙부처**:
```python
content_for_embedding = f"""
서비스명: {servNm}
개요: {wlfareInfoOutlCn}
대상: {tgtrDtlCn}
선정기준: {slctCritCn}
내용: {alwServCn}
""".strip()
```

**지자체**:
```python
content_for_embedding = "\n".join(filter(None, [
    f"대상: {sprtTrgtCn}",
    f"기준: {slctCritCn}",
    f"내용: {alwServCn}",
    f"방법: {aplyMtdCn}"
]))
```

---

## 5. 특이사항 및 주의점

### 5.0 ⚠️ 크리티컬: API 필드명 차이

**지자체 API는 JSON 리스트 필드명이 중앙부처와 완전히 다릅니다!**

| 용도 | 중앙부처 필드명 | 지자체 필드명 | 비고 |
|------|----------------|--------------|------|
| 링크/연락처/URL | `servSeDetailLink` | `wlfareInfoReldCn` | ⚠️ 다름 |
| 이름/설명 | `servSeDetailNm` | `wlfareInfoReldNm` | ⚠️ 다름 |
| 구분 코드 | `servSeCode` | `wlfareInfoDtlCd` | 둘 다 사용 안 함 |

**영향 받는 필드**:
- `inqplCtadrList` (문의처)
- `baslawList` (근거법령)
- `basfrmList` (첨부파일)
- `inqplHmpgReldList` (관련 홈페이지)

**파싱 예시**:
```python
# 중앙부처
contact_info = parse_xml_list_auto(detail, 'inqplCtadrList', 'inqplCtadr', 
                                   ['servSeDetailLink', 'servSeDetailNm'])

# 지자체
contact_info = parse_xml_list_auto(detail, 'inqplCtadrList', 'inqplCtadr', 
                                   ['wlfareInfoReldCn', 'wlfareInfoReldNm'])
```

### 5.1 중앙부처 vs 지자체 차이점

| 항목 | 중앙부처 | 지자체 | 비고 |
|------|---------|--------|------|
| 지역 정보 | ❌ 없음 (전국 대상) | ✅ ctpvNm, sggNm | 하이브리드 RAG 필터링 핵심 |
| 시행기간 | ❌ 없음 | ✅ enfcBgngYmd, enfcEndYmd | 지자체는 기간 제한 있음 |
| 온라인신청 | ✅ onapPsbltYn | ❌ 없음 | |
| 복지정보 개요 | ✅ wlfareInfoOutlCn | ❌ 없음 | |
| 관련 홈페이지 | ✅ inqplHmpgReldList | ✅ inqplHmpgReldList | ⭐ 양쪽 모두 제공 |
| 부서명 | jurMnofNm + jurOrgNm | bizChrDeptNm | 중앙: 부처+부서 조합 |
| 배열 필드 | ⚠️ 코드 아닌 이름 | 이름 | 중앙부처 주의! |
| 서비스 메타 | ✅ sprtCycNm, srvPvsnNm | ✅ sprtCycNm, srvPvsnNm | 양쪽 모두 제공 |

### 5.2 목록 vs 상세 API 차이

| 필드 | 목록 API | 상세 API | 권장 |
|------|---------|---------|------|
| 기본 정보 | ✅ 제공 | ✅ 제공 | 목록에서 가져오기 |
| 부서명 (중앙) | ✅ jurMnofNm + jurOrgNm | ✅ 완전 (조합됨) | ⭐ 상세에서 덮어쓰기 (더 완전) |
| 배열 필드 | ✅ 제공 | ✅ 제공 | ⭐ 상세에서 덮어쓰기 (더 정확) |
| 서비스 메타 | ✅ sprtCycNm, srvPvsnNm | ✅ 제공 | ⭐ 상세에서 덮어쓰기 (더 정확) |
| 핵심 콘텐츠 | ❌ 없음 | ✅ 제공 | ⭐ 상세에서만 가져오기 |
| JSON 리스트 | ❌ 없음 | ✅ 제공 | ⭐ 상세에서만 가져오기 |
| 신청방법 | ❌ 없음 | ✅ applmetList | ⭐ 상세에서 가져와 텍스트로 변환 |

**데이터 수집 전략**:
1. 목록 API에서 기본 정보 + 배열 + 메타 가져오기
2. 상세 API 호출
3. 상세 API에서 핵심 콘텐츠 + JSON 리스트 가져오기
4. 상세 API에 배열/메타가 있으면 **덮어쓰기** (더 정확함)

### 5.3 제거된 필드

다음 필드는 **의미가 없어 DB에 저장하지 않음**:
- `servSeCode`: 010, 020, 040 등 내부 코드 (사용처 불명)

다음 필드는 **코드 배열로 사용하지 않음** (이름 배열만 사용):
- `life_array`: 중앙부처 API에서 이미 이름이 `lifeArray`에 들어있음
- `intrs_thema_array`: 중앙부처 API에서 이미 이름이 `intrsThemaArray`에 들어있음
- `trgter_indvdl_array`: 중앙부처 API에서 이미 이름이 `trgterIndvdlArray`에 들어있음

### 5.4 배열 필드 주의사항 ⚠️

**중요**: 중앙부처 API의 배열 필드는 **코드가 아닌 이름**이 들어있습니다!

**중앙부처**: 쉼표(`,`) 구분, **이름** 제공
```xml
<lifeArray>영유아,임신 · 출산</lifeArray>
<intrsThemaArray>신체건강,임신·출산</intrsThemaArray>
<trgterIndvdlArray>다자녀,장애인,저소득</trgterIndvdlArray>
```

**지자체**: 슬래시(`/`) 또는 쉼표 구분, **이름** 제공
```xml
<lifeNmArray>중장년/노년</lifeNmArray>
```

**변환 후 PostgreSQL 배열**:
```sql
life_nm_array = ARRAY['영유아', '임신 · 출산']
```

**검색 쿼리 (배열 포함 연산자)**:
```sql
-- 사용자가 선택한 연령대와 겹치는지 확인
WHERE life_nm_array && ARRAY['노년', '중장년']
```

**코드 배열은 사용하지 않음**:
- `life_array` (삭제됨)
- `intrs_thema_array` (삭제됨)
- `trgter_indvdl_array` (삭제됨)

---

## 6. 실제 응답 예시

### 6.1 중앙부처 목록 API 응답 (실제 예시)

```xml
<wantedList>
    <totalCount>3</totalCount>
    <pageNo>1</pageNo>
    <numOfRows>10</numOfRows>
    <resultCode>0</resultCode>
    <resultMessage>SUCCESS</resultMessage>
    <servList>
        <inqNum>1416063</inqNum>
        <intrsThemaArray>신체건강,임신·출산</intrsThemaArray>
        <jurMnofNm>보건복지부</jurMnofNm>
        <jurOrgNm>출산정책과</jurOrgNm>
        <lifeArray>영유아,임신 · 출산</lifeArray>
        <onapPsbltYn>Y</onapPsbltYn>
        <rprsCtadr>129</rprsCtadr>
        <servDgst>출산가정에 건강관리사를 파견하여 산모신생아 건강관리 지원...</servDgst>
        <servDtlLink>https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00001188</servDtlLink>
        <servId>WLF00001188</servId>
        <servNm>산모·신생아 건강관리 지원사업</servNm>
        <sprtCycNm>1회성</sprtCycNm>
        <srvPvsnNm>현지비지원(바우처)</srvPvsnNm>
        <svcfrstRegTs>20210903</svcfrstRegTs>
        <trgterIndvdlArray>다자녀,장애인,저소득</trgterIndvdlArray>
    </servList>
    <!-- 추가 servList 항목들... -->
</wantedList>
```

**주요 특징**:
- ⚠️ `lifeArray`, `intrsThemaArray`, `trgterIndvdlArray`에 **코드가 아닌 이름**이 들어있음
- ✅ `jurOrgNm` (부서명) 제공
- ✅ `sprtCycNm`, `srvPvsnNm` 목록 API에도 있음

### 6.2 중앙부처 상세 API 응답 (실제 예시)

```xml
<wantedDtl>
    <servId>WLF00000024</servId>
    <servNm>아이돌봄 서비스</servNm>
    <jurMnofNm>성평등가족부 가족문화과</jurMnofNm>
    <wlfareInfoOutlCn>양육공백 발생 가정에 아이돌보미가 직접 찾아가 돌봄 서비스 제공...</wlfareInfoOutlCn>
    <rprsCtadr>1577-8136</rprsCtadr>
    <sprtCycNm>수시</sprtCycNm>
    <srvPvsnNm>기타</srvPvsnNm>
    <lifeArray>아동, 영유아, 청소년</lifeArray>
    <trgterIndvdlArray>영아민, 다자녀-예비맘, 다자녀, 한부모-조손</trgterIndvdlArray>
    <intrsThemaArray>보호·돌봄, 보육</intrsThemaArray>
    
    <!-- 신청방법 리스트 (형제 노드 반복) -->
    <applmetList>
        <servSeCode>070</servSeCode>
        <servSeDetailLink>방문 신청</servSeDetailLink>
        <servSeDetailNm>사용관리기관</servSeDetailNm>
    </applmetList>
    <applmetList>
        <servSeCode>070</servSeCode>
        <servSeDetailLink>전화 신청</servSeDetailLink>
        <servSeDetailNm>사용관리기관</servSeDetailNm>
    </applmetList>
    
    <!-- 첨부파일 리스트 (형제 노드 반복) -->
    <basfrmList>
        <servSeCode>040</servSeCode>
        <servSeDetailLink>https://bokjiro.go.kr/.../안내.pdf</servSeDetailLink>
        <servSeDetailNm>2025년 아이돌봄 지원사업 안내.pdf</servSeDetailNm>
    </basfrmList>
    <basfrmList>
        <servSeCode>040</servSeCode>
        <servSeDetailLink>https://bokjiro.go.kr/.../신청서.pdf</servSeDetailLink>
        <servSeDetailNm>신청서.pdf</servSeDetailNm>
    </basfrmList>
    
    <!-- 근거법령 -->
    <baslawList>
        <servSeCode>030</servSeCode>
        <servSeDetailNm>아이돌봄 지원법</servSeDetailNm>
    </baslawList>
    
    <resultCode>0</resultCode>
    <resultMessage>SUCCESS</resultMessage>
</wantedDtl>
```

**주요 특징**:
- ✅ `jurMnofNm`에 부처명 + 부서명 조합됨 (성평등가족부 가족문화과)
- ⭐ `applmetList`, `basfrmList` 등이 **형제 노드로 반복**됨
- ✅ 상세 API에도 `lifeArray`, `trgterIndvdlArray`, `intrsThemaArray` 있음
- ✅ 상세 API에도 `sprtCycNm`, `srvPvsnNm` 있음

### 6.3 지자체 상세 API 응답 (일부)

```xml
<servList>
    <servId>LCG00001234</servId>
    <servNm>서울시 어르신 건강검진</servNm>
    <servDgst>만 65세 이상 서울시민 대상 건강검진 지원</servDgst>
    <ctpvNm>서울특별시</ctpvNm>
    <sggNm>종로구</sggNm>
    <bizChrDeptNm>서울시 복지정책과</bizChrDeptNm>
    <enfcBgngYmd>20240101</enfcBgngYmd>
    <enfcEndYmd>20241231</enfcEndYmd>
    <lastModYmd>20240620</lastModYmd>
    <lifeNmArray>중장년/노년</lifeNmArray>
    <intrsThemaNmArray>건강/의료</intrsThemaNmArray>
    <trgterIndvdlNmArray>노인</trgterIndvdlNmArray>
    <sprtCycNm>연</sprtCycNm>
    <srvPvsnNm>서비스</srvPvsnNm>
    <aplyMtdNm>방문</aplyMtdNm>
    <sprtTrgtCn>만 65세 이상 서울시 거주 주민등록상 1년 이상 거주자</sprtTrgtCn>
    <slctCritCn>소득인정액 하위 70% 이하</slctCritCn>
    <alwServCn>건강검진 비용 전액 지원 (연 1회)</alwServCn>
    <aplyMtdCn>주민센터 방문 또는 온라인 신청 (서울시 복지포털)</aplyMtdCn>
    <inqNum>5432</inqNum>
    <inqplCtadrList>
        <servSeDetailLink>02-120</servSeDetailLink>
        <servSeDetailNm>서울시 다산콜센터</servSeDetailNm>
    </inqplCtadrList>
</servList>
```

---

## 7. 관련 문서

- [통합 DB 스키마 설계](./UNIFIED_SCHEMA_DESIGN.md)
- [데이터 수집 설계](./BENEFIT_DATA_COLLECTION_DESIGN.md)
- Supabase 스키마: `/supabase/schema.sql`
- 수집 스크립트:
  - 중앙부처: `/scripts/data_collection/collect_national_welfare.py`
  - 지자체: `/scripts/data_collection/collect_local_welfare.py`

---

## 8. 변경 이력

### 2026-01-22 (v3) - 지자체 API 업데이트 및 크리티컬 버그 수정 🚨

**크리티컬 버그 수정** ⚠️:
1. **지자체 API 필드명이 중앙부처와 완전히 다름!**
   - **중앙부처**: `servSeDetailLink`, `servSeDetailNm`
   - **지자체**: `wlfareInfoReldCn`, `wlfareInfoReldNm`
   - **영향**: `contact_info`, `base_laws`, `attachments`, `related_links` 파싱 100% 실패
   - **증상**: `content_for_embedding`에 "문의처:" 정보 누락
   - **수정**: 모든 JSON 필드 파싱에서 올바른 필드명 사용

**주요 발견사항**:
2. **지자체도 `inqplHmpgReldList` 제공** ⭐
   - 기존 문서에는 중앙부처만 제공한다고 되어있었음
   - 지자체 상세 API도 관련 홈페이지 리스트 제공
   - `related_links` 컬럼에 저장

3. **지자체도 `baslawList`에 URL 제공**
   - `wlfareInfoReldCn` 필드에 법령 URL 포함
   - 기존에는 법령명만 저장한다고 생각했으나 URL도 제공됨

4. **의미없는 코드 필드 제거**
   - 지자체는 `wlfareInfoDtlCd` 사용 (중앙의 `servSeCode`와 동일)
   - 010, 020, 030 등의 내부 코드로 의미 없음
   - DB 저장에서 제외

5. **상세 API에도 배열/메타 존재**
   - 목록 API뿐 아니라 상세 API에도 배열 필드 제공
   - 상세 API 값으로 덮어쓰기 전략 적용

**코드 변경사항**:
- 🚨 `collect_local_welfare.py`: 모든 JSON 필드를 `wlfareInfoReld*`로 수정
- 🚨 `collect_local_welfare.py`: `contact_text` 생성 로직 수정
- `collect_local_welfare.py`: `related_links` 파싱 추가
- `collect_local_welfare.py`: `wlfareInfoDtlCd` 제거
- `collect_local_welfare.py`: 상세 API에서 배열/메타 덮어쓰기 로직 추가

**문서 변경사항**:
- ⚠️ 지자체 API 필드명 전면 수정 (servSeDetail* → wlfareInfoReld*)
- 지자체 상세 API 필드표에 `inqplHmpgReldList` 추가
- 지자체도 `related_links` 제공한다고 업데이트
- 중앙부처 vs 지자체 차이점 테이블 업데이트

### 2026-01-22 (v2) - 실제 API 응답 기반 업데이트

**주요 발견사항**:
1. **XML 구조가 형제 노드 반복** ⚠️
   - `<applmetList>...</applmetList><applmetList>...</applmetList>` 형태
   - 기존 파싱 함수로는 첫 번째 항목만 인식
   - `findall()`로 모든 형제 노드 찾도록 수정

2. **상세 API에도 배열 필드 존재**
   - `lifeArray`, `intrsThemaArray`, `trgterIndvdlArray`
   - 목록 API보다 더 정확할 수 있음
   - 상세 API 값으로 덮어쓰기 전략 적용

3. **상세 API에도 서비스 메타 존재**
   - `sprtCycNm`, `srvPvsnNm`
   - 상세 API 값으로 덮어쓰기

4. **신청방법 리스트 추가** (`applmetList`)
   - JSON 배열로 파싱
   - 텍스트로 포맷팅해서 `apply_method_detail`에 저장

5. **부서명 조합 로직**
   - 목록 API: `jurMnofNm` + `jurOrgNm` 조합
   - 상세 API: `jurMnofNm`에 이미 조합됨

**코드 변경사항**:
- `parse_xml_list_auto()` 함수 수정 - 형제 노드 반복 지원
- 상세 API에서 배열 필드 덮어쓰기 로직 추가
- `applmetList` 파싱 및 텍스트 변환 로직 추가
- 지자체 API도 동일하게 수정

**문서 변경사항**:
- 목록 API 필드표 업데이트 (`jurOrgNm`, `sprtCycNm`, `srvPvsnNm` 추가)
- 상세 API 필드표 업데이트 (`applmetList`, 배열 필드, 서비스 메타 추가)
- XML 구조 설명 보강 (형제 노드 반복 구조)
- 실제 응답 예시로 교체
- 데이터 수집 전략 섹션 추가

---

**작성일**: 2026-01-22  
**최종 업데이트**: 2026-01-22 18:00  
**작성자**: AI Assistant

