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
logging.basicConfig(level=logging.INFO)

def main():
    load_dotenv()
    
    print("\n💡 똑순이 Hybrid Search 테스트 CLI (type 'quit' to exit)")
    print("="*60)
    
    # 1. Setup Mock User Profile
    # Updated to match new schema: target_group, etc.
    # [참고] DB(trgter_indvdl_nm_array) 실제 값 예시:
    # - ['저소득', '한부모·조손']
    # - ['장애인']
    # - ['다문화·북한이탈주민'] 
    # - [] (빈 배열 = 제한 없음/전국민)
    '''
    user_profile = {
        "ctpv_nm": "부산광역시",
        "sgg_nm": "강성구",
        "life_cycle": ["노년"],     # 생애주기 필터링용 (DB: life_nm_array)
        "target_group": [] # 테스트하고 싶은 조건들을 여기에 추가하세요
    }
    '''
    user_profile = {
        "ctpv_nm": "부산광역시",
        "sgg_nm": "강서구",
        "life_cycle": ['청소년'],     # 생애주기 필터링용 (DB: life_nm_array)
        "target_group": [] # 테스트하고 싶은 조건들을 여기에 추가하세요
    }
    #    "target_group": ["저소득", "한부모·조손", "장애인"] # 테스트하고 싶은 조건들을 여기에 추가하세요
    
    print(f"📍 사용자 프로필: {user_profile['ctpv_nm']} {user_profile['sgg_nm']}")
    print(f"   생애주기: {user_profile['life_cycle']}")
    print(f"   대상 특성: {user_profile['target_group']}")
    print("   (주의: DB에 이 조건에 맞는 데이터가 충분히 있어야 테스트가 잘 됩니다)")
    print("="*60)

    try:
        rag_service = RAGService()
    except Exception as e:
        print(f"❌ Failed to initialize RAG Service: {e}")
        return

    while True:
        try:
            query = input("\n🗣️  질문 (예: 육아용품 지원): ").strip()
            if query.lower() in ['quit', 'exit', 'q']:
                break
            if not query:
                continue

            print(f"🔍 '{query}' 검색 & 필터링 중...")
            start_time = time.time()
            
            # 2. Get Recommended Services (List Only)
            results = rag_service.get_recommended_services(query, user_profile, top_k=20)
            
            elapsed = time.time() - start_time
            print(f"⏱️ 소요시간: {elapsed:.2f}초")
            
            if results:
                print(f"\n✅ 추천 혜택 목록 ({len(results)}건):")
                print("-" * 60)
                for i, item in enumerate(results, 1):
                    # Debug Info: Check why this item was picked
                    prov_type = item.get('srv_pvsn_nm') or 'N/A'
                    targets = item.get('trgter_indvdl_nm_array') or '전국민/제한없음'
                    
                    start_date = item.get('enfc_bgng_ymd') or '...'
                    end_date = item.get('enfc_end_ymd') or '...'
                    
                    print(f"[{i}] [{item.get('source_type', 'UNKNOWN')}] {item['serv_nm']}")
                    print(f"    - ID: {item['id']}")
                    print(f"    - 기간: {start_date} ~ {end_date}")
                    print(f"    - 유형: {prov_type} (현금/현물 우선순위 확인)")
                    print(f"    - 생애: {item.get('life_nm_array') or '전생애'}")
                    print(f"    - 대상: {targets}")
                    print(f"    - 지역: {item.get('ctpv_nm', '')} {item.get('sgg_nm', '')}")
                    print("-" * 60)
            else:
                print("\n⚠️  조건에 맞는 혜택이 없습니다.")
                print("   (지역/대상 조건에 맞는 데이터가 DB에 있는지 확인해주세요)")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n👋 안녕히 가세요!")

if __name__ == "__main__":
    main()
