-- 지역 검색 함수
-- 사용자가 입력한 검색어(query_text)와 일치하거나 유사한 지역을 검색합니다.
-- depth가 깊은 순서(동 > 구 > 시)로 정렬하여 반환합니다.
CREATE OR REPLACE FUNCTION search_regions(query_text text)
RETURNS TABLE (
  region_code text,
  name text,
  depth int,
  parent_code text
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    r.region_code,
    r.name,
    r.depth,
    r.parent_code
  FROM
    regions r
  WHERE
    r.name ILIKE '%' || query_text || '%'
    AND r.is_active = true
  ORDER BY
    r.depth DESC,  -- 구체적인 지역(동)부터 먼저 보여줌
    r.name ASC
  LIMIT 10;
END;
$$;
