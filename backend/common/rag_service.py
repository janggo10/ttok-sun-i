import os
import json
import logging
import boto3
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
        self.llm_model_id = "anthropic.claude-3-haiku-20240307-v1:0" 

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

    def search_benefits(self, query_text: str, user_profile: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Execute Hybrid Search (Semantic + Keyword + Metadata Filters)
        user_profile should contain: 'ctpv_nm', 'sgg_nm', 'interest_ages' (list)
        """
        # 1. Generate Query Embedding
        query_embedding = self.generate_embedding(query_text)
        if not query_embedding:
            logger.warning("Could not generate embedding for query.")
            return []

        # 2. Call Supabase RPC
        # RPC signature: search_benefits_hybrid(query_embedding, user_ctpv_nm, user_sgg_nm, user_interest_ages, limit_count)
        try:
            params = {
                "query_embedding": query_embedding,
                "user_ctpv_nm": user_profile.get("ctpv_nm", ""),
                "user_sgg_nm": user_profile.get("sgg_nm", ""),
                "user_interest_ages": user_profile.get("interest_ages", []),
                "limit_count": limit
            }
            
            response = self.supabase.rpc("search_benefits_hybrid", params).execute()
            return response.data
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def generate_answer(self, query_text: str, context_docs: List[Dict[str, Any]], stream: bool = False) -> Any:
        """
        Generate answer using Claude 3 Haiku
        If stream=True, returns a generator. Otherwise returns full string.
        """
        
        # Build Context String
        context_str = ""
        for i, doc in enumerate(context_docs, 1):
            context_str += f"[{i}] {doc['title']}\n"
            context_str += f"   - 내용: {doc['content']}\n"
            context_str += f"   - 링크: {doc['original_url']}\n\n"
            
        if not context_str:
            context_str = "검색된 관련 복지 혜택이 없습니다."

        # System Prompt
        system_prompt = """당신은 대한민국의 복지 혜택을 친절하게 알려주는 '똑순이'입니다.
주어진 <context> 정보를 바탕으로 사용자의 질문에 답변해주세요.
- 사용자가 거주하는 지역과 연령대에 맞는 혜택 위주로 설명하세요.
- 각 혜택의 '지원 대상', '지원 내용', '신청 방법'을 명확히 구분해 설명하세요.
- 답변 끝에는 반드시 출처(링크)를 포함하세요.
- <context>에 없는 내용은 지어내지 말고, 정보가 부족하면 솔직히 말해주세요.
- 항상 친절하고 정중한 어조('~해요'체)를 사용하세요."""

        # Messages
        messages = [
            {
                "role": "user",
                "content": f"""<context>
{context_str}
</context>

질문: {query_text}"""
            }
        ]

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": messages,
            "temperature": 0.5
        })

        try:
            if stream:
                response = self.bedrock.invoke_model_with_response_stream(
                    body=body,
                    modelId=self.llm_model_id
                )
                return response.get('body')
            else:
                response = self.bedrock.invoke_model(
                    body=body,
                    modelId=self.llm_model_id
                )
                response_body = json.loads(response.get('body').read())
                return response_body['content'][0]['text']
                
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return "죄송해요, 답변을 생성하는 도중 문제가 발생했어요. 😢"

    def get_response(self, query_text: str, user_profile: Dict[str, Any], stream: bool = False):
        """
        Main RAG Workflow: Search -> Generate
        Returns (context, answer)
        """
        # 1. Search
        context_docs = self.search_benefits(query_text, user_profile)
        
        # 2. Generate
        answer = self.generate_answer(query_text, context_docs, stream=stream)
        
        return context_docs, answer
