# Onboarding Implementation Guide

이 문서는 카카오톡 챗봇의 **초기 사용자 온보딩(지역 설정, 출생연도 설정)** 로직 구현을 위한 가이드입니다.

## 1. 사전 준비 사항
*   **Supabase RPC 함수**: `search_regions` 함수가 Supabase에 생성되어 있어야 합니다. (`supabase/functions/search_regions.sql`)
*   **패키지**: `requests` (이미 설치됨), `supbabase-py` (이미 설치됨)

## 2. 구현 목표
사용자가 처음 말을 걸었을 때, 다음 순서로 정보를 수집합니다.
1.  **지역 설정**: 사용자가 입력한 텍스트(예: "역삼동")로 행정구역을 검색하고, 선택할 수 있는 **List Card**를 보여줍니다.
2.  **출생연도 설정**: 지역 설정이 완료되면 출생연도를 물어보고 저장합니다.

## 3. 상세 구현 단계

### 3.1. `backend/functions/kakao_webhook/app.py` 수정

기존 `app.py`의 `handle_onboarding` 함수를 확장하여 검색 및 선택 로직을 추가해야 합니다.

#### 주요 로직 변경 흐름
1.  사용자 발화가 **"지역선택: "** 패턴으로 시작하는지 확인합니다.
    *   참이면: 사용자가 리스트에서 지역을 선택한 것입니다. -> DB에 지역 정보 저장 -> 출생연도 질문으로 넘어감.
2.  사용자 지역 정보(`region_code`)가 없는 경우:
    *   사용자 발화를 검색어(`keyword`)로 간주합니다.
    *   Supabase RPC `search_regions` 호출.
    *   검색 결과가 없으면: "다시 입력해주세요" 응답.
    *   검색 결과가 있으면: **List Card** 형태의 JSON 응답 생성 (버튼 클릭 시 "지역선택: [코드] 이름" 발화 유도).

#### 코드 스니펫 (참고용)

**A. 지역 검색 함수**
```python
def search_regions(keyword):
    """Supabase RPC를 통해 지역 검색"""
    try:
        response = supabase.rpc('search_regions', {'keyword': keyword}).execute()
        return response.data
    except Exception as e:
        import traceback
        print(f"Search failed: {e}")
        print(traceback.format_exc())
        return []
```

**B. List Card 생성 함수**
```python
def build_list_card_response(items):
    """검색 결과를 List Card로 변환"""
    list_items = []
    for item in items[:5]:  # 최대 5개
        full_name = item['full_name']
        region_code = item['region_code']
        depth = item['depth']
        
        list_items.append({
            "title": full_name,
            "description": "이 지역으로 설정할까요?",
            "link": {
                "web": ""  # 필수 필드지만 사용 안 함
            },
            "action": "message",
            "messageText": f"지역선택: {region_code} {full_name} ({depth})", # 사용자가 클릭하면 이 메시지가 전송됨
            "extra": {
                "region_code": region_code,
                "depth": depth
            }
        })

    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "listCard": {
                        "header": {
                            "title": "지역을 선택해주세요"
                        },
                        "items": list_items
                    }
                }
            ]
        }
    }
```

**C. 핸들러 예시 (`handle_onboarding`)**

```python
def handle_onboarding(body, user):
    utterance = body['userRequest']['utterance']
    
    # 1. 지역 선택 응답 처리 (사용자가 버튼 클릭 시)
    if utterance.startswith("지역선택:"):
        # "지역선택: 1111051500 청운효자동 (3)" 형태 파싱
        try:
            # 안전한 파싱을 위해 정규식 사용 권장 또는 split 주의
            parts = utterance.split(" ", 2) 
            code = parts[1]
            
            # DB 업데이트
            supabase.table('users').update({
                'region_code': code,
                # 필요하다면 region_name 등 추가 저장
            }).eq('id', user['id']).execute()
            
            return simple_response("지역이 설정되었습니다!\\n\\n다음으로 출생연도를 숫자 4자리로 알려주세요.\\n예) 1955")
        except Exception as e:
            print(f"Parsing failed: {e}")
            return simple_response("지역 선택 중 오류가 발생했습니다. 다시 시도해주세요.")

    # 2. 지역 정보가 없는 경우 -> 검색 수행
    if not user.get('region_code'):
        # 검색어 유효성 검사 (너무 짧으면 스킵 등)
        if len(utterance) < 2:
             return simple_response("두 글자 이상 입력해주세요.\\n예) 서울 강남구, 역삼동")

        results = search_regions(utterance)
        if not results:
            return simple_response("검색된 지역이 없습니다. 다시 입력해주세요.\\n예) 서울 강남구, 역삼동")
        
        return build_list_card_response(results)

    # 3. 출생연도 처리
    if not user.get('birth_year'):
        if utterance.isdigit() and len(utterance) == 4:
            year = int(utterance)
            # 유효성 검사 (1900 ~ 2025)
            if 1900 <= year <= 2025:
                supabase.table('users').update({'birth_year': year}).eq('id', user['id']).execute()
                return simple_response("환영합니다! 모든 설정이 완료되었습니다. 🎉\\n\\n이제 '혜택 알려줘'라고 말해보세요!")
            else:
                 return simple_response("올바른 연도를 입력해주세요 (1900~2025).")
        else:
            return simple_response("출생연도를 정확히 입력해주세요.\\n예) 1955")
```

## 4. 테스트 방법 (Curl)

**1. 일반 텍스트 입력 ("역삼동")**
```bash
curl -X POST "https://YOUR_API_GATEWAY_URL/kakao/webhook" \
     -H "Content-Type: application/json" \
     -d '{
           "userRequest": {
             "user": { "id": "TEST_USER_123" },
             "utterance": "역삼동"
           }
         }'
```
**예상 결과**: `List Card` JSON 응답

**2. 지역 선택 (버튼 클릭 시뮬레이션)**
```bash
# 주의: 실제로는 사용자가 버튼을 눌렀을 때 발화되는 텍스트를 그대로 보냅니다.
curl -X POST "https://YOUR_API_GATEWAY_URL/kakao/webhook" \
     -H "Content-Type: application/json" \
     -d '{
           "userRequest": {
             "user": { "id": "TEST_USER_123" },
             "utterance": "지역선택: 1168010400 서울특별시 강남구 청담동 (3)"
           }
         }'
```
**예상 결과**: "지역이 설정되었습니다..." 텍스트 응답

## 5. 주의사항
*   **환경 변수**: 로컬 테스트 시 `.env` 파일 로드 필수.
*   **에러 처리**: RPC 호출 실패나 파싱 에러 시 사용자에게 친절한 에러 메시지("잠시 후 다시 시도해주세요")를 보내야 합니다.
*   **UX 개선**: 검색 결과가 너무 많을 경우(>5개) 상위 결과만 보여준다는 멘트를 헤더에 추가하는 것이 좋습니다.
