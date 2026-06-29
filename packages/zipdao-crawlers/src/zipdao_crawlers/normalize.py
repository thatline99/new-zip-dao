"""소스별 raw → 표준 정규화 블록(raw["normalized"]).

서빙 API(zipdao-api)는 보증금·월세·면적·접수일·공급유형을 manifest 의 raw["normalized"]
에서 읽는다. 신규 수집은 크롤러가 이 블록을 채우고, 이미 디스크에 있는 manifest 는
`zipdao-crawl normalize` 백필이 같은 함수를 적용한다. 소스마다 raw 형태가 다르므로
source 키로 디스패치한다.

myhome 은 두 형태가 공존한다: HWSPR04 단지·세대(면적·보증금·월세 있음, 접수일 없음)와
HWSPR02 모집공고(보증금·월세·접수일 있음, 면적 없음). 디스크 데이터는 HWSPR04 형태다.
"""

from __future__ import annotations

from zipdao_core.dates import to_iso_date

NORMALIZED_KEYS = (
    "supplyType",
    "depositKRW",
    "monthlyRentKRW",
    "areaM2",
    "applyStart",
    "applyEnd",
    "summary",
    "eligibility",
)


def _won(value: object) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    n = int(digits) if digits else None
    return n if n and n > 0 else None


def _area(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return round(f, 2) if f > 0 else None


def _first(*values: object) -> object | None:
    for v in values:
        if v not in (None, "", 0):
            return v
    return None


def normalize_myhome(raw: dict) -> dict:
    if "item" in raw:
        from zipdao_crawlers.sources.myhome import normalize as normalize_hwspr02

        return normalize_hwspr02(raw["item"])

    head = raw.get("단지") or {}
    units = raw.get("세대목록") or []
    unit_areas = [a for a in (_area(u.get("suplyPrvuseAr")) for u in units) if a]
    unit_deposits = [d for d in (_won(u.get("bassRentGtn")) for u in units) if d]
    unit_rents = [r for r in (_won(u.get("bassMtRntchrg")) for u in units) if r]
    supply = head.get("suplyTyNm") or (units[0].get("suplyTyNm") if units else None)
    return {
        "supplyType": supply or None,
        "depositKRW": _won(head.get("bassRentGtn"))
        or (min(unit_deposits) if unit_deposits else None),
        "monthlyRentKRW": _won(head.get("bassMtRntchrg"))
        or (min(unit_rents) if unit_rents else None),
        "areaM2": _area(head.get("suplyPrvuseAr"))
        or (min(unit_areas) if unit_areas else None),
        "applyStart": None,
        "applyEnd": None,
        "summary": None,
        "eligibility": None,
    }


def normalize_applyhome(raw: dict) -> dict:
    supply = _first(raw.get("RENT_SECD_NM"), raw.get("HOUSE_SECD_NM"))
    return {
        "supplyType": supply,
        "depositKRW": None,
        "monthlyRentKRW": None,
        "areaM2": None,
        "applyStart": to_iso_date(raw.get("RCEPT_BGNDE")),
        "applyEnd": to_iso_date(raw.get("RCEPT_ENDDE")),
        "summary": None,
        "eligibility": None,
    }


def normalize_lh(raw: dict) -> dict:
    from zipdao_crawlers.sources.lh_apply import normalize as normalize_lh_item

    return normalize_lh_item(raw)


def normalize_youth(raw: dict) -> dict:
    return {
        "supplyType": None,
        "depositKRW": None,
        "monthlyRentKRW": None,
        "areaM2": None,
        "applyStart": None,
        "applyEnd": to_iso_date(raw.get("applyDate")),
        "summary": None,
        "eligibility": None,
    }


_DISPATCH = {
    "myhome": normalize_myhome,
    "applyhome": normalize_applyhome,
    "lh_apply": normalize_lh,
    "youth_seoul": normalize_youth,
}


def normalize_for(source: str, raw: dict) -> dict:
    fn = _DISPATCH.get(source)
    return fn(raw) if fn else {}
