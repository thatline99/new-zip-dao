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
