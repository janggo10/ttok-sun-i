import json
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time

# common 모듈 파일들이 같은 디렉토리에 있음
try:
    from supabase_client import SupabaseClient
except ImportError as e:
    print(f"❌ Import Error: {e}")
    raise ImportError(f"Failed to import common modules: {e}")

# Constants
# Consistent with collect_national_welfare.py
API_BASE_URL = "http://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"

def lambda_handler(event, context):
    """
    Data Collector Lambda Function
    Fetches welfare data from Public Data Portal
    """
    print("Starting Data Collector Job...")
    
    # Use BOKJIRO_API_KEY as primary since user confirmed it works
    api_key = os.environ.get('BOKJIRO_API_KEY') or os.environ.get('BOJOGEUM24_API_KEY')
    
    if not api_key:
        print("Error: BOKJIRO_API_KEY is missing.")
        return {'statusCode': 500, 'body': 'API Key Missing'}

    total_count = 0
    inserted_count = 0
    
    try:
        page_no = 1
        num_of_rows = 100
        
        while True:
            # Using params from the working script (collect_national_welfare.py)
            params = {
                'serviceKey': api_key,
                'callTp': 'L',         # L: Local, N: National (User script had 'L' in local script presumably, 'N' in national?)
                                       # Wait, grep showed "callTp='L'" in collect_national_welfare.py? No, grep didn't show param value. 
                                       # View file showed: "callTp": "L" inside fetch_national_welfare_list??
                                       # Line 60: "callTp": "L",  # List type 
                                       # Ah, callTp L means List? No, documentation usually says L=Local, N=National. 
                                       # But the script filename is collect_national... and it queries NationalWelfarelistV001.
                                       # Let's trust the working script's logic: callTp="L" (List?) or maybe it matches the endpoint.
                                       # Actually standard: callTp=L (List), D (Detail).
                                       # And serviceKey is passed decoded? requests handles it.
                'pageNo': page_no,
                'numOfRows': num_of_rows,
                'srchKeyCode': '001'   # 001: Search by Title (from working script)
            }
            
            response = requests.get(API_BASE_URL, params=params)
             # ... rest of logic (parsing) ...
            
            if response.status_code != 200:
                print(f"API Error: {response.status_code} - {response.text}")
                break
                
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError:
                print(f"XML Parse Error. Content: {response.text[:100]}")
                break
                
            result_code = root.findtext('.//resultCode')
            if result_code not in ['00', '0']: # Accept '00' or '0'
                result_msg = root.findtext('.//resultMessage') # changed from resultMsg to resultMessage based on script
                print(f"API Result Error: {result_code} - {result_msg}")
                break
            
            items = root.findall('.//servList')
            if not items:
                print("No more items found.")
                break
                
            print(f"Page {page_no}: Found {len(items)} items. Processing...")
            
            supabase = SupabaseClient.get_client()
            
            for item in items:
                try:
                    serv_id = item.findtext('servId')
                    serv_nm = item.findtext('servNm')
                    
                    # Mapping fields based on working script
                    jur_mnof_nm = item.findtext('jurMnofNm') 
                    jur_org_nm = item.findtext('jurOrgNm')
                    dept_name = f"{jur_mnof_nm} {jur_org_nm}".strip()
                    
                    serv_dgst = item.findtext('servDgst')
                    
                    # LifeNM
                    life_nm = item.findtext('lifeNm')
                    life_array = [x.strip() for x in life_nm.split(',')] if life_nm else []
                    
                    data = {
                        "serv_id": serv_id,
                        "serv_nm": serv_nm,
                        "source_api": "NATIONAL", # The endpoint is NationalWelfareInformations
                        "dept_name": dept_name,
                        "serv_dgst": serv_dgst,
                        "life_nm_array": life_array,
                        "updated_at": datetime.now().isoformat()
                    }
                    
                    supabase.table('benefits').upsert(data, on_conflict='serv_id').execute()
                    inserted_count += 1
                    
                except Exception as e:
                    print(f"Error processing item {serv_id}: {e}")
            
            total_count += len(items)
            page_no += 1
            
            if page_no > 5: 
                print("Reached page limit for testing.")
                break
                
    except Exception as e:
        print(f"Job Failed: {e}")
        return {'statusCode': 500, 'body': str(e)}

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Success',
            'processed': total_count,
            'inserted': inserted_count
        })
    }
