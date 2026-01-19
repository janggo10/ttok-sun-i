"""
똑순이 Slack 알림 유틸리티

2개의 웹훅 URL 사용:
- 모니터링 알람: info, success 레벨
- 에러 알람: warning, error 레벨
"""
import os
import json
import requests
from datetime import datetime
from typing import Optional, Dict, Any

# Slack 웹훅 URL (K-Wave Now와 동일한 채널 사용)
SLACK_MONITORING_WEBHOOK_URL = "https://hooks.slack.com/services/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"
SLACK_ERROR_WEBHOOK_URL = "https://hooks.slack.com/services/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"


def send_slack_notification(
    message: str,
    level: str = "info",
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Slack 알림 전송
    
    Args:
        message: 메인 메시지
        level: info, warning, error, success
        details: 추가 상세 정보
        
    Returns:
        성공 여부
    """
    # 색상 코딩
    colors = {
        "info": "#36a64f",      # 초록
        "warning": "#ff9800",   # 주황
        "error": "#f44336",     # 빨강
        "success": "#4caf50",   # 연두
    }
    
    # 이모지 매핑
    emojis = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "success": "✅",
    }
    
    # Attachment 구성
    attachment = {
        "color": colors.get(level, "#808080"),
        "title": f"{emojis.get(level, '📢')} {message}",
        "fields": [],
        "footer": f"똑순이 [{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'local')}@{os.environ.get('AWS_REGION', 'ap-northeast-2')}]",
        "ts": int(datetime.now().timestamp())
    }
    
    # 상세 정보 추가
    if details:
        for key, value in details.items():
            attachment["fields"].append({
                "title": key,
                "value": str(value),
                "short": len(str(value)) < 50
            })
    
    payload = {
        "attachments": [attachment]
    }
    
    # 레벨에 따라 웹훅 URL 선택
    webhook_url = SLACK_MONITORING_WEBHOOK_URL
    if level in ["error", "warning"]:
        webhook_url = SLACK_ERROR_WEBHOOK_URL
    
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        if response.status_code != 200:
            print(f"❌ Slack 알림 실패: {response.status_code}")
            return False
        else:
            print(f"✅ Slack 알림 전송: {message}")
            return True
            
    except Exception as e:
        print(f"❌ Slack 알림 에러: {e}")
        return False


def notify_data_collection_complete(stats: Dict[str, Any]) -> bool:
    """데이터 수집 완료 알림"""
    details = {
        "출처": stats.get('source', '알 수 없음'),
        "수집 성공": stats.get('success', 0),
        "수집 실패": stats.get('failed', 0),
        "중복 제거": stats.get('duplicates', 0),
        "최종 저장": stats.get('saved', 0),
    }
    
    return send_slack_notification(
        "데이터 수집 완료",
        level="success",
        details=details
    )


def notify_data_collection_error(source: str, error_message: str) -> bool:
    """데이터 수집 에러 알림"""
    return send_slack_notification(
        f"데이터 수집 실패: {source}",
        level="error",
        details={"에러": error_message}
    )


def notify_user_onboarding(user_id: str, region: str = None) -> bool:
    """신규 사용자 온보딩 알림"""
    details = {
        "사용자 ID": user_id,
    }
    if region:
        details["지역"] = region
    
    return send_slack_notification(
        "신규 사용자 가입",
        level="info",
        details=details
    )


def notify_api_error(endpoint: str, error: str) -> bool:
    """API 에러 알림"""
    return send_slack_notification(
        f"API 에러: {endpoint}",
        level="error",
        details={"에러": error}
    )


def notify_info(message: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """일반 정보 알림"""
    return send_slack_notification(message, level="info", details=details)


def notify_warning(message: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """경고 알림"""
    return send_slack_notification(message, level="warning", details=details)


def notify_error(message: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """에러 알림"""
    return send_slack_notification(message, level="error", details=details)


# 레거시 호환성을 위한 클래스 (기존 코드와 호환)
class SlackNotifier:
    """Slack 알림 클래스 (레거시 호환)"""
    
    def send_alert(self, title: str, message: str, level: str = 'INFO'):
        """알림 전송 (레거시 메서드)"""
        level_map = {
            'INFO': 'info',
            'WARNING': 'warning',
            'ERROR': 'error'
        }
        return send_slack_notification(
            title,
            level=level_map.get(level, 'info'),
            details={"메시지": message}
        )
    
    def send_sync_report(self, source: str, success: int, failed: int, duplicates: int):
        """데이터 수집 리포트 (레거시 메서드)"""
        return notify_data_collection_complete({
            'source': source,
            'success': success,
            'failed': failed,
            'duplicates': duplicates,
            'saved': success - duplicates
        })
    
    def send_error(self, function_name: str, error: Exception):
        """에러 알림 (레거시 메서드)"""
        return notify_error(
            f"함수 에러: {function_name}",
            details={
                "에러": str(error),
                "타입": type(error).__name__
            }
        )
