import os
import json
import logging
import boto3
import time
from supabase import create_client
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        # Initialize Supabase
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase = create_client(self.supabase_url, self.supabase_key)

        # Initialize Bedrock
        self.aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        self.bedrock = boto3.client(service_name='bedrock-runtime', region_name=self.aws_region)
        
        # Models
        self.embedding_model_id = "amazon.titan-embed-text-v2:0"

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Amazon Titan Text Embeddings v2"""
        if not text:
            return None
            
        try:
            body = json.dumps({
                "inputText": text,
                "dimensions": 1024,
                "normalize": True
            })
            
            response = self.bedrock.invoke_model(
                body=body,
                modelId=self.embedding_model_id,
                accept="application/json",
                contentType="application/json"
            )
            
            response_body = json.loads(response.get('body').read())
            return response_body.get('embedding')
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def _fetch_eligible_whitelist(self, user_profile: Dict[str, Any]) -> List[Dict]:
        """
        Step 1: Fetch ALL benefits that strictly match the User's Profile using DB Function.
        Function: get_eligible_benefits(p_ctpv, p_sgg, p_life_array, p_target_array)
        """
        try:
            # Prepare params
            params = {
                "p_ctpv": user_profile.get("ctpv_nm"),
                "p_sgg": user_profile.get("sgg_nm"),
                "p_life_array": user_profile.get("life_cycle", []),     # e.g. ["노년"]
                "p_target_array": user_profile.get("target_group", [])  # e.g. ["저소득"]
            }
            
            # Call RPC
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
        # 1. Fetch Eligible Whitelist
        whitelist_items = self._fetch_eligible_whitelist(user_profile)
        whitelist_map = {item['id']: item for item in whitelist_items}
        whitelist_ids = set(whitelist_map.keys())
        
        logger.info(f"User Eligible Universe (Whitelist): {len(whitelist_items)} items")
        
        final_results = []
        seen_ids = set()

        # 2. Vector Search (If query exists)
        if query_text:
            start_embed = time.time()
            embedding = self.generate_embedding(query_text)
            logger.info(f"Query Embedding Gen Time: {time.time() - start_embed:.3f}s")
            
            if embedding:
                try:
                    # Fetch broad candidates with REGIONAL PRE-FILTERING
                    # This ensures local benefits (like ID 7740) are ranked effectively even if national score > local score
                    params = {
                        "query_embedding": embedding,
                        "match_threshold": 0.1, 
                        "match_count": 50,
                        "p_ctpv": user_profile.get("ctpv_nm"),
                        "p_sgg": user_profile.get("sgg_nm")
                    }
                    
                    logger.info(f"Calling match_benefits (Regional Filter: {params['p_ctpv']} {params['p_sgg']})...")
                    rpc_start = time.time()
                    rpc_response = self.supabase.rpc("match_benefits", params).execute()
                    
                    vector_candidates = rpc_response.data
                    logger.info(f"Vector Search Raw Results: {len(vector_candidates)} items (Time: {time.time() - rpc_start:.3f}s)")
                    if vector_candidates:
                        first_match = vector_candidates[0]
                        logger.info(f"Top 1 Vector Match: ID={first_match.get('id')}, Name={first_match.get('serv_nm')}")
                        # Log IDs for debugging
                        found_ids = [str(item.get('id')) for item in vector_candidates]
                        logger.info(f"Vector Found IDs: {found_ids[:10]}...")

                    # 3. Filter Vector Results against Whitelist (Priority 1)
                    for vec_item in vector_candidates:
                        # Ensure ID is correct type for comparison
                        vec_id = vec_item['id']
                        if vec_id in whitelist_ids:
                            if vec_id not in seen_ids:
                                # Mark as VECTOR source
                                item = whitelist_map[vec_id].copy()
                                item['source_type'] = 'VECTOR'
                                final_results.append(item)
                                seen_ids.add(vec_id)
                        else:
                            # Debug: Why was it filtered out?
                            pass # logger.debug(f"Vector match {vec_id} ({vec_item.get('serv_nm')}) rejected by Whitelist")
                                
                    logger.info(f"Vector Search matched & valid: {len(final_results)} / {len(rpc_response.data)}")
                    
                except Exception as e:
                    logger.error(f"Vector search failed: {e}")
            else:
                logger.error("Failed to generate embedding for query.")

        # 4. Fill remaining spots with Whitelist items (Priority 2)
        remaining_slots = top_k - len(final_results)
        
        if remaining_slots > 0:
            # Sort Strategy: Cash/In-kind ("현금", "현물") First
            def priority_sort_key(item):
                prov_type = str(item.get('srv_pvsn_nm', '') or '')
                if '현금' in prov_type or '현물' in prov_type:
                    return 0 # High Priority
                return 1 # Low Priority
            
            # Sort the whitelist (excluding already seen)
            remaining_candidates = [item for item in whitelist_items if item['id'] not in seen_ids]
            remaining_candidates.sort(key=priority_sort_key)
            
            # Fill
            for item in remaining_candidates:
                # Mark as RULES source
                item_copy = item.copy()
                item_copy['source_type'] = 'RULES'
                final_results.append(item_copy)
                seen_ids.add(item['id'])
                remaining_slots -= 1
                if remaining_slots <= 0:
                    break
        
        return final_results
