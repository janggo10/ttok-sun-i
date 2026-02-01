import os
import sys
import json
import time
import logging
import hashlib
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_WORKERS = int(os.environ.get("EMBEDDING_MAX_WORKERS", "20"))

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Suppress noisy library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase credentials missing.")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_openai_client():
    """Initialize OpenAI client"""
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        sys.exit(1)

def generate_embedding(openai_client, text):
    """
    Generate embedding using OpenAI text-embedding-3-small.
    """
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=1536
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None

def split_text(text, max_length=4000, overlap=200):
    """
    Simple text splitter with overlap.
    Titav v2 supports up to 8k tokens, but smaller chunks (512-1024 chars) usually work better for RAG.
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + max_length
        chunk = text[start:end]
        chunks.append(chunk)
        start += (max_length - overlap)
    
    return chunks

def compute_content_hash(content):
    """
    Compute SHA-256 hash of valid content.
    Returns None if content is empty/invalid.
    """
    if not content or str(content).strip() == "":
        return None
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def process_single_chunk(openai_client, supabase, benefit_id, serv_id, chunk_content, chunk_index):
    """
    Generate embedding for a single chunk and save to DB.
    """
    embedding = generate_embedding(openai_client, chunk_content)
    
    if embedding:
        data = {
            "category": "WELFARE",  # 복지 전용 ⭐
            "benefit_id": benefit_id,
            # "serv_id": serv_id, # Column does not exist in benefit_embeddings table
            "content_chunk": chunk_content, # Correct column name: content_chunk
            "chunk_index": chunk_index,
            "embedding": embedding
        }
        
        # Retry logic for DB insert
        max_retries = 3
        for attempt in range(max_retries):
            try:
                supabase.table("benefit_embeddings").insert(data).execute()
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"DB Insert failed for {serv_id} chunk {chunk_index} (Attempt {attempt+1}): {e}")
                time.sleep(1)
                
    return False

def compute_source_hash(item):
    """
    Compute a consistent hash from the raw source fields used for summarization.
    This hash triggers a re-summarization if any of these fields change.
    """
    def clean_str(val):
        if val is None: return ""
        return str(val).strip()

    # Fields used in summarize_with_haiku
    fields = [
        item.get('serv_nm'),
        item.get('ctpv_nm'),
        item.get('sgg_nm'),
        item.get('sprt_cyc_nm'),
        item.get('srv_pvsn_nm'),
        item.get('aply_mtd_nm'),
        item.get('trgter_indvdl_nm_array'),
        item.get('life_nm_array'),
        item.get('target_detail'),
        item.get('select_criteria'),
        item.get('intrs_thema_nm_array'),
        item.get('service_content'),
        item.get('serv_dgst'),
        item.get('wlfare_info_outl_cn'),
        item.get('apply_method_detail'),
        item.get('enfc_bgng_ymd'),
        item.get('enfc_end_ymd'),
        str(item.get('contact_info')) # Convert dict/list/json to string
    ]
    
    raw_str = "|".join([clean_str(f) for f in fields])
    return compute_content_hash(raw_str)


def summarize_with_haiku(bedrock, item_data):
    """
    Create embedding content by combining original fields WITHOUT LLM.
    Returns plain text (no markup, no emojis) for optimal embedding quality.
    
    ⚠️ 함수명은 호환성을 위해 유지하지만, 이제 LLM을 사용하지 않습니다.
    """
    # Prepare Input Data (Handle None values safely)
    def clean(val, default=""):
        if val is None:
            return default
        s = str(val).strip()
        if not s or s.lower() == 'none' or s == '[]':
            return default
        return s

    # ============================================
    # Option A: 최소한 필드만 임베딩 (핵심 서비스 내용)
    # ============================================
    # 포함: 서비스명, 요약, 지원내용, 개요, 제공유형, 지원주기, 신청방법, 신청절차
    # 제외: 지역, 생애주기, 대상특성, 기간, 주제 (DB 필터링으로 처리)
    # 
    # 효과:
    # - 임베딩 토큰 50% 감소 (비용 절감)
    # - 검색 품질 유지 (핵심만 포함)
    # - 가독성 향상 (중복 제거)
    # ============================================
    
    parts = []
    
    # 1. 서비스명 (필수)
    serv_nm = clean(item_data.get('serv_nm'))
    if serv_nm:
        parts.append(f"서비스명: {serv_nm}")
    
    # 2. 서비스 요약 (이미 요약됨! - 가장 중요)
    serv_dgst = clean(item_data.get('serv_dgst'))
    if serv_dgst:
        parts.append(f"요약: {serv_dgst}")
    
    # 3. 복지정보 개요 (중앙부처만)
    wlfare_info = clean(item_data.get('wlfare_info_outl_cn'))
    if wlfare_info:
        parts.append(f"개요: {wlfare_info}")
    
    # 4. 상세 내용 (핵심! - 구체적 금액, 조건 등)
    service_content = clean(item_data.get('service_content'))
    if service_content:
        parts.append(f"지원내용: {service_content}")
    
    # 5. 제공유형 (사용자 검색 패턴: "현금", "카드")
    srv_pvsn = clean(item_data.get('srv_pvsn_nm'))
    if srv_pvsn:
        parts.append(f"제공유형: {srv_pvsn}")
    
    # 6. 지원주기 (사용자 검색 패턴: "매월", "1회성")
    sprt_cyc = clean(item_data.get('sprt_cyc_nm'))
    if sprt_cyc:
        parts.append(f"지원주기: {sprt_cyc}")
    
    # 7. 신청방법 (사용자 검색 패턴: "온라인", "방문")
    apply_method = clean(item_data.get('aply_mtd_nm'))
    if apply_method:
        parts.append(f"신청방법: {apply_method}")
    
    # 8. 신청절차 (구체적 방법: "정부24", "행정복지센터")
    apply_method_detail = clean(item_data.get('apply_method_detail'))
    if apply_method_detail:
        parts.append(f"신청절차: {apply_method_detail}")
    
    # ============================================
    # 최종 결합 (순수 텍스트, 줄바꿈으로 구분)
    # - 임베딩 품질: 약간 향상 (구조화된 정보 인식)
    # - 가독성: 대폭 향상 (디버깅/검증 시 편리)
    # ============================================
    final_content = "\n".join(parts)
    
    # Fallback
    if not final_content.strip():
        final_content = f"서비스명: {item_data.get('serv_nm', '정보없음')}"
    
    return final_content

def process_summary_and_update(supabase, benefit):
    """
    Helper function to create embedding content and update DB.
    Returns (benefit_id, new_content, new_hash) if successful, else (benefit_id, None, None).
    
    ⚠️ bedrock 파라미터 제거됨 - 더 이상 LLM 사용 안 함
    """
    benefit_id = benefit['id']
    serv_id = benefit['serv_id']
    
    max_retries = 8
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            # Create embedding content (no LLM, just plain text combination)
            content = summarize_with_haiku(None, benefit)  # bedrock 사용 안 함

            # Update content in DB
            # We save the SOURCE hash as 'content_hash' so we know this version of source data is processed.
            source_hash = compute_source_hash(benefit)
            
            supabase.table("benefits").update({
                "content_for_embedding": content
                # content_hash update is deferred to ensuring atomicity
            }).eq("id", benefit_id).execute()
            
            return benefit_id, content, source_hash
            
        except Exception as e:
            is_last_attempt = (attempt == max_retries - 1)
            error_msg = str(e)
            
            if is_last_attempt:
                logger.error(f"Failed to update summary for {serv_id} after {max_retries} attempts: {e}")
                return benefit_id, None, None
            
            # Exponential backoff with jitter
            sleep_time = (retry_delay * (2 ** attempt)) + random.uniform(0, 1)
            # logger.warning(f"Summarization retry {attempt+1}/{max_retries} for {serv_id}: {error_msg}. Sleeping {sleep_time:.2f}s...")
            time.sleep(sleep_time)
            
    return benefit_id, None, None

def main():
    logger.info("Starting embedding generation process...")
    logger.info(f"Parallel processing enabled: {MAX_WORKERS} workers")
    
    supabase = get_supabase_client()
    openai_client = get_openai_client()
    
    # 1. Fetch benefits that need embeddings
    limit = 50 # Reduced for better feedback and safety
    page = 0
    total_processed = 0
    total_skipped = 0
    total_updated = 0
    
    # Get total count for progress reporting
    try:
        count_response = supabase.table("benefits").select("id", count="exact").eq("is_active", True).execute()
        total_items = count_response.count
        logger.info(f"Total active benefits to process: {total_items}")
    except Exception as e:
        total_items = "Unknown"
        logger.warning(f"Failed to get total count: {e}")
    
    while True:
        logger.info(f"Fetching page {page} (limit {limit})...")
        
        # Select all necessary columns for LLM summarization
        response = supabase.table("benefits") \
            .select("id, serv_id, serv_nm, content_for_embedding, content_hash, ctpv_nm, sgg_nm, sprt_cyc_nm, srv_pvsn_nm, aply_mtd_nm, trgter_indvdl_nm_array, life_nm_array, target_detail, select_criteria, intrs_thema_nm_array, service_content, serv_dgst, wlfare_info_outl_cn, apply_method_detail, serv_dtl_link, enfc_bgng_ymd, enfc_end_ymd, contact_info") \
            .eq("is_active", True) \
            .range(page * limit, (page + 1) * limit - 1) \
            .execute()
            
        benefits = response.data
        if not benefits:
            break
            
        logger.info(f"Processing batch of {len(benefits)} benefits (Page {page})...")
        
        # [Phase 1] Smart Processing (Hash-based Skip)
        # Only process items where content_hash has changed (or is missing).
        # Since DB hashes will be cleared, this will process everything once, then skip unchanged items later.
        benefits_to_summarize = []
        benefits_map = {b['id']: b for b in benefits}
        
        for benefit in benefits:
            # 1. Compute Hash from SOURCE
            current_source_hash = compute_source_hash(benefit)
            stored_hash = benefit.get('content_hash')
            
            # 2. Check if we can skip
            if stored_hash and current_source_hash == stored_hash:
                total_skipped += 1
                continue
                
            benefits_to_summarize.append(benefit)
            
        if benefits_to_summarize:
            logger.info(f"Queued {len(benefits_to_summarize)} items for processing (Skipped {len(benefits) - len(benefits_to_summarize)} items)...")
            
        failed_summarization_ids = set()
        updated_benefit_hashes = {} # Map benefit_id -> new_source_hash

        print(f"benefits_to_summarize: {len(benefits_to_summarize)}")
        if benefits_to_summarize:
            logger.info(f"Summarizing {len(benefits_to_summarize)} benefits (Source Changed)...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [
                    executor.submit(process_summary_and_update, supabase, b) 
                    for b in benefits_to_summarize
                ]
                
                summarized_count = 0
                for future in as_completed(futures):
                    bid, new_content, new_hash = future.result()
                    summarized_count += 1
                    if summarized_count % 10 == 0:
                        logger.info(f"  - Summarized {summarized_count}/{len(benefits_to_summarize)} items...")
                    if new_content:
                        #print(f"new_content: {new_content}")
                        # Update local memory so embedding step uses the new content
                        benefits_map[bid]['content_for_embedding'] = new_content
                        benefits_map[bid]['content_hash'] = new_hash
                        updated_benefit_hashes[bid] = new_hash
                    else:
                        failed_summarization_ids.add(bid)

        # [Phase 2] Embedding Generation
        # We process ONLY the items that were successfully summarized/updated.
        
        tasks = []
        
        for benefit in benefits_to_summarize:
            benefit_id = benefit['id']
            
            # Check if summarization succeeded
            if benefit_id in failed_summarization_ids:
                logger.warning(f"Skipping embedding for {benefit['serv_nm']} (Summarization Failed)")
                continue

            # It must have been updated if it's not in failed list (logic check)
            effective_hash = updated_benefit_hashes.get(benefit_id)
            if not effective_hash:
                 # Should not happen if logic is correct
                 continue

            # Proceed to embedding
            content = benefits_map[benefit_id].get('content_for_embedding')
            if not content: continue
            
            serv_id = benefit['serv_id']
            
            # Delete old embeddings (since source changed)
            try:
                supabase.table("benefit_embeddings").delete().eq("benefit_id", benefit_id).execute()
                total_updated += 1
            except Exception as e:
                logger.error(f"Failed delete embeddings for {serv_id}: {e}")
                continue
            
            # Add chunks
            chunks = split_text(content)
            for i, chunk in enumerate(chunks):
                tasks.append((benefit_id, serv_id, chunk, i))

        # Execute parallel tasks
        if tasks:
            logger.info(f"Processing {len(tasks)} chunks in parallel...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for task in tasks:
                    futures.append(executor.submit(process_single_chunk, openai_client, supabase, *task))
                
                for future in as_completed(futures):
                    if future.result():
                        total_processed += 1

        # [Safety] Commit Hashes after Embedding
        # This prevents Zombie records if script crashes between Summary and Embedding phases.
        if updated_benefit_hashes:
            logger.info(f"Committing hashes for {len(updated_benefit_hashes)} processed benefits...")
            for bid, h in updated_benefit_hashes.items():
                try:
                    supabase.table("benefits").update({"content_hash": h}).eq("id", bid).execute()
                except Exception as e:
                    logger.error(f"Hash commit failed for {bid}: {e}")

        page += 1

    logger.info("Embedding generation completed!")
    logger.info(f"Total processed chunks: {total_processed}")
    logger.info(f"Total updated benefits: {total_updated}")
    logger.info(f"Total skipped benefits (Hash Match): {total_skipped}")

if __name__ == "__main__":
    main()
