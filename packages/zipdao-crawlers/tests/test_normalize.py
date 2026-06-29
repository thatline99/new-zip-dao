"""정규화 디스패치 단위 테스트 (네트워크 불필요)."""

from __future__ import annotations

from zipdao_crawlers.normalize import (
    normalize_applyhome,
    normalize_for,
    normalize_myhome,
    normalize_youth,
)


def test_myhome_hwspr04_extracts_area_and_price():
    raw = {
        "단지": {
            "suplyTyNm": "영구임대",
            "suplyPrvuseAr": 26.34,
            "bassRentGtn": 3449000,
            "bassMtRntchrg": 76720,
        },
        "세대목록": [
            {"suplyPrvuseAr": 26.34, "bassRentGtn": 3449000, "bassMtRntchrg": 76720},
            {"suplyPrvuseAr": 30.48, "bassRentGtn": 3991000, "bassMtRntchrg": 88010},
        ],
    }
    n = normalize_myhome(raw)
    assert n["supplyType"] == "영구임대"
    assert n["areaM2"] == 26.34
    assert n["depositKRW"] == 3449000
    assert n["monthlyRentKRW"] == 76720
    assert n["applyStart"] is None


def test_myhome_hwspr04_falls_back_to_units_when_head_missing():
    raw = {
        "단지": {"suplyTyNm": "매입임대"},
        "세대목록": [
            {"suplyPrvuseAr": 24.83, "bassRentGtn": 3489000, "bassMtRntchrg": 0},
            {"suplyPrvuseAr": 21.86, "bassRentGtn": 3053000, "bassMtRntchrg": 0},
        ],
    }
    n = normalize_myhome(raw)
    assert n["areaM2"] == 21.86
    assert n["depositKRW"] == 3053000
    assert n["monthlyRentKRW"] is None


def test_myhome_hwspr02_item_shape_delegates():
    raw = {"item": {"suplyTyNm": "국민임대", "rentGtn": "1,000,000", "mtRntchrg": 200000,
                    "beginDe": "20260618", "endDe": "20260702"}}
    n = normalize_myhome(raw)
    assert n["supplyType"] == "국민임대"
    assert n["depositKRW"] == 1000000
    assert n["applyStart"] == "2026-06-18"
    assert n["areaM2"] is None


def test_applyhome_maps_receipt_dates():
    n = normalize_applyhome(
        {"RENT_SECD_NM": "공공임대(10년)", "RCEPT_BGNDE": "2026-06-09", "RCEPT_ENDDE": "2026-06-30"}
    )
    assert n["supplyType"] == "공공임대(10년)"
    assert n["applyStart"] == "2026-06-09"
    assert n["applyEnd"] == "2026-06-30"


def test_youth_does_not_use_posted_date_as_apply_start():
    n = normalize_youth({"postedDate": "2022-09-15", "applyDate": "2022-09-22"})
    assert n["applyStart"] is None
    assert n["applyEnd"] == "2022-09-22"


def test_youth_announcement_without_apply_date_has_no_dates():
    n = normalize_youth({"postedDate": "2022-09-07", "applyDate": None})
    assert n["applyStart"] is None
    assert n["applyEnd"] is None


def test_dispatch_unknown_source_is_empty():
    assert normalize_for("nope", {"x": 1}) == {}
