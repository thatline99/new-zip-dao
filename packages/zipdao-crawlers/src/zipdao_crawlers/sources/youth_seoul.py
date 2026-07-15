"""서울 청년안심주택(soco.seoul.go.kr/youth) 크롤러."""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from zipdao_core.dates import to_iso_date, year_out_of_range
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.fields import normalized_block

BASE = "https://soco.seoul.go.kr"
LIST_JSON = f"{BASE}/youth/pgm/home/yohome/bbsListJson.json"

BOARDS: list[tuple[str, str, str]] = [
    ("BMSR00015", "400008", "임대주택 모집공고"),
]


# 목록 optn2(gubun) 코드 → 공급유형. 저장 데이터 427건 전수 대조로 확인한 매핑.
_GUBUN_SUPPLY = {"1": "공공임대", "2": "민간임대"}


def normalize_raw(raw: dict) -> dict:
    """청년안심주택 raw 데이터를 정규화 블록으로 변환한다."""
    return normalized_block(
        supplyType=_GUBUN_SUPPLY.get(str(raw.get("gubun") or "")),
        applyEnd=to_iso_date(raw.get("applyDate")),
    )


class YouthSeoulCrawler(BaseCrawler):
    """서울 청년안심주택 게시판을 수집하는 크롤러."""

    key = "youth_seoul"
    name = "서울 청년안심주택"
    base_url = f"{BASE}/youth"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """등록된 게시판을 순회하며 공고 요약을 만든다."""
        for bbs_id, menu_no, board_name in BOARDS:
            yield from self._iter_board(bbs_id, menu_no, board_name, since, until)

    def _iter_board(
        self,
        bbs_id: str,
        menu_no: str,
        board_name: str,
        since: int | None,
        until: int | None,
    ) -> Iterator[NoticeStub]:
        page = 1
        referer = f"{BASE}/youth/bbs/{bbs_id}/list.do?menuNo={menu_no}"
        while True:
            resp = self.http.post(
                LIST_JSON,
                data={
                    "bbsId": bbs_id,
                    "pageIndex": page,
                    "searchAdresGu": "",
                    "searchCondition": "",
                    "searchKeyword": "",
                    "optn2": "",
                    "optn5": "",
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
                posted = to_iso_date(r.get("optn1") or r.get("nttBgnde") or r.get("regDate"))
                out = year_out_of_range(posted, since, until)
                if out:
                    stop = stop or out == "older"
                    continue
                board_id = str(r.get("boardId") or "").strip()
                if not board_id:
                    continue
                detail = f"{BASE}/youth/bbs/{bbs_id}/view.do?boardId={board_id}&menuNo={menu_no}"
                yield NoticeStub(
                    notice_id=f"{bbs_id}-{board_id}",
                    title=(r.get("nttSj") or "").strip(),
                    detail_url=detail,
                    posted_date=posted or None,
                    category=board_name,
                    region="서울",
                    extra={
                        "bbsId": bbs_id,
                        "menuNo": menu_no,
                        "boardId": board_id,
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
        """상세 HTML에서 첨부 링크를 추출한다(중복 제거)."""
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

    @staticmethod
    def parse_gu(html: str) -> str | None:
        """상세의 카테고리(자치구)를 추출한다 — 해당 자치구 option 만 텍스트가 채워져 있다."""
        soup = BeautifulSoup(html, "lxml")
        for li in soup.select("ul.view_data li"):
            title = li.select_one("span.title")
            if title and "카테고리" in title.get_text():
                for opt in li.select("option"):
                    text = opt.get_text(strip=True)
                    if text:
                        return text
        return None

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지에서 첨부·자치구를 추출해 Notice 를 만든다."""
        resp = self.http.get(stub.detail_url)
        attachments = self.parse_attachments(resp.text)
        gu = self.parse_gu(resp.text)

        raw = {
            "bbsId": stub.extra.get("bbsId"),
            "boardId": stub.extra.get("boardId"),
            "gubun": stub.extra.get("gubun"),
            "postedDate": stub.posted_date,
            "applyDate": stub.extra.get("applyDate"),
            "_detail_html": resp.text,
        }
        raw["normalized"] = normalize_raw(raw)
        notice = Notice.from_stub(stub, source=self.key, attachments=attachments, raw=raw)
        if gu:
            notice.region = f"서울 {gu}"
        return notice
