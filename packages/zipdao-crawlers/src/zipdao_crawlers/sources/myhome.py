"""마이홈포털 공공임대 입주자모집공고 공공데이터 API 크롤러 소스."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import DataGoKrCrawler
from zipdao_crawlers.normalize import _area, _won
from zipdao_crawlers.sources._myhome_regions import REGIONS

logger = logging.getLogger(__name__)

LIST_EP = "https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList"
COMPLEX_EP = "https://apis.data.go.kr/1613000/HWSPR04/rentalHouseGwList"
NUM_ROWS = 100
COMPLEX_ROWS = 500


def _iso(yyyymmdd) -> str | None:
    if not yyyymmdd:
        return None
    d = str(yyyymmdd).strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def _lh_pan_id(url) -> str | None:
    m = re.search(r"[?&]panId=(\d+)", str(url)) if url else None
    return m.group(1) if m else None


def _match_units(item: dict, complexes: list[dict]) -> list[dict]:
    """공고를 단지(HWSPR04) 행들과 pnu → 단지명 순으로 매칭한다. 미매칭이면 빈 목록."""
    pnu = str(item.get("pnu") or "").strip()
    if pnu:
        rows = [c for c in complexes if str(c.get("pnu") or "").strip() == pnu]
        if rows:
            return rows
    name = (item.get("hsmpNm") or "").strip()
    if name:
        rows = [c for c in complexes if (c.get("hsmpNm") or "").strip() == name]
        if rows:
            return rows
    return []


def normalize(item: dict, units: list[dict] | None = None) -> dict:
    """마이홈 공고 item(+단지 세대목록)을 정규화 블록으로 변환한다.

    금액은 공고의 대표값을 우선하고, 없으면(매입/전세임대 등) 단지 세대
    타입별 값의 최솟값("~부터")을 쓴다. 면적은 공고에 없어 세대 최솟값만.
    """
    units = units or []
    areas = [a for a in (_area(u.get("suplyPrvuseAr")) for u in units) if a]
    deposits = [d for d in (_won(u.get("bassRentGtn")) for u in units) if d]
    rents = [r for r in (_won(u.get("bassMtRntchrg")) for u in units) if r]
    return {
        "supplyType": item.get("suplyTyNm") or None,
        "depositKRW": _won(item.get("rentGtn")) or (min(deposits) if deposits else None),
        "monthlyRentKRW": _won(item.get("mtRntchrg")) or (min(rents) if rents else None),
        "areaM2": min(areas) if areas else None,
        "applyStart": _iso(item.get("beginDe")),
        "applyEnd": _iso(item.get("endDe")),
        "summary": None,
        "eligibility": None,
        "supersedes": item.get("beforePblancId") or None,
        "lhPanId": _lh_pan_id(item.get("url")),
    }


class MyhomeCrawler(DataGoKrCrawler):
    """마이홈 공공데이터 API 로 공고를 수집하는 크롤러."""

    key = "myhome"
    name = "마이홈 공공임대 입주자모집공고(공공데이터 API)"
    base_url = "https://www.myhome.go.kr"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """지역코드별로 공고 요약을 순회한다(단지 세대정보를 함께 붙인다).

        광역 공고는 여러 시군구 조회에 중복 등장하므로 공고 ID 로 중복을 제거하되,
        단지(pnu) 매칭에 성공한 스텁을 우선 보존한다 — 마지막 쓰기가 매칭 결과를
        덮어써 면적·금액을 잃는 것을 막는다.
        """
        best: dict[str, NoticeStub] = {}
        for brtc, signgu, _sido_nm, _sgg_nm in REGIONS:
            picked: list[tuple[dict, str | None]] = []
            for item in self._fetch_region(brtc, signgu):
                posted = _iso(item.get("rcritPblancDe"))
                year = int(posted[:4]) if posted and posted[:4].isdigit() else None
                if since is not None and (year is None or year < since):
                    continue
                if until is not None and (year is None or year > until):
                    continue
                picked.append((item, posted))
            if not picked:
                continue
            complexes = self._fetch_complexes(brtc, signgu)
            for item, posted in picked:
                notice_id = str(item.get("pblancId") or "").strip()
                if not notice_id:
                    continue
                stub = NoticeStub(
                    notice_id=notice_id,
                    title=(item.get("pblancNm") or "").strip(),
                    detail_url=(item.get("pcUrl") or item.get("url") or "").strip(),
                    posted_date=posted,
                    category=item.get("suplyTyNm"),
                    region=f"{item.get('brtcNm', '')} {item.get('signguNm', '')}".strip(),
                    extra={"item": item, "units": _match_units(item, complexes)},
                )
                prev = best.get(notice_id)
                if prev is None or (not prev.extra.get("units") and stub.extra.get("units")):
                    best[notice_id] = stub
        yield from best.values()

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

    def _fetch_complexes(self, brtc: str, signgu: str) -> list[dict]:
        """지역의 임대주택 단지(HWSPR04) 목록을 가져온다. 실패해도 크롤은 계속(빈 목록)."""
        rows: list[dict] = []
        page = 1
        try:
            while True:
                resp = self.http.get(
                    COMPLEX_EP,
                    params={
                        "serviceKey": self._key,
                        "brtcCode": brtc,
                        "signguCode": signgu,
                        "numOfRows": COMPLEX_ROWS,
                        "pageNo": page,
                    },
                )
                items, total = self.parse_items(resp.json())
                if not items:
                    break
                rows.extend(items)
                if page * COMPLEX_ROWS >= total:
                    break
                page += 1
        except Exception:
            logger.warning("단지정보(HWSPR04) 조회 실패: brtc=%s signgu=%s", brtc, signgu)
            return []
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
        """공고 raw 데이터(+단지 세대목록)를 정규화해 Notice 를 만든다."""
        item = stub.extra["item"]
        units = stub.extra.get("units") or []
        raw: dict = {"item": item, "normalized": normalize(item, units)}
        if units:
            raw["세대목록"] = units
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=stub.posted_date,
            category=stub.category,
            region=stub.region,
            attachments=[],
            raw=raw,
        )
