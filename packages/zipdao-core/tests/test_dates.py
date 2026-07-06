from __future__ import annotations

from zipdao_core.dates import to_iso_date


def test_iso_passthrough():
    assert to_iso_date("2026-06-18") == "2026-06-18"
    assert to_iso_date("2026-06-18T09:00:00") == "2026-06-18"


def test_dotted_and_slashed():
    assert to_iso_date("2026.06.18") == "2026-06-18"
    assert to_iso_date("2026/06/18") == "2026-06-18"


def test_yyyymmdd():
    assert to_iso_date("20211115") == "2021-11-15"


def test_epoch_milliseconds():
    # BMSR00013 실측값: epoch ms → KST 날짜
    assert to_iso_date(1781080904000) == "2026-06-10"
    assert to_iso_date("1778804888000") == "2026-05-15"


def test_epoch_seconds():
    assert to_iso_date(1700000000) == "2023-11-15"


def test_empty_and_none():
    assert to_iso_date(None) is None
    assert to_iso_date("") is None
    assert to_iso_date("  ") is None


def test_zero_pads_single_digit_month_day():
    assert to_iso_date("2026.6.8") == "2026-06-08"
    assert to_iso_date("2026-6-8") == "2026-06-08"


def test_rejects_non_date_text():
    assert to_iso_date("미정") is None
