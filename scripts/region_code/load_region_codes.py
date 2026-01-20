#!/usr/bin/env python3
"""
행정안전부 법정동코드 API를 통해 전국 행정구역 데이터를 수집하여
Supabase regions 테이블에 적재하는 스크립트

사용법:
    python scripts/load_region_codes.py

필요한 환경변수:
    - SUPABASE_URL: Supabase 프로젝트 URL
    - SUPABASE_SERVICE_KEY: Supabase Service Role Key
    - MOIS_API_KEY: 행정안전부 표준코드관리시스템 API 키
"""

import os
import sys
import requests
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client, Client
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


# ============================================
# 환경 변수 설정
# ============================================

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ladqubaousblucmrqcrr.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhZHF1YmFvdXNibHVjbXJxY3JyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODgyNDI1MiwiZXhwIjoyMDg0NDAwMjUyfQ.YZfsje16TIRzEKI9N6WgH-49XH-VPqLJwqwp4LlwhxY'
)
MOIS_API_KEY = os.getenv('MOIS_API_KEY', '')  # 행정안전부 API 키
MOIS_API_URL = os.getenv('MOIS_API_URL', 'http://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList')  # 행정안전부 API URL


# ============================================
# Supabase 클라이언트 초기화
# ============================================

def init_supabase() -> Client:
    """Supabase 클라이언트 초기화"""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ============================================
# 스키마 확인
# ============================================

def check_schema(supabase: Client) -> bool:
    """regions 테이블이 존재하는지 확인"""
    try:
        result = supabase.table('regions').select('id').limit(1).execute()
        print("✅ regions 테이블 확인 완료")
        return True
    except Exception as e:
        print(f"❌ regions 테이블을 찾을 수 없습니다: {e}")
        print("\n📋 supabase/schema.sql 파일을 Supabase SQL Editor에서 먼저 실행해주세요.")
        return False


# ============================================
# 행정안전부 API 호출
# ============================================

def fetch_region_codes_from_api(api_key: str, api_url: str) -> List[Dict]:
    """
    행정안전부 표준지역코드 API를 통해 법정동코드 조회
    
    Note: API 키가 없으면 샘플 데이터를 반환합니다.
    실제 사용 시에는 공공데이터포털(https://www.data.go.kr)에서 API 키를 발급받아야 합니다.
    """
    if not api_key:
        print("\n⚠️  행정안전부 API 키가 설정되지 않았습니다.")
        print("샘플 데이터로 테스트를 진행합니다.")
        print("\n실제 사용을 위해서는 다음 단계를 따르세요:")
        print("1. https://www.data.go.kr 방문")
        print("2. 회원가입 및 '행정표준코드관리' API 키 발급")
        print("3. .env 파일에 MOIS_API_KEY 설정")
        return get_sample_region_data()
    
    print(f"🔍 디버깅: API_KEY length={len(api_key)}, API_URL={api_url[:50]}...")
    
    try:
        all_regions = []
        page_no = 1
        max_rows_per_page = 1000  # API 최대 제한 (에러 코드 336)
        
        while True:
            print(f"\n📡 API 호출: {api_url} (페이지 {page_no})")
            
            # 🔧 중요: requests params dict 사용 시 인코딩 문제 발생
            # URL을 직접 구성하면 정상 작동!
            request_url = f"{api_url}?ServiceKey={api_key}&type=xml&pageNo={page_no}&numOfRows={max_rows_per_page}&flag=Y"
            
            print(f"  🔧 파라미터: flag=Y, type=xml, pageNo={page_no}, numOfRows={max_rows_per_page}")
            
            response = requests.get(request_url, timeout=120)
            
            print(f"  ✅ API 응답 수신 완료 ({len(response.content)} bytes)")
            
            # XML 파싱
            root = ET.fromstring(response.content)
            
            # 행정안전부 API 응답 구조: <StanReginCd><head><RESULT>...</RESULT></head><row>...</row></StanReginCd>
            
            # resultCode 확인 (INFO-0 = 정상)
            result_code = root.findtext('.//resultCode', '')
            if result_code != 'INFO-0':
                result_msg = root.findtext('.//resultMsg', 'Unknown error')
                print(f"  ❌ API 오류: {result_msg} (코드: {result_code})")
                print(f"\n📄 원본 응답:")
                print(response.text[:500])
                if page_no == 1:
                    print("\n샘플 데이터로 대체합니다.")
                    return get_sample_region_data()
                else:
                    print(f"\n⚠️  {page_no}페이지에서 오류 발생. 여기까지 수집한 {len(all_regions)}건 반환")
                    break
            
            # 전체 건수 확인 (첫 페이지에서만)
            if page_no == 1:
                total_count = root.findtext('.//totalCount', '0')
                print(f"  📊 전체 데이터: {total_count}건")
            
            # row 파싱 (API 문서에 따라 <row> 태그 사용)
            page_regions = []
            for row in root.findall('.//row'):
                region_cd = row.findtext('region_cd', '').strip()
                locatadd_nm = row.findtext('locatadd_nm', '').strip()  # 지역주소명
                
                # region_cd를 그대로 사용 (이미 10자리 코드)
                if region_cd and locatadd_nm:
                    page_regions.append({
                        'code': region_cd,
                        'name': locatadd_nm
                    })
            
            print(f"  📥 {len(page_regions)}건 수집")
            all_regions.extend(page_regions)
            
            # 더 이상 데이터가 없으면 종료
            if len(page_regions) < max_rows_per_page:
                print(f"\n✅ 전체 {len(all_regions)}개의 지역 코드를 가져왔습니다.")
                break
            
            page_no += 1
        
        return all_regions
        
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        print("샘플 데이터로 대체합니다.")
        return get_sample_region_data()


# ============================================
# 샘플 데이터 (테스트용)
# ============================================

def get_sample_region_data() -> List[Dict]:
    """
    테스트용 샘플 행정구역 데이터
    실제 행정안전부 법정동코드 형식을 따릅니다.
    """
    return [
        # 시/도 (depth=1)
        {'code': '1100000000', 'name': '서울특별시'},
        {'code': '2600000000', 'name': '부산광역시'},
        {'code': '2700000000', 'name': '대구광역시'},
        {'code': '2800000000', 'name': '인천광역시'},
        {'code': '3000000000', 'name': '대전광역시'},
        {'code': '3100000000', 'name': '울산광역시'},
        {'code': '3611000000', 'name': '세종특별자치시'},
        {'code': '4100000000', 'name': '경기도'},
        {'code': '5000000000', 'name': '제주특별자치도'},
        
        # 서울 시/군/구 (depth=2)
        {'code': '1168000000', 'name': '강남구'},
        {'code': '1165000000', 'name': '강동구'},
        {'code': '1162000000', 'name': '강북구'},
        {'code': '1150000000', 'name': '강서구'},
        {'code': '1151000000', 'name': '관악구'},
        
        # 서울 강남구 동 (depth=3)
        {'code': '1168010100', 'name': '역삼동'},
        {'code': '1168010200', 'name': '삼성동'},
        {'code': '1168010300', 'name': '대치동'},
        {'code': '1168010400', 'name': '청담동'},
        {'code': '1168010500', 'name': '논현동'},
        
        # 경기도 시 (depth=2)
        {'code': '4113500000', 'name': '성남시'},
        {'code': '4117000000', 'name': '의정부시'},
        {'code': '4146000000', 'name': '안성시'},
        
        # 경기 성남시 구 (depth=3)
        {'code': '4113510000', 'name': '수정구'},
        {'code': '4113525000', 'name': '중원구'},
        {'code': '4113540000', 'name': '분당구'},
        
        # 경기 성남시 분당구 동 (depth=4)
        {'code': '4113540100', 'name': '서현동'},
        {'code': '4113540200', 'name': '정자동'},
        {'code': '4113540300', 'name': '수내동'},
        
        # 경기 안성시 읍/면 (depth=3)
        {'code': '4146025000', 'name': '공도읍'},
        {'code': '4146031000', 'name': '보개면'},
        {'code': '4146032000', 'name': '금광면'},
    ]


# ============================================
# 지역 코드 파싱 및 계층 구조 분석
# ============================================

def parse_region_code(code: str, name: str) -> Dict:
    """
    10자리 법정동코드를 파싱하여 계층 정보 추출
    
    코드 구조:
    - 1-2자리: 시도코드
    - 3-5자리: 시군구코드
    - 6-8자리: 읍면동코드
    - 9-10자리: 리코드
    
    Returns:
        {
            'region_code': '1168010100',
            'name': '역삼동',
            'sido_code': '11',
            'sgg_code': '680',
            'parent_code': '1168000000',
            'depth': 3,
            'order_num': 0
        }
    """
    code = code.ljust(10, '0')  # 10자리 맞추기
    
    sido_code = code[0:2]
    sgg_code = code[2:5]
    emd_code = code[5:8]  # 읍면동
    ri_code = code[8:10]  # 리
    
    # Depth 결정
    if ri_code != '00':
        depth = 4  # 리
        parent_code = code[0:8] + '00'
    elif emd_code != '000':
        depth = 3  # 읍면동
        parent_code = code[0:5] + '00000'
    elif sgg_code != '000':
        depth = 2  # 시군구
        parent_code = code[0:2] + '00000000'
    else:
        depth = 1  # 시도
        parent_code = None
    
    return {
        'region_code': code,
        'name': name,
        'sido_code': sido_code,
        'sgg_code': sgg_code if sgg_code != '000' else None,
        'parent_code': parent_code,
        'depth': depth,
        'order_num': 0,  # 나중에 인구순 등으로 정렬 가능
        'is_active': True
    }


# ============================================
# 데이터베이스 적재
# ============================================

def load_regions_to_db(supabase: Client, regions: List[Dict]) -> int:
    """
    regions 테이블에 데이터 적재 (벌크 upsert 방식)
    
    폐지된 지역코드 처리:
    - API에서 가져온 코드는 is_active=true로 upsert
    - API에 없는 기존 코드는 is_active=false로 업데이트 (소프트 삭제)
    
    Returns:
        적재된 레코드 수
    """
    print(f"\n📥 {len(regions)}개 지역 데이터를 데이터베이스에 적재 중...")
    
    # 모든 데이터를 파싱
    parsed_regions = []
    api_region_codes = set()  # API에서 가져온 코드 목록
    
    for region_data in regions:
        parsed = parse_region_code(region_data['code'], region_data['name'])
        parsed_regions.append(parsed)
        api_region_codes.add(region_data['code'])
    
    print(f"  ✅ {len(parsed_regions)}개 데이터 파싱 완료")
    
    # 벌크 upsert (배치 크기: 2000개씩)
    batch_size = 2000
    total_inserted = 0
    total_failed = 0
    
    for i in range(0, len(parsed_regions), batch_size):
        batch = parsed_regions[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(parsed_regions) + batch_size - 1) // batch_size
        
        try:
            # 벌크 upsert
            result = supabase.table('regions').upsert(
                batch,
                on_conflict='region_code'
            ).execute()
            
            total_inserted += len(batch)
            print(f"  📦 배치 {batch_num}/{total_batches}: {len(batch)}건 저장 완료 (총 {total_inserted}/{len(parsed_regions)})")
                
        except Exception as e:
            print(f"  ⚠️  배치 {batch_num} 저장 실패: {e}")
            total_failed += len(batch)
    
    print(f"\n✅ 적재 완료: {total_inserted}개 성공, {total_failed}개 실패")
    
    # 폐지된 지역코드 비활성화 (API에 없는 코드)
    print(f"\n🔄 폐지된 지역코드 확인 중...")
    try:
        # 현재 활성 상태인 모든 코드 조회
        all_active = supabase.table('regions').select('region_code').eq('is_active', True).execute()
        db_active_codes = {row['region_code'] for row in all_active.data}
        
        # API에 없는 코드 = 폐지된 코드
        deprecated_codes = db_active_codes - api_region_codes
        
        if deprecated_codes:
            print(f"  ⚠️  {len(deprecated_codes)}개 폐지된 지역코드 발견")
            
            # 비활성화 처리 (소프트 삭제)
            from datetime import datetime
            for code in deprecated_codes:
                supabase.table('regions').update({
                    'is_active': False,
                    'deprecated_at': datetime.now().isoformat()
                }).eq('region_code', code).execute()
            
            print(f"  ✅ {len(deprecated_codes)}개 지역코드를 비활성화 처리했습니다.")
        else:
            print(f"  ✅ 폐지된 지역코드 없음")
            
    except Exception as e:
        print(f"  ⚠️  폐지 코드 처리 실패: {e}")
    
    return total_inserted


# ============================================
# 메인 실행
# ============================================

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🏛️  행정구역 코드 적재 스크립트")
    print("=" * 60)
    
    # 1. Supabase 연결
    print("\n[1/4] Supabase 연결 중...")
    supabase = init_supabase()
    print(f"✅ 연결 완료: {SUPABASE_URL}")
    
    # 2. 스키마 확인
    print("\n[2/4] 스키마 확인 중...")
    if not check_schema(supabase):
        print("\n❌ 스키마가 준비되지 않았습니다. 종료합니다.")
        sys.exit(1)
    
    # 3. 행정코드 데이터 수집
    print("\n[3/4] 행정구역 데이터 수집 중...")
    regions = fetch_region_codes_from_api(MOIS_API_KEY, MOIS_API_URL)
    
    if not regions:
        print("❌ 데이터를 가져오지 못했습니다.")
        sys.exit(1)
    
    # 4. 데이터베이스 적재
    print("\n[4/4] 데이터베이스 적재 중...")
    inserted = load_regions_to_db(supabase, regions)
    
    # 완료
    print("\n" + "=" * 60)
    print(f"✅ 작업 완료!")
    print(f"📊 총 {inserted}개의 행정구역 데이터가 적재되었습니다.")
    print("=" * 60)
    
    # 적재 결과 확인
    print("\n📋 적재 결과 확인:")
    
    # depth별 통계
    stats = {}
    all_regions = supabase.table('regions').select('depth').execute()
    for row in all_regions.data:
        depth = row['depth']
        stats[depth] = stats.get(depth, 0) + 1
    
    print(f"  - Depth 1 (시/도): {stats.get(1, 0)}개")
    print(f"  - Depth 2 (시/군/구): {stats.get(2, 0)}개")
    print(f"  - Depth 3 (읍/면/동): {stats.get(3, 0)}개")
    print(f"  - Depth 4 (리): {stats.get(4, 0)}개")


if __name__ == '__main__':
    main()
