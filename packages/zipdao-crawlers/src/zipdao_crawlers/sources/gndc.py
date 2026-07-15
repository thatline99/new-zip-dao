"""경남개발공사(gndc.co.kr) 공고 게시판 크롤러.

실측(2026-07-15): CMS 게시판이 JSON XHR 로 목록을 내려준다.
- 목록: GET /getBbsArticleList.do (BBS_ID, CURRENT_PAGE, ATTR01=COLM1_CD 분류 필터)
  → {pageInfo, resultList}. 첨부 경로(sysFileNameStr)·원본 파일명(orgFileNameStr)까지 포함.
- 상세: GET /boardview/boardview.do (seqId, BBS_ID, IPDS_IDX, COLM1/COLM1_CD 필수) → 서버렌더 본문.
- 첨부: GET /common/download.do?fileVirtualPath=&fileOrgName= (목록 응답 경로 그대로).
robots.txt 없음(요청 시 에러 페이지 반환).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import quote

from zipdao_core.dates import to_iso_date, year_out_of_range
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.fields import normalized_block, supply_type_from_title

BASE = "https://www.gndc.co.kr"
LIST_API = f"{BASE}/getBbsArticleList.do"
DOWNLOAD = f"{BASE}/common/download.do"

# 공고 게시판(BBS_ID 하나)을 COLM1_CD 코드로 분류 필터링한다.
BBS_ID = "B491A490314446318099F9D828047900"
# (메뉴 seqId, COLM1 코드, 카테고리, 주택 제목 필터 적용 여부)
BOARDS: list[tuple[str, str, str, bool]] = [
    ("0000006202", "notice_06", "임대", False),
    # 분양 게시판은 토지·상가·개장공고가 섞여 있어 주택 관련 제목만 수집한다.
    ("0000006190", "notice_01", "분양", True),
]

_HOUSING_RE = re.compile(r"주택|임대|입주자|셰어하우스")


def normalize_raw(raw: dict) -> dict:
    """경남개발공사 raw 데이터를 정규화 블록으로 변환한다(구조화 필드는 공고문 파싱에 의존)."""
    return normalized_block(supplyType=supply_type_from_title(raw.get("CPDS_SUBJECT")))


class GndcCrawler(BaseCrawler):
    """경남개발공사 공고 게시판을 수집하는 크롤러."""

    key = "gndc"
    name = "경남개발공사"
    base_url = BASE

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """분류별 게시판을 페이지 순회하며 공고 요약을 만든다."""
        for seq_id, colm1, category, housing_only in BOARDS:
            yield from self._iter_board(seq_id, colm1, category, housing_only, since, until)

    def _iter_board(
        self,
        seq_id: str,
        colm1: str,
        category: str,
        housing_only: bool,
        since: int | None,
        until: int | None,
    ) -> Iterator[NoticeStub]:
        page = 1
        while True:
            data = self._fetch_page(colm1, page)
            rows = data.get("resultList") or []
            if not rows:
                break
            # 공지(MUST_LVL≥1) 행이 최신순 목록 위에 고정되어 연도 조기중단은 쓰지 않는다.
            for row in rows:
                stub = self.stub_from_row(row, seq_id=seq_id, colm1=colm1, category=category)
                if stub is None:
                    continue
                if housing_only and not _HOUSING_RE.search(stub.title):
                    continue
                if year_out_of_range(stub.posted_date, since, until):
                    continue
                yield stub
            total_pages = int((data.get("pageInfo") or {}).get("totalPageCount") or 0)
            if page >= total_pages:
                break
            page += 1

    def _fetch_page(self, colm1: str, page: int) -> dict:
        resp = self.http.get(
            LIST_API,
            params={
                "BBS_ID": BBS_ID,
                "BBS_TYPE": "L",
                "CURRENT_PAGE": page,
                "ATTR01": f"COLM1_CD&{colm1}|COLM3_CD",
                "ATTR02": "COLM3_CD",
                "ATTR03": "",
                "ATTR04": "",
                "SEARCH_CONTITION": "CPDS_SUBJECT_CONTENT",
                "SEARCH_KEYWORD": "",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = resp.json()
        return data if isinstance(data, dict) else {}

    @staticmethod
    def stub_from_row(row: dict, *, seq_id: str, colm1: str, category: str) -> NoticeStub | None:
        """목록 행(JSON)을 NoticeStub 으로 변환한다. 식별자가 없으면 None."""
        idx = str(row.get("IPDS_IDX") or "").strip()
        if not idx:
            return None
        posted = to_iso_date(row.get("RGST_DTM") or row.get("CPDS_WDATE"))
        region = "경남"
        district = str(row.get("COLM3_VAL") or "").strip()
        if district and district not in ("기타", "N"):
            region = f"경남 {district}"
        detail_url = (
            f"{BASE}/boardview/boardview.do?seqId={seq_id}&BBS_ID={BBS_ID}"
            f"&IPDS_IDX={idx}&BBS_TYPE=L&COLM1={colm1}&COLM1_CD={colm1}"
        )
        return NoticeStub(
            notice_id=idx,
            title=(row.get("CPDS_SUBJECT") or "").strip(),
            detail_url=detail_url,
            posted_date=posted,
            category=category,
            region=region,
            extra={**row, "_colm1": colm1, "_seqId": seq_id},
        )

    @staticmethod
    def parse_attachments(row: dict) -> list[Attachment]:
        """목록 행의 sysFileNameStr/orgFileNameStr('|' 구분)로 첨부 목록을 만든다."""
        sys_paths = [p for p in str(row.get("sysFileNameStr") or "").split("|") if p.strip()]
        org_names = [n for n in str(row.get("orgFileNameStr") or "").split("|") if n.strip()]
        attachments: list[Attachment] = []
        for i, sys_path in enumerate(sys_paths):
            org = org_names[i].strip() if i < len(org_names) else ""
            url = (
                f"{DOWNLOAD}?fileVirtualPath={quote(sys_path, safe='')}"
                f"&fileOrgName={quote(org, safe='')}"
            )
            attachments.append(Attachment(url=url, filename=org))
        return attachments

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지 스냅샷을 받고 목록 행 데이터로 Notice 를 만든다."""
        resp = self.http.get(stub.detail_url)
        attachments = self.parse_attachments(stub.extra)

        raw = {k: v for k, v in stub.extra.items() if not k.startswith("_")}
        raw["_detail_html"] = resp.text
        raw["normalized"] = normalize_raw(raw)
        return Notice.from_stub(stub, source=self.key, attachments=attachments, raw=raw)
