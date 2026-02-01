"""
Supabase 데이터베이스 클라이언트
"""
import os
from typing import Optional
from supabase import create_client, Client


class SupabaseClient:
    """Supabase 클라이언트 싱글톤"""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Supabase 클라이언트 인스턴스 반환"""
        if cls._instance is None:
            url = os.environ.get('SUPABASE_URL')
            key = os.environ.get('SUPABASE_SERVICE_KEY')
            
            if not url or not key:
                raise ValueError('SUPABASE_URL and SUPABASE_SERVICE_KEY must be set')
            
            cls._instance = create_client(url, key)
        
        return cls._instance
