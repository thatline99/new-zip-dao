"""날짜 정규화 — 다양한 소스 표기를 ISO(YYYY-MM-DD)로.

한국 공공 게시판은 게시일을 ISO 문자열, `YYYYMMDD`, 또는 epoch(초/밀리초) 정수 등
제각각으로 준다. KST(UTC+9) 기준 달력 날짜로 통일한다.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def to_iso_date(value) -> str | None:
    """값을 'YYYY-MM-DD' 로 정규화. 해석 불가하면 None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    if s.isdigit():
        if len(s) == 8:  # YYYYMMDD
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        ts = int(s)
        if len(s) >= 12:  # epoch milliseconds
            ts //= 1000
        # 그 외(10자리 등)는 epoch seconds 로 간주
        try:
            return datetime.fromtimestamp(ts, tz=KST).strftime("%Y-%m-%d")
        except (OSError, ValueError, OverflowError):
            return None

    # 구분자가 섞인 날짜 문자열: 2026.06.18 / 2026/06/18 → 2026-06-18
    s = s.replace(".", "-").replace("/", "-").replace(" ", "")
    return s[:10] if s else None
