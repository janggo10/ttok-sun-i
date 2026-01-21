import os
import sys
import json
import time
import logging
import boto3
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

# Configuration
SUPABASE_URL = "https://ladqubaousblucmrqcrr.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhZHF1YmFvdXNibHVjbXJxY3JyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODgyNDI1MiwiZXhwIjoyMDg0NDAwMjUyfQ.YZfsje16TIRzEKI9N6WgH-49XH-VPqLJwqwp4LlwhxY"
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"

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

def main():
    logger.info("Starting embedding generation process...")
    
    supabase = get_supabase_client()
    bedrock = get_bedrock_client()
    
    # 1. Fetch benefits that need embeddings
    limit = 100
    page = 0
    total_processed = 0
    
    while True:
        logger.info(f"Fetching page {page} (limit {limit})...")
        
        response = supabase.table("benefits") \
            .select("id, serv_id, serv_nm, content_for_embedding") \
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
                
            # Check if embedding already exists
            existing = supabase.table("benefit_embeddings") \
                .select("id") \
                .eq("benefit_id", benefit_id) \
                .limit(1) \
                .execute()
                
            if existing.data:
                logger.info(f"Skipping {serv_id}: Embedding already exists.")
                continue
            
            logger.info(f"Processing {serv_id} ({benefit['serv_nm']})...")
            
            chunks = split_text(content)
            
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = generate_embedding(bedrock, chunk)
                
                if not embedding:
                    logger.error(f"Failed to generate embedding for {serv_id} chunk {i}")
                    continue

                # Insert into benefit_embeddings
                data = {
                    "benefit_id": benefit_id,
                    "embedding": embedding,
                    "content_chunk": chunk,
                    "chunk_index": i
                }
                
                try:
                    supabase.table("benefit_embeddings").insert(data).execute()
                    logger.info(f"Saved embedding for {serv_id} chunk {i}")
                    total_processed += 1
                except Exception as e:
                    logger.error(f"Failed to save embedding for {serv_id} chunk {i}: {e}")
            
                # Rate limiting precaution
                time.sleep(0.1)
            
        page += 1
        
    logger.info(f"Embedding generation complete. Processed {total_processed} new embeddings.")

if __name__ == "__main__":
    main()
