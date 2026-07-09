from __future__ import annotations

from zipdao_crawlers.sources._myhome_regions import REGIONS
from zipdao_crawlers.sources.myhome import MyhomeCrawler

SAMPLE = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE"},
        "body": {
            "totalCount": "1004",
            "numOfRows": "1",
            "pageNo": "1",
            "item": [
                {
                    "hsmpSn": 31845491,
                    "insttNm": "SH공사",
                    "hsmpNm": "원에디션강남",
                    "signguNm": "강남구",
                    "suplyTyNm": "행복주택",
                    "houseTyNm": "아파트",
                    "suplyPrvuseAr": 17.845,
                    "bassRentGtn": 66960000,
                    "bassMtRntchrg": 267000,
                }
            ],
        },
    }
}


def test_parse_items_extracts_units_and_total():
    items, total = MyhomeCrawler.parse_items(SAMPLE)
    assert total == 1004
    assert len(items) == 1
    assert items[0]["hsmpNm"] == "원에디션강남"
    assert items[0]["bassMtRntchrg"] == 267000


def test_parse_items_nodata_and_malformed():
    nodata = {"response": {"header": {"resultCode": "03", "resultMsg": "NODATA_ERROR"}}}
    assert MyhomeCrawler.parse_items(nodata) == ([], 0)
    assert MyhomeCrawler.parse_items({}) == ([], 0)
    assert MyhomeCrawler.parse_items("oops") == ([], 0)


def test_parse_items_single_item_dict_wrapped():
    # item 이 단일 dict 로 올 때 리스트로 정규화
    data = {"response": {"body": {"totalCount": "1", "item": {"hsmpNm": "X"}}}}
    items, total = MyhomeCrawler.parse_items(data)
    assert items == [{"hsmpNm": "X"}] and total == 1


def test_regions_table_loaded():
    assert len(REGIONS) > 200
    # 강남구 = 11/680
    assert ("11", "680", "서울특별시", "강남구") in REGIONS


def test_normalize_maps_rental_fields():
    from zipdao_crawlers.sources.myhome import normalize

    item = {
        "suplyTyNm": "국민임대",
        "rentGtn": "66,960,000",
        "mtRntchrg": 267000,
        "beginDe": "20260618",
        "endDe": "20260702",
    }
    n = normalize(item)
    assert n["supplyType"] == "국민임대"
    assert n["depositKRW"] == 66960000
    assert n["monthlyRentKRW"] == 267000
    assert n["applyStart"] == "2026-06-18"
    assert n["applyEnd"] == "2026-07-02"
    assert n["areaM2"] is None


def test_normalize_units_fill_missing_price_and_area():
    from zipdao_crawlers.sources.myhome import normalize

    units = [
        {"suplyPrvuseAr": 62.081, "bassRentGtn": 20000000, "bassMtRntchrg": 300000},
        {"suplyPrvuseAr": 46.12, "bassRentGtn": 15000000, "bassMtRntchrg": 250000},
        {"suplyPrvuseAr": 0, "bassRentGtn": "0", "bassMtRntchrg": None},  # 무효값은 무시
    ]
    n = normalize({"suplyTyNm": "매입임대", "rentGtn": 0, "mtRntchrg": 0}, units)
    assert n["areaM2"] == 46.12
    assert n["depositKRW"] == 15000000
    assert n["monthlyRentKRW"] == 250000


def test_normalize_item_price_wins_over_units():
    from zipdao_crawlers.sources.myhome import normalize

    units = [{"suplyPrvuseAr": 46.12, "bassRentGtn": 15000000, "bassMtRntchrg": 250000}]
    n = normalize({"suplyTyNm": "행복주택", "rentGtn": 66960000, "mtRntchrg": 267000}, units)
    assert n["depositKRW"] == 66960000
    assert n["monthlyRentKRW"] == 267000
    assert n["areaM2"] == 46.12  # 면적은 공고에 없으므로 단지값


def test_match_units_pnu_first_then_name():
    from zipdao_crawlers.sources.myhome import _match_units

    complexes = [
        {"pnu": "1168010100106530006", "hsmpNm": "원에디션강남", "suplyPrvuseAr": 17.8},
        {"pnu": "9999", "hsmpNm": "다른단지", "suplyPrvuseAr": 30.0},
    ]
    assert _match_units({"pnu": "1168010100106530006", "hsmpNm": ""}, complexes)[0]["suplyPrvuseAr"] == 17.8
    assert _match_units({"pnu": "", "hsmpNm": "다른단지"}, complexes)[0]["suplyPrvuseAr"] == 30.0
    assert _match_units({"pnu": "0000", "hsmpNm": "없는단지"}, complexes) == []
    assert _match_units({}, []) == []


def test_normalize_for_uses_stored_units():
    from zipdao_crawlers.normalize import normalize_for

    raw = {
        "item": {"suplyTyNm": "전세임대", "rentGtn": 0},
        "세대목록": [{"suplyPrvuseAr": 59.9, "bassRentGtn": 12000000, "bassMtRntchrg": 0}],
    }
    n = normalize_for("myhome", raw)
    assert n["areaM2"] == 59.9
    assert n["depositKRW"] == 12000000
    assert n["monthlyRentKRW"] is None


def test_normalize_zero_won_is_missing():
    from zipdao_crawlers.sources.myhome import normalize

    n = normalize({"suplyTyNm": "매입임대", "rentGtn": 0, "mtRntchrg": "0"})
    assert n["depositKRW"] is None
    assert n["monthlyRentKRW"] is None


def test_iso_rejects_malformed():
    from zipdao_crawlers.sources.myhome import _iso

    assert _iso("20260618") == "2026-06-18"
    assert _iso("") is None
    assert _iso(None) is None
    assert _iso("미정") is None
    assert _iso("2026-06-18") is None


def test_lh_pan_id_parses_query_param_only():
    from zipdao_crawlers.sources.myhome import _lh_pan_id

    assert _lh_pan_id("https://apply.lh.or.kr/...?panId=2015122300020009&x=1") == "2015122300020009"
    assert _lh_pan_id("https://x/?a=1&panId=123") == "123"
    # must not match a substring like oldpanId / xpanId
    assert _lh_pan_id("https://x/?oldpanId=999") is None
    assert _lh_pan_id("") is None
    assert _lh_pan_id(None) is None
