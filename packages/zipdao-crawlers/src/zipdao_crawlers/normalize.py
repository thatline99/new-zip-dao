"""소스별 raw 데이터를 표준 정규화 블록(raw['normalized'])으로 변환한다."""

from __future__ import annotations

import re

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


_NUM_RE = re.compile(r"\s*(-?\d+(?:\.\d+)?)")


def _area(value: object) -> float | None:
    if isinstance(value, (int, float)):
        f = float(value)
    elif isinstance(value, str):
        match = _NUM_RE.match(value)
        if not match:
            return None
        f = float(match.group(1))
    else:
        return None
    return round(f, 2) if f > 0 else None


def _first(*values: object) -> object | None:
    for v in values:
        if v not in (None, "", 0):
            return v
    return None


def normalize_myhome(raw: dict) -> dict:
    """마이홈 raw({"item": 공고행, "세대목록": 단지 행들})를 정규화 블록으로 변환한다."""
    from zipdao_crawlers.sources.myhome import normalize as normalize_item

    return normalize_item(raw.get("item") or {}, raw.get("세대목록"))


def normalize_applyhome(raw: dict) -> dict:
    """청약홈 raw 데이터를 정규화 블록으로 변환한다(APT·공공지원민간임대 필드 변형 대응)."""
    supply = _first(
        raw.get("RENT_SECD_NM"),
        raw.get("HOUSE_DETAIL_SECD_NM"),
        raw.get("HOUSE_DTL_SECD_NM"),
        raw.get("HOUSE_SECD_NM"),
    )
    return {
        "supplyType": supply,
        "depositKRW": None,
        "monthlyRentKRW": None,
        "areaM2": None,
        "applyStart": to_iso_date(_first(raw.get("RCEPT_BGNDE"), raw.get("SUBSCRPT_RCEPT_BGNDE"))),
        "applyEnd": to_iso_date(_first(raw.get("RCEPT_ENDDE"), raw.get("SUBSCRPT_RCEPT_ENDDE"))),
        "summary": None,
        "eligibility": None,
    }


def normalize_lh(raw: dict) -> dict:
    """LH 청약플러스 raw 데이터를 정규화 블록으로 변환한다."""
    from zipdao_crawlers.sources.lh_apply import normalize as normalize_lh_item

    return normalize_lh_item(raw, raw.get("일정목록"), raw.get("공급목록"))


def normalize_youth(raw: dict) -> dict:
    """청년안심주택 raw 데이터를 정규화 블록으로 변환한다."""
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
    """소스 키에 맞는 정규화 함수로 raw 데이터를 변환한다."""
    fn = _DISPATCH.get(source)
    return fn(raw) if fn else {}
