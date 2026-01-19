"""
데이터 수집 Lambda 함수 (Placeholder)
TODO: 실제 데이터 수집 로직 구현
"""
import json


def lambda_handler(event, context):
    """
    데이터 수집 Lambda 핸들러
    
    TODO:
    - 보조금24 API 연동
    - 행정안전부 API 연동
    - PDF/HWP 문서 파싱
    - 임베딩 생성 및 저장
    """
    print("데이터 수집 함수 실행 (아직 구현되지 않음)")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Data collector placeholder - 구현 예정'
        })
    }
