#!/usr/bin/env python3
"""
똑선이 전체 데이터 파이프라인 실행 스크립트

실행 순서:
1. 중앙부처 복지 데이터 수집
2. 지자체 복지 데이터 수집
3. 임베딩 생성 (변경된 항목만)

사용법:
    python scripts/run_full_pipeline.py
    
    # 특정 단계만 실행
    python scripts/run_full_pipeline.py --skip-national  # 중앙부처 스킵
    python scripts/run_full_pipeline.py --skip-local     # 지자체 스킵
    python scripts/run_full_pipeline.py --skip-embedding # 임베딩 스킵
"""

import os
import sys
import logging
import subprocess
import time
import json
import re
from datetime import datetime
import argparse

# Setup logging first (before imports that use logger)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import slack notifier
try:
    from scripts.utils.slack_notifier import send_success_notification, send_error_notification, send_pipeline_summary
    SLACK_ENABLED = True
except ImportError:
    logger.warning("Slack notifier not available. Notifications will be skipped.")
    SLACK_ENABLED = False
    def send_success_notification(*args, **kwargs):
        pass
    def send_error_notification(*args, **kwargs):
        pass
    def send_pipeline_summary(*args, **kwargs):
        pass

# Script paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NATIONAL_SCRIPT = os.path.join(SCRIPT_DIR, "data_collection", "collect_national_welfare.py")
LOCAL_SCRIPT = os.path.join(SCRIPT_DIR, "data_collection", "collect_local_welfare.py")
EMBEDDING_SCRIPT = os.path.join(SCRIPT_DIR, "embeddings", "generate_embeddings.py")


def run_script(script_path, script_name):
    """Run a Python script and return (success, result_dict)"""
    logger.info(f"")
    logger.info(f"{'='*60}")
    logger.info(f"🚀 Starting: {script_name}")
    logger.info(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        # Parse result from stdout
        result_data = {}
        if result.stdout:
            # Look for __PIPELINE_RESULT__:{json}
            match = re.search(r'__PIPELINE_RESULT__:(\{.*?\})', result.stdout)
            if match:
                try:
                    result_data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Completed: {script_name} (took {elapsed:.1f}s)")
        return True, result_data
        
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Failed: {script_name} (after {elapsed:.1f}s)")
        logger.error(f"Error output:\n{e.stderr}")
        return False, {}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Failed: {script_name} (after {elapsed:.1f}s)")
        logger.error(f"Unexpected error: {e}")
        return False, {}


def main():
    parser = argparse.ArgumentParser(description="Run full data collection and embedding pipeline")
    parser.add_argument("--skip-national", action="store_true", help="Skip national welfare collection")
    parser.add_argument("--skip-local", action="store_true", help="Skip local welfare collection")
    parser.add_argument("--skip-embedding", action="store_true", help="Skip embedding generation")
    args = parser.parse_args()
    
    logger.info("")
    logger.info("╔═══════════════════════════════════════════════════════════╗")
    logger.info("║       똑선이 전체 데이터 파이프라인 시작                 ║")
    logger.info("╚═══════════════════════════════════════════════════════════╝")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    pipeline_start = time.time()
    results = {}
    stats = {}
    
    # Step 1: National Welfare Collection
    if not args.skip_national:
        success, data = run_script(NATIONAL_SCRIPT, "중앙부처 복지 데이터 수집")
        results["national"] = success
        stats["national"] = data
        
        if success and SLACK_ENABLED:
            send_success_notification(
                title="중앙부처 복지 데이터 수집 완료",
                message="중앙부처 복지 데이터 수집이 성공적으로 완료되었습니다.",
                stats=data
            )
        elif not success:
            logger.error("⚠️  중앙부처 데이터 수집 실패. 계속 진행합니다...")
            if SLACK_ENABLED:
                send_error_notification(
                    title="중앙부처 데이터 수집 실패",
                    error_message="중앙부처 복지 데이터 수집 중 오류가 발생했습니다.",
                    stats=data
                )
    else:
        logger.info("⏭️  Skipping: 중앙부처 복지 데이터 수집")
        results["national"] = None
        stats["national"] = {}
    
    # Step 2: Local Welfare Collection
    if not args.skip_local:
        success, data = run_script(LOCAL_SCRIPT, "지자체 복지 데이터 수집")
        results["local"] = success
        stats["local"] = data
        
        if success and SLACK_ENABLED:
            send_success_notification(
                title="지자체 복지 데이터 수집 완료",
                message="지자체 복지 데이터 수집이 성공적으로 완료되었습니다.",
                stats=data
            )
        elif not success:
            logger.error("⚠️  지자체 데이터 수집 실패. 계속 진행합니다...")
            if SLACK_ENABLED:
                send_error_notification(
                    title="지자체 데이터 수집 실패",
                    error_message="지자체 복지 데이터 수집 중 오류가 발생했습니다.",
                    stats=data
                )
    else:
        logger.info("⏭️  Skipping: 지자체 복지 데이터 수집")
        results["local"] = None
        stats["local"] = {}
    
    # Step 3: Embedding Generation
    if not args.skip_embedding:
        # Only run embeddings if at least one collection succeeded
        if results.get("national") or results.get("local"):
            success, data = run_script(EMBEDDING_SCRIPT, "임베딩 생성")
            results["embedding"] = success
            stats["embedding"] = data
            
            if success and SLACK_ENABLED:
                send_success_notification(
                    title="임베딩 생성 완료",
                    message="벡터 임베딩 생성이 성공적으로 완료되었습니다.",
                    stats=data
                )
            elif not success and SLACK_ENABLED:
                send_error_notification(
                    title="임베딩 생성 실패",
                    error_message="벡터 임베딩 생성 중 오류가 발생했습니다.",
                    stats=data
                )
        else:
            logger.warning("⚠️  데이터 수집이 모두 실패하여 임베딩 생성을 스킵합니다.")
            results["embedding"] = False
            stats["embedding"] = {}
    else:
        logger.info("⏭️  Skipping: 임베딩 생성")
        results["embedding"] = None
        stats["embedding"] = {}
    
    # Summary
    pipeline_elapsed = time.time() - pipeline_start
    
    logger.info("")
    logger.info("╔═══════════════════════════════════════════════════════════╗")
    logger.info("║               파이프라인 실행 완료                       ║")
    logger.info("╚═══════════════════════════════════════════════════════════╝")
    logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total time: {pipeline_elapsed:.1f}s ({pipeline_elapsed/60:.1f} minutes)")
    logger.info("")
    logger.info("Results:")
    
    # National
    if results.get('national') is None:
        logger.info(f"  중앙부처 수집: ⏭️  Skipped")
    elif results.get('national'):
        nat_data = stats.get('national', {})
        total = nat_data.get('total', 0)
        success = nat_data.get('success', 0)
        failed = nat_data.get('failed', 0)
        logger.info(f"  중앙부처 수집: ✅ Success (조회: {total}건, 성공: {success}건, 실패: {failed}건)")
    else:
        logger.info(f"  중앙부처 수집: ❌ Failed")
    
    # Local
    if results.get('local') is None:
        logger.info(f"  지자체 수집:   ⏭️  Skipped")
    elif results.get('local'):
        local_data = stats.get('local', {})
        total = local_data.get('total', 0)
        success = local_data.get('success', 0)
        failed = local_data.get('failed', 0)
        logger.info(f"  지자체 수집:   ✅ Success (조회: {total}건, 성공: {success}건, 실패: {failed}건)")
    else:
        logger.info(f"  지자체 수집:   ❌ Failed")
    
    # Embedding
    if results.get('embedding') is None:
        logger.info(f"  임베딩 생성:   ⏭️  Skipped")
    elif results.get('embedding'):
        emb_data = stats.get('embedding', {})
        new = emb_data.get('new', 0)
        updated = emb_data.get('updated', 0)
        skipped = emb_data.get('skipped', 0)
        logger.info(f"  임베딩 생성:   ✅ Success (신규: {new}건, 갱신: {updated}건, 스킵: {skipped}건)")
    else:
        logger.info(f"  임베딩 생성:   ❌ Failed")
    
    # Send pipeline summary to Slack
    if SLACK_ENABLED:
        send_pipeline_summary(
            total_time=pipeline_elapsed,
            results=results,
            stats=stats
        )
    
    # Exit code
    all_success = all(v is not False for v in results.values())
    if all_success:
        logger.info("")
        logger.info("🎉 All steps completed successfully!")
        sys.exit(0)
    else:
        logger.error("")
        logger.error("⚠️  Some steps failed. Please check the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

