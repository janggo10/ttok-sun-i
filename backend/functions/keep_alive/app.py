"""
Supabase 프로젝트 활성 상태 유지
"""
import os

# common 모듈 파일들이 같은 디렉토리에 있음
try:
from supabase_client import SupabaseClient
except ImportError as e:
    print(f"❌ Import Error: {e}")
    raise ImportError(f"Failed to import common modules: {e}")


def lambda_handler(event, context):
    """주 1회 실행하여 Supabase 프로젝트 활성 상태 유지"""
    try:
        supabase = SupabaseClient.get_client()
        
        # 간단한 쿼리로 활성 상태 유지
        result = supabase.table('users').select('id').limit(1).execute()
        
        return {
            'statusCode': 200,
            'body': f'Keep-alive successful. Users count: {len(result.data)}'
        }
    except Exception as e:
        print(f'Keep-alive failed: {e}')
        return {
            'statusCode': 500,
            'body': str(e)
        }
