from __future__ import annotations

from zipdao_crawlers.fields import _area
from zipdao_crawlers.normalize import normalize_for
from zipdao_crawlers.sources.applyhome import normalize_raw as normalize_applyhome
from zipdao_crawlers.sources.myhome import normalize_raw as normalize_myhome
from zipdao_crawlers.sources.youth_seoul import normalize_raw as normalize_youth


def test_myhome_units_extract_area_and_item_price_wins():
    raw = {
        "item": {"suplyTyNm": "영구임대", "rentGtn": 3449000, "mtRntchrg": 76720},
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


def test_myhome_units_fill_when_item_prices_missing():
    raw = {
        "item": {"suplyTyNm": "매입임대", "rentGtn": 0},
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
    raw = {
        "item": {
            "suplyTyNm": "국민임대",
            "rentGtn": "1,000,000",
            "mtRntchrg": 200000,
            "beginDe": "20260618",
            "endDe": "20260702",
        }
    }
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


def test_area_parses_unit_suffixed_string():
    assert _area("84.99㎡") == 84.99
    assert _area("26.34") == 26.34
    assert _area(26.34) == 26.34
    assert _area("없음") is None
    assert _area(None) is None
