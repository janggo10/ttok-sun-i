import os
import json
import logging
import time
from datetime import datetime
from supabase import create_client
from typing import List, Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        # Initialize Supabase
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase = create_client(self.supabase_url, self.supabase_key)

        # Initialize OpenAI
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set")
        self.openai_client = OpenAI(api_key=openai_api_key)
        
        # Models
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimensions = 1536  # OpenAI text-embedding-3-small 차원
        
        # 🔍 초기화 로그 (디버깅용)
        logger.info(f"✅ RAGService initialized with OpenAI model: {self.embedding_model}, dimensions: {self.embedding_dimensions}")
    
    @staticmethod
    def convert_birth_year_to_life_cycle(birth_year: int) -> List[str]:
        """
        출생연도를 생애주기 배열로 변환
        
        Args:
            birth_year: 출생연도 (예: 1955)
        
        Returns:
            생애주기 배열 (예: ['노년'])
        
        생애주기 기준:
        - 영유아: 0~5세
        - 아동: 6~12세
        - 청소년: 13~18세
        - 청년: 19~34세
        - 중장년: 35~64세
        - 노년: 65세 이상
        """
        current_year = datetime.now().year
        age = current_year - birth_year
        
        if age < 0:
            return []
        elif age <= 5:
            return ['영유아']
        elif age <= 12:
            return ['아동']
        elif age <= 18:
            return ['청소년']
        elif age <= 34:
            return ['청년']
        elif age <= 64:
            return ['중장년']
        else:
            return ['노년']

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI text-embedding-3-small"""
        if not text:
            return None
            
        try:
            logger.info(f"🔍 Generating embedding with {self.embedding_model} (dim={self.embedding_dimensions})")
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=self.embedding_dimensions
            )
            embedding = response.data[0].embedding
            logger.info(f"✅ Embedding generated successfully, length={len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding with OpenAI: {e}")
            return None

    def _fetch_eligible_whitelist(self, user_profile: Dict[str, Any]) -> List[Dict]:
        """
        Step 1: Fetch ALL benefits that strictly match the User's Profile using DB Function.
        Function: get_eligible_benefits(p_ctpv, p_sgg, p_life_array, p_target_array)
        """
        try:
            # Get life_cycle from user profile (직접 저장된 값 사용)
            life_cycle = user_profile.get("life_cycle", [])
            
            # Fallback: birth_year가 있고 life_cycle이 비어있으면 자동 변환
            if not life_cycle and user_profile.get("birth_year"):
                life_cycle = self.convert_birth_year_to_life_cycle(user_profile["birth_year"])
                logger.info(f"Fallback: Converted birth_year {user_profile['birth_year']} to life_cycle: {life_cycle}")
            
            # Get target_group from user profile (직접 저장된 값 사용)
            target_group = user_profile.get("target_group", [])
            
            # Prepare params
            params = {
                "p_ctpv": user_profile.get("ctpv_nm"),
                "p_sgg": user_profile.get("sgg_nm"),
                "p_life_array": life_cycle,           # 사용자 테이블의 life_cycle 컬럼
                "p_target_array": target_group        # 사용자 테이블의 target_group 컬럼
            }
            
            logger.info(f"Whitelist params: ctpv={params['p_ctpv']}, sgg={params['p_sgg']}, life={params['p_life_array']}, target={params['p_target_array']}")
            
            # Call RPC (RPC 함수가 모든 컬럼 반환)
            response = self.supabase.rpc("get_eligible_benefits", params).execute()
            return response.data
            
        except Exception as e:
            logger.error(f"Whitelist fetch failed: {e}")
            return [] 

    def get_recommended_services(self, query_text: str, user_profile: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Main Search Logic:
        1. Get Whitelist (Eligible services based on Profile)
        2. Vector Search (Semantic matches)
        3. Intersect & Prioritize:
           - Top: Vector matches that are in Whitelist
           - Bottom: Remaining Whitelist items (Prioritized by Cash/In-kind)
        """
        # Extract life_cycle and target_group from user profile
        life_cycle = user_profile.get("life_cycle", [])
        if not life_cycle and user_profile.get("birth_year"):
            life_cycle = self.convert_birth_year_to_life_cycle(user_profile["birth_year"])
        
        target_group = user_profile.get("target_group", [])
        
        # 1. Fetch Eligible Whitelist
        whitelist_items = self._fetch_eligible_whitelist(user_profile)
        whitelist_map = {item['id']: item for item in whitelist_items}
        whitelist_ids = set(whitelist_map.keys())
        
        logger.info(f"User Eligible Universe (Whitelist): {len(whitelist_items)} items")
        
        final_results = []
        seen_ids = set()

        # 2. Vector Search (If query exists)
        if query_text:
            logger.info(f"🔎 검색어: '{query_text}'")
            start_embed = time.time()
            embedding = self.generate_embedding(query_text)
            logger.info(f"Query Embedding Gen Time: {time.time() - start_embed:.3f}s")
            
            if embedding:
                try:
                    # Fetch broad candidates with REGIONAL PRE-FILTERING
                    # This ensures local benefits (like ID 7740) are ranked effectively even if national score > local score
                    params = {
                        "query_embedding": embedding,
                        # Threshold 가이드라인:
                        # - 0.40: 최고 품질 (결과 23% 감소)
                        # - 0.35: 최적 균형 (품질 우수 + 충분한 결과) ✅
                        # - 0.33: 더 많은 결과 (품질 약간 저하)
                        "match_threshold": 0.35,
                        "match_count": 50,
                        "p_ctpv": user_profile.get("ctpv_nm"),
                        "p_sgg": user_profile.get("sgg_nm"),
                        "p_life_array": life_cycle or [],
                        "p_target_array": target_group or []
                    }
                    
                    logger.info(f"Calling match_benefits (Filters: {params['p_ctpv']} {params['p_sgg']}, Life: {life_cycle}, Target: {target_group})...")
                    rpc_start = time.time()
                    rpc_response = self.supabase.rpc("match_benefits", params).execute()
                    
                    vector_candidates = rpc_response.data
                    logger.info(f"🔍 Vector Search: {len(vector_candidates)} items found (Time: {time.time() - rpc_start:.3f}s, Threshold: {params['match_threshold']})")
                    
                    # 🐛 디버그: 첫 번째 결과의 모든 필드 확인
                    if vector_candidates and len(vector_candidates) > 0:
                        first_item = vector_candidates[0]
                        logger.info(f"🐛 DEBUG - First item keys: {list(first_item.keys())}")
                        logger.info(f"🐛 DEBUG - similarity value: {first_item.get('similarity', 'NOT_FOUND')}")
                    
                    if vector_candidates:
                        # Top 5 결과 로그 (유사도 포함)
                        logger.info("📊 벡터 검색 결과 (Top 10):")
                        for i, match in enumerate(vector_candidates[:10], 1):
                            similarity = match.get('similarity', 'N/A')
                            serv_nm = match.get('serv_nm', '제목 없음')
                            benefit_id = match.get('id', 'N/A')
                            if similarity != 'N/A':
                                logger.info(f"  #{i} [유사도: {similarity:.3f}] ID={benefit_id} | '{serv_nm}'")
                            else:
                                logger.info(f"  #{i} [유사도: N/A] ID={benefit_id} | '{serv_nm}'")
                    else:
                        logger.warning(f"⚠️ Vector Search returned 0 results! Check: 1) Embeddings exist? 2) Threshold too high?")

                    # 3. Use Vector Results directly (already filtered by SQL)
                    for vec_item in vector_candidates:
                        vec_id = vec_item['id']
                        if vec_id not in seen_ids:
                            # Mark as VECTOR source
                            vec_item['source_type'] = 'VECTOR'
                            final_results.append(vec_item)
                            seen_ids.add(vec_id)
                                
                    logger.info(f"✅ VECTOR results: {len(final_results)} items")
                    
                except Exception as e:
                    logger.error(f"Vector search failed: {e}")
            else:
                logger.error("Failed to generate embedding for query.")

        # 4. Fill remaining spots with Whitelist items (Priority 2)
        remaining_slots = top_k - len(final_results)
        
        if remaining_slots > 0:
            # Sort Strategy:
            # 1. Region Specificity (High Priority):
            #    - Same Gun/Gu (sgg_nm match) -> Priority 0
            #    - Same City/Do (ctpv_nm match) -> Priority 1
            #    - National/Other -> Priority 2
            # 2. Benefit Type (Secondary):
            #    - Cash/In-kind -> sub -1 (boost)
            
            user_sgg = user_profile.get("sgg_nm", "")
            user_ctpv = user_profile.get("ctpv_nm", "")

            def priority_sort_key(item):
                # Region Score (Lower is better)
                item_sgg = str(item.get('sgg_nm') or '')
                item_ctpv = str(item.get('ctpv_nm') or '')
                
                region_score = 2 # Default: National/None
                if item_sgg and item_sgg == user_sgg:
                    region_score = 0 # Match SGG
                elif item_ctpv and item_ctpv == user_ctpv:
                    region_score = 1 # Match CTPV
                
                # Type Score (Tie-breaker)
                prov_type = str(item.get('srv_pvsn_nm', '') or '')
                type_score = 1
                if '현금' in prov_type or '현물' in prov_type:
                    type_score = 0
                
                return (region_score, type_score)
            
            # Sort the whitelist (excluding already seen)
            remaining_candidates = [item for item in whitelist_items if item['id'] not in seen_ids]
            remaining_candidates.sort(key=priority_sort_key)
            
            # Fill
            rules_added = 0
            logger.info("📋 자격기반 결과 추가:")
            for item in remaining_candidates:
                # Mark as RULES source
                item_copy = item.copy()
                item_copy['source_type'] = 'RULES'
                final_results.append(item_copy)
                seen_ids.add(item['id'])
                rules_added += 1
                
                # 로그 출력 (Top 10만)
                if rules_added <= 10:
                    logger.info(f"  #{rules_added} [자격기반] ID={item.get('id')} | '{item.get('serv_nm', '제목 없음')}'")
                
                if len(final_results) >= top_k:
                    break
            
            if rules_added > 10:
                logger.info(f"  ... 및 {rules_added - 10}개 더")
            logger.info(f"✅ RULES results: {rules_added} items added")
        
        # 5. Return final results (already have all needed columns from SQL functions)
        final_candidates = final_results[:top_k]
        logger.info(f"Final Results: {len(final_candidates)} items")
        
        return final_candidates
