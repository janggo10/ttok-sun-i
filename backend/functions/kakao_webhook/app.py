import json
import os
import sys
from datetime import datetime

# Python 3.11 업데이트 - 2026-01-31
# OpenAI text-embedding-3-small 전환 완료 + 상세 로그 (지역/생애주기/대상) - 2026-02-01 v29
# common 모듈 파일들이 같은 디렉토리에 있음

# 전역 변수로 클라이언트 재사용 (Cold Start 최적화)
_supabase_client = None
_rag_service = None

try:
    from supabase_client import SupabaseClient
    from rag_service import RAGService
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print(f"📂 sys.path: {sys.path}")
    print(f"📁 Current dir: {os.path.dirname(__file__) or '.'}")
    try:
        import glob
        files = glob.glob(os.path.join(os.path.dirname(__file__) or '.', '*.py'))
        print(f"📁 Python files: {[os.path.basename(f) for f in files]}")
    except:
        pass
    raise ImportError(f"Failed to import common modules: {e}")

# ----------------------------------------------------
# Main Handler with DB-State Logic
# ----------------------------------------------------

def lambda_handler(event, context):
    """
    KakaoTalk Chatbot Webhook Handler (Stateless -> DB Stateful)
    """
    global _supabase_client, _rag_service
    
    # Warming 요청 처리 (Cold Start 방지용)
    if event.get('warming'):
        return {'statusCode': 200, 'body': json.dumps({'status': 'warmed'})}
    
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

    # 2. Handle Special Commands
    print(f"💬 Utterance: '{utterance}'")
    print(f"👤 User exists: {user is not None}")
    
    # "시작하기" / "안녕" - 신규 가입자용
    if utterance in ['시작하기', '안녕']:
        if not user:
            # 신규 회원: 온보딩 시작
            create_initial_user(supabase, user_id)
            return api_response(response_select_city())
        else:
            # 기존 회원: 이미 가입됨 안내
            return api_response(simple_text_response(
                "이미 가입하셨습니다! 😊\n\n"
                "정보를 다시 입력하려면 '처음으로'를 입력하세요."
            ))
    
    # "처음으로" / "리셋" - 정보 재입력 (디버깅용)
    if utterance in ['처음으로', '리셋']:
        if user:
            # 기존 회원: 정보 초기화 후 온보딩 재시작
            reset_user_state(supabase, user_id)
        else:
            # 신규 회원: 온보딩 시작
            create_initial_user(supabase, user_id)
        return api_response(response_select_city())
    
    # 신규 회원 (특수 명령어 없이 메시지 입력)
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
            # Save gender and move to target_group selection
            update_user_field(supabase, user_id, {'gender': gender})
            return api_response(response_select_target_group(user['ctpv_nm'], user['sgg_nm'], user['birth_year']))
        else:
            return api_response(response_select_gender(user['ctpv_nm'], user['sgg_nm'], user['birth_year']))
    
    # State: Wait for Target Group (대상 특성)
    if user.get('target_group') is None:
        # Parse target_group from utterance
        target_group = parse_target_group(utterance)
        
        if target_group is not None:  # 선택 완료 (빈 배열 포함)
            # Calculate life_cycle from birth_year
            life_cycle = RAGService.convert_birth_year_to_life_cycle(user['birth_year'])
            
            # Complete onboarding!
            update_user_field(supabase, user_id, {
                'target_group': target_group,
                'life_cycle': life_cycle,
                'is_active': True,
                'region_code': resolve_region_code(supabase, user['ctpv_nm'], user['sgg_nm'])
            })
            
            # 온보딩 완료 메시지 + 자동 검색 🎉
            user['target_group'] = target_group
            user['life_cycle'] = life_cycle
            user['is_active'] = True
            
            completion_msg = f"🎉 등록이 완료되었습니다!\n\n" \
                           f"📍 지역: {user['ctpv_nm']} {user['sgg_nm']}\n" \
                           f"🎂 출생: {user['birth_year']}년 ({', '.join(life_cycle)})\n" \
                           f"👤 성별: {'남성' if user['gender']=='M' else '여성'}\n" \
                           f"🎯 대상: {', '.join(target_group) if target_group else '일반'}\n\n" \
                           f"회원님께 맞는 혜택을 찾고 있습니다... 🔍"
            
            # 자동 검색 실행
            return handle_search_query(supabase, user, "맞춤 혜택 추천", auto_search=True)
        else:
            return api_response(response_select_target_group(user['ctpv_nm'], user['sgg_nm'], user['birth_year']))

    # Onboarding Complete - Handle User Query
    return handle_search_query(supabase, user, utterance)


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
        'ctpv_nm': '', 
        'sgg_nm': '', 
        'birth_year': 0, 
        'gender': '', 
        'target_group': None,  # None = not set yet
        'life_cycle': None,    # Will be calculated from birth_year
        'region_code': default_region_code,
        'region_depth': 2,  # Default: 시군구 레벨
        'is_active': False
    }).execute()

def update_user_field(supabase, user_id, data):
    data['updated_at'] = datetime.now().isoformat()
    supabase.table('users').update(data).eq('kakao_user_id', user_id).execute()

def reset_user_state(supabase, user_id):
    default_region_code = get_default_region_code(supabase)
    supabase.table('users').update({
        'ctpv_nm': '', 
        'sgg_nm': '', 
        'birth_year': 0, 
        'gender': '', 
        'target_group': None,
        'life_cycle': None,
        'region_code': default_region_code,
        'region_depth': 2,  # Default: 시군구 레벨
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

def response_select_target_group(city, sgg, birth_year):
    """대상 특성 선택 (복지 혜택 필터링에 중요)"""
    target_options = [
        "저소득층",
        "장애인",
        "한부모가족",
        "다자녀가족",
        "다문화가족",
        "북한이탈주민",
        "국가유공자",
        "해당없음"
    ]
    quick_replies = [{"label": opt, "action": "message", "messageText": opt} for opt in target_options]
    msg = f"🎯 **대상 특성**을 선택해주세요.\n\n" \
          f"해당되는 항목이 있으면 선택하시면\n" \
          f"더 많은 맞춤 혜택을 받으실 수 있습니다.\n\n" \
          f"💡 해당 사항이 없으시면 '해당없음'을 선택해주세요."
    return build_response(msg, quick_replies)



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

def parse_target_group(utterance):
    """
    Parse target_group from user utterance.
    Returns:
        - list: Selected target groups (can be empty list for '해당없음')
        - None: Parsing failed, ask again
    """
    utterance_lower = utterance.lower().strip()
    
    # 해당없음
    if '해당없음' in utterance or '없음' in utterance or '해당사항없음' in utterance or '일반' in utterance:
        return []  # Empty array = 일반인
    
    # Map keywords to target_group values
    target_mapping = {
        '저소득': '저소득층',
        '장애': '장애인',
        '한부모': '한부모가족',
        '다자녀': '다자녀가족',
        '다문화': '다문화가족',
        '북한이탈': '북한이탈주민',
        '탈북': '북한이탈주민',
        '국가유공': '국가유공자',
        '보훈': '국가유공자'
    }
    
    selected = []
    for keyword, value in target_mapping.items():
        if keyword in utterance:
            selected.append(value)
    
    if selected:
        return selected
    
    # Could not parse
    return None

def handle_search_query(supabase, user, query, auto_search=False):
    """
    Handle user query using RAG service.
    
    Args:
        supabase: Supabase client
        user: User profile dict
        query: User's query text
        auto_search: If True, this is an automatic search after onboarding
    """
    try:
        # Validate user profile
        if not user.get('is_active'):
            return api_response(simple_text_response("먼저 회원 정보를 등록해주세요."))
        
        # Initialize RAG Service (환경변수에서 Supabase 자동 초기화)
        rag_service = RAGService()
        
        # Build user profile for RAG
        user_profile = {
            'ctpv_nm': user.get('ctpv_nm'),
            'sgg_nm': user.get('sgg_nm'),
            'birth_year': user.get('birth_year'),
            'gender': user.get('gender'),
            'life_cycle': user.get('life_cycle', []),
            'target_group': user.get('target_group', [])
        }
        
        # Search for services (디버깅용: top_k=30)
        results = rag_service.get_recommended_services(
            query_text=query,  # ← query_text로 수정!
            user_profile=user_profile,
            top_k=30  # 디버깅용 최대 개수
        )
        
        if not results:
            return api_response(simple_text_response(
                "죄송합니다. 😢\n\n"
                "현재 조건에 맞는 혜택을 찾지 못했습니다.\n\n"
                "다른 질문이나 키워드로 다시 시도해보시거나,\n"
                "'처음으로' 라고 말씀하시면 정보를 수정할 수 있습니다."
            ))
        
        # Format results (Option B: 상세 정보 표시 - 디버깅용)
        response_text = f"🎯 찾은 혜택: **{len(results)}개**\n\n"
        
        for idx, benefit in enumerate(results, 1):
            # Source type 표시 (벡터 검색 vs 자격 기반 필터)
            source_type = benefit.get('source_type', 'UNKNOWN')
            serv_nm = benefit.get('serv_nm', '제목 없음')
            similarity = benefit.get('similarity')
            
            # 지역 정보
            ctpv_nm = benefit.get('ctpv_nm', '')
            sgg_nm = benefit.get('sgg_nm', '')
            region_str = f"{ctpv_nm} {sgg_nm}".strip() if ctpv_nm or sgg_nm else "전국"
            
            # 생애주기 정보
            life_cycles = benefit.get('life_nm_array')
            life_str = ', '.join(life_cycles) if life_cycles and len(life_cycles) > 0 else "전체"
            
            # 대상 정보
            targets = benefit.get('trgter_indvdl_nm_array')
            target_str = ', '.join(targets) if targets and len(targets) > 0 else "전국민"
            
            # 디버깅: 서비스명, source_type, 유사도 점수, 지역, 생애주기, 대상 출력
            if source_type == 'VECTOR' and similarity is not None:
                print(f"[DEBUG] Benefit {idx}: {source_type}({similarity:.3f}) | 지역={region_str} | 생애주기=[{life_str}] | 대상=[{target_str}] | '{serv_nm}'")
            else:
                print(f"[DEBUG] Benefit {idx}: {source_type} | 지역={region_str} | 생애주기=[{life_str}] | 대상=[{target_str}] | '{serv_nm}' ")
            
            if source_type == 'VECTOR':
                source_icon = "🔍"
                # 유사도 점수 표시 (벡터 검색인 경우)
                similarity = benefit.get('similarity')
                if similarity is not None:
                    source_label = f"[AI검색 {similarity:.2f}]"
                else:
                    source_label = "[AI검색]"
            elif source_type == 'RULES':
                source_icon = "📋"
                source_label = "[자격기반]"
            else:
                source_icon = "❓"
                source_label = f"[{source_type}]"
            
            response_text += f"**{source_icon}{idx}. {benefit.get('serv_nm', '제목 없음')}** {source_label}\n"
            response_text += f"🆔 ID: {benefit.get('id', 'N/A')}\n"
            response_text += f"📍 {benefit.get('ctpv_nm', '')} {benefit.get('sgg_nm', '')}\n"
            
            # 대상 특성 (배열)
            targets = benefit.get('trgter_indvdl_nm_array')
            if targets and len(targets) > 0:
                response_text += f"👥 대상: {', '.join(targets)}\n"
            else:
                response_text += f"👥 대상: 전국민\n"
            
            # 생애주기 (디버깅용)
            life_cycles = benefit.get('life_nm_array')
            if life_cycles and len(life_cycles) > 0:
                response_text += f"📅 생애주기: {', '.join(life_cycles)}\n"
            else:
                response_text += f"📅 생애주기: 전국민\n"
            
            # 서비스 요약
            if benefit.get('serv_dgst'):
                desc = benefit['serv_dgst']
                if len(desc) > 150:
                    desc = desc[:150] + "..."
                response_text += f"📝 {desc}\n"
            
            # 상세 내용 (접기 형태로 추가)
            service_content = benefit.get('service_content')
            if service_content:
                # 300자 제한 (너무 길면 잘라내기)
                if len(service_content) > 300:
                    service_content = service_content[:300] + "..."
                response_text += f"\n💡 상세내용:\n{service_content}\n"
            
            # 마감일
            if benefit.get('enfc_end_ymd'):
                response_text += f"⏰ 마감: {benefit['enfc_end_ymd']}\n"
            
            # 상세 링크
            response_text += f"🔗 상세: {benefit.get('serv_dtl_link', '정보 없음')}\n"
            response_text += "\n" + "─" * 30 + "\n\n"
        
        # 온보딩 직후 vs 일반 검색에 따라 다른 안내 메시지
        if auto_search:
            response_text += "💬 궁금한 혜택을 아래 버튼을 눌러 질문해보세요!"
            
            # 온보딩 완료 후: 예시 질문 버튼
            quick_replies = [
                {"label": "청년 일자리 지원", "action": "message", "messageText": "청년 일자리 지원금 알려줘"},
                {"label": "육아 지원", "action": "message", "messageText": "육아 지원 혜택 있어?"},
                {"label": "주거비 지원", "action": "message", "messageText": "주거비 지원 받을 수 있을까?"},
                {"label": "처음으로", "action": "message", "messageText": "처음으로"}
            ]
        else:
            response_text += "💬 다른 혜택을 찾으시려면 아래 버튼을 눌러주세요!"
            
            # 일반 질문 후: 간단한 액션 버튼
            quick_replies = [
                {"label": "다른 혜택 찾기", "action": "message", "messageText": "다른 혜택 알려줘"},
                {"label": "처음으로", "action": "message", "messageText": "처음으로"}
            ]
        
        return api_response(build_response(response_text, quick_replies))
        
    except Exception as e:
        print(f"❌ Error in handle_search_query: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return api_response(simple_text_response(
            "죄송합니다. 😢\n\n"
            "혜택 검색 중 오류가 발생했습니다.\n\n"
            f"오류 내용: {str(e)}\n\n"
            "잠시 후 다시 시도해주세요."
        ))
