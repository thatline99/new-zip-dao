"""광주광역시도시공사(gmcc.co.kr) 임대공고 게시판 크롤러.

서버렌더 게시판으로 목록에 상세 href·첨부 직링크·등록일이 그대로 노출된다.
- 목록: GET /board.es?mid=a10402040000&bid=0018&act=list&nPage=N (등록일 내림차순).
  이 게시판(bid=0018)은 분양·입찰·채용·임대공고가 한 스트림에 섞여 있어(분류 컬럼)
  임대공고 행만 골라 수집한다. mid 로 필터된 뷰는 페이지네이션이 JS/세션이라 안 쓴다.
- 상세: GET /board.es?...&act=view&list_no=N — 전체 제목(h2.title)과 첨부 목록
- 첨부: GET /boardDownload.es?bid=0018&list_no=N&seq=N 직링크
robots.txt 에 `*` 그룹이 없어 수집 허용. 광주 APT 분양은 applyhome 이 커버한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from zipdao_core.dates import to_iso_date, year_out_of_range
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.fields import normalized_block, supply_type_from_title

BASE = "https://www.gmcc.co.kr"
MID = "a10402040000"
BID = "0018"
CATEGORY = "임대공고"

_LIST_NO_RE = re.compile(r"list_no=(\d+)")
_DOT_DATE_RE = re.compile(r"\b\d{4}\.\d{2}\.\d{2}\b")


def normalize_raw(raw: dict) -> dict:
    """광주도시공사 raw 데이터를 정규화 블록으로 변환한다(구조화 필드는 공고문 파싱에 의존)."""
    return normalized_block(supplyType=supply_type_from_title(raw.get("title")))


class GmccCrawler(BaseCrawler):
    """광주광역시도시공사 임대공고 게시판을 수집하는 크롤러."""

    key = "gmcc"
    name = "광주광역시도시공사"
    base_url = BASE

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """임대공고 게시판을 페이지 순회하며 공고 요약을 만든다."""
        page = 1
        while True:
            resp = self.http.get(
                f"{BASE}/board.es",
                params={"mid": MID, "bid": BID, "act": "list", "nPage": page},
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
                if row["category"] != CATEGORY:
                    continue
                yield NoticeStub(
                    notice_id=row["listNo"],
                    title=row["title"],
                    detail_url=row["detailUrl"],
                    posted_date=row["posted"],
                    category=row["category"],
                    region="광주",
                    extra={},
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
            a = tr.select_one("a[href*='act=view']")
            if a is None:
                continue
            match = _LIST_NO_RE.search(a.get("href") or "")
            if match is None:
                continue
            title = " ".join(a.get_text(" ", strip=True).replace("새글", "").split())
            category = ""
            cat_td = tr.select_one("td[aria-label='분류']")
            if cat_td is not None:
                category = cat_td.get_text(strip=True)
            posted = None
            for td in tr.select("td"):
                date_match = _DOT_DATE_RE.search(td.get_text(strip=True))
                if date_match:
                    posted = to_iso_date(date_match.group(0))
                    break
            rows.append(
                {
                    "listNo": match.group(1),
                    "title": title,
                    "detailUrl": urljoin(BASE, a.get("href") or ""),
                    "category": category,
                    "posted": posted,
                }
            )
        pages = [int(n) for n in re.findall(r"nPage=(\d+)", html)]
        return rows, max(pages, default=0)

    @staticmethod
    def parse_detail(html: str) -> tuple[str | None, list[Attachment]]:
        """상세 HTML 에서 (전체 제목, 첨부 목록)을 추출한다(첨부는 URL 로 중복 제거)."""
        soup = BeautifulSoup(html, "lxml")
        # 상단 팝업·메뉴에도 h2.title 이 있어 게시글 본문으로 좁혀야 실제 제목이 잡힌다
        view = soup.select_one("article.board_view") or soup
        h2 = view.select_one("h2.title")
        full_title = " ".join(h2.get_text(" ", strip=True).split()) if h2 else None

        attachments: list[Attachment] = []
        seen: set[str] = set()
        for a in view.select("a[href*='boardDownload.es']"):
            url = urljoin(BASE, a.get("href") or "")
            if url in seen:
                continue
            seen.add(url)
            name = a.get_text(" ", strip=True)
            if name == "다운로드":
                continue
            attachments.append(Attachment(url=url, filename=name))
        return full_title, attachments

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지에서 전체 제목·첨부를 추출해 Notice 를 만든다."""
        resp = self.http.get(stub.detail_url)
        full_title, attachments = self.parse_detail(resp.text)

        raw = {
            "listNo": stub.notice_id,
            "title": full_title or stub.title,
            "category": stub.category,
            "postedDate": stub.posted_date,
            "_detail_html": resp.text,
        }
        raw["normalized"] = normalize_raw(raw)
        notice = Notice.from_stub(stub, source=self.key, attachments=attachments, raw=raw)
        if full_title:
            notice.title = full_title
        return notice
