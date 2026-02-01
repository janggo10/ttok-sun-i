#!/bin/bash
# SAM Deploy Script for ttok-sun-i
# 빌드 + 배포를 한 번에 실행합니다

set -e

echo "=========================================="
echo "🚀 ttok-sun-i 배포 시작"
echo "=========================================="
echo ""

# Build (--clean 옵션이 있으면 전달)
if [ "$1" = "--clean" ]; then
    echo "🧹 Clean build requested"
    ./build.sh --clean
    shift  # --clean 제거
else
    ./build.sh
fi

echo ""
echo "=========================================="
echo "📦 Deploying to AWS..."
echo "=========================================="
echo ""

# Deploy (자동 승인 + 강제 업로드)
# 남은 인자들만 전달 (--clean은 이미 제거됨)
sam deploy --no-confirm-changeset --force-upload "$@"

echo ""
echo "=========================================="
echo "🎉 배포 완료!"
echo "=========================================="
echo ""
echo "📋 유용한 명령어:"
echo "   • 실시간 로그: sam logs -n KakaoWebhookFunction --stack-name ttok-sun-i --tail"
echo "   • 스택 정보: aws cloudformation describe-stacks --stack-name ttok-sun-i"
echo "   • Webhook URL: aws cloudformation describe-stacks --stack-name ttok-sun-i --query 'Stacks[0].Outputs[?OutputKey==\`KakaoWebhookUrl\`].OutputValue' --output text"
echo ""
