"""
카카오톡 챗봇 웹훅 핸들러
"""
import json

from common.slack_notifier import SlackNotifier
from common.supabase_client import SupabaseClient


slack = SlackNotifier()
supabase = SupabaseClient.get_client()


def lambda_handler(event, context):
    """카카오 챗봇 웹훅 핸들러"""
    print("🚀 Lambda handler started")
    try:
        print(f"📥 Raw event: {json.dumps(event, ensure_ascii=False)}")
        
        print("📦 Parsing body...")
        body = json.loads(event['body'])
        print(f"✅ Body parsed successfully")
        
        user_key = body['userRequest']['user']['id']
        utterance = body['userRequest']['utterance']
        print(f"👤 User: {user_key}, Message: {utterance}")
        
        # 사용자 조회 또는 생성
        print("🔍 Getting user...")
        user = get_or_create_user(user_key)
        print(f"✅ User retrieved")
        
        # 온보딩 상태 확인
        if not user.get('region_code') or not user.get('birth_year'):
            print("📝 Onboarding needed")
            return handle_onboarding(body, user)
        
        # 일반 대화 처리 (다음 단계에서 구현)
        print("💬 Sending simple response")
        return simple_response("안녕하세요! 똑순이입니다 👵\\n\\n혜택 검색 기능은 곧 준비됩니다!")
        
    except Exception as e:
        import traceback
        error_msg = f"❌ ERROR: {str(e)}"
        error_trace = traceback.format_exc()
        print(error_msg)
        print(f"📋 Traceback:\n{error_trace}")
        slack.send_error('kakao_webhook', e)
        return error_response()


def get_or_create_user(kakao_user_id: str):
    """사용자 조회 또는 생성"""
    result = supabase.table('users').select('*').eq('kakao_user_id', kakao_user_id).execute()
    
    if result.data:
        return result.data[0]
    
    # 신규 사용자 생성
    new_user = supabase.table('users').insert({
        'kakao_user_id': kakao_user_id
    }).execute()
    
    slack.send_alert('신규 사용자', f'사용자 ID: {kakao_user_id}', 'INFO')
    return new_user.data[0]


def handle_onboarding(body, user):
    """온보딩 플로우 처리"""
    utterance = body['userRequest']['utterance']
    
    # 지역 설정 미완료
    if not user.get('region_code'):
        # TODO: 지역 파싱 로직 구현
        return simple_response(
            '안녕하세요! 똑순이입니다 👵\\n\\n'
            '맞춤 혜택을 알려드리려면 거주 지역이 필요해요.\\n\\n'
            '예) 서울특별시 은평구\\n'
            '예) 부산광역시 해운대구'
        )
    
    # 출생연도 미완료
    if not user.get('birth_year'):
        # TODO: 출생연도 파싱 로직 구현
        return simple_response(
            '출생 연도를 알려주세요.\\n\\n'
            '예) 1955\\n'
            '예) 1960'
        )


def simple_response(text: str):
    """간단한 텍스트 응답"""
    kakao_response = {
        'version': '2.0',
        'template': {
            'outputs': [{
                'simpleText': {
                    'text': text
                }
            }]
        }
    }
    
    # API Gateway Lambda Proxy 형식으로 반환
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(kakao_response, ensure_ascii=False)
    }


def error_response():
    """에러 응답"""
    return simple_response(
        '죄송합니다. 일시적인 오류가 발생했어요.\\n'
        '잠시 후 다시 시도해주세요.'
    )
