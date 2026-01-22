import os
import sys
import logging
import json
import hashlib
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

# Configuration - Load from .env file
BOKJIRO_API_KEY = os.getenv("BOKJIRO_API_KEY")
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

def compute_content_hash(text):
    """Generate SHA256 hash of content for embedding change detection"""
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def fetch_welfare_list(ctpv_nm, page_no=1, num_of_rows=1000):
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
            result_code = root.findtext('.//resultCode')
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
    
    total_items_fetched = 0
    total_success_count = 0
    total_failed_count = 0
    
    for ctpv in ctpv_list:
        logger.info(f"Fetching welfare list for {ctpv}...")
        
        # Pagination for each ctpv - continue until no more data
        ctpv_items = []
        page = 1
        while True:
            welfare_items = fetch_welfare_list(ctpv, page_no=page, num_of_rows=1000)
            if not welfare_items:
                logger.info(f"  {ctpv} - Completed at page {page}.")
                break
            
            ctpv_items.extend(welfare_items)
            
            # If less than 1000 items, it's the last page
            if len(welfare_items) < 1000:
                logger.info(f"  {ctpv} - Last page (page {page}, {len(welfare_items)} items).")
                break
            
            page += 1
        
        logger.info(f"Found {len(ctpv_items)} items in {ctpv}.")
        total_items_fetched += len(ctpv_items)
        
        for item in ctpv_items:
            # 1. Extract basic info from list
            serv_id = safe_find_text(item, 'servId')
            serv_nm = safe_find_text(item, 'servNm')
            
            if not serv_id or not serv_nm:
                logger.warning(f"Skipping item without servId or servNm")
                continue
            
            # 2. Fetch detail
            detail = fetch_welfare_detail(serv_id)
            if not detail:
                logger.warning(f"Skipping {serv_id}: Failed to fetch details.")
                continue
            
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
            aply_mtd_nm = safe_find_text(item, 'aplyMtdNm')  # 또는 aplYMtdNm
            
            # 상세 API에 있으면 덮어쓰기
            if safe_find_text(detail, 'sprtCycNm'):
                sprt_cyc_nm = safe_find_text(detail, 'sprtCycNm')
            if safe_find_text(detail, 'srvPvsnNm'):
                srv_pvsn_nm = safe_find_text(detail, 'srvPvsnNm')
            if safe_find_text(detail, 'aplyMtdNm'):
                aply_mtd_nm = safe_find_text(detail, 'aplyMtdNm')
            
            # 5. Helper to parse XML lists to JSON
            # Note: XML 구조가 3가지 형태일 수 있음:
            # 형태1: <parent><field>value</field></parent> (단일 항목)
            # 형태2: <parent><child><field>value</field></child></parent> (단일 항목, child 있음)
            # 형태3: <parent>...</parent><parent>...</parent> (다중 항목, 형제 노드로 반복)
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
            
            # 6. Parse JSON fields (wlfareInfoDtlCd 제거)
            # ⚠️ 주의: 지자체 API는 필드명이 다름! (중앙: servSeDetail*, 지자체: wlfareInfoReld*)
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
                    # 지자체 API 필드명: wlfareInfoReldCn, wlfareInfoReldNm
                    link = contact.get('wlfareInfoReldCn', '')  # 연락처/URL
                    name = contact.get('wlfareInfoReldNm', '')  # 담당부서명/설명
                    if name and link:
                        contact_parts.append(f"{name}: {link}")
                    elif link:
                        contact_parts.append(link)
                    elif name:
                        contact_parts.append(name)
                if contact_parts:
                    contact_text = f"문의처: {', '.join(contact_parts)}"
            
            # 7. Construct content_for_embedding
            content_for_embedding = "\n".join(filter(None, [
                f"서비스명: {serv_nm}",
                f"개요: {safe_find_text(detail, 'servDgst') or ''}",
                f"대상: {trgt_detail}",
                f"기준: {slct_detail}",
                f"내용: {serv_content}",
                f"방법: {aply_detail}",
                contact_text,  # 이미 "문의처: ..." 형식
                f"상세링크: {safe_find_text(item, 'servDtlLink')}"
            ]))
            
            # 8. Construct cleaned_data
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
                "content_hash": compute_content_hash(content_for_embedding),  # 임베딩 변경 감지용
                
                "contact_info": contact_info,
                "base_laws": base_laws,
                "attachments": attachments,
                "related_links": related_links,
                
                "inq_num": int(safe_find_text(detail, 'inqNum') or 0),
                "is_active": True,
                "updated_at": datetime.now().isoformat()
            }
            
            # 9. Upsert to Supabase
            try:
                result = supabase.table("benefits").upsert(cleaned_data, on_conflict="serv_id").execute()
                logger.info(f"Saved {serv_id}: {serv_nm}")
                total_success_count += 1
            except Exception as e:
                logger.error(f"Failed to save {serv_id}: {e}")
                total_failed_count += 1

    # Final Summary
    logger.info("")
    logger.info("="*60)
    logger.info("지자체 복지 데이터 수집 완료")
    logger.info("="*60)
    logger.info(f"총 조회: {total_items_fetched}건")
    logger.info(f"성공: {total_success_count}건")
    logger.info(f"실패: {total_failed_count}건")
    logger.info("="*60)
    
    # Output result as JSON for pipeline orchestration
    print(f"\n__PIPELINE_RESULT__:{json.dumps({'total': total_items_fetched, 'success': total_success_count, 'failed': total_failed_count})}")

if __name__ == "__main__":
    main()
