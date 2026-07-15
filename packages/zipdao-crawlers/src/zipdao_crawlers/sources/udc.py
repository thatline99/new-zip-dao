"""울산도시공사(umca.co.kr, 구 udc.or.kr) 임대공고 게시판 크롤러.

실측(2026-07-15): eGov 계열 서버렌더 게시판, robots.txt `Allow: /`.
- 목록: GET /umca/bbs/list.do?bbsId=&mId=&page=N → tr 행(제목 a href 에 dataId) + goPage(끝페이지)
- 상세: GET /umca/bbs/view.do?bbsId=&mId=&dataId= → 첨부는 HHBbs.DownFile(ctx, bbsId, fileId, sn)
- 첨부: GET /umca/bbs/FileDown.do?bbsId=&atchFileId=&fileSn=
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from zipdao_core.dates import year_out_of_range
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.fields import normalized_block, supply_type_from_title

BASE = "https://www.umca.co.kr"
FILE_DOWN = f"{BASE}/umca/bbs/FileDown.do"

# (bbsId, mId, 카테고리) — 임대공고 게시판. (분양공고 0003 은 산업단지 용지 위주라 제외)
BOARDS: list[tuple[str, str, str]] = [
    ("BBS_0000000000000004", "001001004000000000", "임대공고"),
]

_DATA_ID_RE = re.compile(r"dataId=(\d+)")
_LAST_PAGE_RE = re.compile(r"goPage\((\d+)\)")
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_DOWN_FILE_RE = re.compile(r"HHBbs\.DownFile\('[^']*',\s*'([^']*)',\s*'([^']*)',\s*'(\d+)'\)")
_SIZE_SUFFIX_RE = re.compile(r"\s*\([\d.,]+\s*KByte\)\s*$")


def normalize_raw(raw: dict) -> dict:
    """울산도시공사 raw 데이터를 정규화 블록으로 변환한다(구조화 필드는 공고문 파싱에 의존)."""
    return normalized_block(supplyType=supply_type_from_title(raw.get("title")))


class UdcCrawler(BaseCrawler):
    """울산도시공사 임대공고 게시판을 수집하는 크롤러."""

    key = "udc"
    name = "울산도시공사"
    base_url = BASE

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """게시판을 페이지 순회하며 공고 요약을 만든다."""
        for bbs_id, m_id, category in BOARDS:
            yield from self._iter_board(bbs_id, m_id, category, since, until)

    def _iter_board(
        self,
        bbs_id: str,
        m_id: str,
        category: str,
        since: int | None,
        until: int | None,
    ) -> Iterator[NoticeStub]:
        page = 1
        while True:
            resp = self.http.get(
                f"{BASE}/umca/bbs/list.do",
                params={"bbsId": bbs_id, "mId": m_id, "page": page},
            )
            rows, last_page = self.parse_list(resp.text)
            if not rows:
                break

            stop = False
            for row in rows:
                out = year_out_of_range(row["posted"], since, until)
                if out:
                    stop = stop or out == "older"
                    continue
                detail = f"{BASE}/umca/bbs/view.do?bbsId={bbs_id}&mId={m_id}&dataId={row['dataId']}"
                yield NoticeStub(
                    notice_id=row["dataId"],
                    title=row["title"],
                    detail_url=detail,
                    posted_date=row["posted"],
                    category=category,
                    region="울산",
                    extra={"bbsId": bbs_id, "mId": m_id},
                )
            if stop or page >= last_page:
                break
            page += 1

    @staticmethod
    def parse_list(html: str) -> tuple[list[dict], int]:
        """목록 HTML 에서 (행 목록, 마지막 페이지 번호)를 추출한다."""
        soup = BeautifulSoup(html, "lxml")
        rows: list[dict] = []
        for tr in soup.select("tbody tr"):
            a = tr.select_one("a[href*='view.do']")
            if a is None:
                continue
            match = _DATA_ID_RE.search(a.get("href") or "")
            if match is None:
                continue
            title = " ".join(a.get_text(" ", strip=True).split())
            posted: str | None = None
            for td in tr.select("td"):
                date_match = _ISO_DATE_RE.search(td.get_text(strip=True))
                if date_match:
                    posted = date_match.group(0)
                    break
            rows.append({"dataId": match.group(1), "title": title, "posted": posted})

        last_page = max((int(n) for n in _LAST_PAGE_RE.findall(html)), default=0)
        return rows, last_page

    @staticmethod
    def parse_attachments(html: str) -> list[Attachment]:
        """상세 HTML 의 HHBbs.DownFile 호출에서 첨부 목록을 만든다."""
        soup = BeautifulSoup(html, "lxml")
        attachments: list[Attachment] = []
        seen: set[str] = set()
        for a in soup.select("a[onclick*='HHBbs.DownFile']"):
            match = _DOWN_FILE_RE.search(a.get("onclick") or "")
            if match is None:
                continue
            bbs_id, atch_file_id, file_sn = match.groups()
            url = f"{FILE_DOWN}?bbsId={bbs_id}&atchFileId={atch_file_id}&fileSn={file_sn}"
            if url in seen:
                continue
            seen.add(url)
            img = a.select_one("img[alt]")
            filename = (img.get("alt") or "").strip() if img else ""
            if not filename:
                filename = _SIZE_SUFFIX_RE.sub("", a.get_text(" ", strip=True)).strip()
            attachments.append(Attachment(url=url, filename=filename))
        return attachments

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지에서 첨부를 추출해 Notice 를 만든다."""
        resp = self.http.get(stub.detail_url)
        attachments = self.parse_attachments(resp.text)

        raw = {
            "dataId": stub.notice_id,
            "title": stub.title,
            "bbsId": stub.extra.get("bbsId"),
            "postedDate": stub.posted_date,
            "_detail_html": resp.text,
        }
        raw["normalized"] = normalize_raw(raw)
        return Notice.from_stub(stub, source=self.key, attachments=attachments, raw=raw)
