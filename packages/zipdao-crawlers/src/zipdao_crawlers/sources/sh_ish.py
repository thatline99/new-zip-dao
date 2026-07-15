"""SH 인터넷청약시스템(i-sh.co.kr/app) 공고 게시판 크롤러.

실측(2026-07-15): 게시판은 서버렌더 HTML 로, 목록·상세 모두 mainform POST 다.
- 목록: POST {게시판}/list.do (page, multi_itm_seq) → tbody 행 + getPaging(마지막페이지)
- 상세: POST {게시판}/view.do (seq) → 본문 + initParam.downList(첨부 JSON)
- 첨부: GET /app/com/file/innoFD.do?brdId=&seq=&fileTp=&fileSeq= (이노릭스 스트림)
robots.txt 의 `*` 그룹은 /app 게시판을 막지 않는다(차단 목록은 /gcms/brd 등).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from zipdao_core.dates import year_of
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler

BASE = "https://www.i-sh.co.kr"
FILE_DOWN = f"{BASE}/app/com/file/innoFD.do"

# (multi_itm_seq, 카테고리, 게시판 경로) — 공고 게시판(전체 m_241)의 비트 플래그 중
# 입주자 모집과 직결되는 분류만. (512 주택매입은 SH 가 기존주택을 사들이는 공고라 제외)
BOARDS: list[tuple[str, str, str]] = [
    ("2", "주택임대", "/app/lay2/program/S1T294C297/www/brd/m_247"),
    ("1", "주택분양", "/app/lay2/program/S1T294C296/www/brd/m_244"),
]

_DETAIL_SEQ_RE = re.compile(r"getDetailView\('(\d+)'\)")
_LAST_PAGE_RE = re.compile(r"getPaging\((\d+),")
_DOWN_LIST_RE = re.compile(r"initParam\.downList\s*=\s*(\[.*?\])\s*;", re.S)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# 제목에서 공급유형을 추정하는 키워드(앞선 항목 우선). 게시판에 구조화 필드가 없다.
_SUPPLY_KEYWORDS = [
    "행복주택",
    "장기전세",
    "장기미임대",
    "국민임대",
    "영구임대",
    "공공임대",
    "매입임대",
    "전세임대",
    "사회주택",
    "안심주택",
    "두레주택",
    "도시형생활주택",
    "신혼희망타운",
    "공공분양",
]


def _supply_from_title(title: str) -> str | None:
    for keyword in _SUPPLY_KEYWORDS:
        if keyword in title:
            return keyword
    return None


def normalize_raw(raw: dict) -> dict:
    """SH 게시판 raw 데이터를 정규화 블록으로 변환한다(구조화 필드는 공고문 파싱에 의존)."""
    return {
        "supplyType": _supply_from_title(str(raw.get("title") or "")),
        "depositKRW": None,
        "monthlyRentKRW": None,
        "areaM2": None,
        "applyStart": None,
        "applyEnd": None,
        "winnerAnnounceDate": None,
        "supplyHouseholds": None,
        "summary": None,
        "eligibility": None,
    }


class ShIshCrawler(BaseCrawler):
    """SH 인터넷청약 공고 게시판을 수집하는 크롤러."""

    key = "sh_ish"
    name = "SH 인터넷청약"
    base_url = f"{BASE}/app"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """분류별 게시판을 페이지 순회하며 공고 요약을 만든다."""
        for seq_flag, category, board_path in BOARDS:
            yield from self._iter_board(seq_flag, category, board_path, since, until)

    def _iter_board(
        self,
        seq_flag: str,
        category: str,
        board_path: str,
        since: int | None,
        until: int | None,
    ) -> Iterator[NoticeStub]:
        page = 1
        while True:
            resp = self.http.post(
                f"{BASE}{board_path}/list.do",
                data={"page": page, "seq": "", "multi_itm_seq": seq_flag},
            )
            rows, last_page = self.parse_list(resp.text)
            if not rows:
                break

            stop = False
            for row in rows:
                year = year_of(row["posted"])
                if year is not None:
                    if until is not None and year > until:
                        continue
                    if since is not None and year < since:
                        stop = True
                        continue
                yield NoticeStub(
                    notice_id=row["seq"],
                    title=row["title"],
                    detail_url=f"{BASE}{board_path}/view.do?seq={row['seq']}",
                    posted_date=row["posted"],
                    category=category,
                    region="서울",
                    extra={
                        "multiItmSeq": seq_flag,
                        "boardPath": board_path,
                        "dept": row["dept"],
                    },
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
            a = tr.select_one("a[onclick*='getDetailView']")
            if a is None:
                continue
            match = _DETAIL_SEQ_RE.search(a.get("onclick") or "")
            if match is None:
                continue
            for span in a.select("span"):  # "NEW" 아이콘 제거
                span.extract()
            title = " ".join(a.get_text(" ", strip=True).split())

            tds = tr.select("td")
            posted: str | None = None
            for td in tds:
                date_match = _ISO_DATE_RE.search(td.get_text(strip=True))
                if date_match:
                    posted = date_match.group(0)
                    break
            dept: str | None = None
            for i, td in enumerate(tds):
                if "txtL" in (td.get("class") or []) and i + 1 < len(tds):
                    dept = tds[i + 1].get_text(strip=True) or None
                    break

            rows.append({"seq": match.group(1), "title": title, "posted": posted, "dept": dept})

        last_page = max((int(n) for n in _LAST_PAGE_RE.findall(html)), default=0)
        return rows, last_page

    @staticmethod
    def parse_attachments(html: str) -> list[Attachment]:
        """상세 HTML 의 initParam.downList JSON 에서 첨부 목록을 만든다."""
        match = _DOWN_LIST_RE.search(html)
        if match is None:
            return []
        try:
            items = json.loads(match.group(1))
        except ValueError:
            return []

        attachments: list[Attachment] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            brd_id = item.get("brdId")
            seq = item.get("seq")
            file_seq = item.get("fileSeq")
            if not (brd_id and seq and file_seq):
                continue
            file_tp = item.get("fileTp") or "A"
            url = f"{FILE_DOWN}?brdId={brd_id}&seq={seq}&fileTp={file_tp}&fileSeq={file_seq}"
            attachments.append(Attachment(url=url, filename=(item.get("oriFileNm") or "").strip()))
        return attachments

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지를 POST 로 받아 첨부를 추출하고 Notice 를 만든다."""
        board_path = stub.extra.get("boardPath") or BOARDS[0][2]
        resp = self.http.post(
            f"{BASE}{board_path}/view.do",
            data={
                "page": 1,
                "seq": stub.notice_id,
                "multi_itm_seq": stub.extra.get("multiItmSeq") or "0",
            },
        )
        attachments = self.parse_attachments(resp.text)

        raw = {
            "seq": stub.notice_id,
            "title": stub.title,
            "dept": stub.extra.get("dept"),
            "multiItmSeq": stub.extra.get("multiItmSeq"),
            "postedDate": stub.posted_date,
            "_detail_html": resp.text,
        }
        raw["normalized"] = normalize_raw(raw)
        return Notice.from_stub(stub, source=self.key, attachments=attachments, raw=raw)
