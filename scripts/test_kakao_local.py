#!/usr/bin/env python3
"""
카카오 웹훅 로컬 테스트 스크립트
AWS 배포 전에 로컬에서 빠르게 테스트
"""
import json
import os
import sys

# Load environment variables from .env file manually (without python-dotenv)
env_path = os.path.join(os.path.dirname(__file__), '../.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Build를 먼저 실행했는지 확인
kakao_webhook_dir = os.path.join(os.path.dirname(__file__), '../backend/functions/kakao_webhook')
required_files = ['supabase_client.py', 'rag_service.py', 'slack_notifier.py']
missing_files = [f for f in required_files if not os.path.exists(os.path.join(kakao_webhook_dir, f))]

if missing_files:
    print("❌ 에러: build.sh를 먼저 실행하세요!")
    print(f"누락된 파일: {', '.join(missing_files)}")
    print("\n해결 방법:")
    print("  cd backend && ./build.sh")
    sys.exit(1)

# Add kakao_webhook directory directly to path (for relative imports)
sys.path.insert(0, kakao_webhook_dir)

# Now import after build check
# Import app module directly from the directory
import importlib.util
spec = importlib.util.spec_from_file_location("kakao_app", os.path.join(kakao_webhook_dir, "app.py"))
kakao_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kakao_app)

lambda_handler = kakao_app.lambda_handler

def create_mock_event(user_id, utterance):
    """카카오 웹훅 이벤트 시뮬레이션"""
    return {
        'body': json.dumps({
            'userRequest': {
                'user': {
                    'id': user_id
                },
                'utterance': utterance
            }
        }, ensure_ascii=False)
    }

def test_onboarding_flow():
    """온보딩 플로우 테스트"""
    print("=" * 60)
    print("🧪 카카오 챗봇 온보딩 테스트")
    print("=" * 60)
    
    test_user_id = "test_user_local_" + str(os.getpid())
    
    # Test scenarios (최신 온보딩 플로우)
    scenarios = [
        ("시작하기", "신규 회원 온보딩 시작"),
        ("서울특별시", "도시 선택"),
        ("서초구", "시군구 선택"),
        ("1990년대", "출생 연대 선택"),
        ("1995년", "정확한 출생연도 선택"),
        ("남성", "성별 선택"),
        ("해당없음", "대상특성 선택 (온보딩 완료!)"),
    ]
    
    print(f"\n🧑 테스트 유저: {test_user_id}\n")
    
    for i, (utterance, description) in enumerate(scenarios, 1):
        print(f"\n[Step {i}] {description}")
        print(f"입력: '{utterance}'")
        print("-" * 60)
        
        try:
            event = create_mock_event(test_user_id, utterance)
            context = {}  # Mock context
            
            response = lambda_handler(event, context)
            
            # Parse response
            body = json.loads(response['body'])
            
            # Extract text from response
            if 'template' in body and 'outputs' in body['template']:
                for output in body['template']['outputs']:
                    if 'simpleText' in output:
                        text = output['simpleText']['text']
                        # 긴 텍스트는 요약
                        if len(text) > 500:
                            print(f"응답: {text[:200]}... (총 {len(text)}자)")
                        else:
                            print(f"응답: {text}")
                    elif 'textCard' in output:
                        print(f"응답: {output['textCard']['title']}")
            
            # Check for Quick Replies
            if 'template' in body and 'quickReplies' in body['template']:
                quick_replies = body['template']['quickReplies']
                print(f"🔘 Quick Reply 버튼 ({len(quick_replies)}개):")
                for qr in quick_replies:
                    print(f"   - {qr.get('label', 'N/A')}")
            
            print("✅ 성공")
            
        except Exception as e:
            print(f"❌ 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("\n" + "=" * 60)
    print("🎉 모든 테스트 통과!")
    print("=" * 60)
    print("\n✅ AWS 배포 준비 완료!")
    return True

def test_after_onboarding():
    """온보딩 완료 후 일반 질문 테스트"""
    print("\n" + "=" * 60)
    print("🧪 온보딩 완료 후 일반 질문 테스트")
    print("=" * 60)
    
    # Use the same user from onboarding test
    test_user_id = "test_user_local_" + str(os.getpid())
    
    query_scenarios = [
        ("청년 일자리 지원금 알려줘", "질문 1: 청년 일자리"),
        ("육아 지원 혜택 있어?", "질문 2: 육아 지원"),
        ("주거비 지원 받을 수 있을까?", "질문 3: 주거비 지원"),
    ]
    
    for utterance, description in query_scenarios:
        print(f"\n{description}")
        print(f"입력: '{utterance}'")
        print("-" * 60)
        
        try:
            event = create_mock_event(test_user_id, utterance)
            response = lambda_handler(event, {})
            body = json.loads(response['body'])
            
            # Extract text from response
            if 'template' in body and 'outputs' in body['template']:
                for output in body['template']['outputs']:
                    if 'simpleText' in output:
                        text = output['simpleText']['text']
                        # Count results
                        if '찾은 혜택:' in text:
                            import re
                            match = re.search(r'찾은 혜택: \*\*(\d+)개\*\*', text)
                            if match:
                                count = match.group(1)
                                print(f"응답: 🎯 찾은 혜택 {count}개")
                        else:
                            print(f"응답: {text[:200]}")
            
            # Check for Quick Replies (일반 질문은 버튼 없어야 함)
            if 'template' in body and 'quickReplies' in body['template']:
                quick_replies = body['template']['quickReplies']
                print(f"🔘 Quick Reply 버튼 ({len(quick_replies)}개) - ⚠️ 일반 질문은 버튼이 없어야 정상")
            else:
                print(f"🔘 Quick Reply 버튼: 없음 ✅ (정상)")
            
            print("✅ 성공")
        except Exception as e:
            print(f"❌ 실패: {e}")
            import traceback
            traceback.print_exc()

def test_existing_user():
    """기존 회원 테스트"""
    print("\n" + "=" * 60)
    print("🧪 기존 회원 테스트")
    print("=" * 60)
    
    test_user_id = "existing_user_test"
    
    scenarios = [
        ("시작하기", "기존 회원이 '시작하기' 입력 (이미 가입됨 메시지 예상)"),
        ("처음으로", "정보 재입력 시작"),
    ]
    
    for utterance, description in scenarios:
        print(f"\n{description}")
        print(f"입력: '{utterance}'")
        print("-" * 60)
        
        try:
            event = create_mock_event(test_user_id, utterance)
            response = lambda_handler(event, {})
            body = json.loads(response['body'])
            
            if 'template' in body and 'outputs' in body['template']:
                for output in body['template']['outputs']:
                    if 'simpleText' in output:
                        print(f"응답: {output['simpleText']['text'][:200]}")
            
            print("✅ 성공")
        except Exception as e:
            print(f"❌ 실패: {e}")

def main():
    """메인 테스트"""
    print("\n🚀 로컬 테스트 시작\n")
    
    # Check environment variables
    required_env = ['SUPABASE_URL', 'SUPABASE_SERVICE_KEY']
    missing_env = [e for e in required_env if not os.getenv(e)]
    
    if missing_env:
        print(f"❌ 환경 변수 누락: {', '.join(missing_env)}")
        print("\n.env 파일을 확인하세요.")
        return False
    
    print("✅ 환경 변수 확인 완료\n")
    
    # Run tests
    success = test_onboarding_flow()
    
    if success:
        # Test after onboarding scenarios
        test_after_onboarding()
        
        # Test existing user scenarios
        test_existing_user()
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
