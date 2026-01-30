import json
import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from backend.functions.kakao_webhook.app import lambda_handler

def mock_kakao_request(user_id, step=None, params=None, client_extra=None):
    if params is None:
        params = {}
    if client_extra is None:
        client_extra = {}
        
    # Construct ClientExtra based on step if needed or assume passed correctly
    # In real Kakao, clientExtra is passed via button click.
    # We simulate the payload arriving at the webhook.
    
    payload = {
        "userRequest": {
            "user": {
                "id": user_id
            },
            "utterance": "Test input"
        },
        "action": {
            "params": params,
            "clientExtra": client_extra
        }
    }
    
    # If starting, no clientExtra usually, just utterance
    if step == 'START':
        pass # Defaults handle it
        
    return payload

def run_scenario():
    user_id = "TEST_USER_001"
    print(f"--- Starting Onboarding Scenario for {user_id} ---")
    
    # 1. Start
    print("\n[Step 1] Sending Start Trigger...")
    evt = {"body": json.dumps(mock_kakao_request(user_id, 'START'))}
    ctx = {}
    resp = lambda_handler(evt, ctx)
    print_response(resp)
    
    # Simulate user selecting "서울특별시"
    # The previous response (City Selection) would have a button for "서울특별시"
    # That button's extra data: {"next_step": "SELECT_SGG", "city": "서울특별시"}
    
    # 2. Select City
    print("\n[Step 2] User selects '서울특별시'...")
    extra = {"next_step": "SELECT_SGG", "city": "서울특별시"}
    params = {"city": "서울특별시"} # Sometimes params duplicate extra depending on skill setup
    evt = {"body": json.dumps(mock_kakao_request(user_id, client_extra=extra, params=params))}
    resp = lambda_handler(evt, ctx)
    print_response(resp)
    
    # 3. Select SGG
    print("\n[Step 3] User selects '종로구'...")
    extra = {"next_step": "SELECT_BIRTH_YEAR_RANGE", "city": "서울특별시", "sgg": "종로구"}
    params = {"sgg": "종로구"} 
    evt = {"body": json.dumps(mock_kakao_request(user_id, client_extra=extra, params=params))}
    resp = lambda_handler(evt, ctx)
    print_response(resp)
    
    # 4. Select Birth Range
    print("\n[Step 4] User selects '1950년대'...")
    extra = {"next_step": "SELECT_BIRTH_YEAR", "city": "서울특별시", "sgg": "종로구", "birth_range": "1950"}
    params = {"birth_range": "1950"} # Value
    evt = {"body": json.dumps(mock_kakao_request(user_id, client_extra=extra, params=params))}
    resp = lambda_handler(evt, ctx)
    print_response(resp)
    
    # 5. Select Birth Year
    print("\n[Step 5] User selects '1955년'...")
    extra = {"next_step": "SELECT_GENDER", "city": "서울특별시", "sgg": "종로구", "birth_year": 1955}
    params = {"birth_year": 1955}
    evt = {"body": json.dumps(mock_kakao_request(user_id, client_extra=extra, params=params))}
    resp = lambda_handler(evt, ctx)
    print_response(resp)

    # 6. Select Gender
    print("\n[Step 6] User selects '남성'...")
    extra = {"next_step": "COMPLETE", "city": "서울특별시", "sgg": "종로구", "birth_year": 1955}
    params = {"gender": "M"}
    evt = {"body": json.dumps(mock_kakao_request(user_id, client_extra=extra, params=params))}
    resp = lambda_handler(evt, ctx)
    print_response(resp)

def print_response(resp):
    try:
        if 'template' in resp:
            # Simple text
            if 'outputs' in resp['template']:
                for out in resp['template']['outputs']:
                    if 'simpleText' in out:
                        print(f"Bot: {out['simpleText']['text']}")
            
            # Quick Replies
            if 'quickReplies' in resp['template']:
                print("Quick Replies: ", [qr['label'] for qr in resp['template']['quickReplies']])
                # print("  (Meta): ", [qr['extra'] for qr in resp['template']['quickReplies']])
    except:
        print("Raw Response:", resp)

if __name__ == "__main__":
    run_scenario()
