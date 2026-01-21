#!/usr/bin/env python3
"""
복지로 API 테스트 스크립트 (중앙부처 복지서비스)

✅ 연동 성공!
- API: 한국사회보장정보원_중앙부처복지서비스
- 엔드포인트: NationalWelfareInformationsV001
- 목록조회: /NationalWelfarelistV001
- 상세조회: /NationalWelfaredetailedV001

성공한 파라미터 패턴:
- callTp=L (필수!)
- 필터: srchKeyCode, lifeArray, trgterIndvdlArray, intrsThemaArray
- 정렬: orderBy=popular
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path
import json
import xml.etree.ElementTree as ET

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent  # scripts의 부모 = ttok-sun-i
sys.path.insert(0, str(project_root))

# 환경 변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv가 설치되어 있지 않습니다.")
    print("실행: pip install python-dotenv")
    sys.exit(1)


class BokjiroAPITester:
    """
    복지로 API 테스트 클래스 (중앙부처복지서비스)
    
    API 정보:
    - 한국사회보장정보원_중앙부처복지서비스
    - 엔드포인트: https://apis.data.go.kr/B554287/NationalWelfareInformationsV001
    - 목록조회: /NationalWelfarelistV001
    - 상세조회: /NationalWelfaredetailedV001
    
    ** 목록조회 API 응답 필드 (NationalWelfarelistV001) **
    - servId: 서비스 고유 ID (예: WLF00001188)
    - servNm: 서비스명 (예: 산모·신생아 건강관리 지원사업)
    - servDgst: 서비스 요약 설명
    - servDtlLink: 상세정보 링크 (복지로 사이트)
    - jurMnofNm: 주관부처명 (예: 보건복지부) ⭐ 중앙부처 API 고유!
    - jurOrgNm: 주관기관명 (예: 출산정책과) ⭐ 중앙부처 API 고유!
    - rprsCtadr: 대표연락처 (예: 129) ⭐ 중앙부처 API 고유!
    - onapPsbltYn: 온라인신청가능여부 (Y/N) ⭐ 중앙부처 API 고유!
    - svcfrstRegTs: 최초등록일 (YYYYMMDD)
    - lifeArray: 생애주기 (예: 영유아,임신 · 출산)
    - intrsThemaArray: 관심주제 (예: 신체건강,임신·출산)
    - trgterIndvdlArray: 대상자 (예: 다자녀,장애인,저소득)
    - sprtCycNm: 지원주기 (예: 1회성, 수시, 월)
    - srvPvsnNm: 서비스제공방법 (예: 전자바우처, 현금지급)
    - inqNum: 조회수
    
    ** 상세조회 API 응답 필드 (NationalWelfaredetailedV001) **
    
    [기본 정보 - 목록 API와 동일]
    - servId, servNm, lifeArray, intrsThemaArray, trgterIndvdlArray
    - sprtCycNm, srvPvsnNm
    - jurMnofNm: 주관부처 (예: 보건복지부 자활정책과)
    - rprsCtadr: 대표연락처 (예: 129)
    
    [상세 내용 - 상세 API에만 있음, RAG 핵심!] ⭐⭐⭐
    - wlfareInfoOutlCn: 복지정보 개요 (서비스 전체 설명)
    - tgtrDtlCn: 지원대상 상세 설명 (수백~수천 자)
    - slctCritCn: 선정기준 상세 설명 (자격 요건 상세)
    - alwServCn: 지원서비스 상세 내용 (금액, 기간, 방법)
    - crtrYr: 기준연도 (예: 2025)
    
    [부가 정보 - 상세 API에만 있음] ⭐
    - applmetList[]: 신청방법 목록
      - servSeCode: 서비스구분코드 (070 등)
    
    - inqplCtadrList[]: 문의처/연락처 목록
      - servSeCode: 서비스구분코드 (010)
      - servSeDetailLink: 연락처 (예: 129)
      - servSeDetailNm: 담당기관명 (예: 보건복지상담센터)
    
    - inqplHmpgReldList[]: 관련 홈페이지 목록
      - servSeCode: 서비스구분코드 (020)
      - servSeDetailLink: URL
      - servSeDetailNm: 사이트명
    
    - basfrmList[]: 서식/첨부파일 목록
      - servSeCode: 서비스구분코드 (040)
      - servSeDetailLink: 다운로드 URL
      - servSeDetailNm: 파일명 (예: 2025년 자활사업 안내.pdf)
    
    - baslawList[]: 근거법령 목록
      - servSeCode: 서비스구분코드 (030)
      - servSeDetailNm: 법령명
    
    ⚠️ 중앙부처 API는 지역 정보 없음!
    - ctpvNm, sggNm 필드 없음 (전국 단위 서비스)
    """
    
    def __init__(self):
        #self.api_key = os.getenv('BOKJIRO_API_KEY')
        self.api_key = '82b26bbf4c159c48aeb0570892efdce9d3438cf0acf78b2cffd055952bd2ddba'
        self.base_url = 'https://apis.data.go.kr/B554287/NationalWelfareInformationsV001'  # 중앙부처
        
        if not self.api_key:
            print("❌ 오류: BOKJIRO_API_KEY 환경변수가 설정되지 않았습니다.")
            print("\n.env 파일에 다음을 추가하세요:")
            print("BOKJIRO_API_KEY=발급받은_API_키")
            sys.exit(1)
        
        # API 키 일부만 출력 (보안)
        masked_key = self.api_key[:10] + '...' + self.api_key[-10:] if len(self.api_key) > 20 else '***'
        print(f"🔑 API 키 로드됨: {masked_key}")
    
    def test_list_api(self, page_no=1, num_of_rows=10, 
                     srch_key_code='001', life_array=None, 
                     trgter_indvdl_array=None, intrs_thema_array=None,
                     age=None, onap_psblt_yn=None, order_by='popular'):
        """
        중앙부처 복지서비스 목록조회 API 테스트
        
        Args:
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 한 페이지 결과 수 (기본값: 10, 최대 1000)
            srch_key_code: 검색키코드 (001:제목, 002:내용, 003:제목+내용)
            life_array: 생애주기 코드 (예: 007=임신·출산)
            trgter_indvdl_array: 대상자 코드 (예: 050=저소득)
            intrs_thema_array: 관심주제 코드 (예: 010=신체건강)
            age: 나이
            onap_psblt_yn: 온라인신청가능여부 (Y/N)
            order_by: 정렬 (popular=인기순, date=최신순)
        
        Note:
            callTp=L 파라미터가 필수!
            성공 URL: callTp=L&srchKeyCode=001&...
        """
        print("\n" + "="*60)
        print("📋 중앙부처 복지서비스 목록조회 API 테스트")
        print("="*60)
        
        # API 엔드포인트
        endpoint = f"{self.base_url}/NationalWelfarelistV001"
        
        # URL 파라미터 구성
        params = [
            f"serviceKey={self.api_key}",
            "callTp=L",  # 필수!
            f"pageNo={page_no}",
            f"numOfRows={num_of_rows}",
            f"srchKeyCode={srch_key_code}"
        ]
        
        # 선택적 필터 파라미터
        if life_array:
            params.append(f"lifeArray={life_array}")
        if trgter_indvdl_array:
            params.append(f"trgterIndvdlArray={trgter_indvdl_array}")
        if intrs_thema_array:
            params.append(f"intrsThemaArray={intrs_thema_array}")
        if age:
            params.append(f"age={age}")
        if onap_psblt_yn:
            params.append(f"onapPsbltYn={onap_psblt_yn}")
        if order_by:
            params.append(f"orderBy={order_by}")
        
        request_url = f"{endpoint}?{'&'.join(params)}"
        
        print(f"\n🔗 요청 URL: {endpoint}")
        print(f"📄 파라미터:")
        print(f"   - serviceKey: (인증키)")
        print(f"   - callTp: L (목록조회)")
        print(f"   - pageNo: {page_no}")
        print(f"   - numOfRows: {num_of_rows}")
        print(f"   - srchKeyCode: {srch_key_code}")
        if life_array:
            print(f"   - lifeArray: {life_array}")
        if trgter_indvdl_array:
            print(f"   - trgterIndvdlArray: {trgter_indvdl_array}")
        if intrs_thema_array:
            print(f"   - intrsThemaArray: {intrs_thema_array}")
        if age:
            print(f"   - age: {age}")
        if onap_psblt_yn:
            print(f"   - onapPsbltYn: {onap_psblt_yn}")
        if order_by:
            print(f"   - orderBy: {order_by}")
        
        try:
            # API 호출
            print("\n⏳ API 호출 중...")
            response = requests.get(request_url, timeout=10)
            
            # 상태 코드 확인
            if response.status_code == 200:
                print(f"✅ HTTP 상태 코드: {response.status_code}")
            else:
                print(f"❌ HTTP 상태 코드: {response.status_code}")
            
            if response.status_code != 200:
                print(f"\n❌ 오류 상세:")
                print(f"   HTTP 상태: {response.status_code}")
                print(f"   응답 내용: {response.text[:500]}")
                
                # 403 에러 특별 처리
                if response.status_code == 403:
                    print("\n" + "="*60)
                    print("🔧 403 Forbidden 에러 해결 방법")
                    print("="*60)
                    print("\n1️⃣ 활용신청 상태 확인 (가장 중요!)")
                    print("   https://www.data.go.kr → 로그인")
                    print("   → 마이페이지 → 오픈API → 개발계정")
                    print("   → '한국사회보장정보원_중앙부처복지서비스' 상태 확인")
                    print("   → '승인' 상태인지 확인!")
                    print("\n2️⃣ 올바른 API 키 사용")
                    print("   ⚠️  '일반 인증키 (Encoding)' 사용 (위쪽 키)")
                    print("   ❌ '일반 인증키 (Decoding)' 사용하면 403 에러!")
                    print("\n3️⃣ .env 파일 업데이트")
                    print("   BOKJIRO_API_KEY=일반_인증키_Encoding_버전")
                    print("\n💡 신청 후 승인까지 1~2일 소요될 수 있습니다.")
                
                return None
            
            # XML 파싱
            print("\n📊 응답 데이터 분석 중...")
            
            # 디버깅: 원본 응답 일부 출력
            print(f"\n🔍 원본 응답 (처음 500자):")
            print(response.text[:500])
            print("\n" + "="*60)
            
            root = ET.fromstring(response.content)
            
            # 결과 분석
            self._analyze_response(root)
            
            return root
            
        except requests.exceptions.Timeout:
            print("❌ 오류: API 요청 시간 초과 (10초)")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 오류: API 요청 실패 - {e}")
            return None
        except ET.ParseError as e:
            print(f"❌ 오류: XML 파싱 실패 - {e}")
            print(f"응답 내용: {response.text[:500]}")
            return None
    
    def _analyze_response(self, root):
        """XML 응답 분석 (중앙부처 API)"""
        
        print("\n" + "="*60)
        print("📊 응답 데이터 분석 결과")
        print("="*60)
        
        # 헤더 정보 추출 (루트 직속)
        result_code = root.findtext('resultCode', '')
        result_msg = root.findtext('resultMessage', '')
        total_count = root.findtext('totalCount', '0')
        page_no = root.findtext('pageNo', '0')
        num_of_rows = root.findtext('numOfRows', '0')
        
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
        
        # 데이터 항목 추출 (servList 태그)
        items = root.findall('servList')
        
        if not items:
            print("\n⚠️  데이터 항목이 없습니다.")
            return
        
        print(f"\n📦 조회된 중앙부처 복지 서비스: {len(items)}개")
        print("\n" + "-"*60)
        
        # 샘플 데이터 출력 (처음 3개)
        for idx, item in enumerate(items[:3], 1):
            print(f"\n[{idx}] 복지 서비스 정보:")
            
            # 기본 정보
            print("  [기본 정보]")
            print(f"    - servId: {item.findtext('servId', '(없음)')}")
            print(f"    - servNm: {item.findtext('servNm', '(없음)')}")
            
            # 중앙부처 고유 정보 ⭐
            print("  [중앙부처 정보] ⭐")
            print(f"    - jurMnofNm (주관부처): {item.findtext('jurMnofNm', '(없음)')}")
            print(f"    - jurOrgNm (주관기관): {item.findtext('jurOrgNm', '(없음)')}")
            print(f"    - rprsCtadr (대표연락처): {item.findtext('rprsCtadr', '(없음)')}")
            print(f"    - onapPsbltYn (온라인신청): {item.findtext('onapPsbltYn', '(없음)')}")
            
            # 요약 정보
            serv_dgst = item.findtext('servDgst', '')
            if serv_dgst:
                print(f"  [서비스 요약]")
                print(f"    {serv_dgst[:100]}...")
            
            # 메타 정보
            print("  [메타 정보]")
            print(f"    - lifeArray: {item.findtext('lifeArray', '(없음)')}")
            print(f"    - intrsThemaArray: {item.findtext('intrsThemaArray', '(없음)')}")
            print(f"    - trgterIndvdlArray: {item.findtext('trgterIndvdlArray', '(없음)')}")
            print(f"    - sprtCycNm: {item.findtext('sprtCycNm', '(없음)')}")
            print(f"    - srvPvsnNm: {item.findtext('srvPvsnNm', '(없음)')}")
            print(f"    - inqNum: {item.findtext('inqNum', '0')}")
            
            print("-"*60)
        
        # 통계 분석
        print("\n" + "="*60)
        print("📊 중앙부처 API 특성 분석")
        print("="*60)
        
        # 주관부처 분포
        dept_stats = {}
        for item in items:
            dept = item.findtext('jurMnofNm', '기타')
            dept_stats[dept] = dept_stats.get(dept, 0) + 1
        
        print("\n📍 주관부처별 분포:")
        for dept, count in sorted(dept_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {dept}: {count}개")
        
        # 온라인신청 가능 여부
        online_count = sum(1 for item in items if item.findtext('onapPsbltYn') == 'Y')
        print(f"\n💻 온라인신청 가능: {online_count}/{len(items)}개")
        
        # 결론
        print("\n" + "="*60)
        print("💡 중앙부처 API 특징")
        print("="*60)
        print("✅ 전국 단위 복지 서비스")
        print("✅ 주관부처/기관 정보 제공")
        print("✅ 대표연락처 제공")
        print("✅ 온라인신청 가능 여부 표시")
        print("⚠️  지역 정보 없음 (ctpvNm, sggNm)")
        print("\n→ 지자체 API와 함께 사용하여 통합 DB 구축 필요!")
    
    def save_sample_response(self, root, filename='bokjiro_sample_response.xml'):
        """샘플 응답 저장"""
        output_dir = project_root / 'scripts' / 'samples'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        print(f"\n💾 샘플 응답 저장됨: {output_path}")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("🔬 중앙부처 복지서비스 API 테스트 도구")
    print("="*60)
    print(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 테스터 초기화
    tester = BokjiroAPITester()
    
    # 성공한 파라미터로 테스트
    print("\n[테스트] 중앙부처 복지서비스 목록조회 (필터 없음)")
    root = tester.test_list_api(
        page_no=1,
        num_of_rows=20,  # 더 많이 조회
        srch_key_code='001',  # 제목 검색
        life_array=None,  # 전체 생애주기
        trgter_indvdl_array=None,  # 전체 대상자
        intrs_thema_array=None,  # 전체 관심주제
        age=None,  # 전체 연령
        onap_psblt_yn=None,  # 온라인신청 필터 없음
        order_by='popular'  # 인기순
    )
    
    if root is not None:
        total_count = root.findtext('totalCount', '0')
        
        # 샘플 응답 저장
        tester.save_sample_response(root, 'national_welfare_sample.xml')
        
        print("\n" + "="*80)
        print("✅ 테스트 완료!")
        print("="*80)
        print(f"\n📊 중앙부처 복지 서비스: 총 {total_count}개")
        print(f"📁 샘플 저장: scripts/samples/national_welfare_sample.xml")
        
        print("\n📝 다음 단계:")
        print("1. 상세조회 API 테스트")
        print("2. 지자체 API와 필드 비교 → 통합 스키마 설계")
        print("3. DB 저장 로직 구현")
    else:
        print("\n" + "="*80)
        print("❌ 테스트 실패")
        print("="*80)
        print("\n🔧 해결 방법:")
        print("1. API 키가 올바른지 확인")
        print("2. 활용신청이 승인되었는지 확인")
        print("3. 네트워크 연결 확인")


if __name__ == '__main__':
    main()

