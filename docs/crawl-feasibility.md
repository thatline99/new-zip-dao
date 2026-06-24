# 사이트별 크롤 실현가능성 (실측 결과)

> 2026-06-24 실측. 각 사이트의 robots / HTML 구조 / 차단 여부를 직접 확인했다.
> 원칙: **robots.txt Disallow는 존중**한다. 공개 API가 공식 채널인 경우 그쪽을 우선한다.

## 요약

| key | 사이트 | 판정 | 근거 |
| --- | --- | --- | --- |
| `youth_seoul` | 서울 청년안심주택 | ✅ **구현 완료** | eGov AJAX 목록(`bbsListJson.json`) + 서버렌더 상세 + `fileDown.do` 첨부. 실제 PDF 다운로드 검증됨 |
| `gndc` | 경남개발공사 | 🟡 구현 가능(미완) | 정적 셸 + 다중 AJAX 보드(`selectListItemUserList.do`, bbsid 기반). 행 JSON 엔드포인트 추가 발굴 필요 |
| `applyhome` | 청약홈 | ✅ **API 구현** | odcloud API(15098547). APT 분양/임대 2804건, **2020~2026 이력**. 메타+PBLANC_URL(원본 PDF는 SPA라 제외) |
| `sh_ish` | SH 인터넷청약 | 🟡 발굴 필요 | SPA 셸(1.4KB). XHR 목록 엔드포인트 발굴 필요 |
| `myhome` | 마이홈포털 | ✅ **API 구현** | 공공주택 API(15108420, HWSPR04). 전국 공공임대 단지·세대(보증금·월세·면적·공급유형). signguCode 3자리 |
| `lh_apply` | LH청약플러스 | ✅ **API 구현(메타만)** | 공공데이터 API(15058530)로 **현재 공고 메타+DTL_URL** 수집. ⚠️ 5년 이력·원본 PDF 불가(아래) |
| `gh` | 경기주택도시공사 | ⛔ robots(전체) | robots.txt `Disallow: /` — 전체 차단. 존중하여 제외 |
| `daejeon` | 대전도시공사 | ⛔ WAF | 자동요청 400 "Request Blocked"(WAF). 우회 미시도 |
| `udc` | 울산도시공사 | ⚠️ 연결실패 | 실측 시 응답 없음(HTTP 000). 재시도/네트워크 점검 필요 |

## 세부

### ✅ youth_seoul — 구현 완료 (참조 구현)
- 목록: `POST /youth/pgm/home/yohome/bbsListJson.json` (bbsId, pageIndex, …) → JSON `resultList`(boardId·nttSj·게시일 optn1·atchFileId) + `pagingInfo`(totPage). 보드 3종(BMSR00015/00013/00020).
- 상세: `GET /youth/bbs/{bbsId}/view.do?boardId=..&menuNo=..` → `<a href="/coHouse/cmmn/file/fileDown.do?atchFileId=..&fileSn=..">파일명</a>`.
- 검증: `run youth_seoul --limit 3` → 실제 PDF(v1.6) 3건 저장, sha256·바이트 기록. BMSR00015 단독 415건/42페이지.

### ✅ lh_apply — 공공데이터 API 구현 (메타데이터만)
- 엔드포인트: `http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1`
- 필수 파라미터: `ServiceKey, PG_SZ, PAGE, PAN_NT_ST_DT(YYYY.MM.DD), CLSG_DT`. 유형 `UPP_AIS_TP_CD`(05 분양·06 임대·13 주거복지·39 신혼희망).
- 수집: 현재 공고 335건(임대 236·주거복지 61·분양 20·신혼 18) + 각 `DTL_URL`·상태·지역·일정.
- ⚠️ **한계(실측 확인)**:
  - **5년 이력 불가**: `PAN_NT_ST_DT/CLSG_DT` 윈도우를 2022/2023/2024로 바꿔도 응답이 동일(전부 현재 2026 공고). API는 **현재 게시 중 공고 스냅샷만** 제공.
  - **원본 PDF/HWP 불가**: 첨부는 robots가 막은 `/lhapply/lhFile.do`. API는 메타데이터+DTL_URL만.
- → LH는 "현재 공고 메타데이터"가 합법 채널의 천장. 과거 공고문 아카이브는 별도 협의 필요.

### ⛔ robots 존중 제외
- **GH**: `Disallow: /` 전면 차단 → 크롤 제외. (단, 공공데이터 fileData `15119414` GH주택청약 모집정보 CSV는 별도 채널로 활용 가능)

### ✅ myhome — 마이홈 공공주택 API 구현
- 엔드포인트: `http://apis.data.go.kr/1613000/HWSPR04/rentalHouseGwList` (serviceKey, **brtcCode 2자리 + signguCode 3자리** 필수).
- 참고문서 코드표에서 시군구 255개 추출 → `sources/_myhome_regions.py` 임베드. 시군구별 조회 → 단지별 manifest.
- 데이터: 기관·주소·공급유형(영구/국민/행복/매입/통합공공 등)·주택유형·**면적·보증금·월임대료** (PDF 아님, 구조화 데이터).
- ⚠️ 초기 NODATA 원인 = signguCode를 5자리(11110)로 넣어서. 정답은 3자리(종로 110, 강남 680). 참고문서로 해결.

### ⚠️ 차단/실패 (추가 작업 필요)
- **대전도시공사**: WAF가 비브라우저 요청 차단. 정식 협의 또는 공식 데이터 채널 권장.
- **울산도시공사**: 실측 무응답. 시간대/차단 여부 재확인 필요.

### ✅ applyhome — 청약홈 odcloud API 구현
- 엔드포인트: `https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail` (serviceKey, page, perPage).
- APT 분양/임대 **2804건, 2020~2026(최신순)** — LH와 달리 다년 이력 제공. 메타+PBLANC_URL 수집.
- 원본 PDF는 청약홈 사이트(SPA)라 제외. 추가 오퍼레이션(오피스텔·무순위·공공지원민간임대)은 후속 확장 가능.

### 🟡 SH — XHR 발굴 필요
SH 인터넷청약은 랜딩이 JS 셸이라 목록 XHR(JSON) 엔드포인트를 추가 발굴해야 한다.

## 다음 단계
1. `DATA_GO_KR_SERVICE_KEY` 확보 → LH(`15058530`)·청약홈(`15098547`) API 소스 추가(메타데이터·상세URL).
2. gndc 행 JSON 엔드포인트 발굴 → 정적 보드형 지역공사 패턴 확립 후 SH/마이홈 확장.
3. 대전 WAF·울산 무응답은 별도 점검.
