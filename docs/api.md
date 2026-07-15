# 서빙 API 레퍼런스 (zipdao-api)

수집한 공고를 MCP 서버가 검색·조회하도록 제공하는 FastAPI 앱. 코드: `packages/zipdao-api/`.

## 기동

```bash
uv run uvicorn zipdao_api.app:app --port 9000    # 로컬 (운영 Docker 는 docs/operations.md)
```

환경변수:

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DATA_DIR` | `./data` | manifest 루트(`$DATA_DIR/raw` 를 읽음) |
| `RELOAD_INTERVAL_SECONDS` | `600` | 이 주기(초)로 store 를 자동 리로드해 재시작 없이 새 크롤 데이터 반영. `0` 이면 비활성 |

## 엔드포인트

### GET /health
`{"status": "ok"}` 헬스체크.

### GET /notices — 검색

| 파라미터 | 설명 |
| --- | --- |
| `q` | 공백 구분 토큰의 **AND 부분일치**. 대상: 제목·지역·분류·공급유형·요약·소스 태그(청년/lh/청약홈/마이홈) |
| `region` | 지역 매칭(아래 규약) |
| `supplyType` | 부분일치 (예: "매입임대") |
| `source` | 소스 key 정확 일치 |
| `since` / `until` | 게시일 범위. `YYYY` 또는 `YYYY-MM-DD`(구분자 `-`·`.`·`/` 허용) |
| `status` | `접수중` / `마감` / `예정` / `미정` |
| `sort` | 정렬 순서 |
| `limit` / `offset` | 페이지네이션. limit 기본 200, **200 초과는 200 으로 클램프** |

응답 `lastUpdated` 는 `data/last_crawl` 스탬프(크론이 기록) 우선, 없으면 최신 `crawledAt`.

### GET /notices/{source}/{notice_id} — 상세

### GET /sources — 등록 소스 목록(구현 여부 포함)

### POST /recommend — 조건 추천

요청 필드: `limit`(1~50 필수) · `region` · `age` · `maxDepositKRW` · `maxMonthlyRentKRW` ·
`supplyType` · `status`(기본 `접수중`, `전체` 가능).

규칙: 지역 불일치·공급유형 불일치·가격 상한 초과·나이 범위 밖은 제외. 가격 조건 충족 +2점,
39세 이하이면서 청년/행복 유형 +1점. 정렬은 점수 → 상태(접수중 우선) → 게시일 역순.

### POST /qa — 자연어 질의

`{"question": "..."}` 를 받아 한국어 토큰화(조사·부호 제거, 2자 미만·영어 불용어 제외) 후
관련 공고 **상위 5건 고정** 반환.

## 서빙 계층 필터링

수집된 manifest 전부가 API 에 노출되지는 않는다. 로드 시 제외:

- 분양(`_is_sale`)·비주거 어린이집(`_is_non_housing`) 공급유형
- `category == "공지/안내"` 인 게시글
- 정정공고로 대체된 마이홈 공고(`raw.normalized.supersedes` 가 가리키는 것)
- 마이홈과 같은 공고를 가리키는 LH 쌍둥이(`lhPanId` 일치 시 LH 쪽 제거)

## 상태(status) 계산

접수시작/종료일과 오늘(KST)로 계산: 종료일 지남 → `마감`, 시작 전 → `예정`,
접수일이 하나라도 있으면 → `접수중`, 둘 다 없으면 → `미정`.

## 지역 매칭 규약

- 광역시·도 정식/약칭 17종 정규화(예: "경기도"="경기", "서울특별시"="서울").
- 시군구 토큰은 **어두(prefix) 일치**만 인정 — "서구" 검색이 "강서구"에 걸리지 않는다.
- 개칭·통합 지역 별칭 확장: 인천 영종구/제물포구/서해구(분할 전 명칭 포함), 전남광주통합특별시 등.
