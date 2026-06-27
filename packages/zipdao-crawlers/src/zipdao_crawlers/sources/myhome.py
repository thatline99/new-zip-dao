"""마이홈포털 공공임대 입주자모집공고 — 공공데이터 API (data.go.kr 1613000).

오퍼레이션: HWSPR02/rsdtRcritNtcList (공공임대 모집공고 목록)
필수 파라미터: serviceKey, brtcCode(시도 2자리), signguCode(시군구 3자리)
응답 item 필드: pblancId, pblancNm, suplyTyNm, rentGtn(보증금), mtRntchrg(월세),
brtcNm, signguNm, fullAdres, rcritPblancDe, beginDe, endDe, pcUrl, url.
면적은 이 오퍼레이션에 없음(전용면적은 HWSPR04에 있으나 미인가).
"""

from __future__ import annotations

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
    return d or None


def _won(value) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def normalize(item: dict) -> dict:
    return {
        "supplyType": item.get("suplyTyNm") or None,
        "depositKRW": _won(item.get("rentGtn")),
        "monthlyRentKRW": _won(item.get("mtRntchrg")),
        "areaM2": None,
        "applyStart": _iso(item.get("beginDe")),
        "applyEnd": _iso(item.get("endDe")),
        "summary": None,
        "eligibility": None,
    }


class MyhomeCrawler(BaseCrawler):
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
        if not isinstance(data, dict):
            return [], 0
        body = data.get("response", {}).get("body") or {}
        items = body.get("item") or []
        if isinstance(items, dict):
            items = [items]
        total = int(body.get("totalCount") or 0)
        return items, total

    def fetch_detail(self, stub: NoticeStub) -> Notice:
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
