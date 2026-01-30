import json
import os
import sys
from datetime import datetime

# Add layer path for local testing (virtualenv) or Lambda layer
# Assuming standard structure where common is accessible
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

try:
    from common.supabase_client import SupabaseClient
except ImportError:
    # Fallback for different execution environments
    try:
        from backend.common.supabase_client import SupabaseClient
    except ImportError:
        print("Warning: SupabaseClient import failed. DB operations will fail.")
        SupabaseClient = None

# ----------------------------------------------------
# Main Handler with DB-State Logic
# ----------------------------------------------------

def lambda_handler(event, context):
    """
    KakaoTalk Chatbot Webhook Handler (Stateless -> DB Stateful)
    """
    print(f"Event: {json.dumps(event, ensure_ascii=False)}")
    
    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
    except:
        body = {}
        
    user_request = body.get('userRequest', {})
    user_id = user_request.get('user', {}).get('id')
    utterance = user_request.get('utterance', '').strip()
    
    if not user_id:
        return api_response(simple_text_response("유저 정보를 찾을 수 없습니다."))

    # 1. Fetch User State from DB
    supabase = SupabaseClient.get_client()
    user = None
    try:
        res = supabase.table('users').select('*').eq('kakao_user_id', user_id).execute()
        if res.data:
            user = res.data[0]
    except Exception as e:
        print(f"DB Fetch Error: {e}")

    # 2. Determine Current State & Reset Logic
    # If user says "시작하기", "처음으로" -> Reset DB State
    if utterance in ['시작하기', '처음으로', '안녕', '리셋']:
        reset_user_state(supabase, user_id)
        return api_response(response_select_city())
        
    # If New User -> Create and Ask City
    if not user:
        create_initial_user(supabase, user_id)
        return api_response(response_select_city())

    # 3. State Machine Logic
    # We check what is missing in the User Profile in order: City -> SGG -> Birth -> Gender
    
    # State: Wait for City
    if not user.get('ctpv_nm'):
        # Check if utterance is a valid City
        if is_valid_city(utterance):
            # Update City, Ask SGG
            update_user_field(supabase, user_id, {'ctpv_nm': utterance})
            return api_response(response_select_sgg(utterance))
        else:
            return api_response(response_select_city(fail_msg=True))
            
    # State: Wait for SGG
    if not user.get('sgg_nm'):
        # Check if utterance is valid SGG (simple check or trust user)
        # Note: 'utterance' is what user typed or clicked.
        # Ideally we check against DB regions, but for MVP we trust if length > 0
        if utterance and len(utterance) > 1:
             # Update SGG, Ask Birth Range
            update_user_field(supabase, user_id, {'sgg_nm': utterance})
            return api_response(response_select_birth_range(user['ctpv_nm'], utterance))
        else:
            return api_response(response_select_sgg(user['ctpv_nm'], fail_msg=True))
            
    # State: Wait for Birth Year (Range or Direct)
    curr_birth_year = user.get('birth_year')
    if not curr_birth_year or curr_birth_year == 0:
        clean_text = utterance.replace(' ', '')
        
        # 1. Check if it's a Range Selection (e.g. "1950년대", "1930년대이전")
        if any(x in clean_text for x in ['년대', '이전', '이후']):
            # Extract the decade
            # "1950년대" -> 1950
            # "1930년대이전" -> 1930
            # Find the first 4 digit number
            import re
            match = re.search(r'\d{4}', clean_text)
            if match:
                start_year_str = match.group()
                return api_response(response_select_birth_year(user['ctpv_nm'], user['sgg_nm'], start_year_str))
        
        # 2. Check if it's a Specific Year (e.g. "1953년", "1953")
        # Extract digits
        val = ''.join(filter(str.isdigit, clean_text))
        if len(val) == 4:
            year = int(val)
            # Valid range check 1900~2030
            if 1900 <= year <= 2030:
                 update_user_field(supabase, user_id, {'birth_year': year})
                 return api_response(response_select_gender(user['ctpv_nm'], user['sgg_nm'], year))
                 
        # 3. Fallback: Show Range Selection again
        return api_response(response_select_birth_range(user['ctpv_nm'], user['sgg_nm']))

    # State: Wait for Gender
    if not user.get('gender'):
        if '남' in utterance:
            gender = 'M'
        elif '여' in utterance:
            gender = 'F'
        else:
            gender = None
            
        if gender:
            # Complete!
            update_user_field(supabase, user_id, {
                'gender': gender, 
                'is_active': True,
                # Resolve region code here for completeness
                'region_code': resolve_region_code(supabase, user['ctpv_nm'], user['sgg_nm'])
            })
            return api_response(simple_text_response(f"반갑습니다! 🎉\n\n- 지역: {user['ctpv_nm']} {user['sgg_nm']}\n- 출생: {user.get('birth_year')}년\n- 성별: {'남성' if gender=='M' else '여성'}\n\n등록이 완료되었습니다.\n이제 '혜택 추천해줘' 라고 말씀하시면 딱 맞는 복지 혜택을 찾아드릴게요!"))
        else:
            return api_response(response_select_gender(user['ctpv_nm'], user['sgg_nm'], user['birth_year']))

    # If all fields exist -> Already Onboarded
    return api_response(simple_text_response(f"이미 등록된 사용자입니다.\n혜택을 찾으시려면 '혜택 추천'이라고 말씀해주세요.\n\n(정보를 수정하려면 '처음으로' 라고 말씀해주세요.)"))


def api_response(response_data):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_data, ensure_ascii=False)
    }

# ----------------------------------------------------
# DB Helpers
# ----------------------------------------------------

def create_initial_user(supabase, user_id):
    default_region_code = get_default_region_code(supabase)
    supabase.table('users').upsert({
        'kakao_user_id': user_id,
        'ctpv_nm': '', 'sgg_nm': '', 'birth_year': 0, 'gender': '', 
        'region_code': default_region_code, 'region_depth': 0,
        'is_active': False
    }).execute()

def update_user_field(supabase, user_id, data):
    data['updated_at'] = datetime.now().isoformat()
    supabase.table('users').update(data).eq('kakao_user_id', user_id).execute()

def reset_user_state(supabase, user_id):
    default_region_code = get_default_region_code(supabase)
    supabase.table('users').update({
        'ctpv_nm': '', 'sgg_nm': '', 'birth_year': 0, 'gender': '', 
        'region_code': default_region_code, 'region_depth': 0,
        'is_active': False
    }).eq('kakao_user_id', user_id).execute()

def get_default_region_code(supabase):
    try:
        # Fetch any valid region code (e.g., limit 1)
        res = supabase.table('regions').select('region_code').limit(1).execute()
        if res.data:
            return res.data[0]['region_code']
    except:
        pass
    return "1100000000" # Fallback to Seoul if query fails (hoping it exists)

def resolve_region_code(supabase, city, sgg):
    try:
        # Simple lookup fallback
        res = supabase.table('regions').select('region_code').eq('name', f"{city} {sgg}").execute()
        if res.data:
            return res.data[0]['region_code']
    except:
        pass
    return "0000000000"

def is_valid_city(text):
    cities = ["서울특별시", "경기도", "부산광역시", "인천광역시", "대구광역시", "경상남도", "경상북도", "전라남도", "전라북도", "충청남도", "충청북도", "광주광역시", "강원특별자치도", "대전광역시", "울산광역시", "세종특별자치시", "제주특별자치도"]
    return any(c in text for c in cities)

# ----------------------------------------------------
# Response Builders (Updated to 'message' action)
# ----------------------------------------------------

def response_select_city(fail_msg=False):
    cities = ["서울특별시", "경기도", "부산광역시", "인천광역시", "대구광역시", "경상남도", "경상북도", "전라남도", "전라북도", "충청남도", "충청북도", "광주광역시", "강원특별자치도"] 
    quick_replies = [{"label": c, "action": "message", "messageText": c} for c in cities]
    msg = "거주하시는 **지역(시/도)**을 선택해주세요." if not fail_msg else "정확한 지역(시/도)을 목록에서 선택해주세요."
    return build_response(msg, quick_replies)

def response_select_sgg(city, fail_msg=False):
    sgg_list = get_sgg_list_from_db(city)
    quick_replies = [{"label": s, "action": "message", "messageText": s} for s in sgg_list[:25]]
    msg = f"**{city}**의 어느 구/군에 사시나요?" if not fail_msg else "목록에 있는 구/군을 선택해주세요."
    return build_response(msg, quick_replies)

def response_select_birth_range(city, sgg):
    ranges = ["1930년대 이전", "1940년대", "1950년대", "1960년대", "1970년대 이후"]
    quick_replies = [{"label": r, "action": "message", "messageText": r} for r in ranges]
    return build_response(f"**{city} {sgg}**에 사시는군요.\n태어나신 연대가 언제이신가요?", quick_replies)

def response_select_birth_year(city, sgg, start_year_str):
    start_year = int(start_year_str)
    quick_replies = []
    for i in range(10):
        year = start_year + i
        quick_replies.append({"label": f"{year}년", "action": "message", "messageText": f"{year}년"})
    return build_response(f"정확한 출생연도를 선택해주세요.", quick_replies)

def response_select_gender(city, sgg, birth_year):
    quick_replies = [
        {"label": "남성", "action": "message", "messageText": "남성"},
        {"label": "여성", "action": "message", "messageText": "여성"}
    ]
    return build_response(f"성별을 선택해주세요.", quick_replies)



# ----------------------------------------------------
# Utilities
# ----------------------------------------------------

def get_sgg_list_from_db(ctpv_nm):
    """Fetch distinct SGG names for a CTPV from regions table"""
    try:
        supabase = SupabaseClient.get_client()
        # Assuming db structure: regions table has sgg_nm where ctpv_nm matches.
        # Actually regions table has 'name'. We might need to query 'regions' where 'parent_code' matches the ctpv code.
        # But 'regions' table stores full name in 'name'.
        # Easier: Query 'benefits' distinct sgg_nm? No, benefits might not cover all.
        # Query 'regions' with depth=2.
        
        # Let's simplify: Use hardcoded for demo or basic query if possible.
        # For 'regions' table: finding children of a city is complex without proper hierarchy mapping in code.
        # HACK: Query `benefits` table for distinct sgg_nm in that province (since we only care about places with benefits?)
        # Better HACK: Just hardcode for Jongno/Busan/etc as examples if DB is empty.
        
        # Let's try fetch from DB 'regions' table using 'sido_code' logic if available, OR just 'benefits'.
        # Actually, let's just query `regions` where name like '{ctpv_nm}%' and depth=2?
        # Regions table: name='서울특별시 종로구'.
        
        res = supabase.table('regions').select('name').ilike('name', f"{ctpv_nm}%").eq('depth', 2).execute()
        if res.data:
            # Extract SGG part. "서울특별시 종로구" -> "종로구"
            return [r['name'].replace(f"{ctpv_nm} ", "") for r in res.data]
            
        return ["종로구", "중구", "강남구"] # Fallback
    except:
        return ["종로구", "중구", "강남구"] # Fallback

def build_response(text, quick_replies):
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text
                    }
                }
            ],
            "quickReplies": quick_replies
        }
    }

def simple_text_response(text):
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": text
                    }
                }
            ]
        }
    }
