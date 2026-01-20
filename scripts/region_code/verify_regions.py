#!/usr/bin/env python3
"""
Supabase regions 테이블 데이터 검증 스크립트
"""

from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("=" * 70)
print("🔍 Supabase regions 테이블 데이터 검증")
print("=" * 70)

# 전체 통계
print("\n📊 전체 통계:")
result = supabase.table('regions').select('depth', count='exact').execute()
print(f"  총 레코드 수: {result.count}개")

# Depth별 통계
for depth in [1, 2, 3, 4]:
    result = supabase.table('regions').select('*', count='exact').eq('depth', depth).execute()
    print(f"  - Depth {depth}: {result.count}개")

# Depth별 샘플 데이터
print("\n📋 Depth별 샘플 데이터:")

print("\n🏙️  Depth 1 (시/도) - 전체 목록:")
result = supabase.table('regions').select('region_code, name, depth').eq('depth', 1).order('region_code').execute()
for row in result.data:
    print(f"  {row['region_code']} - {row['name']}")

print("\n🏘️  Depth 2 (시/군/구) - 샘플 10개:")
result = supabase.table('regions').select('region_code, name, parent_code, depth').eq('depth', 2).limit(10).execute()
for row in result.data:
    print(f"  {row['region_code']} - {row['name']} (상위: {row['parent_code']})")

print("\n🏡 Depth 3 (읍/면/동) - 샘플 10개:")
result = supabase.table('regions').select('region_code, name, parent_code, depth').eq('depth', 3).limit(10).execute()
for row in result.data:
    print(f"  {row['region_code']} - {row['name']} (상위: {row['parent_code']})")

print("\n🏠 Depth 4 (리) - 샘플 10개:")
result = supabase.table('regions').select('region_code, name, parent_code, depth').eq('depth', 4).limit(10).execute()
for row in result.data:
    print(f"  {row['region_code']} - {row['name']} (상위: {row['parent_code']})")

# 서울 강남구 계층 구조 확인
print("\n🎯 서울 강남구 계층 구조 예시:")
print("\n  1. 서울특별시 (Depth 1):")
result = supabase.table('regions').select('*').eq('region_code', '1100000000').execute()
if result.data:
    print(f"     {result.data[0]['region_code']} - {result.data[0]['name']}")

print("\n  2. 강남구 (Depth 2):")
result = supabase.table('regions').select('*').eq('region_code', '1168000000').execute()
if result.data:
    print(f"     {result.data[0]['region_code']} - {result.data[0]['name']} (parent: {result.data[0]['parent_code']})")

print("\n  3. 강남구 하위 동 (Depth 3) - 5개:")
result = supabase.table('regions').select('*').eq('parent_code', '1168000000').limit(5).execute()
for row in result.data:
    print(f"     {row['region_code']} - {row['name']} (parent: {row['parent_code']})")

print("\n" + "=" * 70)
print("✅ 검증 완료!")
print("=" * 70)
