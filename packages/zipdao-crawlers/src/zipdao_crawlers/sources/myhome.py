"""마이홈포털 공공임대 입주자모집공고 공공데이터 API 크롤러 소스."""

from __future__ import annotations

import re
from collections.abc import Iterator

from zipdao_core.config import load_settings
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.sources._myhome_regions import REGIONS

LIST_EP = "https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList"
NUM_ROWS = 100


def _iso(yyyymmdd) -> str | None:
    if not yyyymmdd:
        return None
    d = str(yyyymmdd).strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def _won(value) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    n = int(digits) if digits else None
    # 매입/전세임대 등은 목록 API 가 0 을 반환 → 값 없음으로 취급
    return n if n and n > 0 else None


def _lh_pan_id(url) -> str | None:
    m = re.search(r"[?&]panId=(\d+)", str(url)) if url else None
    return m.group(1) if m else None


def normalize(item: dict) -> dict:
    """마이홈 공고 item 을 정규화 블록으로 변환한다."""
    return {
        "supplyType": item.get("suplyTyNm") or None,
        "depositKRW": _won(item.get("rentGtn")),
        "monthlyRentKRW": _won(item.get("mtRntchrg")),
        "areaM2": None,
        "applyStart": _iso(item.get("beginDe")),
        "applyEnd": _iso(item.get("endDe")),
        "summary": None,
        "eligibility": None,
        "supersedes": item.get("beforePblancId") or None,
        "lhPanId": _lh_pan_id(item.get("url")),
    }


class MyhomeCrawler(BaseCrawler):
    """마이홈 공공데이터 API 로 공고를 수집하는 크롤러."""

    key = "myhome"
    name = "마이홈 공공임대 입주자모집공고(공공데이터 API)"
    base_url = "https://www.myhome.go.kr"

    def __init__(self, http) -> None:
        super().__init__(http)
        self._key = load_settings().data_go_kr_service_key
        if not self._key:
            raise RuntimeError(
                "DATA_GO_KR_SERVICE_KEY 미설정(.env). 공공데이터포털 인증키가 필요합니다."
            )

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """지역코드별로 공고 요약을 순회한다."""
        for brtc, signgu, sido_nm, sgg_nm in REGIONS:
            for item in self._fetch_region(brtc, signgu):
                posted = _iso(item.get("rcritPblancDe"))
                year = int(posted[:4]) if posted and posted[:4].isdigit() else None
                if since is not None and (year is None or year < since):
                    continue
                if until is not None and (year is None or year > until):
                    continue
                yield NoticeStub(
                    notice_id=str(item.get("pblancId") or "").strip(),
                    title=(item.get("pblancNm") or "").strip(),
                    detail_url=(item.get("pcUrl") or item.get("url") or "").strip(),
                    posted_date=posted,
                    category=item.get("suplyTyNm"),
                    region=f"{item.get('brtcNm', '')} {item.get('signguNm', '')}".strip(),
                    extra={"item": item},
                )

    def _fetch_region(self, brtc: str, signgu: str) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while True:
            resp = self.http.get(
                LIST_EP,
                params={
                    "serviceKey": self._key,
                    "brtcCode": brtc,
                    "signguCode": signgu,
                    "numOfRows": NUM_ROWS,
                    "pageNo": page,
                },
            )
            items, total = self.parse_items(resp.json())
            if not items:
                break
            rows.extend(items)
            if page * NUM_ROWS >= total:
                break
            page += 1
        return rows

    @staticmethod
    def parse_items(data) -> tuple[list[dict], int]:
        """마이홈 응답에서 (항목 목록, 전체건수)를 추출한다."""
        if not isinstance(data, dict):
            return [], 0
        body = data.get("response", {}).get("body") or {}
        items = body.get("item") or []
        if isinstance(items, dict):
            items = [items]
        total = int(body.get("totalCount") or 0)
        return items, total

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """공고 raw 데이터를 정규화해 Notice 를 만든다."""
        item = stub.extra["item"]
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=stub.posted_date,
            category=stub.category,
            region=stub.region,
            attachments=[],
            raw={"item": item, "normalized": normalize(item)},
        )
