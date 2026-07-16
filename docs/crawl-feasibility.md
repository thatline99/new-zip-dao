# 사이트별 크롤 실현가능성

> 실측 기준일: 2026-07-15 (건수·페이지 수는 이 시점 값).
> 원칙: robots.txt Disallow 는 존중한다. 공개 API 가 공식 채널인 경우 그쪽을 우선한다.

## 요약

| key | 사이트 | 판정 | 채널·근거 |
| --- | --- | --- | --- |
| `lh_apply` | LH청약플러스 | API 구현(메타만) | 공공데이터 API(15058530). 한계: 과거 이력·원본 PDF 불가 |
| `sh_ish` | SH 인터넷청약 | 게시판 크롤 구현 | list.do POST 순회 + view.do 상세 + innoFD.do 첨부. 다년 이력·원본 PDF |
| `applyhome` | 청약홈 | API 구현 | odcloud API(15098547). 2020~ 이력 2,804건. 원본 PDF 불가(SPA) |
| `youth_seoul` | 서울 청년안심주택 | 게시판 크롤 구현 | bbsListJson AJAX + 서버렌더 상세 + fileDown.do 첨부 |
| `gh` | 경기주택도시공사 | API 구현(이력만) | 사이트는 robots 전면 차단 → odcloud API(15119414). 한계: 연 1회 스냅샷 |
| `udc` | 울산도시공사 | 게시판 크롤 구현 | umca.co.kr bbs/list.do + FileDown.do 첨부 |
| `gndc` | 경남개발공사 | 게시판 크롤 구현 | getBbsArticleList.do JSON + download.do 첨부 |
| `myhome` | 마이홈포털 | API 구현 | 공공주택 API(15108420). 보증금·월세·면적 구조화 데이터 |
| `daejeon` | 대전도시공사 | 차단(WAF) | 자동 요청을 400 "Request Blocked" 로 차단. 협의/공식 채널 필요 |

모든 구현 소스는 `run <key> --limit N` 실수집으로 파일 무결성(sha256)까지 검증되어 있다.

## 세부

### lh_apply — 공공데이터 API (메타데이터만)
- 엔드포인트: `http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1`
- 파라미터: `serviceKey, PG_SZ, PAGE, PAN_NT_ST_DT(YYYY.MM.DD), CLSG_DT, UPP_AIS_TP_CD`(05 분양·06 임대·13 주거복지·39 신혼희망).
- 수집 범위: 현재 게시 중 공고(약 335건)의 메타데이터 + `DTL_URL`·상태·지역·일정.
- 한계:
  - **과거 이력 불가** — 날짜 파라미터를 과거로 줘도 현재 게시분만 반환(스냅샷 API).
  - **원본 PDF/HWP 불가** — 첨부 경로 `/lhapply/lhFile.do` 가 robots 차단 영역. 링크만 노출(`link_only`).
- LH 는 "현재 공고 메타데이터"가 합법 채널의 천장. 과거 공고문 아카이브는 별도 협의 필요.

### sh_ish — SH 인터넷청약 게시판
- 서버렌더 eGov 계열 게시판. 세션 쿠키 없이 접근하면 에러 페이지로 리다이렉트되므로 쿠키 유지 필수.
- 목록: `POST /app/lay2/program/S1T294C{296,297}/www/brd/m_{244,247}/list.do` (`page`, `multi_itm_seq`).
  분류 비트 플래그: 1 주택분양 · 2 주택임대 · 512 주택매입(수집 제외 — SH 의 기존주택 매입 공고).
  주택임대 단독 약 1,660건(166페이지×10행), 다년 이력 제공.
- 상세: `POST {게시판}/view.do` (`seq`). NetFunnel(대기열)은 클라이언트 스크립트라 서버가 강제하지 않는다.
- 첨부: 상세의 `initParam.downList` JSON → `GET /app/com/file/innoFD.do?brdId=&seq=&fileTp=&fileSeq=`.
- robots: `*` 그룹 Disallow 는 /gcms/brd·/cent*/brd 등이며 /app 게시판·innoFD.do 는 허용.

### applyhome — 청약홈 odcloud API
- 엔드포인트: `https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail` (+공공지원민간임대 오퍼레이션).
- APT 분양/임대 2,804건, 2020년~ 다년 이력. 메타+PBLANC_URL 수집, 주택형별(Mdl) 면적 보강.
- 원본 PDF 는 청약홈 사이트가 SPA 라 제외. 오피스텔·무순위 오퍼레이션은 후속 확장 여지.

### youth_seoul — 서울 청년안심주택 게시판
- 목록: `POST /youth/pgm/home/yohome/bbsListJson.json` (bbsId, pageIndex) → JSON `resultList` + `pagingInfo`.
- 상세: `GET /youth/bbs/{bbsId}/view.do?boardId=..` → `fileDown.do` 첨부 링크.
- 원본 PDF 수집 가능. 임대주택 모집공고 보드 단독 약 415건.

### gh — 경기주택도시공사 (공공데이터 API, 이력 전용)
- 사이트 직접 크롤은 robots `Disallow: /` 전면 차단이라 제외.
- 채널: 공공데이터포털 'GH주택청약 모집정보'(fileData 15119414)의 odcloud API —
  `GET https://api.odcloud.kr/api/15119414/v1/uddi:{판별 UDDI}`. 연도판 3개(2023·2024·2025), 2017년~ 이력.
- 필드: 공고명·게시일자·접수시작/종료일자·당첨자발표일자·입주예정년월·주택관리번호 등.
  공고문 PDF·상세 URL 없음(공고 페이지가 robots 차단 영역).
- **연 1회(매년 8월) 스냅샷 갱신** — 최신 공고는 이 채널로 못 받는다. 새 판이 나오면
  `sources/gh.py` 의 `SNAPSHOTS` 에 UDDI 를 추가한다.
- **최신 공고 대안 경로(미구현)**: 청약센터 `apply.gh.or.kr` 는 본사(www)와 달리
  robots `Allow: /*` 로 전면 허용이고 청약공고 목록(`/sb/sr/sr7150/selectPbancRentHouseList.do`,
  공고명·게시일·마감일·상태 테이블)이 열려 있다. XHR 발굴 후 구현하면 스냅샷 공백 해소 가능.
- 서비스키로 데이터셋 활용신청이 되어 있어야 호출 가능(미신청 시 401).
- 스냅샷 간 중복 공고는 최신판부터 순회 + 주택관리번호 기반 notice_id 로 엔진이 스킵.

### udc — 울산도시공사 게시판
- 공식 도메인은 `https://www.umca.co.kr` (구 udc.or.kr 는 DNS 소멸). robots `Allow: /`.
- 목록: `GET /umca/bbs/list.do?bbsId=BBS_0000000000000004&mId=001001004000000000&page=N`
  (임대공고, 약 146건 다년 이력). 분양공고 게시판(…0003)은 산업단지 용지 위주라 제외.
- 상세: `GET /umca/bbs/view.do?bbsId=&mId=&dataId=` — 첨부는 `HHBbs.DownFile` 호출에서 추출 →
  `GET /umca/bbs/FileDown.do?bbsId=&atchFileId=&fileSn=`.

### gndc — 경남개발공사 게시판
- 목록: `GET /getBbsArticleList.do` (BBS_ID, `ATTR01=COLM1_CD&{코드}|COLM3_CD` 분류 필터, CURRENT_PAGE)
  → JSON `{pageInfo, resultList}`. 분류 코드: notice_06 임대 · notice_01 분양(토지·상가 혼재 — 주택 제목만 수집).
- 첨부: 목록 행의 `sysFileNameStr`/`orgFileNameStr`('|' 구분) →
  `GET /common/download.do?fileVirtualPath=&fileOrgName=` 로 바로 다운로드.
- 상세: `GET /boardview/boardview.do?seqId=&BBS_ID=&IPDS_IDX=&BBS_TYPE=L&COLM1=&COLM1_CD=`
  (COLM1 파라미터 누락 시 본문이 렌더되지 않는다).
- 지역: 행 `COLM3_VAL`(시군명) → "경남 {시군}". robots.txt 없음.

### myhome — 마이홈 공공주택 API
- 목록: `https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList` — 지역코드 없이 전국 일괄 조회.
  비어 있으면 시군구(brtcCode+signguCode) 순회로 폴백.
- 단지 보강: `https://apis.data.go.kr/1613000/HWSPR04/rentalHouseGwList` (brtcCode 2자리 + signguCode)
  로 세대별 면적·보증금·월임대료를 붙인다.
- signguCode 는 5자리 법정동 코드가 아니라 **3자리**다(종로 110, 강남 680) — 코드표는 `sources/_myhome_regions.py` 에 임베드.
- 데이터: 기관·주소·공급유형·주택유형·**면적·보증금·월임대료** (문서가 아닌 구조화 데이터).

### daejeon — 차단 (미구현)
- WAF 가 비브라우저 요청을 400 "Request Blocked" 로 차단. 우회하지 않는다.
- 진행하려면 기관 협의 또는 공식 데이터 채널 확보가 필요.

## 신규 소스 후보 실측 (미등록)

직접 소스가 없는 광역시의 커버리지 공백(대전 사례와 동급)을 메울 후보들.

| 후보 | 판정 | 근거 |
| --- | --- | --- |
| 부산도시공사 | 크롤 가능(발굴 필요) | 본사 robots `Allow: /`, BMC청약센터(apply.bmc.busan.kr)는 `Allow: /*`. 청약 목록(smw113020/selectPbancRentHouseList.do)은 XHR 렌더 — 엔드포인트 발굴 필요 |
| 광주광역시도시공사 | 크롤 가능(게시판 URL 확인 필요) | gmcc.co.kr robots 에 `*` 그룹 없음(허용). 메인이 서버렌더로 모집공고 노출 — 공고 게시판 경로 실측 필요 |
| 대구도시개발공사 | 직접 크롤 차단 | dudc.or.kr robots `Disallow: /`. 공공데이터셋에 임대공고류 없음. 대안: 대구안방(anbang.daegu.go.kr, 대구시 포털) 게시판 발굴 — 임대공고 게재 여부 불확실 |

부산 공공데이터셋은 현황성(임대료·관리현황)뿐이라 공고 수집은 사이트 크롤이 경로다.

## 남은 작업
1. sh_ish·gndc·udc·gh 백필(`--since 2021`) 및 정기 수집 크론 편입.
2. GH 최신 공고가 myhome 통합 경로로 올라오는지 확인(연 1회 스냅샷 공백 보완).
3. 대전: 협의/공식 채널 검토. GH: 매년 8월 신규 스냅샷 UDDI 추가.
