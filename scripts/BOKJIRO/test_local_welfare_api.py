#!/usr/bin/env python3
"""
복지로 API 테스트 스크립트 (지자체복지서비스)

API 정보:
- API명: 한국사회보장정보원_지자체복지서비스
- 제공기관: 한국사회보장정보원
- 데이터 형식: XML / JSON
- 공공데이터포털: https://www.data.go.kr/data/15083323/fileData.do

테스트 목적:
- 지자체복지서비스 API 연결 테스트
- 응답 구조 분석
- 서울/경기 데이터 확인
- 중앙부처 API와 비교
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path
import json
import xml.etree.ElementTree as ET

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 환경 변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv가 설치되어 있지 않습니다.")
    print("실행: pip install python-dotenv")
    sys.exit(1)


class LocalWelfareAPITester:
    """
    지자체복지서비스 API 테스트 클래스
    
    API 정보:
    - 한국사회보장정보원_지자체복지서비스
    - 엔드포인트: https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations
    - 목록조회: /LcgvWelfarelist
    - 상세조회: /LcgvWelfaredetailed
    
    ** 목록조회 API 응답 필드 (LcgvWelfarelist) **
    - servId: 서비스 고유 ID (예: WLF00002780)
    - servNm: 서비스명
    - servDgst: 서비스 요약 설명
    - servDtlLink: 상세정보 링크 (복지로 사이트)
    - ctpvNm: 시도명 (예: 서울특별시)
    - sggNm: 시군구명 (예: 종로구)
    - bizChrDeptNm: 담당부서
    - aplyMtdNm: 신청방법 (예: 방문, 우편, 인터넷)
    - sprtCycNm: 지원주기 (예: 월, 연, 1회성)
    - srvPvsnNm: 서비스제공방법 (예: 현금지급, 현물)
    - lastModYmd: 최종수정일 (YYYYMMDD)
    - lifeNmArray: 생애주기 (예: 노년, 청년, 중장년)
    - intrsThemaNmArray: 관심주제 (예: 생활지원, 서민금융)
    - trgterIndvdlNmArray: 대상자 (예: 보훈대상자, 저소득)
    - inqNum: 조회수
    
    ** 상세조회 API 응답 필드 (LcgvWelfaredetailed) **
    
    [기본 정보 - 목록 API와 동일]
    - servId: 서비스 고유 ID (예: WLF00006199)
    - servNm: 서비스명 (예: 자립준비청년 생활보조수당 지원)
    - servDgst: 서비스 요약 설명 (100자 내외)
    - ctpvNm: 시도명 (예: 서울특별시)
    - sggNm: 시군구명 (예: 용산구)
    - bizChrDeptNm: 담당부서 (예: 서울특별시 용산구 생활지원국 아동청소년과)
    - lifeNmArray: 생애주기 (예: 청년)
    - intrsThemaNmArray: 관심주제 (예: 보호·돌봄, 서민금융)
    - sprtCycNm: 지원주기 (예: 월, 연, 1회성)
    - srvPvsnNm: 서비스제공방법 (예: 현금지급, 현물, 바우처)
    - aplyMtdNm: 신청방법 (예: 방문, 전화, 우편, E-mail)
    - lastModYmd: 최종수정일 (YYYYMMDD, 예: 20260115)
    - inqNum: 조회수 (예: 274)
    
    [시행 기간 - 상세 API에만 있음] ⭐
    - enfcBgngYmd: 시행시작일 (YYYYMMDD, 예: 20260101)
    - enfcEndYmd: 시행종료일 (YYYYMMDD, 예: 99991231 = 무기한)
    
    [상세 내용 - 상세 API에만 있음, RAG 핵심!] ⭐⭐⭐
    - sprtTrgtCn: 지원대상 상세 설명 (수백 자, 구체적 자격 조건)
      예) "○ 사업대상 : 용산구 거주 자립준비청년
          - 아동복지시설, 가정위탁 보호종료 아동 중..."
    
    - slctCritCn: 선정기준 상세 설명 (수백 자, 자격 요건)
      예) "아동복지시설, 가정위탁 보호종료 아동 중 보호종료일을 기준으로..."
    
    - alwServCn: 지원서비스 상세 내용 (금액, 기간, 방법 등)
      예) "- 지원내용 : 자립준비청년 1인당 월 20만원 지급
          - 지원기간 : 최대 60회..."
    
    - aplyMtdCn: 신청방법 상세 절차 (수백 자, 단계별 안내)
      예) "(1) 방문신청
           - 사전신청 : 보호종료 예정자(본인 또는...)
          (2) 우편 또는 팩스 신청..."
    
    [부가 정보 - 상세 API에만 있음] ⭐
    - inqplCtadrList[]: 문의처/연락처 목록 (배열)
      - wlfareInfoDtlCd: 정보구분코드 (예: 010)
      - wlfareInfoReldCn: 연락처 (예: 02-2199-7033)
      - wlfareInfoReldNm: 담당부서명 (예: 용산구청 아동청소년과)
    
    - baslawList[]: 근거법령 목록 (배열)
      - wlfareInfoDtlCd: 정보구분코드 (예: 030)
      - wlfareInfoReldNm: 법령명 (예: 서울특별시 용산구 보호대상아동...)
    
    - basfrmList[]: 서식/첨부파일 목록 (배열)
      - wlfareInfoDtlCd: 정보구분코드 (예: 040)
      - wlfareInfoReldCn: 다운로드 URL
      - wlfareInfoReldNm: 파일명 (예: 지급신청서.hwp, 조례.hwp)
    
    
    ═══════════════════════════════════════════════════════════
    📊 DB 저장 전략 제안
    ═══════════════════════════════════════════════════════════
    
    ┌─────────────────────────────────────────────────────────┐
    │ 방안 1: 목록 API만 사용 (비추천)                        │
    ├─────────────────────────────────────────────────────────┤
    │ [저장 필드]                                             │
    │ - 기본: servId, servNm, servDgst                       │
    │ - 지역: ctpvNm, sggNm                                   │
    │ - 메타: lifeNmArray, intrsThemaNmArray                 │
    │ - 링크: servDtlLink (복지로 사이트)                    │
    │                                                         │
    │ [장점] 빠른 수집 (357개 한번에)                         │
    │ [단점] ❌ RAG 품질 낮음 (상세 설명 없음)               │
    │       ❌ 사용자에게 불완전한 정보 제공                 │
    │       ❌ servDtlLink로 외부 사이트 의존                │
    └─────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────┐
    │ 방안 2: 상세 API 사용 (강력 추천!) ⭐⭐⭐              │
    ├─────────────────────────────────────────────────────────┤
    │ [저장 필드 - benefits 테이블]                           │
    │                                                         │
    │ 1) 기본 정보 (인덱싱용)                                │
    │   - serv_id (PK)                                       │
    │   - serv_nm                                            │
    │   - ctpv_nm, sgg_nm (지역 필터용)                      │
    │   - biz_chr_dept_nm                                    │
    │                                                         │
    │ 2) 기간 정보 (만료 체크용)                             │
    │   - enfc_bgng_ymd, enfc_end_ymd                        │
    │   - last_mod_ymd                                       │
    │                                                         │
    │ 3) 분류 메타 (필터링용)                                │
    │   - life_nm_array                                      │
    │   - intrs_thema_nm_array                               │
    │   - sprt_cyc_nm, srv_pvsn_nm, aply_mtd_nm              │
    │                                                         │
    │ 4) 핵심 상세 내용 (RAG/임베딩용) 🎯                    │
    │   - serv_dgst (요약)                                   │
    │   - sprt_trgt_cn (지원대상 상세) ← 임베딩 핵심!       │
    │   - slct_crit_cn (선정기준 상세) ← 임베딩 핵심!       │
    │   - alw_serv_cn (지원내용 상세) ← 임베딩 핵심!        │
    │   - aply_mtd_cn (신청방법 상세) ← 임베딩 핵심!        │
    │                                                         │
    │   💡 전략: 4개 필드를 결합해서 하나의 벡터 임베딩 생성 │
    │   → "content_for_embedding" 컬럼에 통합 저장          │
    │                                                         │
    │ 5) 부가 정보 (JSON 저장)                               │
    │   - contact_info (JSON: inqplCtadrList)                │
    │   - base_law_info (JSON: baslawList)                   │
    │   - attachments (JSON: basfrmList)                     │
    │                                                         │
    │ 6) 통계                                                 │
    │   - inq_num (조회수)                                   │
    │   - created_at, updated_at                             │
    │                                                         │
    │ [장점] ✅ RAG 품질 최고 (상세 설명으로 정확한 매칭)    │
    │       ✅ 완전한 정보 (지원대상, 선정기준, 금액 등)     │
    │       ✅ 첨부파일 다운로드 링크 제공                   │
    │       ✅ 문의처 정보로 사용자 편의성 향상              │
    │                                                         │
    │ [단점] ⚠️ 357번 API 호출 필요 (10-20분 소요)          │
    │       ⚠️ 구현 복잡도 증가                              │
    │                                                         │
    │ [수집 전략]                                             │
    │   1) 목록 API로 servId 리스트 수집 (357개)            │
    │   2) 각 servId로 상세 API 호출 (rate limit 고려)      │
    │   3) 상세 데이터를 benefits 테이블에 저장              │
    │   4) 임베딩 생성 (별도 프로세스)                       │
    └─────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────┐
    │ 방안 3: 하이브리드 (점진적, 복잡도 높음)                │
    ├─────────────────────────────────────────────────────────┤
    │ [단계 1] 목록 API로 기본 정보만 빠르게 저장            │
    │ [단계 2] 백그라운드에서 상세 API로 점진적 업데이트      │
    │                                                         │
    │ [장점] ⚙️ 빠른 초기 출시                               │
    │ [단점] ❌ 복잡한 구현 (상태 관리, 동기화 로직)         │
    │       ❌ 일관성 문제 (일부는 상세, 일부는 기본)        │
    └─────────────────────────────────────────────────────────┘
    
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    🎯 최종 권장: 방안 2 (상세 API 사용)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    이유:
    1. ✅ RAG 품질이 프로젝트 핵심 가치
       - 상세 설명 없이는 정확한 매칭 불가능
       - "65세 이상, 서울 거주" 같은 조건은 상세 설명에만 있음
    
    2. ✅ 357개는 관리 가능한 규모
       - 10-20분이면 수집 완료
       - 일일 1회만 실행하면 됨
    
    3. ✅ MVP 완성도 향상
       - 사용자에게 완전한 정보 제공
       - 신청방법, 문의처까지 안내 가능
    
    4. ✅ 향후 확장성
       - 경기도, 전국 확대 시에도 동일 로직 사용
       - 데이터 품질 일관성 유지
    """
    
    # 코드표 정의
    LIFE_CYCLE = {
        '001': '영유아',
        '002': '아동',
        '003': '청소년',
        '004': '청년',
        '005': '중장년',
        '006': '노년',
        '007': '임신·출산'
    }
    
    HOUSEHOLD_TYPE = {
        '010': '다문화·탈북민',
        '020': '다자녀',
        '030': '보훈대상자',
        '040': '장애인',
        '050': '저소득',
        '060': '한부모·조손'
    }
    
    INTEREST_THEME = {
        '010': '신체건강', '020': '정신건강', '030': '생활지원', '040': '주거',
        '050': '일자리', '060': '문화·여가', '070': '안전·위기', '080': '임신·출산',
        '090': '보육', '100': '교육', '110': '입양·위탁', '120': '보호·돌봄',
        '130': '서민금융', '140': '법률'
    }
    
    def __init__(self):
        # API 키
        #self.api_key = os.getenv('LOCAL_WELFARE_API_KEY') or os.getenv('BOKJIRO_API_KEY')
        self.api_key = '82b26bbf4c159c48aeb0570892efdce9d3438cf0acf78b2cffd055952bd2ddba'
        
        if not self.api_key:
            print("❌ 오류: API 키가 설정되지 않았습니다.")
            print("\n.env 파일에 다음 중 하나를 추가하세요:")
            print("LOCAL_WELFARE_API_KEY=발급받은_API_키")
            print("또는")
            print("BOKJIRO_API_KEY=발급받은_API_키")
            sys.exit(1)
        
        # API 키 일부만 출력 (보안)
        masked_key = self.api_key[:10] + '...' + self.api_key[-10:] if len(self.api_key) > 20 else '***'
        print(f"🔑 API 키 로드됨: {masked_key}")
        
        # API 엔드포인트
        self.base_url = 'https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations'
        self.list_endpoint = f"{self.base_url}/LcgvWelfarelist"
        self.detail_endpoint = f"{self.base_url}/LcgvWelfaredetailed"
    
    def test_list_api(self, page_no=1, num_of_rows=10, 
                     life_array='006', age=65, 
                     intrs_thema_array='010,020,030,040,120', ctpv_nm='서울특별시'):
        """
        지자체복지서비스 목록조회 API 테스트 (시니어 맞춤형)
        
        Args:
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 한 페이지 결과 수 (기본값: 10, 최대 500)
            life_array: 생애주기 (기본값: 006 노년) - 시니어 타겟
            age: 나이 (기본값: 65) - 시니어 기준
            intrs_thema_array: 관심주제 (기본값: 010,020,030,040,120)
                               - 010: 신체건강, 020: 정신건강, 030: 생활지원
                               - 040: 주거, 120: 보호·돌봄
            ctpv_nm: 시도명 (기본값: 서울특별시)
        
        Note:
            ** Phase 1 MVP 전략 **
            - 타겟: 시니어 (65세 이상)
            - 관심주제: 건강, 생활, 주거, 돌봄 핵심 주제만
            - 지역: 서울특별시만 (초기 출시)
        """
        print("\n" + "="*60)
        print("📋 지자체복지서비스 목록조회 API 테스트 (시니어 맞춤)")
        print("="*60)
        
        # URL 파라미터 구성
        params = [
            f"serviceKey={self.api_key}",
            f"pageNo={page_no}",
            f"numOfRows={num_of_rows}"
        ]
        
        # 시니어 필터 파라미터 추가
        if life_array:
            params.append(f"lifeArray={life_array}")
        if age:
            params.append(f"age={age}")
        if intrs_thema_array:
            params.append(f"intrsThemaArray={intrs_thema_array}")
        if ctpv_nm:
            params.append(f"ctpvNm={ctpv_nm}")
        
        request_url = f"{self.list_endpoint}?{'&'.join(params)}"
        
        print(f"\n🔗 요청 URL: {self.list_endpoint}")
        print(f"📄 파라미터:")
        print(f"   - serviceKey: (인증키)")
        print(f"   - pageNo: {page_no}")
        print(f"   - numOfRows: {num_of_rows}")
        if life_array:
            print(f"   - lifeArray: {life_array} ({self.LIFE_CYCLE.get(life_array, '알 수 없음')}) 🎯")
        if age:
            print(f"   - age: {age} (시니어 기준) 🎯")
        if intrs_thema_array:
            themes = [self.INTEREST_THEME.get(code, code) for code in intrs_thema_array.split(',')]
            print(f"   - intrsThemaArray: {intrs_thema_array} ({', '.join(themes)})")
        if ctpv_nm:
            print(f"   - ctpvNm: {ctpv_nm} (지역 필터)")
        
        try:
            # API 호출
            print("\n⏳ API 호출 중...")
            response = requests.get(request_url, timeout=30)
            
            # 상태 코드 확인
            if response.status_code == 200:
                print(f"✅ HTTP 상태 코드: {response.status_code}")
            else:
                print(f"❌ HTTP 상태 코드: {response.status_code}")
            
            if response.status_code != 200:
                print(f"\n❌ 오류 상세:")
                print(f"   HTTP 상태: {response.status_code}")
                print(f"   응답 내용: {response.text[:500]}")
                return None
            
            # XML 파싱
            print("\n📊 응답 데이터 분석 중...")
            
            # 디버깅: 원본 응답 일부 출력
            print(f"\n🔍 원본 응답 (처음 1000자):")
            print(response.text[:1000])
            print("\n" + "="*60)
            
            root = ET.fromstring(response.content)
            
            # 결과 분석
            self._analyze_response(root)
            
            return root
            
        except requests.exceptions.Timeout:
            print("❌ 오류: API 요청 시간 초과 (30초)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 오류: API 요청 실패 - {e}")
            return None
        except ET.ParseError as e:
            print(f"❌ 오류: XML 파싱 실패 - {e}")
            print(f"응답 내용: {response.text[:500]}")
            return None
    
    def _analyze_response(self, root):
        """XML 응답 분석"""
        
        print("\n" + "="*60)
        print("📊 응답 데이터 분석 결과")
        print("="*60)
        
        # 헤더 정보 추출 (구조 확인 필요)
        total_count = root.findtext('.//totalCount', '0')
        page_no = root.findtext('.//pageNo', '0')
        num_of_rows = root.findtext('.//numOfRows', '0')
        result_code = root.findtext('.//resultCode', '')
        result_msg = root.findtext('.//resultMessage', '')
        
        print("\n📋 헤더 정보:")
        if result_code:
            print(f"  - 결과 코드: {result_code}")
        if result_msg:
            print(f"  - 결과 메시지: {result_msg}")
        if total_count and total_count != '0':
            print(f"  - 전체 데이터 수: {total_count}개")
        if page_no and page_no != '0':
            print(f"  - 현재 페이지: {page_no}")
        if num_of_rows and num_of_rows != '0':
            print(f"  - 페이지당 결과 수: {num_of_rows}")
        
        # 데이터 항목 추출 (태그명 확인 필요)
        # 가능한 태그들: item, row, servList 등
        items = root.findall('.//servList') or root.findall('.//item') or root.findall('.//row')
        
        if not items:
            print("\n⚠️  데이터 항목이 없습니다.")
            print("   XML 구조를 확인하세요 (위 원본 응답 참고)")
            return
        
        print(f"\n📦 조회된 지자체 복지 서비스: {len(items)}개")
        print("\n" + "-"*60)
        
        # 샘플 데이터 출력
        for idx, item in enumerate(items[:3], 1):  # 처음 3개만
            print(f"\n[{idx}] 복지 서비스 정보:")
            
            # 모든 필드 출력
            for child in item:
                tag = child.tag
                text = child.text or '(없음)'
                # 너무 긴 텍스트는 잘라서 표시
                if len(text) > 100:
                    text = text[:100] + '...'
                print(f"  - {tag}: {text}")
            
            print("-"*60)
    
    def test_detail_api(self, serv_id):
        """
        지자체복지서비스 상세조회 API 테스트
        
        Args:
            serv_id: 서비스 고유 ID (예: WLF00002780, WLF00000138)
        
        Request Parameters:
            - serviceKey: 인증키 (필수)
            - servId: 서비스ID (필수)
        
        Note:
            목록조회에서 얻은 servId로 상세 정보 조회
            상세조회는 서비스 1개의 전체 상세 정보를 반환
        """
        print("\n" + "="*60)
        print("📋 지자체복지서비스 상세조회 API 테스트")
        print("="*60)
        
        # URL 구성
        request_url = f"{self.detail_endpoint}?serviceKey={self.api_key}&servId={serv_id}"
        
        print(f"\n🔗 요청 URL: {self.detail_endpoint}")
        print(f"📄 파라미터:")
        print(f"   - serviceKey: (인증키)")
        print(f"   - servId: {serv_id}")
        
        try:
            # API 호출
            print("\n⏳ API 호출 중...")
            response = requests.get(request_url, timeout=30)
            
            # 상태 코드 확인
            if response.status_code == 200:
                print(f"✅ HTTP 상태 코드: {response.status_code}")
            else:
                print(f"❌ HTTP 상태 코드: {response.status_code}")
                print(f"   응답 내용: {response.text[:500]}")
                return None
            
            # XML 파싱
            print("\n📊 응답 데이터 분석 중...")
            
            # 디버깅: 원본 응답 일부 출력
            print(f"\n🔍 원본 응답 (처음 2000자):")
            print(response.text[:2000])
            print("\n" + "="*60)
            
            root = ET.fromstring(response.content)
            
            # 결과 분석
            self._analyze_detail_response(root)
            
            return root
            
        except requests.exceptions.Timeout:
            print("❌ 오류: API 요청 시간 초과 (30초)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 오류: API 요청 실패 - {e}")
            return None
        except ET.ParseError as e:
            print(f"❌ 오류: XML 파싱 실패 - {e}")
            print(f"응답 내용: {response.text[:500]}")
            return None
    
    def _analyze_detail_response(self, root):
        """상세조회 XML 응답 분석"""
        
        print("\n" + "="*60)
        print("📊 상세조회 응답 데이터 분석 결과")
        print("="*60)
        
        # 헤더 정보
        result_code = root.findtext('resultCode', '')
        result_msg = root.findtext('resultMessage', '')
        
        print("\n📋 헤더 정보:")
        if result_code:
            print(f"  - 결과 코드: {result_code}")
        if result_msg:
            print(f"  - 결과 메시지: {result_msg}")
        
        # 상세 정보 필드 (루트 태그 자체가 상세 데이터 컨테이너)
        print(f"\n📦 상세 정보 필드 ({len(list(root))}개):")
        print("\n" + "-"*60)
        
        # 기본 정보
        print("\n[기본 정보]")
        print(f"  - servId: {root.findtext('servId', '(없음)')}")
        print(f"  - servNm: {root.findtext('servNm', '(없음)')}")
        print(f"  - ctpvNm: {root.findtext('ctpvNm', '(없음)')}")
        print(f"  - sggNm: {root.findtext('sggNm', '(없음)')}")
        print(f"  - bizChrDeptNm: {root.findtext('bizChrDeptNm', '(없음)')}")
        
        # 기간 정보
        print("\n[시행 기간]")
        print(f"  - enfcBgngYmd: {root.findtext('enfcBgngYmd', '(없음)')}")
        print(f"  - enfcEndYmd: {root.findtext('enfcEndYmd', '(없음)')}")
        print(f"  - lastModYmd: {root.findtext('lastModYmd', '(없음)')}")
        
        # 상세 내용 (목록 API에는 없는 필드들)
        print("\n[상세 내용] ⭐")
        
        serv_dgst = root.findtext('servDgst', '')
        if serv_dgst:
            print(f"  - servDgst (요약): {serv_dgst[:100]}...")
        
        sprt_trgt_cn = root.findtext('sprtTrgtCn', '')
        if sprt_trgt_cn:
            print(f"  - sprtTrgtCn (지원대상): {sprt_trgt_cn[:100]}...")
        
        slct_crit_cn = root.findtext('slctCritCn', '')
        if slct_crit_cn:
            print(f"  - slctCritCn (선정기준): {slct_crit_cn[:100]}...")
        
        alw_serv_cn = root.findtext('alwServCn', '')
        if alw_serv_cn:
            print(f"  - alwServCn (지원내용): {alw_serv_cn[:100]}...")
        
        aply_mtd_cn = root.findtext('aplyMtdCn', '')
        if aply_mtd_cn:
            print(f"  - aplyMtdCn (신청방법): {aply_mtd_cn[:100]}...")
        
        # 메타 정보
        print("\n[메타 정보]")
        print(f"  - lifeNmArray: {root.findtext('lifeNmArray', '(없음)')}")
        print(f"  - intrsThemaNmArray: {root.findtext('intrsThemaNmArray', '(없음)')}")
        print(f"  - sprtCycNm: {root.findtext('sprtCycNm', '(없음)')}")
        print(f"  - srvPvsnNm: {root.findtext('srvPvsnNm', '(없음)')}")
        print(f"  - aplyMtdNm: {root.findtext('aplyMtdNm', '(없음)')}")
        print(f"  - inqNum: {root.findtext('inqNum', '(없음)')}")
        
        # 부가 정보 (리스트)
        print("\n[부가 정보]")
        
        inqpl_list = root.findall('inqplCtadrList')
        if inqpl_list:
            print(f"  - 문의처/연락처: {len(inqpl_list)}개")
            for idx, item in enumerate(inqpl_list[:2], 1):
                name = item.findtext('wlfareInfoReldNm', '')
                contact = item.findtext('wlfareInfoReldCn', '')
                print(f"    [{idx}] {name}: {contact}")
        
        baslaw_list = root.findall('baslawList')
        if baslaw_list:
            print(f"  - 근거법령: {len(baslaw_list)}개")
            for idx, item in enumerate(baslaw_list[:2], 1):
                name = item.findtext('wlfareInfoReldNm', '')
                print(f"    [{idx}] {name}")
        
        basfrm_list = root.findall('basfrmList')
        if basfrm_list:
            print(f"  - 서식/첨부파일: {len(basfrm_list)}개")
            for idx, item in enumerate(basfrm_list[:2], 1):
                name = item.findtext('wlfareInfoReldNm', '')
                url = item.findtext('wlfareInfoReldCn', '')
                print(f"    [{idx}] {name}")
                if url and len(url) < 100:
                    print(f"        URL: {url}")
    
    def save_sample_response(self, root, filename='local_welfare_sample_response.xml'):
        """샘플 응답 저장"""
        output_dir = project_root / 'scripts' / 'BOKJIRO' / 'samples'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        print(f"\n💾 샘플 응답 저장됨: {output_path}")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🔬 지자체복지서비스 API 테스트 도구")
    print("="*60)
    print(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 테스터 초기화
    tester = LocalWelfareAPITester()
    
    # 필터 강도별 테스트
    print("\n" + "="*80)
    print("🔍 지자체 복지 API 데이터 범위 확인 테스트")
    print("="*80)
    
    # 테스트 1: 관심주제 필터 제거 (서울 시니어 전체)
    print("\n[테스트 1] 서울 시니어 전체 (관심주제 필터 제거)")
    print("-" * 80)
    root1 = tester.test_list_api(
        page_no=1,
        num_of_rows=50,
        life_array='006',
        age=65,
        intrs_thema_array=None,  # 관심주제 필터 제거
        ctpv_nm='서울특별시'
    )
    
    count1 = '0'
    items1 = 0
    if root1 is not None:
        count1 = root1.findtext('.//totalCount', '0')
        items1 = len(root1.findall('.//servList'))
        print(f"📊 전체: {count1}개 | 이번 페이지: {items1}개")
        tester.save_sample_response(root1, 'test1_seoul_senior_all.xml')
    
    # 테스트 2: 생애주기 필터도 제거 (서울 전체 연령)
    print("\n[테스트 2] 서울 전체 연령 (생애주기 필터도 제거)")
    print("-" * 80)
    root2 = tester.test_list_api(
        page_no=1,
        num_of_rows=50,
        life_array=None,  # 생애주기 필터 제거
        age=None,         # 나이 필터 제거
        intrs_thema_array=None,
        ctpv_nm='서울특별시'
    )
    
    count2 = '0'
    items2 = 0
    if root2 is not None:
        count2 = root2.findtext('.//totalCount', '0')
        items2 = len(root2.findall('.//servList'))
        print(f"📊 전체: {count2}개 | 이번 페이지: {items2}개")
        tester.save_sample_response(root2, 'test2_seoul_all_ages.xml')
    
    # 테스트 3: 지역 필터도 제거 (전국 전체)
    print("\n[테스트 3] 전국 전체 (모든 필터 제거)")
    print("-" * 80)
    root3 = tester.test_list_api(
        page_no=1,
        num_of_rows=50,
        life_array=None,
        age=None,
        intrs_thema_array=None,
        ctpv_nm=None  # 지역 필터 제거
    )
    
    count3 = '0'
    items3 = 0
    if root3 is not None:
        count3 = root3.findtext('.//totalCount', '0')
        items3 = len(root3.findall('.//servList'))
        print(f"📊 전체: {count3}개 | 이번 페이지: {items3}개")
        tester.save_sample_response(root3, 'test3_nationwide_all.xml')
    
    # 결과 요약
    print("\n" + "="*80)
    print("✅ 테스트 완료 - 데이터 범위 확인")
    print("="*80)
    print("\n📊 결과 요약:")
    print(f"  [1] 서울 시니어 전체:")
    print(f"      - 전체 건수: {count1}개")
    print(f"      - 조회된 건수: {items1}개")
    print(f"  [2] 서울 전체 연령:")
    print(f"      - 전체 건수: {count2}개")
    print(f"      - 조회된 건수: {items2}개")
    print(f"  [3] 전국 전체:")
    print(f"      - 전체 건수: {count3}개")
    print(f"      - 조회된 건수: {items3}개")
    
    print("\n💡 분석:")
    total = int(count3) if count3.isdigit() else 0
    if total < 100:
        print(f"  ⚠️  지자체 API는 데이터가 제한적입니다! (전국 전체: {total}개)")
        print("  → 중앙부처 API 또는 다른 API 추가 연동 검토 필요")
    elif total < 1000:
        print(f"  ⚙️  데이터가 보통 수준입니다. (전국 전체: {total}개)")
        print("  → 추가 API 연동으로 데이터 보강 권장")
    else:
        print(f"  ✅ 충분한 데이터가 있습니다! (전국 전체: {total}개)")
    
    # 페이징 안내
    if items3 == 50 and int(count3) > 50:
        print(f"\n⚠️  주의: 전체 {count3}개 중 50개만 조회됨")
        print("  → 전체 데이터 수집 시 페이징 처리 필요!")
    
    # 상세조회 API 테스트
    print("\n" + "="*80)
    print("🔍 상세조회 API 테스트")
    print("="*80)
    
    if root2 is not None:
        # 서울 전체 연령 목록에서 첫 번째 서비스 ID 추출
        serv_list = root2.findall('.//servList')
        if serv_list:
            first_serv_id = serv_list[0].findtext('servId')
            if first_serv_id:
                print(f"\n📋 테스트할 서비스 ID: {first_serv_id}")
                
                detail_root = tester.test_detail_api(first_serv_id)
                
                if detail_root is not None:
                    tester.save_sample_response(detail_root, 'detail_sample.xml')
            else:
                print("\n⚠️  서비스 ID를 찾을 수 없습니다.")
        else:
            print("\n⚠️  목록 데이터가 없어 상세조회를 테스트할 수 없습니다.")
    
    # 최종 요약 및 비교 분석
    print("\n" + "="*80)
    print("✅ 모든 테스트 완료!")
    print("="*80)
    
    print("\n" + "="*80)
    print("📊 목록 API vs 상세 API 비교 분석")
    print("="*80)
    
    print("\n[목록조회 API (LcgvWelfarelist)]")
    print("  ✅ 장점:")
    print("     - 한 번에 여러 서비스 조회 가능 (페이징)")
    print("     - 빠른 응답 속도")
    print("     - 기본 정보 제공 (요약, 지역, 신청방법 등)")
    print("  ⚠️  단점:")
    print("     - 상세 설명 부족")
    print("     - 지원대상/선정기준 상세 내용 없음")
    print("     - 첨부파일/서식 정보 없음")
    
    print("\n[상세조회 API (LcgvWelfaredetailed)]")
    print("  ✅ 장점:")
    print("     - 완전한 정보 제공")
    print("     - 상세 설명 (지원대상, 선정기준, 신청방법 등)")
    print("     - 문의처, 근거법령, 첨부파일 정보")
    print("     - 시행기간 정보")
    print("  ⚠️  단점:")
    print("     - 서비스별로 개별 호출 필요")
    print("     - API 호출 횟수 증가")
    
    print("\n💡 저장 전략 권장:")
    print("  ┌─────────────────────────────────────────┐")
    print("  │ 옵션 A: 목록 API만 사용 (빠른 구현)    │")
    print("  │  - 목록 API로 357개 수집               │")
    print("  │  - 기본 정보만 DB 저장                 │")
    print("  │  - servDtlLink로 복지로 사이트 연결   │")
    print("  │  ⚙️  간단하지만 정보 부족              │")
    print("  └─────────────────────────────────────────┘")
    print("  ┌─────────────────────────────────────────┐")
    print("  │ 옵션 B: 목록 + 상세 API 조합 ⭐ 추천  │")
    print("  │  1) 목록 API로 servId 목록 수집        │")
    print("  │  2) 각 servId로 상세 API 호출          │")
    print("  │  3) 상세 정보를 DB에 저장              │")
    print("  │  ✅ 완전한 정보, RAG 품질 향상         │")
    print("  │  ⚠️  357번 API 호출 필요 (시간 소요)   │")
    print("  └─────────────────────────────────────────┘")
    print("  ┌─────────────────────────────────────────┐")
    print("  │ 옵션 C: 하이브리드 (점진적)             │")
    print("  │  1) 초기: 목록 API로 빠르게 수집       │")
    print("  │  2) 배경: 상세 API로 점진적 업데이트   │")
    print("  │  ⚙️  초기 출시 빠르고 나중에 보강      │")
    print("  └─────────────────────────────────────────┘")
    
    print("\n📝 다음 단계:")
    print("1. XML 파일들 확인")
    print("   - test2_seoul_all_ages.xml (목록조회)")
    print("   - detail_sample.xml (상세조회)")
    print("2. 저장 전략 결정 (A, B, C 중 선택)")
    print("3. benefits 테이블 스키마 확정")
    print("4. 데이터 수집 스크립트 구현")
    
    # 테스트 실패 체크
    if root1 is None and root2 is None and root3 is None:
        print("\n" + "="*80)
        print("❌ 모든 테스트 실패!")
        print("="*80)
        print("\n🔧 해결 방법:")
        print("1. API 키가 올바른지 확인")
        print("2. 활용신청이 승인되었는지 확인")
        print("3. 네트워크 연결 확인")


if __name__ == '__main__':
    main()

