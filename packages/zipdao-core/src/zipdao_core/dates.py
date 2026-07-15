"""다양한 소스의 날짜 표기를 ISO(YYYY-MM-DD)로 정규화한다."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
_DATE_RE = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")


def to_iso_date(value) -> str | None:
    """값을 'YYYY-MM-DD'로 정규화한다. 해석 불가하면 None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    if s.isdigit():
        if len(s) == 8:
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        ts = int(s)
        if len(s) >= 12:
            ts //= 1000
        try:
            return datetime.fromtimestamp(ts, tz=KST).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return None

    match = _DATE_RE.match(s)
    if not match:
        return None
    year, month, day = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def year_of(iso_date: str | None) -> int | None:
    """ISO 날짜 문자열에서 연도(int)를 뽑는다. 해석 불가하면 None."""
    if iso_date and iso_date[:4].isdigit():
        return int(iso_date[:4])
    return None


def year_out_of_range(iso_date: str | None, since: int | None, until: int | None) -> str | None:
    """날짜 연도가 [since, until] 밖이면 'newer'/'older', 안이거나 판정 불가면 None.

    'older' 는 최신순 목록을 도는 크롤러의 조기 중단 신호로 쓸 수 있다.
    """
    year = year_of(iso_date)
    if year is None:
        return None
    if until is not None and year > until:
        return "newer"
    if since is not None and year < since:
        return "older"
    return None
