import os
import sys
import json
import logging
import boto3
from dotenv import load_dotenv
from supabase import create_client

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
TITAN_MODEL_ID = "amazon.titan-embed-text-v2:0"

def get_clients():
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    bedrock = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)
    return supabase, bedrock

def generate_embedding(bedrock, text):
    try:
        body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
        response = bedrock.invoke_model(
            body=body, modelId=TITAN_MODEL_ID, 
            accept="application/json", contentType="application/json"
        )
        return json.loads(response.get('body').read()).get('embedding')
    except Exception as e:
        logger.error(f"Bedrock error: {e}")
        return None

def test_search(query, expected_keyword=None, ctpv="서울특별시", sgg="관악구"):
    supabase, bedrock = get_clients()
    
    logger.info(f"\n🔎 Testing Query: '{query}' (Context: {ctpv} {sgg})")
    
    # 1. Generate Query Vector
    vector = generate_embedding(bedrock, query)
    if not vector:
        logger.error("Failed to generate vector.")
        return

    # 2. Call Hybrid Search RPC
    params = {
        "query_embedding": vector,
        "user_ctpv_nm": ctpv,
        "user_sgg_nm": sgg,
        "user_interest_ages": ["청년", "중장년", "노년"], 
        "limit_count": 3
    }
    
    try:
        response = supabase.rpc("search_benefits_hybrid", params).execute()
        results = response.data
        
        if not results:
            logger.warning("No results found.")
            return

        for i, item in enumerate(results):
            similarity = item.get('similarity', 0)
            title = item.get('title', 'No Title')
            serv_id = item.get('serv_id', 'No ID')
            content = item.get('content', '')
            
            logger.info(f"   {i+1}. [{similarity:.4f}] {serv_id} | {title}")
            logger.info(f"       {content[:100]}..." if len(content) > 100 else f"       {content}")
            
            if i == 0 and expected_keyword and expected_keyword not in title:
                logger.warning(f"      ⚠️ Expected top result to contain '{expected_keyword}'")
            elif i == 0 and expected_keyword:
                 logger.info(f"      ✅ Top result matches expected keyword!")

    except Exception as e:
        logger.error(f"Search failed: {e}")

def main():
    # Test Cases based on 5 initial items + Jeju items
    test_search("자립준비 청년이 받을 수 있는 돈은?", "자립준비청년")
    test_search("아기 낳았는데 축하 선물 뭐 있어?", "출생축하용품")
    test_search("수도 요금 할인 받고 싶어", "수도요금")
    
    # Jeju specific test case with correct context
    test_search("제주도에서 교통비 지원해주는거 있어?", "제주교통복지카드", ctpv="제주특별자치도", sgg="제주시")

if __name__ == "__main__":
    main()
