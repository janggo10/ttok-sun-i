#!/bin/bash
# SAM Build Script for ttok-sun-i
# 자동으로 common 모듈을 각 Lambda 함수에 복사하고 빌드합니다 (Flat 구조)

set -e

echo "=================================="
echo "🚀 ttok-sun-i Build Script"
echo "=================================="
echo ""

# Clean build cache (선택적)
# --clean 옵션이 있거나 .aws-sam이 없으면 삭제
if [ "$1" = "--clean" ]; then
    echo "🧹 Cleaning build cache..."
    rm -rf .aws-sam
    echo "   ✅ Removed .aws-sam/"
    shift  # --clean 제거 (sam build에 전달하지 않기 위해)
elif [ ! -d ".aws-sam" ]; then
    echo "🧹 Cleaning build cache..."
    rm -rf .aws-sam
    echo "   ✅ Removed .aws-sam/"
else
    echo "♻️  Using existing build cache (빠른 빌드)"
    echo "   💡 Tip: 전체 재빌드는 './build.sh --clean'"
fi
echo ""

# Prepare common modules for each Lambda function (Flat structure)
echo "📦 Copying common modules to Lambda functions..."
for func_dir in functions/*/; do
    if [ -f "${func_dir}app.py" ]; then
        func_name=$(basename "$func_dir")
        echo "   📦 $func_name"
        
        # Copy common modules directly to function directory
        cp common/supabase_client.py "${func_dir}supabase_client.py"
        cp common/rag_service.py "${func_dir}rag_service.py"
        cp common/slack_notifier.py "${func_dir}slack_notifier.py"
    fi
done
echo "   ✅ Common modules copied to all functions"
echo ""

# Build SAM
echo "🏗️  Building SAM application..."
sam build "$@"

echo ""
echo "=================================="
echo "✨ Build completed successfully!"
echo "=================================="
echo ""
echo "📋 Next steps:"
echo "   • Deploy: sam deploy"
echo "   • Or use: ./deploy.sh"
echo "   • Logs: sam logs -n ttok-sun-i-kakao-webhook --tail"
echo ""
