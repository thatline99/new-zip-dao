# 사이트별 크롤 실현가능성 (실측 결과)

> 2026-06-24 실측. 각 사이트의 robots / HTML 구조 / 차단 여부를 직접 확인했다.
> 원칙: **robots.txt Disallow는 존중**한다. 공개 API가 공식 채널인 경우 그쪽을 우선한다.

## 요약

| key | 사이트 | 판정 | 근거 |
| --- | --- | --- | --- |
| `youth_seoul` | 서울 청년안심주택 | ✅ **구현 완료** | eGov AJAX 목록(`bbsListJson.json`) + 서버렌더 상세 + `fileDown.do` 첨부. 실제 PDF 다운로드 검증됨 |
| `gndc` | 경남개발공사 | 🟡 구현 가능(미완) | 정적 셸 + 다중 AJAX 보드(`selectListItemUserList.do`, bbsid 기반). 행 JSON 엔드포인트 추가 발굴 필요 |
| `applyhome` | 청약홈 | 🟡 API 권장 | 랜딩이 SPA 셸(1KB). 공식 채널 = 공공데이터포털 `15098547`(서비스키 필요) |
| `sh_ish` | SH 인터넷청약 | 🟡 발굴 필요 | SPA 셸(1.4KB). XHR 목록 엔드포인트 발굴 필요 |
| `myhome` | 마이홈포털 | 🟡 발굴 필요 | SPA 셸(0.5KB). 통합검색 XHR 또는 공공데이터 파일셋 발굴 필요 |
| `lh_apply` | LH청약플러스 | ⛔ robots(파일) | robots가 `/lhapply/lhFile.do`·`/lhapply/apply/csvc/lhFile.do`(첨부 다운로드) **Disallow**. 공식 채널 = 공공데이터포털 `15058530` 사용 |
| `gh` | 경기주택도시공사 | ⛔ robots(전체) | robots.txt `Disallow: /` — 전체 차단. 존중하여 제외 |
| `daejeon` | 대전도시공사 | ⛔ WAF | 자동요청 400 "Request Blocked"(WAF). 우회 미시도 |
| `udc` | 울산도시공사 | ⚠️ 연결실패 | 실측 시 응답 없음(HTTP 000). 재시도/네트워크 점검 필요 |

## 세부

### ✅ youth_seoul — 구현 완료 (참조 구현)
- 목록: `POST /youth/pgm/home/yohome/bbsListJson.json` (bbsId, pageIndex, …) → JSON `resultList`(boardId·nttSj·게시일 optn1·atchFileId) + `pagingInfo`(totPage). 보드 3종(BMSR00015/00013/00020).
- 상세: `GET /youth/bbs/{bbsId}/view.do?boardId=..&menuNo=..` → `<a href="/coHouse/cmmn/file/fileDown.do?atchFileId=..&fileSn=..">파일명</a>`.
- 검증: `run youth_seoul --limit 3` → 실제 PDF(v1.6) 3건 저장, sha256·바이트 기록. BMSR00015 단독 415건/42페이지.

### ⛔ robots 존중 제외
- **LH청약플러스**: 메타데이터는 공공데이터포털 분양임대공고문 API(`15058530`)가 공식 배포 채널. 첨부 PDF는 robots가 막으므로 API의 상세URL/파일정보를 통해서만 접근(서비스키 필요).
- **GH**: `Disallow: /` 전면 차단 → 크롤 제외.

### ⚠️ 차단/실패 (추가 작업 필요)
- **대전도시공사**: WAF가 비브라우저 요청 차단. 정식 협의 또는 공식 데이터 채널 권장.
- **울산도시공사**: 실측 무응답. 시간대/차단 여부 재확인 필요.

### 🟡 SPA — XHR 발굴 필요
청약홈·SH·마이홈은 랜딩이 JS 셸이라 실제 목록 XHR(JSON) 엔드포인트를 브라우저 네트워크 탭으로 추가 발굴해야 한다.
청약홈·LH는 **공공데이터포털 OpenAPI**가 공식·합법 채널이므로, 서비스키 확보 후 API 우선 수집을 권장한다(`DATA_GO_KR_SERVICE_KEY`).

## 다음 단계
1. `DATA_GO_KR_SERVICE_KEY` 확보 → LH(`15058530`)·청약홈(`15098547`) API 소스 추가(메타데이터·상세URL).
2. gndc 행 JSON 엔드포인트 발굴 → 정적 보드형 지역공사 패턴 확립 후 SH/마이홈 확장.
3. 대전 WAF·울산 무응답은 별도 점검.
