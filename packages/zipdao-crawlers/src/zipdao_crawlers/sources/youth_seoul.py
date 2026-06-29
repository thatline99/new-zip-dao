"""서울 청년안심주택 (soco.seoul.go.kr/youth) 크롤러.

실측 결과(검증본):
  - 목록은 JS AJAX: POST /youth/pgm/home/yohome/bbsListJson.json
      data: bbsId, pageIndex, searchAdresGu, searchCondition, searchKeyword, optn2, optn5
      resp(JSON): resultList[{boardId, nttSj, optn1(게시일 YYYY-MM-DD), optn2(공공/민간),
                  optn3(담당), optn4(청약신청일), atchFileId, regDate, ...}], pagingInfo{totPage,...}
  - 상세는 서버 렌더링: GET /youth/bbs/{bbsId}/view.do?boardId=..&menuNo=..
      첨부: <span class="file"> 안의 <a href="/coHouse/cmmn/file/fileDown.do?atchFileId=..&fileSn=..">파일명</a>
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from zipdao_core.dates import to_iso_date
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.normalize import normalize_youth

BASE = "https://soco.seoul.go.kr"
LIST_JSON = f"{BASE}/youth/pgm/home/yohome/bbsListJson.json"

# (bbsId, menuNo, 게시판 이름)
# BMSR00015=임대주택 모집공고(게시일 optn1=ISO)만 수집한다.
# BMSR00013(공지/안내)은 주택공고가 아니라 제외, BMSR00020(매입임대)은 빈 보드라 제외.
BOARDS: list[tuple[str, str, str]] = [
    ("BMSR00015", "400008", "임대주택 모집공고"),
]


class YouthSeoulCrawler(BaseCrawler):
    key = "youth_seoul"
    name = "서울 청년안심주택"
    base_url = f"{BASE}/youth"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        for bbs_id, menu_no, board_name in BOARDS:
            yield from self._iter_board(bbs_id, menu_no, board_name, since, until)

    def _iter_board(
        self, bbs_id: str, menu_no: str, board_name: str,
        since: int | None, until: int | None,
    ) -> Iterator[NoticeStub]:
        page = 1
        referer = f"{BASE}/youth/bbs/{bbs_id}/list.do?menuNo={menu_no}"
        while True:
            resp = self.http.post(
                LIST_JSON,
                data={
                    "bbsId": bbs_id, "pageIndex": page,
                    "searchAdresGu": "", "searchCondition": "",
                    "searchKeyword": "", "optn2": "", "optn5": "",
                },
                headers={"X-Requested-With": "XMLHttpRequest", "Referer": referer},
            )
            data = resp.json()
            rows = data.get("resultList") or []
            paging = data.get("pagingInfo") or {}
            if not rows:
                break

            stop = False
            for r in rows:
                # 보드별 날짜 표기 상이: optn1(ISO) → nttBgnde/regDate(epoch ms) 순 폴백.
                posted = to_iso_date(
                    r.get("optn1") or r.get("nttBgnde") or r.get("regDate")
                )
                year = int(posted[:4]) if posted and posted[:4].isdigit() else None
                if year is not None:
                    if until is not None and year > until:
                        continue  # 너무 최신 — 건너뛰고 더 과거로
                    if since is not None and year < since:
                        stop = True  # 목록은 최신순 → since 미만이면 이후 전부 과거
                        continue
                board_id = str(r.get("boardId") or "").strip()
                if not board_id:
                    continue
                detail = (
                    f"{BASE}/youth/bbs/{bbs_id}/view.do"
                    f"?boardId={board_id}&menuNo={menu_no}"
                )
                yield NoticeStub(
                    notice_id=f"{bbs_id}-{board_id}",
                    title=(r.get("nttSj") or "").strip(),
                    detail_url=detail,
                    posted_date=posted or None,
                    category=board_name,
                    region="서울",
                    extra={
                        "bbsId": bbs_id, "menuNo": menu_no, "boardId": board_id,
                        "atchFileId": r.get("atchFileId"),
                        "gubun": r.get("optn2"),
                        "applyDate": to_iso_date(r.get("optn4")),
                    },
                )
            total_page = int(paging.get("totPage") or 0)
            if stop or page >= total_page:
                break
            page += 1

    @staticmethod
    def parse_attachments(html: str) -> list[Attachment]:
        """상세 HTML에서 fileDown.do 첨부 링크를 추출(중복 제거). 순수 함수(테스트용)."""
        soup = BeautifulSoup(html, "lxml")
        attachments: list[Attachment] = []
        seen: set[str] = set()
        for a in soup.select('a[href*="fileDown.do"]'):
            href = a.get("href") or ""
            if "fileDown.do" not in href:
                continue
            full = urljoin(BASE, href)
            if full in seen:
                continue
            seen.add(full)
            attachments.append(Attachment(url=full, filename=a.get_text(strip=True)))
        return attachments

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        resp = self.http.get(stub.detail_url)
        attachments = self.parse_attachments(resp.text)

        raw = {
            "bbsId": stub.extra.get("bbsId"),
            "boardId": stub.extra.get("boardId"),
            "gubun": stub.extra.get("gubun"),
            "postedDate": stub.posted_date,
            "applyDate": stub.extra.get("applyDate"),
            "_detail_html": resp.text,
        }
        raw["normalized"] = normalize_youth(raw)
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=stub.posted_date,
            category=stub.category,
            region=stub.region,
            attachments=attachments,
            raw=raw,
        )
