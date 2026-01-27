import os
import sys
import json
import time
import logging
import hashlib
import random
from botocore.exceptions import ClientError
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
MAX_WORKERS = int(os.environ.get("EMBEDDING_MAX_WORKERS", "3"))

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

def get_bedrock_client():
    try:
        return boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock client: {e}")
        sys.exit(1)

def generate_embedding(bedrock, text):
    """
    Generate embedding using Amazon Titan Text Embeddings v2.
    """
    model_id = "amazon.titan-embed-text-v2:0"
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,
        "normalize": True
    })

    try:
        response = bedrock.invoke_model(
            body=body,
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get('body').read())
        return response_body['embedding']
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

def process_single_chunk(bedrock, supabase, benefit_id, serv_id, chunk_content, chunk_index):
    """
    Generate embedding for a single chunk and save to DB.
    """
    embedding = generate_embedding(bedrock, chunk_content)
    
    if embedding:
        data = {
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
    Summarize benefit information using Claude 3 Haiku.
    Returns markdown formatted string.
    """
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    
    # Prepare Input Data (Handle None values safely)
    def clean(val, default="정보 없음"):
        if val is None:
            return default
        s = str(val).strip()
        if not s or s.lower() == 'none' or s == '[]':
            return default
        return s

    ctpv = item_data.get('ctpv_nm')
    sgg = item_data.get('sgg_nm')
    location_raw = f"{ctpv or ''} {sgg or ''}".strip()
    location = location_raw if location_raw else "전국"
    
    serv_nm = clean(item_data.get('serv_nm'))
    sprt_cyc_nm = clean(item_data.get('sprt_cyc_nm'))
    srv_pvsn_nm = clean(item_data.get('srv_pvsn_nm'))
    aply_mtd_nm = clean(item_data.get('aply_mtd_nm'), "")
    
    trgter_indvdl_nm_array = clean(item_data.get('trgter_indvdl_nm_array'), "")
    life_nm_array = clean(item_data.get('life_nm_array'), "")
    target_detail = clean(item_data.get('target_detail'), "")
    select_criteria = clean(item_data.get('select_criteria'), "")
    
    intrs_thema_nm_array = clean(item_data.get('intrs_thema_nm_array'), "복지")
    
    # Combine content fields for richer context
    content_parts = []
    if item_data.get('serv_dgst'): content_parts.append(f"요약: {item_data.get('serv_dgst')}")
    if item_data.get('wlfare_info_outl_cn'): content_parts.append(f"개요: {item_data.get('wlfare_info_outl_cn')}")
    if item_data.get('service_content'): content_parts.append(f"상세: {item_data.get('service_content')}")
    
    service_content = "\n".join(content_parts) if content_parts else "상세 내용 참조"
    
    apply_method_detail = clean(item_data.get('apply_method_detail'), "")

    
    # Parse Contact Info
    contact_info_raw = item_data.get('contact_info')
    contact_list = []
    
    if contact_info_raw:
        try:
             # Handle multiple types (list of objects, json string, or single dict)
            contacts = []
            if isinstance(contact_info_raw, list):
                contacts = contact_info_raw
            elif isinstance(contact_info_raw, str):
                try:
                    parsed = json.loads(contact_info_raw)
                    contacts = parsed if isinstance(parsed, list) else [parsed]
                except:
                    # Maybe it's not JSON, just a string?
                    pass
            else:
                 contacts = [contact_info_raw]
            
            for c in contacts:
                # If c is still string (broken json?), skip
                if not isinstance(c, dict): 
                    continue

                # Type A: servSeDetailNm / servSeDetailLink
                name_a = c.get('servSeDetailNm')
                phone_a = c.get('servSeDetailLink')
                
                # Type B: wlfareInfoReldNm / wlfareInfoReldCn
                name_b = c.get('wlfareInfoReldNm')
                phone_b = c.get('wlfareInfoReldCn')
                
                name = name_a or name_b
                phone = phone_a or phone_b
                
                if name:
                    clean_name = str(name).strip()
                    clean_phone = str(phone).strip() if phone else "연락처 없음"
                    contact_list.append(f"{clean_name} ({clean_phone})")
                    
        except Exception as e:
            logger.warning(f"Failed to parse contact_info for {serv_nm}: {e}")

    contact_str = ", ".join(contact_list) if contact_list else "문의처 정보 없음"

    # Extract Period
    bgng = clean(item_data.get('enfc_bgng_ymd'), "")
    end = clean(item_data.get('enfc_end_ymd'), "")
    
    period_str = "정보 없음"
    if bgng or end:
        if end == '9999-12-31':
             period_str = f"{bgng} ~ (계속)" if bgng else "(계속)"
        elif bgng and end:
             period_str = f"{bgng} ~ {end}"
        elif bgng:
             period_str = f"{bgng} ~ (계속)"
        elif end:
             period_str = f"~ {end}"
    else:
        period_str = "별도 공지 / 상시"

    # --- 1. Prepare Content for LLM (Benefit Description ONLY) ---
    benefit_context_parts = []
    if item_data.get('serv_dgst'):
        benefit_context_parts.append(f"[서비스 요약]\n{item_data.get('serv_dgst')}")
    if item_data.get('wlfare_info_outl_cn'):
        benefit_context_parts.append(f"[복지정보 개요]\n{item_data.get('wlfare_info_outl_cn')}")
    if item_data.get('service_content'):
        benefit_context_parts.append(f"[상세 내용]\n{item_data.get('service_content')}")
    
    benefit_raw_text = "\n\n".join(benefit_context_parts)
    
    # If there is absolutely no content, provide a fallback
    if not benefit_raw_text.strip():
        benefit_summary = "상세 지원 내용이 공고에 명시되지 않았습니다. 문의처를 통해 확인해주세요."
    else:
        # LLM Call - Just for Benefit Synthesis
        system_prompt = """당신은 복지 혜택의 다양한 상세 설명들을 종합하여, 명확하고 이해하기 쉬운 핵심 '지원 내용'으로 요약하는 전문가입니다.
중복된 내용을 제거하고, 사용자가 '어떤 서비스이며, 어떤 혜택을 받을 수 있는지' 바로 알 수 있도록 자연스러운 문장으로 정리하세요.
대상 자격이나 신청 방법은 언급하지 마세요. 오직 '어떤 서비스 이고, 어떤 혜택 자체'에만 집중하세요.
"""
        user_message = f"""다음 혜택의 내용을 요약해줘:

[서비스명]: {serv_nm}

{benefit_raw_text}
"""
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000, # Reduced tokens
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
            "temperature": 0.0
        })

        # LLM Call - Just for Benefit Synthesis
        max_llm_retries = 15
        llm_retry_delay = 3
        benefit_summary = None

        for llm_attempt in range(max_llm_retries):
            try:
                response = bedrock.invoke_model(
                    body=body,
                    modelId=model_id,
                    accept="application/json",
                    contentType="application/json"
                )
                response_body = json.loads(response.get('body').read())
                benefit_summary = response_body['content'][0]['text']
                break # Success
            except Exception as e:
                is_last_llm_attempt = (llm_attempt == max_llm_retries - 1)
                if is_last_llm_attempt:
                    logger.error(f"LLM Summarization failed for {item_data.get('serv_nm')} after {max_llm_retries} attempts: {e}")
                    benefit_summary = benefit_raw_text[:1000] # Fallback
                else:
                    # Exponential backoff for LLM call
                    sleep_time = (llm_retry_delay * (2 ** llm_attempt)) + random.uniform(0, 1)
                    time.sleep(sleep_time)
            
    # --- 2. Construct Final Document Programmatically ---
    
    # Section 1: Target
    # Combine array fields and text fields
    target_info_parts = []
    target_info_parts.append(f"- **대상**: {trgter_indvdl_nm_array} {life_nm_array}")
    target_info_parts.append(f"- **지역**: {location}")
    target_info_parts.append(f"- **기간**: {period_str}")
    
    target_info_parts.append(f"- **지원대상 상세**: {target_detail}")
    target_info_parts.append(f"- **선정기준**: {select_criteria}")
        
    target_section = "\n".join(target_info_parts)

    # Section 3: Apply
    apply_info_parts = []
    apply_info_parts.append(f"- **방법**: {aply_mtd_nm}")
    apply_info_parts.append(f"- **문의**: {contact_str}")
        
    if apply_method_detail != "":
        apply_info_parts.append(f"- **신청방법 상세**: {apply_method_detail}")
        
    apply_section = "\n".join(apply_info_parts)

    # Final Assembly
    final_document = f"""# {serv_nm}

# 1. 🎯 지원 대상 및 조건
{target_section}

# 2. 🎁 혜택 내용
[{intrs_thema_nm_array}]
- **제공유형**: {srv_pvsn_nm} 
- **지원주기**: {sprt_cyc_nm}
- **내용**:
{benefit_summary}

# 3. 📝 신청 및 이용 방법
{apply_section}
"""

    return final_document

def process_summary_and_update(bedrock, supabase, benefit):
    """
    Helper function to summarize a single benefit and update DB.
    Returns (benefit_id, new_content, new_hash) if successful, else (benefit_id, None, None).
    """
    benefit_id = benefit['id']
    serv_id = benefit['serv_id']
    
    max_retries = 8
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            # Generate Summary
            summary = summarize_with_haiku(bedrock, benefit)
            #print(summary)
            
            # Append Link
            serv_dtl_link = benefit.get('serv_dtl_link')
            if serv_dtl_link:
                summary = f"{summary}\n\n# 4. 🌐 상세 보기 (공식 공고)\n- [복지로 공고문 바로가기]({serv_dtl_link})"
            else:
                 summary = f"{summary}\n\n# 4. 🌐 상세 보기 (공식 공고)\n- 링크 정보 없음"

            # Update content in DB
            # We save the SOURCE hash as 'content_hash' so we know this version of source data is processed.
            source_hash = compute_source_hash(benefit)
            
            supabase.table("benefits").update({
                "content_for_embedding": summary
                # content_hash update is deferred to ensuring atomicity
            }).eq("id", benefit_id).execute()
            
            return benefit_id, summary, source_hash
            
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
    bedrock = get_bedrock_client()
    
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
                    executor.submit(process_summary_and_update, bedrock, supabase, b) 
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
                    futures.append(executor.submit(process_single_chunk, bedrock, supabase, *task))
                
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
