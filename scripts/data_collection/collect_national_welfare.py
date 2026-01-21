import os
import sys
import requests
import xml.etree.ElementTree as ET
import logging
import time
from dotenv import load_dotenv
from supabase import create_client
import json

# Add parent directory to path to allow importing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
BOKJIRO_API_KEY =  "82b26bbf4c159c48aeb0570892efdce9d3438cf0acf78b2cffd055952bd2ddba"
SUPABASE_URL = "https://ladqubaousblucmrqcrr.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhZHF1YmFvdXNibHVjbXJxY3JyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODgyNDI1MiwiZXhwIjoyMDg0NDAwMjUyfQ.YZfsje16TIRzEKI9N6WgH-49XH-VPqLJwqwp4LlwhxY"


# API Endpoints
# National Welfare Information List/Detail
LIST_API_URL = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
DETAIL_API_URL = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase credentials missing.")
        raise ValueError("Supabase credentials missing.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def safe_find_text(element, tag):
    """Helper to safely find text in XML element"""
    if element is None:
        return None
    found = element.find(tag)
    return found.text.strip() if found is not None and found.text else None

def fetch_national_welfare_list(page_no=1, num_of_rows=50):
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
            logger.error(f"Detail API Error for {serv_id}: {result_code} - {msg}")
            return None
            
        # The structure is usually different for detail
        # Assuming typical Bokjiro structure, but needs verification.
        # Based on local script experience, verify the root element for specific fields.
        return root 
    except Exception as e:
        logger.error(f"Failed to fetch detail for {serv_id}: {e}")
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
            .update({"is_active": False, "updated_at": "now()"}) \
            .eq("source_api", "NATIONAL") \
            .execute()
        logger.info("Reset complete.")
    except Exception as e:
        logger.error(f"Failed to reset active status: {e}")
        return

    # Step 2: Fetch and Update (Mark active if found)
    # Processing pages (National API usually has ~370 items, 100 per page = 4 pages)
    for page in range(1, 100): 
        logger.info(f"Fetching page {page}...")
        items = fetch_national_welfare_list(page_no=page, num_of_rows=100)
        
        if not items:
            logger.info("No more items found or error occurred.")
            break
            
        logger.info(f"Found {len(items)} items on page {page}.")
        
        success_count = 0
        for item in items:
            serv_id = safe_find_text(item, 'servId')
            serv_nm = safe_find_text(item, 'servNm')
            
            if not serv_id:
                continue
            
            # Extract fields from List Response (V001)
            serv_dtl_link = safe_find_text(item, 'servDtlLink')
            enfc_bgng_ymd = format_date(safe_find_text(item, 'svcfrstRegTs')) 
            
            # Contact & Dept Info
            dept_contact = safe_find_text(item, 'rprsCtadr')
            dept_name = safe_find_text(item, 'jurMnofNm') # Ministry name
            
            # Metadata
            inq_num = int(safe_find_text(item, 'inqNum') or 0)
            onap_psblt_yn = safe_find_text(item, 'onapPsbltYn')
            
            # Arrays (Comma separated strings in XML)
            def parse_array(val):
                return [x.strip() for x in val.split(',')] if val else []

            life_array = parse_array(safe_find_text(item, 'lifeArray'))
            life_nm_array = parse_array(safe_find_text(item, 'lifeNmArray'))
            intrs_thema_array = parse_array(safe_find_text(item, 'intrsThemaArray'))
            intrs_thema_nm_array = parse_array(safe_find_text(item, 'intrsThemaNmArray'))
            trgter_indvdl_array = parse_array(safe_find_text(item, 'trgterIndvdlArray'))
            trgter_indvdl_nm_array = parse_array(safe_find_text(item, 'trgterIndvdlNmArray'))

            detail_root = fetch_national_welfare_detail(serv_id)
            if not detail_root:
                logger.warning(f"Skipping {serv_id}: Failed to fetch details.")
                continue
            
            # Extract Detail Fields (V001)
            serv_digest = safe_find_text(detail_root, './/wlfareInfoOutlCn') or "" 
            tgt_info = safe_find_text(detail_root, './/tgtrDtlCn') or ""       
            slct_crit = safe_find_text(detail_root, './/slctCritCn') or ""     
            alw_serv_cn = safe_find_text(detail_root, './/alwServCn') or ""    
            
            # Helper to parse XML lists to JSON
            def parse_xml_list(root, parent_tag, child_tag, fields):
                results = []
                parent = root.find(f'.//{parent_tag}')
                if parent:
                    for child in parent.findall(child_tag):
                        data = {field: safe_find_text(child, field) for field in fields}
                        results.append(data)
                return json.dumps(results, ensure_ascii=False)

            # JSON Fields
            contact_info = parse_xml_list(detail_root, 'inqplCtadrList', 'inqplCtadr', ['servSeCode', 'servSeDetailLink', 'servSeDetailNm'])
            attachments = parse_xml_list(detail_root, 'basfrmList', 'basfrm', ['servSeCode', 'servSeDetailLink', 'servSeDetailNm'])
            base_laws = parse_xml_list(detail_root, 'baslawList', 'baslaw', ['servSeCode', 'servSeDetailNm'])
            related_links = parse_xml_list(detail_root, 'inqplHmpgReldList', 'inqplHmpgReld', ['servSeCode', 'servSeDetailLink', 'servSeDetailNm'])
            
            # Application Method (formatted text from list if available)
            # Some APIs provide explicit text, others list. Prioritize explicit text if exists, else format list.
            # V001 tends to have 'applmetList'. We can format it.
            # Or check if there is a text field like 'aplyMtdCn' (sometimes absent in V001).
            # We will use what's available.
            
            # Construct content for embedding
            content_blob = f"""
            서비스명: {serv_nm}
            대상: {tgt_info}
            선정기준: {slct_crit}
            내용: {alw_serv_cn}
            개요: {serv_digest}
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
                
                # Arrays
                "life_array": life_array,
                "life_nm_array": life_nm_array,
                "intrs_thema_array": intrs_thema_array,
                "intrs_thema_nm_array": intrs_thema_nm_array,
                "trgter_indvdl_array": trgter_indvdl_array,
                "trgter_indvdl_nm_array": trgter_indvdl_nm_array,
                
                # Details
                "serv_dgst": safe_find_text(item, 'servDgst'),
                "wlfare_info_outl_cn": serv_digest,
                "target_detail": tgt_info,
                "select_criteria": slct_crit,
                "service_content": alw_serv_cn,
                #"apply_method_detail": ... # format from list?
                "content_for_embedding": content_blob,
                
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
            try:
                supabase.table("benefits").upsert(db_data, on_conflict="serv_id").execute()
                success_count += 1
                logger.info(f"Saved {serv_nm}")
            except Exception as e:
                logger.error(f"Failed to upsert {serv_id}: {e}")
                
            time.sleep(0.05) # Rate limit
            
        logger.info(f"Page {page} complete. Saved {success_count} items.")

if __name__ == "__main__":
    main()
