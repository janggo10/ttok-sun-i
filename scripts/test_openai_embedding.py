#!/usr/bin/env python3
"""
OpenAI text-embedding-3-small 테스트 스크립트
목적: API 연결 확인 및 기본 임베딩 생성 테스트
비용: $0.0001 (거의 무료)
"""
import os
import sys
from pathlib import Path
from openai import OpenAI

# .env 파일 자동 로드
def load_env_file():
    """프로젝트 루트의 .env 파일을 로드"""
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if not env_file.exists():
        print(f"⚠️  WARNING: .env 파일을 찾을 수 없습니다: {env_file}")
        return
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # 따옴표 제거
                value = value.strip().strip('"').strip("'")
                os.environ[key.strip()] = value
    
    print(f"✅ .env 파일 로드 완료: {env_file}")

# .env 로드 실행
load_env_file()

def test_openai_embedding():
    """OpenAI 임베딩 API 테스트"""
    
    # 1. API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY 환경변수가 설정되지 않았습니다!")
        print("   .env 파일을 확인하거나 다음 명령어로 설정하세요:")
        print("   export OPENAI_API_KEY='sk-proj-...'")
        sys.exit(1)
    
    print("✅ OPENAI_API_KEY 확인 완료")
    print(f"   Key 앞 10자: {api_key[:10]}...")
    print()
    
    # 2. OpenAI 클라이언트 초기화
    try:
        client = OpenAI(api_key=api_key)
        print("✅ OpenAI 클라이언트 초기화 성공")
    except Exception as e:
        print(f"❌ ERROR: OpenAI 클라이언트 초기화 실패: {e}")
        sys.exit(1)
    
    # 3. 테스트 텍스트 (한국어)
    test_texts = [
        "65세 이상 어르신을 위한 효도수당 지원 사업입니다.",
        "저소득 가구의 난방비를 지원하는 에너지 바우처 제도입니다.",
        "빈집 정리 및 철거 지원 사업으로 주거환경을 개선합니다."
    ]
    
    print()
    print("=" * 60)
    print("🧪 OpenAI text-embedding-3-small 테스트 시작")
    print("=" * 60)
    print()
    
    for idx, text in enumerate(test_texts, 1):
        print(f"[테스트 {idx}/3] {text[:30]}...")
        
        try:
            # 4. 임베딩 생성
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                dimensions=1536
            )
            
            # 5. 결과 확인
            embedding = response.data[0].embedding
            print(f"  ✅ 임베딩 생성 성공!")
            print(f"     - 차원: {len(embedding)}")
            print(f"     - 첫 5개 값: {embedding[:5]}")
            print(f"     - 토큰 사용량: {response.usage.total_tokens} tokens")
            print()
            
        except Exception as e:
            print(f"  ❌ ERROR: 임베딩 생성 실패: {e}")
            sys.exit(1)
    
    # 6. 비용 계산
    total_tokens = len(" ".join(test_texts).split()) * 1.5  # 대략적인 토큰 수
    estimated_cost = (total_tokens / 1_000_000) * 0.02
    
    print("=" * 60)
    print("🎉 모든 테스트 통과!")
    print("=" * 60)
    print(f"📊 예상 비용: ${estimated_cost:.6f} (약 {estimated_cost * 1400:.2f}원)")
    print()
    print("✅ OpenAI API가 정상적으로 작동합니다!")
    print("✅ text-embedding-3-small 모델을 사용할 준비가 되었습니다!")
    print()
    print("다음 단계:")
    print("1. Supabase 스키마 변경 (벡터 차원 1024 → 1536)")
    print("2. 전체 복지 데이터 재임베딩")
    print("3. Lambda 함수 배포")

if __name__ == "__main__":
    test_openai_embedding()
