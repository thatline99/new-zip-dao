# 공고 출처 카탈로그

수집 대상 사이트 분류. 코드상 등록은 [`registry.py`](../packages/zipdao-crawlers/src/zipdao_crawlers/registry.py).
목표: **각 사이트 5년치 공고 전부 — 공고문 PDF/HWP, 공고 내 이미지 포함.**

## 전국 통합 청약 포털 (핵심)

| key | 사이트 | URL | 비고 |
| --- | --- | --- | --- |
| `lh_apply` | LH청약플러스 | https://apply.lh.or.kr | 국민·공공·행복·매입임대·든든전세 등 LH 공고 대부분 |
| `sh_ish` | SH 인터넷청약시스템 | https://www.i-sh.co.kr/app | 서울주택도시개발공사. 사회주택·예술인마을·협동조합주택 |
| `applyhome` | 청약홈 | https://www.applyhome.co.kr | 한국부동산원. 분양·공공임대 통합 청약 |
| `youth_seoul` | 서울 청년안심주택 | https://soco.seoul.go.kr/youth | 서울시 공동체주택플랫폼. 청년안심주택 민간임대 |

## 지역 도시·개발공사

| key | 사이트 | URL | 비고 |
| --- | --- | --- | --- |
| `gh` | 경기주택도시공사(GH) | https://www.gh.or.kr | 다산 포레스트·김포한강 등 |
| `udc` | 울산도시공사(UDC) | https://www.udc.or.kr | 율동 위드유아파트 등 |
| `daejeon` | 대전도시공사 | https://www.dcco.kr | 청년매입임대 등 |
| `gndc` | 경남개발공사 | https://www.gndc.co.kr | 거북이집 셰어하우스 등 |

## 민간임대·공공지원 통합

| key | 사이트 | URL | 비고 |
| --- | --- | --- | --- |
| `myhome` | 마이홈포털 | https://www.myhome.go.kr | 국토부 주거복지 통합. LH·SH·지자체·민간 통합 검색(공공지원 민간임대 포함) |

## 사회주택·토지임대부 (개별 운영기관)

어울리 에어스페이스 · 옥류정원 · 유니버설디자인하우스 창동 · 한지붕 협동조합 · 마을과집 협동조합 등은
**SH 인터넷청약**(`sh_ish`) 또는 각 운영기관(사회적기업·협동조합) 자체 공고로 모집.
→ 1차로 `sh_ish`·`myhome` 통합 경로에서 커버, 누락분은 개별 기관 소스 추가 검토.

## 구현 진행

각 소스는 실측(목록/페이지네이션/상세/첨부 셀렉터 확인) 후 `sources/<key>.py` 에 구현하고
`registry.py` 의 `SourceInfo(crawler=...)` 에 연결한다. 진행 상태는 `zipdao-crawl list` 의 ✅/⬜ 로 확인.

추천 구현 순서: `lh_apply`(물량 최대·핵심) → `applyhome` → `sh_ish` → `myhome` → 지역 공사.
```
