"""공고 필드 값(금액·면적 등) 공용 파싱 헬퍼."""

from __future__ import annotations

import re


def _won(value: object) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    n = int(digits) if digits else None
    return n if n and n > 0 else None


def _count(value: object) -> int | None:
    """양의 정수(세대수 등 개수) 값. 없거나 0 이하이면 None."""
    return _won(value)


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


# 제목에서 공급유형을 추정하는 키워드(앞선 항목 우선).
# 구조화 필드가 없는 게시판형 소스(sh_ish·gndc)가 쓴다.
_SUPPLY_KEYWORDS = [
    "행복주택",
    "장기전세",
    "장기미임대",
    "국민임대",
    "영구임대",
    "통합공공임대",
    "공공임대",
    "매입임대",
    "전세임대",
    "사회주택",
    "안심주택",
    "두레주택",
    "셰어하우스",
    "도시형생활주택",
    "신혼희망타운",
    "공공분양",
]


def supply_type_from_title(title: object) -> str | None:
    """제목 문자열에서 공급유형 키워드를 찾는다. 없으면 None."""
    text = str(title or "")
    for keyword in _SUPPLY_KEYWORDS:
        if keyword in text:
            return keyword
    return None


# 정규화 블록(raw.normalized)의 공통 키 — 모든 소스가 최소 이 키들을 갖는다.
_NORMALIZED_KEYS = (
    "supplyType",
    "depositKRW",
    "monthlyRentKRW",
    "areaM2",
    "applyStart",
    "applyEnd",
    "winnerAnnounceDate",
    "supplyHouseholds",
    "summary",
    "eligibility",
)


def normalized_block(**fields: object) -> dict:
    """공통 키를 None 으로 깐 정규화 블록에 주어진 값을 얹는다(소스 고유 키 추가 허용)."""
    block: dict = dict.fromkeys(_NORMALIZED_KEYS)
    block.update(fields)
    return block
