import os
import sys
import json
import logging
import time
from dotenv import load_dotenv

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.common.rag_service import RAGService

# Setup minimal logging
logging.basicConfig(level=logging.ERROR)

def process_stream(stream):
    """Handle Bedrock Streaming Output"""
    full_text = ""
    print("\n🤖 똑순이: ", end="", flush=True)
    
    for event in stream:
        chunk = event.get('chunk')
        if chunk:
            chunk_json = json.loads(chunk.get('bytes').decode())
            if chunk_json.get('type') == 'content_block_delta':
                text_delta = chunk_json['delta']['text']
                print(text_delta, end="", flush=True)
                full_text += text_delta
                
    print("\n")
    return full_text

def main():
    load_dotenv()
    
    print("\n💡 똑순이 RAG 서비스 테스트 CLI (type 'quit' to exit)")
    print("="*60)
    
    # 1. Setup Mock User Profile
    # In a real app, this comes from the DB (onboarding data)
    user_profile = {
        "ctpv_nm": "서울특별시",
        "sgg_nm": "강남구",
        "interest_ages": ["청년", "중장년"] 
    }
    
    print(f"📍 사용자 프로필 설정: {user_profile['ctpv_nm']} {user_profile['sgg_nm']} (관심: {', '.join(user_profile['interest_ages'])})")
    print("="*60)

    try:
        rag_service = RAGService()
    except Exception as e:
        print(f"❌ Failed to initialize RAG Service: {e}")
        return

    while True:
        try:
            query = input("\n🗣️  질문: ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                break
            if not query:
                continue

            print(f"🔍 '{query}' 검색 중...")
            
            # 2. Get Response (Streamed)
            context_docs, stream = rag_service.get_response(query, user_profile, stream=True)
            
            # Print Context Used
            if context_docs:
                print(f"\n📚 참고 문서 ({len(context_docs)}건):")
                for i, doc in enumerate(context_docs, 1):
                    # Truncate content for display
                    content_preview = doc['content'][:100].replace('\n', ' ') + "..."
                    print(f"  [{i}] {doc['title']} (유사도: {doc['similarity']:.4f})")
                    # print(f"      {content_preview}")
            else:
                print("\n⚠️  참고할 만한 문서가 발견되지 않았습니다.")

            # Print Answer
            process_stream(stream)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n👋 안녕히 가세요!")

if __name__ == "__main__":
    main()
