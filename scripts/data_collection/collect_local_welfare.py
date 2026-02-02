import logging
import json
import hashlib
import time
import os
import sys
from datetime import datetime, timezone, timedelta
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

# Suppress httpx/httpcore logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

# Configuration - Load from .env file
PUBLIC_DATA_PORTAL_API_KEY = os.getenv("PUBLIC_DATA_PORTAL_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

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

def fetch_existing_db_state(supabase):
    """
    Fetch all existing Local benefits (serv_id, last_mod_ymd) from DB.
    Returns a dictionary: { serv_id: last_mod_ymd }
    """
    db_state = {}
    try:
        # Supabase default limit is 1000. Need to paginate if more.
        # However, for 4000 items, we can try to loop ranges or use a large limit if allowed?
        # Supabase-py `select` usually respects the query. Let's try paging just in case.
        batch_size = 1000
        start = 0
        while True:
            response = supabase.table("benefits") \
                .select("serv_id, last_mod_ymd") \
                .eq("source_api", "LOCAL") \
                .range(start, start + batch_size - 1) \
                .execute()
            
            rows = response.data
            if not rows:
                break
            
            for row in rows:
                if row['serv_id']:
                    db_state[row['serv_id']] = row['last_mod_ymd']
            
            if len(rows) < batch_size:
                break
            start += batch_size
            
        logger.info(f"Loaded {len(db_state)} existing items from DB.")
        return db_state
    except Exception as e:
        logger.error(f"Failed to fetch existing DB state: {e}")
        return {}

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

def get_now_kst():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()

def compute_content_hash(text):
    """Generate SHA256 hash of content for embedding change detection"""
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def fetch_welfare_list(page_no=1, num_of_rows=1000):
    params = {
        "serviceKey": PUBLIC_DATA_PORTAL_API_KEY,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    
    try:
        response = requests.get(LIST_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        result_code = root.findtext('.//resultCode')
        if result_code not in ['00', '0']:
            msg = root.findtext('.//resultMessage')
            logger.error(f"API Error: {result_code} - {msg}")
            return []
            
        items = root.findall('.//servList')
        return items
    except Exception as e:
        logger.error(f"Failed to fetch welfare list: {e}")
        return []

def fetch_welfare_detail(serv_id):
    params = {
        "serviceKey": PUBLIC_DATA_PORTAL_API_KEY,
        "servId": serv_id
    }
    
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            response = requests.get(DETAIL_API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # Detail root usually contains items directly under root or wrapped
            if root.find('servId') is None:
                 # Try check result code if wrapped
                result_code = root.findtext('.//resultCode')
                if result_code and result_code not in ['00', '0']:
                    # Force retry on API error if temporary, or just log error?
                    # Assuming some errors are transient, but others are permanent.
                    # For now treating non-00 as failure, but we could improve this.
                    if attempt < max_retries - 1:
                        logger.warning(f"Detail API Error for {serv_id}: {result_code} (Attempt {attempt+1}/{max_retries}). Retrying...")
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    else:
                        logger.error(f"Detail API Error for {serv_id}: {result_code}")
                        return None
            
            return root
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"Request failed for {serv_id}: {e} (Attempt {attempt+1}/{max_retries}). Retrying...")
                time.sleep(retry_delay * (2 ** attempt))
            else:
                logger.error(f"Failed to fetch detail for {serv_id} after {max_retries} attempts: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error for {serv_id}: {e}")
            return None
    return None

def main():
    logger.info("Starting local welfare data collection (All Regions)...")
    
    if not PUBLIC_DATA_PORTAL_API_KEY:
        logger.error("PUBLIC_DATA_PORTAL_API_KEY is missing.")
        return

    supabase = get_supabase_client()

    # Step 1: Load DB State for Incremental Update
    logger.info("Loading existing DB state for incremental update...")
    db_state = fetch_existing_db_state(supabase)
    seen_ids = set()
    skipped_count = 0
    
    # Removed initial Soft Delete - will handle at the end
    
    total_items_fetched = 0
    total_success_count = 0
    total_failed_count = 0
    
    # Parallel processing setup
    MAX_WORKERS = 4
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Function to process single item (extracted from loop)
    def process_item(item, detail):
        # 3. Parse arrays (목록 API에서 먼저, 상세 API에서 덮어쓰기)
        life_nm_array = parse_array_from_str(safe_find_text(item, 'lifeNmArray'))
        intrs_thema_nm_array = parse_array_from_str(safe_find_text(item, 'intrsThemaNmArray'))
        trgter_indvdl_nm_array = parse_array_from_str(safe_find_text(item, 'trgterIndvdlNmArray'))
        
        # 상세 API에도 배열이 있으면 덮어쓰기 (더 정확할 수 있음)
        detail_life = parse_array_from_str(safe_find_text(detail, 'lifeNmArray'))
        detail_intrs = parse_array_from_str(safe_find_text(detail, 'intrsThemaNmArray'))
        detail_trgter = parse_array_from_str(safe_find_text(detail, 'trgterIndvdlNmArray'))
        
        if detail_life:
            life_nm_array = detail_life
        if detail_intrs:
            intrs_thema_nm_array = detail_intrs
        if detail_trgter:
            trgter_indvdl_nm_array = detail_trgter
        
        # 4. Parse detail text fields
        trgt_detail = safe_find_text(detail, 'sprtTrgtCn') or ""
        slct_detail = safe_find_text(detail, 'slctCritCn') or ""
        serv_content = safe_find_text(detail, 'alwServCn') or ""
        aply_detail = safe_find_text(detail, 'aplyMtdCn') or ""
        
        # 서비스 메타데이터 (목록 API에서 먼저, 상세 API에서 덮어쓰기)
        sprt_cyc_nm = safe_find_text(item, 'sprtCycNm')
        srv_pvsn_nm = safe_find_text(item, 'srvPvsnNm')
        aply_mtd_nm = safe_find_text(item, 'aplyMtdNm')
        
        # 상세 API에 있으면 덮어쓰기
        if safe_find_text(detail, 'sprtCycNm'):
            sprt_cyc_nm = safe_find_text(detail, 'sprtCycNm')
        if safe_find_text(detail, 'srvPvsnNm'):
            srv_pvsn_nm = safe_find_text(detail, 'srvPvsnNm')
        if safe_find_text(detail, 'aplyMtdNm'):
            aply_mtd_nm = safe_find_text(detail, 'aplyMtdNm')
        
        # 5. Helper to parse XML lists to JSON
        def parse_xml_list_auto(root, parent_tag, possible_child_tag, fields):
            import json
            results = []
            
            # 시도 1: 형제로 반복되는 parent_tag들 찾기 (형태3)
            parents = root.findall(f'.//{parent_tag}')
            if not parents:
                return json.dumps([], ensure_ascii=False)
            
            # 각 parent에서 데이터 추출
            for parent in parents:
                # child_tag가 있는지 확인
                children = parent.findall(possible_child_tag)
                if children:
                    # 형태2: child가 있는 경우
                    for child in children:
                        data = {field: safe_find_text(child, field) for field in fields}
                        if any(data.values()):
                            results.append(data)
                else:
                    # 형태1: parent 안에 직접 필드가 있는 경우
                    data = {field: safe_find_text(parent, field) for field in fields}
                    if any(data.values()):
                        results.append(data)
            
            return json.dumps(results, ensure_ascii=False)
        
        # 6. Parse JSON fields
        contact_info = parse_xml_list_auto(detail, 'inqplCtadrList', 'inqplCtadr', ['wlfareInfoReldCn', 'wlfareInfoReldNm'])
        base_laws = parse_xml_list_auto(detail, 'baslawList', 'baslaw', ['wlfareInfoReldCn', 'wlfareInfoReldNm'])
        attachments = parse_xml_list_auto(detail, 'basfrmList', 'basfrm', ['wlfareInfoReldCn', 'wlfareInfoReldNm'])
        related_links = parse_xml_list_auto(detail, 'inqplHmpgReldList', 'inqplHmpgReld', ['wlfareInfoReldCn', 'wlfareInfoReldNm'])
        
        # contact_info를 텍스트로 변환
        contact_text = ""
        if contact_info != '[]':
            contacts = json.loads(contact_info)
            contact_parts = []
            for contact in contacts:
                link = contact.get('wlfareInfoReldCn', '')
                name = contact.get('wlfareInfoReldNm', '')
                if name and link:
                    contact_parts.append(f"{name}: {link}")
                elif link:
                    contact_parts.append(link)
                elif name:
                    contact_parts.append(name)
            if contact_parts:
                contact_text = f"문의처: {', '.join(contact_parts)}"
        
        # 7. Construct content_for_embedding
        serv_nm = safe_find_text(item, 'servNm')
        content_for_embedding = "\n".join(filter(None, [
            f"서비스명: {serv_nm}",
            f"개요: {safe_find_text(detail, 'servDgst') or ''}",
            f"대상: {trgt_detail}",
            f"기준: {slct_detail}",
            f"내용: {serv_content}",
            f"방법: {aply_detail}",
            contact_text,
            f"상세링크: {safe_find_text(item, 'servDtlLink')}"
        ]))
        
        # 8. Construct cleaned_data
        serv_id = safe_find_text(item, 'servId')
        cleaned_data = {
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
            
            "sprt_cyc_nm": sprt_cyc_nm,
            "srv_pvsn_nm": srv_pvsn_nm,
            "aply_mtd_nm": aply_mtd_nm,
            
            "serv_dgst": safe_find_text(detail, 'servDgst'),
            "serv_dtl_link": safe_find_text(item, 'servDtlLink'),
            
            "target_detail": trgt_detail,
            "select_criteria": slct_detail,
            "service_content": serv_content,
            "apply_method_detail": aply_detail,
            
            "content_for_embedding": content_for_embedding,
            "content_hash": compute_content_hash(content_for_embedding),
            
            "contact_info": contact_info,
            "base_laws": base_laws,
            "attachments": attachments,
            "related_links": related_links,
            
            "inq_num": int(safe_find_text(detail, 'inqNum') or 0),
            "is_active": True,
            "updated_at": get_now_kst()
        }
        
        # 9. Upsert to Supabase
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                supabase.table("benefits").upsert(cleaned_data, on_conflict="serv_id").execute()
                # logger.info(f"Saved {serv_id}: {serv_nm}")
                return True
            except Exception as e:
                # Check for specific errors if possible, or just retry all exceptions
                if attempt < max_retries - 1:
                    logger.warning(f"Upsert failed for {serv_id}: {e} (Attempt {attempt+1}/{max_retries}). Retrying...")
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Failed to save {serv_id} after {max_retries} attempts: {e}")
                    return False
        return False

    def process_item_wrapper(item):
        serv_id = safe_find_text(item, 'servId')
        serv_nm = safe_find_text(item, 'servNm')
        
        if not serv_id or not serv_nm:
            return False
        
        # Fetch detail
        detail = fetch_welfare_detail(serv_id)
        if not detail:
            logger.warning(f"Skipping {serv_id}: Failed to fetch details.")
            return False
            
        return process_item(item, detail)

    # Pagination loop (all regions)
    page = 1
    while True:
        logger.info(f"Fetching page {page}...")
        welfare_items = fetch_welfare_list(page_no=page, num_of_rows=1000)
        if not welfare_items:
            logger.info(f"  Completed at page {page}.")
            break
        
        logger.info(f"  Found {len(welfare_items)} items on page {page}.")
        total_items_fetched += len(welfare_items)
        
        # Incremental Filtering
        items_to_process = []
        
        for item in welfare_items:
            serv_id = safe_find_text(item, 'servId')
            if not serv_id:
                continue
            
            seen_ids.add(serv_id) # Mark as seen (active)
            
            # Check for changes
            api_mod_date_str = safe_find_text(item, 'lastModYmd')
            api_mod_date = parse_date(api_mod_date_str)
            
            db_mod_date = db_state.get(serv_id)
            
            # Condition: If Exists AND dates match -> Skip Detail
            if db_mod_date and api_mod_date and db_mod_date == api_mod_date:
                skipped_count += 1
                total_success_count += 1 # Count as success for reporting
                # We could update `updated_at` here but to save API calls we assume Soft Delete logic handles `is_active`
                # (Since we won't mark it inactive at the end, it stays Active)
                continue
            
            # New or Changed -> Add to processing list
            items_to_process.append(item)
            
        if not items_to_process:
            logger.info(f"  Page {page}: All {len(welfare_items)} items are up-to-date. Skipping detail fetch.")
            page += 1
            continue
            
        logger.info(f"  Page {page}: Processing {len(items_to_process)} items ({len(welfare_items) - len(items_to_process)} skipped)...")
        
        # Use ThreadPoolExecutor for parallel processing of NEW/CHANGED items only
        page_success = 0
        page_failed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_item_wrapper, item): item for item in items_to_process}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    page_success += 1
                    total_success_count += 1
                else:
                    page_failed += 1
                    total_failed_count += 1
        
        logger.info(f"  Page {page} complete. Updated/Inserted: {page_success}, Failed: {page_failed}")
        
        page += 1

    # Final Step: Soft Delete (Differential)
    # Mark items as inactive if they are in DB but NOT in the API list (seen_ids)
    all_db_ids = set(db_state.keys())
    # Note: db_state only contains "LOCAL" items as queried
    ids_to_deactivate = list(all_db_ids - seen_ids)
    
    if ids_to_deactivate:
        logger.info(f"Soft Deleting {len(ids_to_deactivate)} items that are no longer in API...")
        # Update in batches of 100 to avoid huge query
        batch_size = 100
        for i in range(0, len(ids_to_deactivate), batch_size):
            batch = ids_to_deactivate[i:i+batch_size]
            try:
                supabase.table("benefits") \
                    .update({"is_active": False, "updated_at": get_now_kst()}) \
                    .in_("serv_id", batch) \
                    .execute()
            except Exception as e:
                logger.error(f"Failed to batch soft-delete: {e}")
    else:
        logger.info("No items to soft delete.")

    # Final Summary
    logger.info("")
    logger.info("="*60)
    logger.info("지자체 복지 데이터 수집 및 동기화 완료")
    logger.info("="*60)
    logger.info(f"총 발견(API): {total_items_fetched}건")
    logger.info(f"스킵(변경없음): {skipped_count}건")
    logger.info(f"업데이트/신규: {total_success_count - skipped_count}건")
    logger.info(f"실패: {total_failed_count}건")
    logger.info(f"삭제처리: {len(ids_to_deactivate)}건")
    logger.info("="*60)
    
    # Output result as JSON for pipeline orchestration
    print(f"\n__PIPELINE_RESULT__:{json.dumps({'total': total_items_fetched, 'success': total_success_count, 'failed': total_failed_count})}")

if __name__ == "__main__":
    main()
