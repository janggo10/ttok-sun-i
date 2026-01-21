# 통합 DB 스키마 설계

## 목적
중앙부처복지서비스 API와 지자체복지서비스 API의 데이터를 단일 DB에 통합 저장하기 위한 스키마 설계

## 중요 설계 결정사항 ⭐

### 연령 필터링 전략
- **기존 계획**: 사용자에게 나이(숫자)를 입력받아 `target_age_min`, `target_age_max`로 필터링
- **변경된 전략**: 사용자에게 관심 연령대(청년, 중장년, 노년 등)를 복수 선택받아 `life_array`로 필터링
- **장점**:
  1. API 응답 필드(`lifeArray`)와 직접 매칭 → 텍스트 파싱 불필요
  2. 구현 복잡도 대폭 감소, 에러 가능성 제거
  3. 데이터 정확도 향상
- **데이터 수집**: 시니어 대상만이 아닌 **모든 연령대 혜택 수집** (향후 확장 대비)

## 1. API 비교 분석

### 1.1 데이터 규모
- **지자체 API**: 서울 전체 357개
- **중앙부처 API**: 전국 365개
- **합계**: 약 700개 (초기 MVP)

### 1.2 필드 비교

| 필드 유형 | 지자체 API | 중앙부처 API | 통합 전략 |
|----------|-----------|------------|----------|
| **고유 ID** | servId | servId | 공통 컬럼 ✅ |
| **서비스명** | servNm | servNm | 공통 컬럼 ✅ |
| **요약** | servDgst | servDgst | 공통 컬럼 ✅ |
| **지역** | ctpvNm, sggNm | ❌ 없음 | nullable (중앙은 NULL) |
| **부처/부서** | bizChrDeptNm | jurMnofNm | 통합 컬럼 (dept_name) |
| **연락처** | ❌ | rprsCtadr | nullable (지자체는 NULL) |
| **온라인신청** | ❌ | onapPsbltYn | nullable |
| **생애주기(연령대)** ⭐ | lifeNmArray | lifeArray | 통합 컬럼 (life_nm_array 배열) |
| **관심주제** | intrsThemaNmArray | intrsThemaArray | 통합 컬럼 (intrs_thema_nm_array 배열) |
| **대상자** | trgterIndvdlNmArray | trgterIndvdlArray | 통합 컬럼 (trgter_indvdl_nm_array 배열) |
| **지원대상** | sprtTrgtCn | tgtrDtlCn | 통합 컬럼 (target_detail) |
| **선정기준** | slctCritCn | slctCritCn | 공통 컬럼 ✅ |
| **지원내용** | alwServCn | alwServCn | 공통 컬럼 ✅ |
| **신청방법** | aplyMtdCn | applmetList | 통합 컬럼 (apply_method) |
| **문의처** | contact_info (JSON) | inqplCtadrList | 통합 JSON |
| **첨부파일** | basfrmList | basfrmList | 통합 JSON |
| **근거법령** | baslawList | baslawList | 통합 JSON |

---

## 2. 통합 스키마 설계

### 2.1 benefits 테이블 (메인)

```sql
CREATE TABLE benefits (
    -- 기본 정보
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    serv_id VARCHAR(20) UNIQUE NOT NULL,  -- WLF00001188
    serv_nm VARCHAR(500) NOT NULL,         -- 서비스명
    source_api VARCHAR(20) NOT NULL,       -- 'LOCAL' or 'NATIONAL'
    
    -- 지역 정보 (지자체 API만, 중앙부처는 NULL)
    ctpv_nm VARCHAR(50),                   -- 시도명 (서울특별시)
    sgg_nm VARCHAR(50),                    -- 시군구명 (종로구)
    
    -- 부서/기관 정보
    dept_name VARCHAR(200),                -- 담당부서/주관부처
    dept_contact VARCHAR(100),             -- 연락처 (중앙부처 rprsCtadr 또는 지자체 contact_info에서)
    
    -- 기간 정보
    enfc_bgng_ymd DATE,                    -- 시행시작일 (지자체만)
    enfc_end_ymd DATE,                     -- 시행종료일 (지자체만)
    crtr_yr INTEGER,                       -- 기준연도 (중앙부처만)
    last_mod_ymd DATE,                     -- 최종수정일
    
    -- 분류 메타데이터 (PostgreSQL 배열 타입)
    life_array TEXT[],                     -- 생애주기 코드 배열 ['002001005', '002001006']
    life_nm_array TEXT[],                  -- 생애주기 명칭 배열 ['중장년', '노년']
    intrs_thema_array TEXT[],              -- 관심주제 코드 배열
    intrs_thema_nm_array TEXT[],           -- 관심주제 명칭 배열
    trgter_indvdl_array TEXT[],            -- 대상자 코드 배열
    trgter_indvdl_nm_array TEXT[],         -- 대상자 명칭 배열
    sprt_cyc_nm VARCHAR(50),               -- 지원주기 (월, 연, 1회성)
    srv_pvsn_nm VARCHAR(50),               -- 서비스제공방법 (현금지급, 현물)
    aply_mtd_nm VARCHAR(200),              -- 신청방법 (방문, 온라인 등)
    
    -- 온라인신청 (중앙부처만)
    onap_psblt_yn CHAR(1),                 -- Y/N (중앙부처만, 지자체는 NULL)
    
    -- 핵심 콘텐츠 (요약)
    serv_dgst TEXT,                        -- 서비스 요약
    wlfare_info_outl_cn TEXT,              -- 복지정보 개요 (중앙부처만)
    serv_dtl_link VARCHAR(500),            -- 상세정보 링크 (복지로)
    
    -- 핵심 콘텐츠 (상세) - RAG/임베딩용 ⭐⭐⭐
    target_detail TEXT,                    -- 지원대상 상세 (sprtTrgtCn/tgtrDtlCn)
    select_criteria TEXT,                  -- 선정기준 상세 (slctCritCn)
    service_content TEXT,                  -- 지원내용 상세 (alwServCn)
    apply_method_detail TEXT,              -- 신청방법 상세 (aplyMtdCn 또는 applmetList)
    
    -- 통합 임베딩 컬럼 (4개 필드 결합) ⭐⭐⭐
    content_for_embedding TEXT,            -- 위 4개 필드 결합 (RAG용)
    
    -- 부가 정보 (JSON)
    contact_info JSONB,                    -- 문의처 정보
    attachments JSONB,                     -- 첨부파일 목록
    base_laws JSONB,                       -- 근거법령 목록
    related_links JSONB,                   -- 관련 홈페이지 (중앙부처)
    
    -- 통계
    inq_num INTEGER DEFAULT 0,             -- 조회수
    
    -- 시스템 정보
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 인덱스
    CONSTRAINT benefits_source_api_check CHECK (source_api IN ('LOCAL', 'NATIONAL'))
);

-- 인덱스 생성
CREATE INDEX idx_benefits_region ON benefits(ctpv_nm, sgg_nm) WHERE ctpv_nm IS NOT NULL;

-- 배열 검색을 위한 GIN 인덱스 (연령대, 관심주제 필터링) ⭐
CREATE INDEX idx_benefits_life_array ON benefits USING gin(life_nm_array);
CREATE INDEX idx_benefits_intrs_thema ON benefits USING gin(intrs_thema_nm_array);

CREATE INDEX idx_benefits_source_api ON benefits(source_api);
CREATE INDEX idx_benefits_updated_at ON benefits(updated_at);

-- 전문검색 인덱스
CREATE INDEX idx_benefits_content_search ON benefits USING gin(
    to_tsvector('korean', 
        COALESCE(serv_nm, '') || ' ' || 
        COALESCE(serv_dgst, '') || ' ' ||
        COALESCE(target_detail, '') || ' ' ||
        COALESCE(service_content, '')
    )
);
```

---

## 3. 데이터 매핑 전략

### 3.1 지자체 API → benefits 테이블

```python
{
    # 기본 정보
    'serv_id': servId,
    'serv_nm': servNm,
    'source_api': 'LOCAL',
    
    # 지역 정보 ⭐
    'ctpv_nm': ctpvNm,
    'sgg_nm': sggNm,
    
    # 부서 정보
    'dept_name': bizChrDeptNm,
    'dept_contact': extract_from_contact_info(inqplCtadrList),
    
    # 기간 정보 ⭐
    'enfc_bgng_ymd': parse_date(enfcBgngYmd),
    'enfc_end_ymd': parse_date(enfcEndYmd),
    'last_mod_ymd': parse_date(lastModYmd),
    
    # 분류 (배열 타입) ⭐ 연령대 필터링 핵심
    'life_array': parse_array(lifeArray),           # ['002001005', '002001006']
    'life_nm_array': parse_array(lifeNmArray),     # ['중장년', '노년']
    'intrs_thema_array': parse_array(intrsThemaArray),
    'intrs_thema_nm_array': parse_array(intrsThemaNmArray),
    'trgter_indvdl_array': parse_array(trgterIndvdlArray),
    'trgter_indvdl_nm_array': parse_array(trgterIndvdlNmArray),
    'sprt_cyc_nm': sprtCycNm,
    'srv_pvsn_nm': srvPvsnNm,
    'aply_mtd_nm': aplyMtdNm,
    
    # 콘텐츠
    'serv_dgst': servDgst,
    'serv_dtl_link': servDtlLink,
    'target_detail': sprtTrgtCn,      # ⭐ RAG 핵심
    'select_criteria': slctCritCn,     # ⭐ RAG 핵심
    'service_content': alwServCn,      # ⭐ RAG 핵심
    'apply_method_detail': aplyMtdCn,  # ⭐ RAG 핵심
    
    # 통합 임베딩 텍스트
    'content_for_embedding': f"{sprtTrgtCn}\n\n{slctCritCn}\n\n{alwServCn}\n\n{aplyMtdCn}",
    
    # JSON
    'contact_info': json.dumps(inqplCtadrList),
    'attachments': json.dumps(basfrmList),
    'base_laws': json.dumps(baslawList),
    
    # 통계
    'inq_num': inqNum,
}
```

### 3.2 중앙부처 API → benefits 테이블

```python
{
    # 기본 정보
    'serv_id': servId,
    'serv_nm': servNm,
    'source_api': 'NATIONAL',
    
    # 지역 정보 (중앙부처는 NULL) ⭐
    'ctpv_nm': None,
    'sgg_nm': None,
    
    # 부서 정보
    'dept_name': jurMnofNm,           # 보건복지부 자활정책과
    'dept_contact': rprsCtadr,        # 129 ⭐
    
    # 기간 정보
    'crtr_yr': int(crtrYr),           # 2025 ⭐
    'last_mod_ymd': parse_date(svcfrstRegTs),  # 최초등록일
    
    # 분류 (배열 타입) ⭐ 연령대 필터링 핵심
    'life_array': parse_array(lifeArray),           # ['002001005', '002001006']
    'life_nm_array': parse_array(lifeNmArray),     # ['중장년', '노년']
    'intrs_thema_array': parse_array(intrsThemaArray),
    'intrs_thema_nm_array': parse_array(intrsThemaNmArray),
    'trgter_indvdl_array': parse_array(trgterIndvdlArray),
    'trgter_indvdl_nm_array': parse_array(trgterIndvdlNmArray),
    'sprt_cyc_nm': sprtCycNm,
    'srv_pvsn_nm': srvPvsnNm,
    'aply_mtd_nm': extract_from_applmetList(applmetList),
    
    # 온라인신청 ⭐
    'onap_psblt_yn': onapPsbltYn,
    
    # 콘텐츠
    'serv_dgst': servDgst,
    'wlfare_info_outl_cn': wlfareInfoOutlCn,  # 중앙부처만 ⭐
    'serv_dtl_link': servDtlLink,
    'target_detail': tgtrDtlCn,       # ⭐ RAG 핵심
    'select_criteria': slctCritCn,     # ⭐ RAG 핵심
    'service_content': alwServCn,      # ⭐ RAG 핵심
    'apply_method_detail': format_applmetList(applmetList),  # ⭐ RAG 핵심
    
    # 통합 임베딩 텍스트
    'content_for_embedding': f"{wlfareInfoOutlCn}\n\n{tgtrDtlCn}\n\n{slctCritCn}\n\n{alwServCn}",
    
    # JSON
    'contact_info': json.dumps(inqplCtadrList),
    'attachments': json.dumps(basfrmList),
    'base_laws': json.dumps(baslawList),
    'related_links': json.dumps(inqplHmpgReldList),  # 중앙부처만 ⭐
    
    # 통계
    'inq_num': inqNum if inqNum else 0,
}
```

---

## 4. 핵심 설계 결정

### 4.1 source_api 필드 ⭐
- **목적**: 데이터 출처 구분
- **값**: 'LOCAL' (지자체) or 'NATIONAL' (중앙부처)
- **용도**: 
  - 지역 필터링 로직 분기
  - 업데이트 전략 차별화
  - 데이터 출처 표시

### 4.2 지역 정보 처리 ⭐⭐⭐
```sql
-- 지자체 복지: ctpv_nm, sgg_nm 모두 값 있음
ctpv_nm = '서울특별시'
sgg_nm = '종로구'

-- 중앙부처 복지: 둘 다 NULL
ctpv_nm = NULL
sgg_nm = NULL

-- 쿼리 예시 (하이브리드 RAG) ⭐⭐⭐
SELECT * FROM benefits
WHERE (
    -- 사용자 지역에 해당하는 지자체 복지
    (ctpv_nm = '서울특별시' AND sgg_nm = '종로구')
    OR
    -- 또는 전국 단위 중앙부처 복지
    (ctpv_nm IS NULL AND source_api = 'NATIONAL')
)
-- 사용자가 선택한 연령대와 일치 (배열 포함 연산자)
AND life_nm_array && ARRAY['중장년', '노년']  -- 사용자가 관심 있는 연령대
```

### 4.3 배열 필드 파싱 (parse_array 함수) ⭐

API 응답의 배열 필드는 쉼표로 구분된 문자열 형태:
```
lifeArray: "002001005,002001006"
lifeNmArray: "중장년,노년"
```

Python에서 PostgreSQL 배열로 변환:
```python
def parse_array(value: str) -> list:
    """쉼표로 구분된 문자열을 리스트로 변환"""
    if not value or value.strip() == '':
        return []
    return [item.strip() for item in value.split(',') if item.strip()]

# 사용 예시
life_array = parse_array("002001005,002001006")  # ['002001005', '002001006']
life_nm_array = parse_array("중장년,노년")       # ['중장년', '노년']
```

### 4.4 content_for_embedding 필드 ⭐⭐⭐
**목적**: RAG를 위한 통합 임베딩 생성

**구성**:
```
[지자체]
{지원대상 상세}

{선정기준 상세}

{지원내용 상세}

{신청방법 상세}

[중앙부처]
{복지정보 개요}

{지원대상 상세}

{선정기준 상세}

{지원내용 상세}
```

**임베딩 생성 시**:
```python
embedding = get_embedding(content_for_embedding)
# → benefit_embeddings 테이블에 저장
```

### 4.5 JSON 필드 활용
**이유**: API별로 구조가 다른 복잡한 데이터

```python
# contact_info 예시
{
    "contacts": [
        {
            "name": "보건복지상담센터",
            "phone": "129",
            "type": "hotline"
        }
    ]
}

# attachments 예시
{
    "files": [
        {
            "name": "2025년 자활사업 안내.pdf",
            "url": "https://bokjiro.go.kr/...",
            "code": "040"
        }
    ]
}
```

---

## 5. 연령대 코드 매핑 ⭐⭐⭐

### 5.1 생애주기(lifeArray) 코드 정의

API에서 제공하는 생애주기 코드와 명칭:

| 코드 | 명칭 | 설명 | 예상 연령대 |
|------|------|------|------------|
| 002001001 | 영유아 | 취학 전 아동 | 0~5세 |
| 002001002 | 아동 | 초등학생 | 6~12세 |
| 002001003 | 청소년 | 중고등학생 | 13~18세 |
| 002001004 | 청년 | 대학생, 사회초년생 | 19~34세 |
| 002001005 | 중장년 | 중년층 | 35~64세 |
| 002001006 | 노년 | 시니어 | 65세 이상 |

### 5.2 온보딩에서 사용자 입력

**기존 방식** (❌ 파싱 필요):
```
- 거주지: 서울특별시 종로구
- 나이: 68세 → DB에서 target_age_min/max와 비교
```

**새로운 방식** (✅ 직접 매칭):
```
- 거주지: 서울특별시 종로구
- 관심 연령대 (복수 선택): ['중장년', '노년']
  → DB에서 life_nm_array && ARRAY['중장년', '노년'] 로 검색
```

### 5.3 데이터 수집 전략

**변경 전**:
- 시니어 대상 혜택만 수집 (노년 필터)

**변경 후** ⭐:
- **모든 연령대 혜택 수집** (필터 없음)
- 이유:
  1. 향후 서비스 확장 대비 (청년, 중장년 등)
  2. 재수집 불필요
  3. 스토리지 비용 < 개발/운영 비용
  4. 연령대별 혜택 통계 파악 가능

---

## 6. benefit_embeddings 테이블 (벡터 저장)

```sql
CREATE TABLE benefit_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    benefit_id BIGINT REFERENCES benefits(id) ON DELETE CASCADE,
    embedding VECTOR(1536),              -- OpenAI ada-002 dimension
    content_chunk TEXT,                  -- 임베딩된 원본 텍스트
    chunk_index INTEGER DEFAULT 0,       -- 청크 순서 (큰 문서는 분할)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 벡터 검색 인덱스
    UNIQUE(benefit_id, chunk_index)
);

-- ivfflat 인덱스 (빠른 근사 검색)
CREATE INDEX idx_benefit_embeddings_vector ON benefit_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

## 7. 하이브리드 RAG 쿼리 예시

```sql
-- Step 1: SQL 필터링 (지역 + 연령대) ⭐⭐⭐
WITH filtered_benefits AS (
    SELECT id, serv_id, serv_nm, source_api
    FROM benefits
    WHERE (
        -- 서울 종로구 지자체 복지 OR 전국 중앙부처 복지
        (ctpv_nm = '서울특별시' AND sgg_nm = '종로구')
        OR (ctpv_nm IS NULL AND source_api = 'NATIONAL')
    )
    -- 사용자가 선택한 연령대 (배열 포함 연산자)
    AND life_nm_array && ARRAY['중장년', '노년']
    AND (
        enfc_end_ymd IS NULL 
        OR enfc_end_ymd > CURRENT_DATE
    )  -- 유효한 복지만
)
-- Step 2: 벡터 검색 (filtered_benefits 범위 내에서만)
SELECT 
    b.serv_id,
    b.serv_nm,
    b.serv_dgst,
    b.source_api,
    b.ctpv_nm,
    b.sgg_nm,
    be.embedding <=> $1 AS similarity  -- $1 = 사용자 질문 임베딩
FROM filtered_benefits fb
JOIN benefit_embeddings be ON fb.id = be.benefit_id
JOIN benefits b ON fb.id = b.id
ORDER BY similarity
LIMIT 5;
```

---

## 8. 중복 제거 전략

### 8.1 중복 가능성
- 지자체 API와 중앙부처 API에 **동일 서비스**가 있을 수 있음
- 예: "기초연금" → 중앙부처(보건복지부)에도 있고, 지자체(서울시)에도 있을 수 있음

### 8.2 중복 방지
```sql
-- servId는 UNIQUE 제약조건
-- 같은 servId면 덮어쓰기 or 스킵

INSERT INTO benefits (serv_id, serv_nm, ...)
VALUES ('WLF00001188', '산모신생아건강관리', ...)
ON CONFLICT (serv_id) 
DO UPDATE SET
    updated_at = NOW(),
    -- 필요시 특정 필드만 업데이트
    serv_nm = EXCLUDED.serv_nm,
    content_for_embedding = EXCLUDED.content_for_embedding;
```

### 8.3 업데이트 전략
- **일일 1회** 전체 데이터 수집
- `last_mod_ymd` 비교 → 변경된 것만 업데이트
- 삭제된 서비스는 `enfc_end_ymd`를 과거로 설정

---

## 9. 구현 우선순위

### Phase 1: MVP (현재)
1. ✅ benefits 테이블 생성
2. ✅ 지자체 API 데이터 수집 (서울 357개)
3. ✅ 중앙부처 API 데이터 수집 (전국 365개)
4. ✅ content_for_embedding 생성
5. ⏳ benefit_embeddings 테이블에 벡터 저장 (1.3 단계)

### Phase 2: 확장
- 경기도 지자체 데이터 추가
- 다른 지역 확대
- 실시간 업데이트 로직

---

## 10. 다음 단계

1. **Supabase에서 테이블 생성**
   ```bash
   supabase/schema.sql 업데이트
   ```

2. **데이터 수집 스크립트 구현**
   ```
   scripts/data_collection/collect_benefits.py
   ```

3. **DB 저장 로직 구현**
   ```python
   - 지자체 API → benefits 매핑
   - 중앙부처 API → benefits 매핑
   - Supabase INSERT
   ```

4. **임베딩 생성 (1.3 단계)**
   ```python
   - content_for_embedding → OpenAI API
   - benefit_embeddings 저장
   ```

---

## 11. 예상 데이터 크기

| 항목 | 지자체 | 중앙부처 | 합계 |
|-----|-------|---------|-----|
| 서비스 수 | 357개 | 365개 | **722개** |
| 평균 텍스트 길이 | ~2000자 | ~2500자 | ~2250자 |
| 임베딩 차원 | 1536 | 1536 | 1536 |
| 예상 DB 크기 | ~5MB | ~5MB | **~10MB** |
| 예상 벡터 크기 | ~2MB | ~2MB | **~4MB** |

**총 예상 크기**: ~15MB (MVP)

---

## 12. 핵심 결론

### ✅ 통합 가능!
- 두 API의 핵심 필드는 **80% 공통**
- 나머지 20%는 **nullable** 또는 **JSON**으로 처리
- `source_api` 필드로 출처 구분

### ⭐ 핵심 차별점
- **지자체**: 지역 정보 (ctpv_nm, sgg_nm)
- **중앙부처**: 부처 정보 (jurMnofNm), 온라인신청 (onapPsbltYn)

### 🎯 RAG 전략
```
SQL 필터링 (지역 + 연령)
    ↓
벡터 검색 (필터된 범위 내)
    ↓
LLM 응답 생성
```

이 스키마로 **하이브리드 RAG 구현 완벽 지원**! 🚀

