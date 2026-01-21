import os
import sys
import logging
from datetime import datetime
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# Add parent directory to path to import common modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
BOKJIRO_API_KEY =  "82b26bbf4c159c48aeb0570892efdce9d3438cf0acf78b2cffd055952bd2ddba"
SUPABASE_URL = "https://ladqubaousblucmrqcrr.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhZHF1YmFvdXNibHVjbXJxY3JyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODgyNDI1MiwiZXhwIjoyMDg0NDAwMjUyfQ.YZfsje16TIRzEKI9N6WgH-49XH-VPqLJwqwp4LlwhxY"

# AWS 설정 (K-Wave Now와 동일)"

# API Endpoints (Verified from test_local_welfare_api.py)
BASE_URL = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
LIST_API_URL = f"{BASE_URL}/LcgvWelfarelist"
DETAIL_API_URL = f"{BASE_URL}/LcgvWelfaredetailed"

def get_supabase_client():
    from supabase import create_client
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase credentials missing in .env")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def parse_date(date_str):
    if not date_str or len(date_str) != 8:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").date().isoformat()
    except ValueError:
        return None

def parse_array_from_str(value_str):
    """
    Parses a string that might be slash-separated or comma-separated into a list.
    XML text already comes as string.
    Example: "중장년/노년" -> ["중장년", "노년"]
    """
    if not value_str:
        return None
    
    value_str = value_str.strip()
    if not value_str:
        return None

    if "/" in value_str:
        return [x.strip() for x in value_str.split("/") if x.strip()]
    elif "," in value_str:
        return [x.strip() for x in value_str.split(",") if x.strip()]
    else:
        return [value_str]

def safe_find_text(element, tag, default=None):
    if element is None:
        return default
    child = element.find(tag)
    return child.text if child is not None else default

def fetch_welfare_list(ctpv_nm, page_no=1, num_of_rows=20):
    params = {
        "serviceKey": BOKJIRO_API_KEY,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
        "ctpvNm": ctpv_nm
    }
    
    try:
        response = requests.get(LIST_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        result_code = root.findtext('.//resultCode')
        if result_code not in ['00', '0']:
            msg = root.findtext('.//resultMessage')
            logger.error(f"API Error for {ctpv_nm}: {result_code} - {msg}")
            return []
            
        items = root.findall('.//servList')
        return items
    except Exception as e:
        logger.error(f"Failed to fetch welfare list for {ctpv_nm}: {e}")
        return []

def fetch_welfare_detail(serv_id):
    params = {
        "serviceKey": BOKJIRO_API_KEY,
        "servId": serv_id
    }
    
    try:
        response = requests.get(DETAIL_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        # Detail root usually contains items directly under root or wrapped
        # Checking logic based on test_local_welfare_api.py context
        
        if root.find('servId') is None:
             # Try check result code if wrapped
            if result_code and result_code not in ['00', '0']:
                logger.error(f"Detail API Error for {serv_id}: {result_code}")
                return None
        
        return root
    except Exception as e:
        logger.error(f"Failed to fetch detail for {serv_id}: {e}")
        return None

def main():
    logger.info("Starting local welfare data collection (All Regions)...")
    
    if not BOKJIRO_API_KEY:
        logger.error("BOKJIRO_API_KEY is missing.")
        return

    supabase = get_supabase_client()

    # Step 1: Soft Delete - Mark all existing local benefits as inactive
    logger.info("Soft Delete: Marking all existing local benefits as inactive...")
    try:
        supabase.table("benefits") \
            .update({"is_active": False, "updated_at": "now()"}) \
            .eq("source_api", "LOCAL") \
            .execute()
        logger.info("Reset complete.")
    except Exception as e:
        logger.error(f"Failed to reset active status: {e}")
        return
    
    # List of 17 Major Administrative Divisions in South Korea
    ctpv_list = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시", 
        "광주광역시", "대전광역시", "울산광역시", "세종특별자치시", 
        "경기도", "강원특별자치도", "충청북도", "충청남도", 
        "전북특별자치도", "전라남도", "경상북도", "경상남도", 
        "제주특별자치도"
    ]
    
    total_success_count = 0
    
    for ctpv in ctpv_list:
        logger.info(f"Fetching welfare list for {ctpv}...")
        welfare_items = fetch_welfare_list(ctpv, num_of_rows=100) 
        
        logger.info(f"Found {len(welfare_items)} items in {ctpv}.")
        
        for item in welfare_items:
            # ... (parsing logic)
            serv_id = safe_find_text(item, 'servId')
            # ...
            
            # (Inside loop, constructing cleaned_data)
            cleaned_data = {
                # ... existing fields ...
                "serv_id": serv_id,
                "serv_nm": serv_nm,
                "source_api": "LOCAL",
                "ctpv_nm": safe_find_text(detail, 'ctpvNm'),
                "sgg_nm": safe_find_text(detail, 'sggNm'),
                "dept_name": safe_find_text(detail, 'bizChrDeptNm'),
                
                "enfc_bgng_ymd": parse_date(safe_find_text(detail, 'enfcBgngYmd')),
                "enfc_end_ymd": parse_date(safe_find_text(detail, 'enfcEndYmd')),
                "last_mod_ymd": parse_date(safe_find_text(detail, 'lastModYmd')),
                
                "life_nm_array": life_nm_array,
                "intrs_thema_nm_array": intrs_thema_nm_array,
                "trgter_indvdl_nm_array": trgter_indvdl_nm_array,
                
                "sprt_cyc_nm": safe_find_text(detail, 'sprtCycNm'),
                "srv_pvsn_nm": safe_find_text(detail, 'srvPvsnNm'),
                "aply_mtd_nm": safe_find_text(detail, 'aplyMtdNm'),
                
                "serv_dgst": safe_find_text(detail, 'servDgst'),
                "serv_dtl_link": safe_find_text(item, 'servDtlLink'),
                
                "target_detail": trgt_detail,
                "select_criteria": slct_detail,
                "service_content": serv_content,
                "apply_method_detail": aply_detail,
                
                "content_for_embedding": "\n".join(filter(None, [
                    f"대상: {trgt_detail}",
                    f"기준: {slct_detail}",
                    f"내용: {serv_content}",
                    f"방법: {aply_detail}"
                ])),
                
                "contact_info": contact_info,
                "base_laws": base_laws,
                "attachments": attachments,
                
                "inq_num": int(safe_find_text(detail, 'inqNum') or 0),
                "is_active": True,
                "updated_at": datetime.now().isoformat()
            }
            
            # 4. Upsert to Supabase
            try:
                result = supabase.table("benefits").upsert(cleaned_data, on_conflict="serv_id").execute()
                logger.info(f"Saved {serv_id}")
                total_success_count += 1
            except Exception as e:
                logger.error(f"Failed to save {serv_id}: {e}")

    logger.info(f"Collection complete. Successfully saved {total_success_count} items from all regions.")

if __name__ == "__main__":
    main()
