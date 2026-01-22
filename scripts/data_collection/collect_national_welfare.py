import logging
import time
import hashlib
from datetime import datetime, timezone, timedelta
import hashlib
from dotenv import load_dotenv
from supabase import create_client
import json
import sys
import os

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress httpx/httpcore logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

# Configuration - Load from .env file
BOKJIRO_API_KEY = os.getenv("BOKJIRO_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


# API Endpoints
# National Welfare Information List/Detail
LIST_API_URL = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
DETAIL_API_URL = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase credentials missing.")
        raise ValueError("Supabase credentials missing.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    """Helper to safely find text in XML element"""
    if element is None:
        return None
    found = element.find(tag)
    return found.text.strip() if found is not None and found.text else None

def get_now_kst():
    return datetime.now(timezone(timedelta(hours=9))).isoformat()

def fetch_national_welfare_list(page_no=1, num_of_rows=1000):
    params = {
        "serviceKey": BOKJIRO_API_KEY,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
        "callTp": "L",  # List type
        "srchKeyCode": "001" # Mandatory: Search by Title
    }
    
    try:
        response = requests.get(LIST_API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        # Check if response is XML
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            logger.error(f"Failed to parse XML response: {response.text[:200]}")
            return []

        result_code = root.findtext('.//resultCode')
        # Bokjiro APIs sometimes use '00' or '0' for success
        if result_code not in ['00', '0']:
            msg = root.findtext('.//resultMessage')
            logger.error(f"API Error: {result_code} - {msg}")
            return []
            
        items = root.findall('.//servList')
        return items
    except Exception as e:
        logger.error(f"Failed to fetch national welfare list page {page_no}: {e}")
        return []

def fetch_national_welfare_detail(serv_id):
    params = {
        "serviceKey": BOKJIRO_API_KEY,
        "callTp": "D", # Detail type
        "servId": serv_id
    }
    
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            '''
            # Debug: Print URL for curl testing
            req = requests.Request('GET', DETAIL_API_URL, params=params)
            prepped = req.prepare()
            print(f"DEBUG DETAIL URL: {prepped.url}")
            '''
    
            response = requests.get(DETAIL_API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            result_code = root.findtext('.//resultCode')
            if result_code not in ['00', '0']:
                msg = root.findtext('.//resultMessage')
                if attempt < max_retries - 1:
                    logger.warning(f"Detail API Error for {serv_id}: {result_code} (Attempt {attempt+1}/{max_retries}). Retrying...")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    logger.error(f"Detail API Error for {serv_id}: {result_code} - {msg}")
                    return None
                
            # The structure is usually different for detail
            # Assuming typical Bokjiro structure, but needs verification.
            # Based on local script experience, verify the root element for specific fields.
            return root 
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"Request failed for {serv_id}: {e} (Attempt {attempt+1}/{max_retries}). Retrying...")
                time.sleep(retry_delay * (2 ** attempt))
            else:
                logger.error(f"Failed to fetch detail for {serv_id} after {max_retries} attempts: {e}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch detail for {serv_id}: {e}")
            return None
    return None

def parse_life_cycle(detail_root):
    # This logic depends on exact XML field names for life cycle (e.g., 'lifeNm', 'trgterNm' etc.)
    # For now, we'll try to extract target text to infer lifecycle or use specific mapped fields if available
    # National API typically has fields like 'lifeArray' or similar descriptions.
    # Placeholder logic:
    target = safe_find_text(detail_root, './/trgterIndvdlArray') # Example tag
    if not target:
        target = safe_find_text(detail_root, './/tgtInfo') # Example
        
    # In a real scenario, we map specific keywords (youth, elderly) to our enum
    # For this MVP, we return a generic mapping or empty if standard fields aren't found.
    return ["전생애"] # Default fallback

def format_date(date_str):
    if not date_str:
        return None
    # Usually YYYYMMDD or YYYY-MM-DD
    clean = date_str.replace("-", "").replace(".", "").strip()
    if len(clean) == 8:
        return f"{clean[:4]}-{clean[4:6]}-{clean[6:]}"
    return None

def compute_content_hash(text):
    """Generate SHA256 hash of content for embedding change detection"""
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def main():
    logger.info("Starting National Welfare Data Collection...")
    
    if not BOKJIRO_API_KEY:
        logger.error("BOKJIRO_API_KEY is missing.")
        return

    supabase = get_supabase_client()

    # Step 1: Soft Delete - Mark all existing national benefits as inactive
    logger.info("Soft Delete: Marking all existing national benefits as inactive...")
    try:
        supabase.table("benefits") \
            .update({"is_active": False, "updated_at": get_now_kst()}) \
            .eq("source_api", "NATIONAL") \
            .execute()
        logger.info("Reset complete.")
    except Exception as e:
        logger.error(f"Failed to reset active status: {e}")
        return

    # Step 2: Fetch and Update (Mark active if found)
    # Processing pages - continue until no more data
    total_items_fetched = 0
    total_success = 0
    total_failed = 0
    
    page = 1
    MAX_WORKERS = 4
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Function to process single item (extracted from loop)
    def process_item(item, detail_root):
        serv_nm = safe_find_text(item, 'servNm')
        serv_id = safe_find_text(item, 'servId')
        
        # Extract fields from List Response (V001)
        serv_dtl_link = safe_find_text(item, 'servDtlLink')
        enfc_bgng_ymd = format_date(safe_find_text(item, 'svcfrstRegTs')) 
        
        # Contact & Dept Info
        dept_contact = safe_find_text(item, 'rprsCtadr')
        dept_name = safe_find_text(item, 'jurMnofNm')  # Ministry name (e.g., 보건복지부)
        dept_org = safe_find_text(item, 'jurOrgNm')     # Department name (e.g., 출산정책과)
        
        # 부처명 + 부서명 조합 (둘 다 있으면)
        if dept_name and dept_org:
            dept_name = f"{dept_name} {dept_org}"
        
        # Metadata
        inq_num = int(safe_find_text(item, 'inqNum') or 0)
        onap_psblt_yn = safe_find_text(item, 'onapPsbltYn')
        
        # Service metadata (목록 API에도 있음)
        sprt_cyc_nm = safe_find_text(item, 'sprtCycNm')      # 1회성, 월 등
        srv_pvsn_nm = safe_find_text(item, 'srvPvsnNm')      # 현지비지원(바우처) 등
        
        # Arrays (Comma separated strings in XML)
        def parse_array(val):
            return [x.strip() for x in val.split(',')] if val else []

        # 주의: lifeArray에 이름이 들어있음 (코드 아님)
        life_nm_array = parse_array(safe_find_text(item, 'lifeArray'))
        intrs_thema_nm_array = parse_array(safe_find_text(item, 'intrsThemaArray'))
        trgter_indvdl_nm_array = parse_array(safe_find_text(item, 'trgterIndvdlArray'))

        # Extract Detail Fields (V001)
        serv_digest = safe_find_text(detail_root, './/wlfareInfoOutlCn') or "" 
        tgt_info = safe_find_text(detail_root, './/tgtrDtlCn') or ""       
        slct_crit = safe_find_text(detail_root, './/slctCritCn') or ""     
        alw_serv_cn = safe_find_text(detail_root, './/alwServCn') or ""
        
        # 상세 API에서 dept_name을 다시 가져옴 (더 완전한 정보가 있을 수 있음)
        dept_name_detail = safe_find_text(detail_root, './/jurMnofNm')
        if dept_name_detail:  # 상세 API에 더 자세한 정보가 있으면 덮어쓰기
            dept_name = dept_name_detail
            # logger.info(f"[{serv_id}] Updated dept_name from detail API: '{dept_name}'")  # Reduced verbosity
        
        # Helper to parse XML lists to JSON
        def parse_xml_list_auto(root, parent_tag, possible_child_tag, fields):
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

        # JSON Fields
        contact_info = parse_xml_list_auto(detail_root, 'inqplCtadrList', 'inqplCtadr', ['servSeDetailLink', 'servSeDetailNm'])
        attachments = parse_xml_list_auto(detail_root, 'basfrmList', 'basfrm', ['servSeDetailLink', 'servSeDetailNm'])
        base_laws = parse_xml_list_auto(detail_root, 'baslawList', 'baslaw', ['servSeDetailNm'])
        related_links = parse_xml_list_auto(detail_root, 'inqplHmpgReldList', 'inqplHmpgReld', ['servSeDetailLink', 'servSeDetailNm'])
        
        # 신청방법 리스트 (applmetList - 다중 항목)
        apply_methods = parse_xml_list_auto(detail_root, 'applmetList', 'applmet', ['servSeDetailLink', 'servSeDetailNm'])
        
        # 신청방법 텍스트로 포맷팅 (JSON 리스트를 텍스트로 변환)
        apply_method_detail = None
        if apply_methods != '[]':
            methods_list = json.loads(apply_methods)
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
            if formatted_methods:
                apply_method_detail = ', '.join(formatted_methods)
        
        # 상세 API에서 배열 필드도 확인 (목록 API와 다를 수 있음)
        detail_life_array = parse_array(safe_find_text(detail_root, './/lifeArray'))
        detail_intrs_array = parse_array(safe_find_text(detail_root, './/intrsThemaArray'))
        detail_trgter_array = parse_array(safe_find_text(detail_root, './/trgterIndvdlArray'))
        
        # 상세 API에 더 많은 정보가 있으면 덮어쓰기
        if detail_life_array:
            life_nm_array = detail_life_array
        if detail_intrs_array:
            intrs_thema_nm_array = detail_intrs_array
        if detail_trgter_array:
            trgter_indvdl_nm_array = detail_trgter_array
        
        # 상세 API에서 서비스 메타도 확인
        detail_sprt_cyc = safe_find_text(detail_root, './/sprtCycNm')
        detail_srv_pvsn = safe_find_text(detail_root, './/srvPvsnNm')
        if detail_sprt_cyc:
            sprt_cyc_nm = detail_sprt_cyc
        if detail_srv_pvsn:
            srv_pvsn_nm = detail_srv_pvsn
        
        # contact_info를 텍스트로 변환
        contact_text = ""
        if contact_info != '[]':
            contacts = json.loads(contact_info)
            contact_parts = []
            for contact in contacts:
                link = contact.get('servSeDetailLink', '')
                name = contact.get('servSeDetailNm', '')
                if link and name:
                    contact_parts.append(f"{name}: {link}")
                elif link:
                    contact_parts.append(link)
                elif name:
                    contact_parts.append(name)
            if contact_parts:
                contact_text = f"문의처: {', '.join(contact_parts)}"
        
        # Construct content for embedding
        content_blob = f"""
        서비스명: {serv_nm}
        개요: {serv_digest}
        대상: {tgt_info}
        선정기준: {slct_crit}
        내용: {alw_serv_cn}
        {contact_text}
        상세링크: {serv_dtl_link}
        """.strip()
        
        # Prepare DB Object
        db_data = {
            "serv_id": serv_id,
            "serv_nm": serv_nm,
            "source_api": "NATIONAL",
            "ctpv_nm": None, 
            "sgg_nm": None,
            "dept_name": dept_name,
            "dept_contact": dept_contact,
            "enfc_bgng_ymd": enfc_bgng_ymd,
            "enfc_end_ymd": None,
            "serv_dtl_link": serv_dtl_link,
            
            # Arrays (이름만 저장, 코드 배열은 제거)
            "life_nm_array": life_nm_array,
            "intrs_thema_nm_array": intrs_thema_nm_array,
            "trgter_indvdl_nm_array": trgter_indvdl_nm_array,
            
            # Service metadata
            "sprt_cyc_nm": sprt_cyc_nm,
            "srv_pvsn_nm": srv_pvsn_nm,
            
            # Details
            "serv_dgst": safe_find_text(item, 'servDgst'),
            "wlfare_info_outl_cn": serv_digest,
            "target_detail": tgt_info,
            "select_criteria": slct_crit,
            "service_content": alw_serv_cn,
            "apply_method_detail": apply_method_detail,
            "content_for_embedding": content_blob,
            "content_hash": compute_content_hash(content_blob),  # 임베딩 변경 감지용
            
            # Metadata
            "inq_num": inq_num,
            "onap_psblt_yn": onap_psblt_yn,
            "is_active": True,
            
            # JSONs
            "contact_info": contact_info,
            "attachments": attachments,
            "base_laws": base_laws,
            "related_links": related_links
        }
        
        # Upsert
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                supabase.table("benefits").upsert(db_data, on_conflict="serv_id").execute()
                # logger.info(f"Saved {serv_nm}") # Reduced verbosity
                return True
            except Exception as e:
                # Retry on Supabase connection errors
                if attempt < max_retries - 1:
                    logger.warning(f"Upsert failed for {serv_id}: {e} (Attempt {attempt+1}/{max_retries}). Retrying...")
                    time.sleep(retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Failed to upsert {serv_id} after {max_retries} attempts: {e}")
                    return False
        return False

    def process_item_wrapper(item):
        serv_id = safe_find_text(item, 'servId')
        if not serv_id:
            return False

        detail_root = fetch_national_welfare_detail(serv_id)
        if not detail_root:
            logger.warning(f"Skipping {serv_id}: Failed to fetch details.")
            return False
        
        return process_item(item, detail_root)

    while True:
        logger.info(f"Fetching page {page}...")
        items = fetch_national_welfare_list(page_no=page, num_of_rows=1000)
        
        if not items:
            logger.info(f"No more items found. Completed at page {page}.")
            break
        
        # 1000 items check logic not strictly needed as we check empty, but good for info
        logger.info(f"Found {len(items)} items on page {page}. Starting parallel processing ({MAX_WORKERS} workers)...")
        total_items_fetched += len(items)
        
        page_success = 0
        page_failed = 0
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_item_wrapper, item): item for item in items}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    page_success += 1
                    total_success += 1
                else:
                    page_failed += 1
                    total_failed += 1
            
        logger.info(f"Page {page} complete. Success: {page_success}, Failed: {page_failed}")
        page += 1  # Move to next page
    
    # Final Summary
    logger.info("")
    logger.info("="*60)
    logger.info("중앙부처 복지 데이터 수집 완료")
    logger.info("="*60)
    logger.info(f"총 조회: {total_items_fetched}건")
    logger.info(f"성공: {total_success}건")
    logger.info(f"실패: {total_failed}건")
    logger.info("="*60)
    
    # Output result as JSON for pipeline orchestration
    print(f"\n__PIPELINE_RESULT__:{json.dumps({'total': total_items_fetched, 'success': total_success, 'failed': total_failed})}")

if __name__ == "__main__":
    main()
