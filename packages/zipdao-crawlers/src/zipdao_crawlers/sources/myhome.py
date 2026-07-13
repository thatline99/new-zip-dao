"""마이홈포털 공공임대 입주자모집공고 공공데이터 API 크롤러 소스."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from zipdao_core.dates import to_iso_date, year_of
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import DataGoKrCrawler
from zipdao_crawlers.fields import _area, _count, _won
from zipdao_crawlers.sources._myhome_regions import REGIONS

logger = logging.getLogger(__name__)

LIST_EP = "https://apis.data.go.kr/1613000/HWSPR02/rsdtRcritNtcList"
COMPLEX_EP = "https://apis.data.go.kr/1613000/HWSPR04/rentalHouseGwList"
NUM_ROWS = 100
COMPLEX_ROWS = 500


def _lh_pan_id(url: object) -> str | None:
    m = re.search(r"[?&]panId=(\d+)", str(url)) if url else None
    return m.group(1) if m else None


def _region_codes(
    item: dict, by_name: dict[tuple[str, str], tuple[str, str]]
) -> tuple[str, str] | None:
    """단지(HWSPR04) 조회용 (광역, 시군구) 코드를 구한다.

    pnu 앞 5자리가 곧 시군구 코드라 우선 사용한다 — 광역 단위 공고는
    signguNm 이 비어 있어 지역명 매핑만으로는 코드를 찾을 수 없다.
    """
    pnu = str(item.get("pnu") or "").strip()
    if len(pnu) >= 5 and pnu[:5].isdigit():
        return pnu[:2], pnu[2:5]
    return by_name.get(((item.get("brtcNm") or "").strip(), (item.get("signguNm") or "").strip()))


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
        "applyStart": to_iso_date(item.get("beginDe")),
        "applyEnd": to_iso_date(item.get("endDe")),
        "winnerAnnounceDate": to_iso_date(item.get("przwnerPresnatnDe")),
        "supplyHouseholds": _count(item.get("sumSuplyCo")),
        "summary": None,
        "eligibility": None,
        "supersedes": item.get("beforePblancId") or None,
        "lhPanId": _lh_pan_id(item.get("url")),
    }


def normalize_raw(raw: dict) -> dict:
    """저장된 raw({"item": 공고행, "세대목록": 단지 행들})를 정규화 블록으로 변환한다."""
    return normalize(raw.get("item") or {}, raw.get("세대목록"))


class MyhomeCrawler(DataGoKrCrawler):
    """마이홈 공공데이터 API 로 공고를 수집하는 크롤러."""

    key = "myhome"
    name = "마이홈 공공임대 입주자모집공고(공공데이터 API)"
    base_url = "https://www.myhome.go.kr"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """전국 공고를 한 번에 조회하고 단지(HWSPR04) 세대정보를 붙인다.

        지역코드를 생략하면 전국 조회가 되므로 시군구 250여 회 순회가 필요 없다.
        비공식 동작일 수 있어 비어 있으면 시군구 순회로 폴백한다.
        한 공고가 단지(houseSn)별 여러 행으로 오므로 공고 ID 로 중복을 제거하되,
        단지(pnu) 매칭에 성공한 행을 우선 보존한다.
        """
        items: list[dict] = []
        try:
            items = self._fetch_all(LIST_EP, NUM_ROWS)
        except Exception:
            logger.warning("마이홈 전국 조회 실패(예외)")
        if not items:
            logger.warning("마이홈 전국 조회가 비어 있음 — 시군구 순회로 폴백")
            items = [
                it
                for brtc, signgu, _sido, _sgg in REGIONS
                for it in self._fetch_all(
                    LIST_EP, NUM_ROWS, {"brtcCode": brtc, "signguCode": signgu}
                )
            ]

        region_codes = {(sido, sgg): (brtc, signgu) for brtc, signgu, sido, sgg in REGIONS}
        complexes_cache: dict[tuple[str, str], list[dict]] = {}
        best: dict[str, NoticeStub] = {}
        for item in items:
            posted = to_iso_date(item.get("rcritPblancDe"))
            year = year_of(posted)
            if since is not None and (year is None or year < since):
                continue
            if until is not None and (year is None or year > until):
                continue
            notice_id = str(item.get("pblancId") or "").strip()
            if not notice_id:
                continue
            codes = _region_codes(item, region_codes)
            if codes is None:
                units: list[dict] = []
            else:
                if codes not in complexes_cache:
                    try:
                        complexes_cache[codes] = self._fetch_complexes(*codes)
                    except Exception:
                        complexes_cache[codes] = None
                        logger.warning(
                            "단지정보(HWSPR04) 조회 실패: brtc=%s signgu=%s — 지역 공고 저장 생략",
                            *codes,
                        )
                cached = complexes_cache[codes]
                if cached is None:
                    continue
                units = _match_units(item, cached)
            stub = NoticeStub(
                notice_id=notice_id,
                title=(item.get("pblancNm") or "").strip(),
                detail_url=(item.get("pcUrl") or item.get("url") or "").strip(),
                posted_date=posted,
                category=item.get("suplyTyNm"),
                region=f"{item.get('brtcNm', '')} {item.get('signguNm', '')}".strip(),
                extra={"item": item, "units": units},
            )
            prev = best.get(notice_id)
            if prev is None or (not prev.extra.get("units") and stub.extra.get("units")):
                best[notice_id] = stub
        yield from best.values()

    def _fetch_all(
        self, endpoint: str, rows_per_page: int, extra_params: dict | None = None
    ) -> list[dict]:
        """endpoint 를 페이지 순회해 전체 행을 모은다(지역코드는 extra_params 로)."""
        rows: list[dict] = []
        page = 1
        while True:
            resp = self.http.get(
                endpoint,
                params={
                    "serviceKey": self._key,
                    "numOfRows": rows_per_page,
                    "pageNo": page,
                    **(extra_params or {}),
                },
            )
            items, total = self.parse_items(resp.json())
            if not items:
                break
            rows.extend(items)
            if page * rows_per_page >= total:
                break
            page += 1
        return rows

    def _fetch_complexes(self, brtc: str, signgu: str) -> list[dict]:
        """지역의 임대주택 단지(HWSPR04) 목록을 가져온다. 실패 시 예외를 올린다."""
        return self._fetch_all(COMPLEX_EP, COMPLEX_ROWS, {"brtcCode": brtc, "signguCode": signgu})

    @staticmethod
    def parse_items(data: object) -> tuple[list[dict], int]:
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
        return Notice.from_stub(stub, source=self.key, raw=raw)
