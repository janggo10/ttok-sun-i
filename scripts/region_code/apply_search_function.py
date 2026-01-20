import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL or SUPABASE_SERVICE_KEY not found in .env")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# SQL 파일 읽기
sql_file_path = 'supabase/functions/search_regions.sql'
with open(sql_file_path, 'r') as f:
    sql_content = f.read()

print(f"Executing SQL from {sql_file_path}...")

try:
    # Supabase Python 클라이언트에는 직접 SQL을 실행하는 `rpc` 외에 `query` 메서드가 없으므로
    # postgresql 클라이언트(psycopg2)를 쓰거나, Supabase 대시보드 SQL Editor를 권장함.
    # 하지만 여기서는 `postgres` 함수(만약 있다면)를 rpc로 호출하거나, 
    # 대안으로 `v1/query` REST API를 사용할 수도 잇음.
    
    # 하지만 가장 확실한 방법은 DB connection string을 이용하는 것임.
    # .env에 DB_URL이 있는지 확인 필요.
    
    # 만약 DB 접속 정보가 없다면, 일단 사용자가 직접 실행하도록 안내하거나
    # `supabase-py`의 `rpc`를 활용해볼 수 있음. 하지만 `create function`은 rpc 호출로 불가능.
    
    # 여기서는 간단히 안내만 하는 것이 아니라 실제 실행을 시도해야 함.
    # 
    # 그런데 잠깐, Supabase Python 클라이언트로는 DDL 실행이 어렵습니다.
    # 따라서 이 스크립트는 "실행할 SQL 내용을 보여주는" 용도로 사용하거나
    # psql이 설치되어 있다면 subprocess로 실행해야 합니다.
    
    print("\n[SQL Content]")
    print(sql_content)
    print("\n⚠️  Supabase Python Client does not support running raw SQL/DDL directly.")
    print("Please run the above SQL in the Supabase SQL Editor.")
    
except Exception as e:
    print(f"Error: {e}")
