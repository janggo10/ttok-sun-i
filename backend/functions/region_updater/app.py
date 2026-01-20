"""
행정구역 코드 업데이트 Lambda 함수
분기별 1회 실행되어 행정안전부 API에서 최신 법정동코드를 가져와 Supabase에 동기화합니다.
"""
import os
import sys
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Set

# 상위 디렉토리의 common 모듈을 사용하기 위해 path 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from common.supabase_client import SupabaseClient
from common.slack_notifier import notify_info, notify_error

# Lambda 실행 시 필요한 환경변수
# MOIS_API_KEY
# MOIS_API_URL
# SUPABASE_URL
# SUPABASE_SERVICE_KEY
# SLACK_MONITORING_WEBHOOK / SLACK_ERROR_WEBHOOK

supabase = SupabaseClient.get_client()

def lambda_handler(event, context):
    """Lambda 핸들러"""
    print("🚀 Region Updater started")
    
    try:
        # 환경변수 확인
        mois_api_key = os.getenv('MOIS_API_KEY')
        mois_api_url = os.getenv('MOIS_API_URL', 'https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList')
        
        if not mois_api_key:
            raise ValueError("MOIS_API_KEY is not set")
            
        print("📡 Fetching region codes from MOIS API...")
        regions = fetch_all_regions(mois_api_key, mois_api_url)
        print(f"✅ Fetched {len(regions)} regions from API")
        
        if not regions:
            print("⚠️ No regions fetched, skipping update")
            notify_info("Region Updater: 업데이트할 데이터가 없습니다.")
            return {
                'statusCode': 200,
                'body': json.dumps('No regions to update')
            }
            
        print("💾 Updating database...")
        stats = update_database(regions)
        print(f"✅ Database update complete: {stats}")
        
        # Slack 알림 (성공 -> 모니터링 채널)
        message = (
            f"✅ *행정구역 코드 업데이트 완료*\n"
            f"- API 수집: {len(regions)}건\n"
            f"- 신규/갱신: {stats['inserted']}건\n"
            f"- 폐지(삭제): {stats['deprecated']}건"
        )
        notify_info("Region Updater 완료", details={
            "수집": f"{len(regions)}건",
            "갱신": f"{stats['inserted']}건",
            "폐지": f"{stats['deprecated']}건"
        })
        
        return {
            'statusCode': 200,
            'body': json.dumps(stats)
        }
        
    except Exception as e:
        import traceback
        error_msg = f"❌ Region Updater Failed: {str(e)}"
        print(error_msg)
        print(traceback.format_exc())
        
        # Slack 알림 (실패 -> 에러 채널)
        notify_error("Region Updater 실패", details={
            "Error": str(e)
        })
        raise e


def fetch_all_regions(api_key: str, api_url: str) -> List[Dict]:
    """API에서 모든 지역 코드 수집 (페이징 처리)"""
    all_regions = []
    page_no = 1
    max_rows_per_page = 1000  # API Limit
    
    while True:
        print(f"  Fetching page {page_no}...")
        
        # requests params 사용 시 인코딩 문제 발생 가능성 방지를 위해 직접 URL 구성
        url = f"{api_url}?ServiceKey={api_key}&type=xml&pageNo={page_no}&numOfRows={max_rows_per_page}&flag=Y"
        
        try:
            response = requests.get(url, timeout=60)
            # API 에러 체크는 XML 파싱 후 수행
            
            root = ET.fromstring(response.content)
            
            # Result Code Check
            result_code = root.findtext('.//resultCode', '')
            if result_code != 'INFO-0':
                result_msg = root.findtext('.//resultMsg', 'Unknown error')
                raise Exception(f"API Error: {result_msg} (Code: {result_code})")
            
            # Parse Rows
            page_regions = []
            for row in root.findall('.//row'):
                region_cd = row.findtext('region_cd', '').strip()
                locatadd_nm = row.findtext('locatadd_nm', '').strip()
                
                if region_cd and locatadd_nm:
                    page_regions.append({
                        'code': region_cd,
                        'name': locatadd_nm
                    })
            
            all_regions.extend(page_regions)
            
            # End Check
            if len(page_regions) < max_rows_per_page:
                break
                
            page_no += 1
            
        except Exception as e:
            print(f"  ❌ Error on page {page_no}: {e}")
            raise e
            
    return all_regions


def parse_region_code(code: str, name: str) -> Dict:
    """지역 코드 파싱"""
    code = code.ljust(10, '0')
    
    sido_code = code[0:2]
    sgg_code = code[2:5]
    emd_code = code[5:8]
    ri_code = code[8:10]
    
    # Depth 결정
    if ri_code != '00':
        depth = 4
        parent_code = code[0:8] + '00'
    elif emd_code != '000':
        depth = 3
        parent_code = code[0:5] + '00000'
    elif sgg_code != '000':
        depth = 2
        parent_code = code[0:2] + '00000000'
    else:
        depth = 1
        parent_code = None
    
    return {
        'region_code': code,
        'name': name,
        'sido_code': sido_code,
        'sgg_code': sgg_code if sgg_code != '000' else None,
        'parent_code': parent_code,
        'depth': depth,
        'order_num': 0,
        'is_active': True,
        'updated_at': datetime.now().isoformat()
    }


def update_database(regions: List[Dict]) -> Dict:
    """데이터베이스 업데이트 (벌크 처리)"""
    stats = {'inserted': 0, 'deprecated': 0}
    
    # 1. Parsing
    parsed_regions = []
    api_codes = set()
    
    for r in regions:
        parsed = parse_region_code(r['code'], r['name'])
        parsed_regions.append(parsed)
        api_codes.add(r['code'])
        
    # 2. Bulk Upsert
    batch_size = 2000
    for i in range(0, len(parsed_regions), batch_size):
        batch = parsed_regions[i:i + batch_size]
        try:
            supabase.table('regions').upsert(
                batch,
                on_conflict='region_code'
            ).execute()
            stats['inserted'] += len(batch)
            print(f"  Updated batch {i//batch_size + 1}: {len(batch)} records")
        except Exception as e:
            print(f"  ❌ Batch update failed: {e}")
            raise e
            
    # 3. Soft Delete Deprecated
    try:
        # DB의 모든 활성 코드 가져오기
        all_active = supabase.table('regions').select('region_code').eq('is_active', True).execute()
        db_codes = {row['region_code'] for row in all_active.data}
        
        deprecated = db_codes - api_codes
        
        if deprecated:
            print(f"  ⚠️ Found {len(deprecated)} deprecated regions")
            for code in deprecated:
                supabase.table('regions').update({
                    'is_active': False,
                    'deprecated_at': datetime.now().isoformat()
                }).eq('region_code', code).execute()
                stats['deprecated'] += 1
                
    except Exception as e:
        print(f"  ❌ Deprecation check failed: {e}")
        # Deprecation 실패는 전체 실패로 간주하지 않음 (선택적)
        
    return stats
