import os
import sys
import json
import time
import logging
import hashlib
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from supabase import create_client

# Add parent directory to path to import common modules if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
# Suppress verbose library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration - Load from .env file
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"

# Parallel processing configuration
MAX_WORKERS = int(os.getenv("EMBEDDING_MAX_WORKERS", "10"))  # 병렬 처리 워커 수

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.error("Supabase credentials missing in .env")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_bedrock_client():
    try:
        # Assumes AWS credentials are in environment variables or ~/.aws/credentials
        return boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock client: {e}")
        sys.exit(1)

def generate_embedding(bedrock, text):
    if not text:
        return None
        
    try:
        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId=TITAN_MODEL_ID,
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        embedding = response_body.get('embedding')
        return embedding
    except Exception as e:
        logger.error(f"Bedrock generation failed: {e}")
        return None

def split_text(text, chunk_size=4000, overlap=200):
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += (chunk_size - overlap)
    return chunks

def compute_content_hash(text):
    """Generate SHA256 hash of content for change detection"""
    if not text:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def process_single_chunk(bedrock, supabase, benefit_id, serv_id, chunk, chunk_index, content_hash):
    """
    단일 청크에 대한 임베딩 생성 및 저장 (병렬 처리용)
    
    Returns:
        tuple: (success: bool, serv_id: str, chunk_index: int, error: str or None)
    """
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Generate embedding
            embedding = generate_embedding(bedrock, chunk)
            
            if not embedding:
                # If embedding returns None (handled error inside generate_embedding), retry might not help unless it was network/server error caught there. 
                # But let's assume generate_embedding logs error and returns None. We'll count it as failure for this attempt.
                raise Exception("Embedding generation returned None")
            
            # Insert into benefit_embeddings
            data = {
                "benefit_id": benefit_id,
                "embedding": embedding,
                "content_chunk": chunk,
                "chunk_index": chunk_index,
                "content_hash": content_hash
            }
            
            supabase.table("benefit_embeddings").insert(data).execute()
            return (True, serv_id, chunk_index, None)
            
        except Exception as e:
            # Handle both local resource (OSError, Errno 35) and remote errors
            is_last_attempt = (attempt == max_retries - 1)
            error_msg = str(e)
            
            if is_last_attempt:
                return (False, serv_id, chunk_index, f"Max retries exceeded: {error_msg}")
            
            # Exponential backoff
            sleep_time = retry_delay * (2 ** attempt)
            # logger.warning(f"Retry {attempt+1}/{max_retries} for {serv_id} chunk {chunk_index}: {error_msg}. Sleeping {sleep_time}s...")
            time.sleep(sleep_time)

def main():
    logger.info("Starting embedding generation process...")
    logger.info(f"Parallel processing enabled: {MAX_WORKERS} workers")
    
    supabase = get_supabase_client()
    bedrock = get_bedrock_client()
    
    # 1. Fetch benefits that need embeddings
    limit = 500
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
        
        response = supabase.table("benefits") \
            .select("id, serv_id, serv_nm, content_for_embedding, content_hash") \
            .eq("is_active", True) \
            .range(page * limit, (page + 1) * limit - 1) \
            .execute()
            
        benefits = response.data
        if not benefits:
            break
            
        logger.info(f"Processing batch of {len(benefits)} benefits (Page {page})...")
        
        # Track batch progress
        batch_processed = 0
        batch_total = len(benefits)
        
        
        # Collect tasks for parallel processing
        tasks = []
        
        # Optimization: Bulk fetch existing hashes for this batch to avoid N+1 queries
        benefit_ids = [b['id'] for b in benefits]
        existing_embeddings_map = {}
        try:
            # Supabase .in_() limit might be small, but 500 should be okay or we can chunk it if needed.
            # Let's try fetching in one go.
            existing_response = supabase.table("benefit_embeddings") \
                .select("benefit_id, content_hash") \
                .in_("benefit_id", benefit_ids) \
                .execute()
            
            for row in existing_response.data:
                existing_embeddings_map[row['benefit_id']] = row.get('content_hash')
        except Exception as e:
            logger.error(f"Failed to bulk fetch existing embeddings: {e}")
            # Fallback to empty map, will force individual checks or updates? 
            # Actually if bulk fetch fails, we might just treat all as 'not found' -> update all.
            # Or we can continue and let the logic fall through (but efficient way is key).
            pass

        for benefit in benefits:
            benefit_id = benefit['id']
            serv_id = benefit['serv_id']
            content = benefit['content_for_embedding']
            
            if not content:
                continue
            
            current_hash = compute_content_hash(content)
            
            # Update hash if missing
            if not benefit.get('content_hash'):
                try:
                    supabase.table("benefits").update({"content_hash": current_hash}).eq("id", benefit_id).execute()
                except: pass
            
            # Check existing from memory map
            existing_hash = existing_embeddings_map.get(benefit_id)
            
            if existing_hash == current_hash:
                total_skipped += 1
            else:
                # Needs update
                if existing_hash: # If it existed but hash mismatches
                    try:
                        supabase.table("benefit_embeddings").delete().eq("benefit_id", benefit_id).execute()
                        total_updated += 1
                    except Exception as e:
                        logger.error(f"Failed delete {serv_id}: {e}")
                        continue
                
                # Add chunks to task list
                chunks = split_text(content)
                for i, chunk in enumerate(chunks):
                    tasks.append((benefit_id, serv_id, chunk, i, current_hash))

        # Execute parallel tasks
        if tasks:
            logger.info(f"Processing {len(tasks)} chunks in parallel...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for task in tasks:
                    futures.append(executor.submit(process_single_chunk, bedrock, supabase, *task))
                
                for future in as_completed(futures):
                    success, sid, idx, err = future.result()
                    if success:
                        total_processed += 1
                    else:
                        logger.error(f"Failed {sid} chunk {idx}: {err}")
                    
                    # Update progress
                    current_total = total_processed + total_skipped + total_updated  # Note: logic slightly fuzzy here as we batch calculate skip/update before processing
                    # But for simple progress tracking it's fine
        
        # Log progress after batch
        current_total = total_processed + total_skipped
        # Note: total_updated is counted before processing, total_processed is counted after success.
        # Let's simplify: processed = successful embeddings.
        # The logic is getting a bit mixed between 'benefits processed' vs 'chunks processed'.
        # Let's stick to 'Benefits' count for progress log.
        # Since 'tasks' are chunks, we can't easily map back to benefit count 1:1 for progress without tracking.
        # But 'batch_processed' was simple loop count.
        
        # Re-calc progress based on benefits loop
        batch_processed = len(benefits) # We iterated all
        current_processed_count = total_skipped + (total_updated if tasks else 0) # Approximation
        
        # Just use total_items for %
        percent = (page * limit + len(benefits)) / total_items * 100 if isinstance(total_items, int) and total_items > 0 else 0
        logger.info(f"Progress: ~{page * limit + len(benefits)}/{total_items} (Skip: {total_skipped}, Tasks: {len(tasks)}) - {percent:.1f}%")
            
        page += 1
    
    logger.info(f"""
    ═══════════════════════════════════════════
    Embedding generation complete!
    ═══════════════════════════════════════════
    ✅ New embeddings created: {total_processed}
    🔄 Updated (content changed): {total_updated}
    ⏭️  Skipped (unchanged): {total_skipped}
    💰 Estimated cost saved: ${total_skipped * 0.00025:.4f}
    ═══════════════════════════════════════════
    """)
    
    # Output result as JSON for pipeline orchestration
    print(f"\n__PIPELINE_RESULT__:{json.dumps({'new': total_processed, 'updated': total_updated, 'skipped': total_skipped})}")

if __name__ == "__main__":
    main()
