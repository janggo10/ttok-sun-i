#!/usr/bin/env python3
"""
100세누리 일자리 데이터 수집 스크립트

- API: 공공데이터포털 100세누리 구인정보
- 수집: 목록 → 상세 → Supabase 저장
- 마감일 지난 공고 제외 (count만 출력)
"""

import os
import sys
import time
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import List, Dict, Optional
from dotenv import load_dotenv


# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Error: supabase-py not installed")
    print("Run: pip install supabase")
    sys.exit(1)


# ============================================
# Configuration
# ============================================

# Load environment variables
load_dotenv()


API_KEY = os.getenv("PUBLIC_DATA_PORTAL_API_KEY") 
if not API_KEY:
    print("❌ Error: PUBLIC_DATA_PORTAL_API_KEY not set")
    sys.exit(1)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

# API Endpoints
BASE_URL = "http://apis.data.go.kr/B552474/SenuriService"
LIST_URL = f"{BASE_URL}/getJobList"
DETAIL_URL = f"{BASE_URL}/getJobInfo"

# Settings
PAGE_SIZE = 100000  # numOfRows per page
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


# ============================================
# Helper Functions
# ============================================

def parse_xml_response(xml_text: str) -> Dict:
    """Parse XML response to dict"""
    try:
        root = ET.fromstring(xml_text)
        
        # Check response code
        result_code = root.find('.//resultCode')
        if result_code is not None and result_code.text != '00':
            result_msg = root.find('.//resultMsg').text if root.find('.//resultMsg') is not None else 'Unknown error'
            raise Exception(f"API Error: {result_code.text} - {result_msg}")
        
        return root
    except ET.ParseError as e:
        print(f"❌ XML Parse Error: {e}")
        print(f"Response: {xml_text[:500]}")
        raise


def xml_to_dict(element) -> Dict:
    """Convert XML element to dict"""
    result = {}
    for child in element:
        if len(child) == 0:  # Leaf node
            result[child.tag] = child.text
        else:  # Has children
            result[child.tag] = xml_to_dict(child)
    return result


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string (YYYYMMDD) to date object"""
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime.strptime(date_str, '%Y%m%d').date()
    except:
        return None


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse datetime string (ISO 8601) to datetime object"""
    if not dt_str:
        return None
    try:
        # Format: 2015-05-26T10:56:51+09:00
        return datetime.fromisoformat(dt_str.replace('+09:00', '+09:00'))
    except:
        return None


def calculate_hash(job_id: str, title: str, detail_content: str) -> str:
    """Calculate content hash for duplicate detection"""
    content = f"{job_id}{title}{detail_content}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


# ============================================
# API Functions
# ============================================

def fetch_job_list(page_no: int = 1) -> Optional[Dict]:
    """
    Fetch job list from API
    
    Returns:
        {
            'items': [job_dict, ...],
            'total_count': int,
            'page_no': int,
            'num_of_rows': int
        }
    """
    params = {
        'serviceKey': API_KEY,
        'pageNo': page_no,
        'numOfRows': PAGE_SIZE
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            print(f"🔍 Fetching page {page_no} (attempt {attempt + 1}/{MAX_RETRIES})...")
            response = requests.get(LIST_URL, params=params, timeout=30)
            response.raise_for_status()
            
            root = parse_xml_response(response.text)
            
            # Extract data
            body = root.find('.//body')
            if body is None:
                return None
            
            items = []
            items_elem = body.find('items')
            if items_elem is not None:
                for item in items_elem.findall('item'):
                    items.append(xml_to_dict(item))
            
            total_count = int(body.find('totalCount').text) if body.find('totalCount') is not None else 0
            
            return {
                'items': items,
                'total_count': total_count,
                'page_no': page_no,
                'num_of_rows': PAGE_SIZE
            }
            
        except Exception as e:
            print(f"⚠️ Error fetching page {page_no}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise
    
    return None


def fetch_job_detail(job_id: str) -> Optional[Dict]:
    """Fetch job detail from API"""
    params = {
        'serviceKey': API_KEY,
        'id': job_id
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(DETAIL_URL, params=params, timeout=30)
            response.raise_for_status()
            
            root = parse_xml_response(response.text)
            
            # Extract item
            item = root.find('.//item')
            if item is None:
                print(f"⚠️ No detail found for job_id: {job_id}")
                return None
            
            return xml_to_dict(item)
            
        except Exception as e:
            print(f"⚠️ Error fetching detail for {job_id}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                return None
    
    return None


# ============================================
# Database Functions
# ============================================

def init_supabase() -> Client:
    """Initialize Supabase client"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def save_job(supabase: Client, job_data: Dict) -> bool:
    """
    Save job posting to Supabase
    
    Returns:
        True if saved, False if skipped (duplicate or error)
    """
    try:
        job_id = job_data.get('jobId')
        if not job_id:
            print(f"⚠️ Missing jobId, skipping")
            return False
        
        # Check if exists
        existing = supabase.table('job_postings').select('id').eq('job_id', job_id).execute()
        
        # Prepare data
        detail_content = job_data.get('detCnts', '')
        title = job_data.get('recrTitle') or job_data.get('wantedTitle', '')
        
        data = {
            'job_id': job_id,
            'title': title,
            'deadline': parse_date(job_data.get('toDd')),
            'employment_type_code': job_data.get('emplymShp'),
            'employment_type_nm': job_data.get('emplymShpNm'),
            'organization_name': job_data.get('oranNm'),
            'workplace_code': job_data.get('workPlc'),
            'workplace_nm': job_data.get('workPlcNm'),
            'age_limit': int(job_data.get('age')) if job_data.get('age') else None,
            'age_limit_max': job_data.get('ageLim'),
            'clerk': job_data.get('clerk'),
            'clerk_contact': job_data.get('clerkContt'),
            'job_category_code': job_data.get('jobcls'),
            'job_category_nm': job_data.get('jobclsNm'),
            'detail_content': detail_content,
            'wanted_title': job_data.get('wantedTitle'),
            'wanted_auth_no': job_data.get('wantedAuthNo'),
            'create_date': parse_datetime(job_data.get('createDy')),
            'update_date': parse_datetime(job_data.get('updDy')),
            'fri_accept_date': parse_date(job_data.get('frAcptDd')),
            'to_accept_date': parse_date(job_data.get('toAcptDd')),
            'place_detail_address': job_data.get('plDetAddr'),
            'place_biz_nm': job_data.get('plbizNm'),
            'representative': job_data.get('repr'),
            'content_hash': calculate_hash(job_id, title, detail_content),
            'is_active': True
        }
        
        if existing.data:
            # Update
            supabase.table('job_postings').update(data).eq('job_id', job_id).execute()
            print(f"✅ Updated: {job_id} - {title[:50]}")
        else:
            # Insert
            supabase.table('job_postings').insert(data).execute()
            print(f"✅ Inserted: {job_id} - {title[:50]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving job {job_data.get('jobId')}: {e}")
        return False


# ============================================
# Main Collection Logic
# ============================================

def collect_all_jobs():
    """Collect all job postings (excluding expired)"""
    print("=" * 60)
    print("🚀 100세누리 일자리 데이터 수집 시작")
    print("=" * 60)
    
    supabase = init_supabase()
    
    page = 1
    total_jobs = 0
    saved_jobs = 0
    expired_jobs = 0
    error_jobs = 0
    
    start_time = time.time()
    
    while True:
        # Fetch list
        result = fetch_job_list(page)
        if not result or not result['items']:
            print(f"\n✅ No more items on page {page}")
            break
        
        print(f"\n📄 Page {page}: {len(result['items'])} items (Total: {result['total_count']})")
        
        for job in result['items']:
            total_jobs += 1
            job_id = job.get('jobId')
            
            # Check if expired (skip)
            deadline_str = job.get('deadline')  # '마감' 문자열
            to_date = parse_date(job.get('toDd'))  # 마감일 (YYYYMMDD)
            
            is_expired = False
            if deadline_str == '마감':
                is_expired = True
            elif to_date and to_date < date.today():
                is_expired = True
            
            if is_expired:
                expired_jobs += 1
                #print(f"⏭️  Skipped (expired): {job_id}")
                continue
            
            # Fetch detail
            detail = fetch_job_detail(job_id)
            if detail:
                # Merge list + detail
                merged_job = {**job, **detail}
                
                # Save
                if save_job(supabase, merged_job):
                    saved_jobs += 1
                else:
                    error_jobs += 1
            else:
                # Save list only
                if save_job(supabase, job):
                    saved_jobs += 1
                else:
                    error_jobs += 1
            
            # Rate limiting
            #time.sleep(0.1)
        print(f"Saved {saved_jobs} jobs, {expired_jobs} expired, {error_jobs} errors")
        
        # Next page
        if len(result['items']) < PAGE_SIZE:
            print(f"\n✅ Last page reached")
            break
        
        page += 1
        time.sleep(0.1)  # Be nice to the API
    
    # Summary
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("📊 수집 완료 요약")
    print("=" * 60)
    print(f"⏱️  소요 시간: {elapsed_time:.1f}초")
    print(f"📄 총 공고 수: {total_jobs}")
    print(f"✅ 저장 완료: {saved_jobs}")
    print(f"⏭️  마감 제외: {expired_jobs}")
    print(f"❌ 저장 실패: {error_jobs}")
    print("=" * 60)


# ============================================
# Entry Point
# ============================================

if __name__ == "__main__":
    try:
        collect_all_jobs()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
