"""
Slack 알림 유틸리티

사용법:
    from scripts.utils.slack_notifier import send_success_notification, send_error_notification
    
    send_success_notification(
        title="데이터 수집 완료",
        message="중앙부처 복지 데이터 수집이 완료되었습니다.",
        stats={"total": 374, "success": 370, "failed": 4}
    )
"""

import os
import json
import requests
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Slack Webhook URLs from environment variables
SLACK_SUCCESS_WEBHOOK = os.getenv("SLACK_SUCCESS_WEBHOOK_URL")
SLACK_ERROR_WEBHOOK = os.getenv("SLACK_ERROR_WEBHOOK_URL")


def send_slack_message(webhook_url: str, payload: dict) -> bool:
    """Send a message to Slack via webhook"""
    if not webhook_url:
        logger.warning("Slack webhook URL not configured. Skipping notification.")
        return False
    
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        logger.info("Slack notification sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def send_success_notification(
    title: str,
    message: str,
    stats: Optional[Dict] = None,
    color: str = "good"
) -> bool:
    """
    성공 채널에 알림 전송
    
    Args:
        title: 알림 제목
        message: 알림 메시지
        stats: 통계 데이터 (예: {"total": 100, "success": 98, "failed": 2})
        color: 메시지 색상 (good=녹색, warning=노랑, danger=빨강)
    """
    fields = []
    
    # 통계 정보 추가
    if stats:
        for key, value in stats.items():
            # 한글 라벨 매핑
            label_map = {
                "total": "총 조회",
                "success": "성공",
                "failed": "실패",
                "new": "신규 생성",
                "updated": "갱신",
                "skipped": "스킵"
            }
            label = label_map.get(key, key)
            
            # 이모지 추가
            emoji_map = {
                "total": "📊",
                "success": "✅",
                "failed": "❌",
                "new": "🆕",
                "updated": "🔄",
                "skipped": "⏭️"
            }
            emoji = emoji_map.get(key, "•")
            
            fields.append({
                "title": f"{emoji} {label}",
                "value": f"{value:,}건",
                "short": True
            })
    
    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"🎉 {title}",
                "text": message,
                "fields": fields,
                "footer": "똑선이 데이터 파이프라인",
                "ts": int(datetime.now().timestamp())
            }
        ]
    }
    
    return send_slack_message(SLACK_SUCCESS_WEBHOOK, payload)


def send_error_notification(
    title: str,
    error_message: str,
    details: Optional[str] = None,
    stats: Optional[Dict] = None
) -> bool:
    """
    에러 채널에 알림 전송
    
    Args:
        title: 에러 제목
        error_message: 에러 메시지
        details: 상세 정보 (스택 트레이스 등)
        stats: 통계 데이터
    """
    fields = []
    
    # 에러 메시지 추가
    if error_message:
        fields.append({
            "title": "⚠️ 에러 메시지",
            "value": f"```{error_message[:500]}```",
            "short": False
        })
    
    # 상세 정보 추가
    if details:
        fields.append({
            "title": "📋 상세 정보",
            "value": f"```{details[:500]}```",
            "short": False
        })
    
    # 통계 정보 추가
    if stats:
        stats_text = "\n".join([f"• {k}: {v}" for k, v in stats.items()])
        fields.append({
            "title": "📊 통계",
            "value": stats_text,
            "short": False
        })
    
    payload = {
        "attachments": [
            {
                "color": "danger",
                "title": f"🚨 {title}",
                "text": "데이터 파이프라인에서 에러가 발생했습니다.",
                "fields": fields,
                "footer": "똑선이 데이터 파이프라인",
                "ts": int(datetime.now().timestamp())
            }
        ]
    }
    
    return send_slack_message(SLACK_ERROR_WEBHOOK, payload)


def send_pipeline_summary(
    total_time: float,
    results: Dict[str, bool],
    stats: Dict[str, Dict]
) -> bool:
    """
    전체 파이프라인 요약 알림
    
    Args:
        total_time: 총 실행 시간 (초)
        results: 각 단계별 성공/실패 여부 {"national": True, "local": True, "embedding": True}
        stats: 각 단계별 통계 {"national": {...}, "local": {...}, "embedding": {...}}
    """
    all_success = all(v is not False for v in results.values())
    
    fields = []
    
    # 중앙부처
    if results.get("national") is not None:
        nat_stats = stats.get("national", {})
        status = "✅" if results.get("national") else "❌"
        value = f"{status} 조회: {nat_stats.get('total', 0)}건, 성공: {nat_stats.get('success', 0)}건, 실패: {nat_stats.get('failed', 0)}건"
        fields.append({"title": "중앙부처 수집", "value": value, "short": False})
    
    # 지자체
    if results.get("local") is not None:
        local_stats = stats.get("local", {})
        status = "✅" if results.get("local") else "❌"
        value = f"{status} 조회: {local_stats.get('total', 0)}건, 성공: {local_stats.get('success', 0)}건, 실패: {local_stats.get('failed', 0)}건"
        fields.append({"title": "지자체 수집", "value": value, "short": False})
    
    # 임베딩
    if results.get("embedding") is not None:
        emb_stats = stats.get("embedding", {})
        status = "✅" if results.get("embedding") else "❌"
        value = f"{status} 신규: {emb_stats.get('new', 0)}건, 갱신: {emb_stats.get('updated', 0)}건, 스킵: {emb_stats.get('skipped', 0)}건"
        fields.append({"title": "임베딩 생성", "value": value, "short": False})
    
    # 실행 시간
    fields.append({
        "title": "⏱️ 총 실행 시간",
        "value": f"{total_time:.1f}초 ({total_time/60:.1f}분)",
        "short": True
    })
    
    if all_success:
        return send_success_notification(
            title="전체 파이프라인 완료",
            message="모든 단계가 성공적으로 완료되었습니다! 🎉",
            stats=None  # fields에 이미 포함
        )
    else:
        # 실패한 단계 찾기
        failed_steps = [k for k, v in results.items() if v is False]
        return send_error_notification(
            title="파이프라인 일부 실패",
            error_message=f"다음 단계가 실패했습니다: {', '.join(failed_steps)}",
            details=None,
            stats=None
        )

