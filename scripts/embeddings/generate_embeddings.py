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
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration - Load from .env file
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"

# Parallel processing configuration
MAX_WORKERS = int(os.getenv("EMBEDDING_MAX_WORKERS", "5"))  # 병렬 처리 워커 수

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
    try:
        # Generate embedding
        embedding = generate_embedding(bedrock, chunk)
        
        if not embedding:
            return (False, serv_id, chunk_index, "Failed to generate embedding")
        
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
        return (False, serv_id, chunk_index, str(e))

def main():
    logger.info("Starting embedding generation process...")
    logger.info(f"Parallel processing enabled: {MAX_WORKERS} workers")
    
    supabase = get_supabase_client()
    bedrock = get_bedrock_client()
    
    # 1. Fetch benefits that need embeddings
    limit = 100
    page = 0
    total_processed = 0
    total_skipped = 0
    total_updated = 0
    
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
            
        logger.info(f"Processing {len(benefits)} benefits...")
        
        for benefit in benefits:
            benefit_id = benefit['id']
            serv_id = benefit['serv_id']
            content = benefit['content_for_embedding']
            
            if not content:
                logger.warning(f"Skipping {serv_id}: No content for embedding.")
                continue
            
            # Compute current content hash
            current_hash = compute_content_hash(content)
            
            # Update content_hash in benefits table if missing
            if not benefit.get('content_hash'):
                try:
                    supabase.table("benefits") \
                        .update({"content_hash": current_hash}) \
                        .eq("id", benefit_id) \
                        .execute()
                except Exception as e:
                    logger.warning(f"Failed to update content_hash for {serv_id}: {e}")
            
            # Check if embedding already exists with same content_hash
            existing = supabase.table("benefit_embeddings") \
                .select("id, content_hash") \
                .eq("benefit_id", benefit_id) \
                .limit(1) \
                .execute()
            
            if existing.data:
                existing_hash = existing.data[0].get('content_hash')
                
                # If content hasn't changed, skip
                if existing_hash == current_hash:
                    logger.info(f"✓ Skipping {serv_id}: Embedding up-to-date (hash match)")
                    total_skipped += 1
                    continue
                else:
                    # Content changed - delete old embeddings
                    logger.info(f"🔄 Content changed for {serv_id}, regenerating embeddings...")
                    try:
                        supabase.table("benefit_embeddings") \
                            .delete() \
                            .eq("benefit_id", benefit_id) \
                            .execute()
                        total_updated += 1
                    except Exception as e:
                        logger.error(f"Failed to delete old embeddings for {serv_id}: {e}")
                        continue
            
            logger.info(f"Processing {serv_id} ({benefit['serv_nm']})...")
            
            chunks = split_text(content)
            
            # 병렬 처리: 모든 청크를 동시에 처리
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Submit all chunks for parallel processing
                futures = []
                for i, chunk in enumerate(chunks):
                    future = executor.submit(
                        process_single_chunk,
                        bedrock,
                        supabase,
                        benefit_id,
                        serv_id,
                        chunk,
                        i,
                        current_hash
                    )
                    futures.append(future)
                
                # Collect results
                for future in as_completed(futures):
                    success, serv_id_result, chunk_idx, error = future.result()
                    if success:
                        logger.info(f"✓ Saved embedding for {serv_id_result} chunk {chunk_idx}")
                        total_processed += 1
                    else:
                        logger.error(f"✗ Failed for {serv_id_result} chunk {chunk_idx}: {error}")
            
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
