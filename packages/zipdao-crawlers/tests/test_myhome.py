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
        "przwnerPresnatnDe": "20261001",
        "sumSuplyCo": 170,
    }
    n = normalize(item)
    assert n["supplyType"] == "국민임대"
    assert n["depositKRW"] == 66960000
    assert n["monthlyRentKRW"] == 267000
    assert n["applyStart"] == "2026-06-18"
    assert n["applyEnd"] == "2026-07-02"
    assert n["areaM2"] is None
    assert n["winnerAnnounceDate"] == "2026-10-01"
    assert n["supplyHouseholds"] == 170


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
    assert (
        _match_units({"pnu": "1168010100106530006", "hsmpNm": ""}, complexes)[0]["suplyPrvuseAr"]
        == 17.8
    )
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


def test_iter_notices_dedupes_preferring_unit_matched(monkeypatch):
    from zipdao_crawlers.sources import myhome as mod

    # 한 공고가 단지별 여러 행으로 옴 — 두 번째 행(B시)에서만 단지(pnu) 매칭 성공
    row_a = {
        "pblancId": "P1",
        "pblancNm": "광역 공고",
        "rcritPblancDe": "20260701",
        "pnu": "PNU-A",
        "brtcNm": "경기도",
        "signguNm": "A시",
    }
    row_b = {**row_a, "pnu": "PNU1", "signguNm": "B시"}
    monkeypatch.setattr(
        mod, "REGIONS", [("41", "100", "경기도", "A시"), ("41", "200", "경기도", "B시")]
    )
    crawler = mod.MyhomeCrawler.__new__(mod.MyhomeCrawler)
    crawler._fetch_all = lambda ep, rows, extra=None: [row_a, row_b]
    complexes = {"100": [], "200": [{"pnu": "PNU1", "suplyPrvuseAr": 21.5}]}
    crawler._fetch_complexes = lambda brtc, signgu: complexes[signgu]

    stubs = list(crawler.iter_notices(2026, None))
    assert len(stubs) == 1  # 중복 제거
    assert stubs[0].extra["units"] == [{"pnu": "PNU1", "suplyPrvuseAr": 21.5}]  # 매칭본 보존


def test_iter_notices_falls_back_to_region_loop_when_nationwide_empty(monkeypatch):
    from zipdao_crawlers.sources import myhome as mod

    monkeypatch.setattr(mod, "REGIONS", [("41", "100", "경기도", "A시")])
    crawler = mod.MyhomeCrawler.__new__(mod.MyhomeCrawler)
    row = {
        "pblancId": "P9",
        "pblancNm": "폴백 공고",
        "rcritPblancDe": "20260701",
        "brtcNm": "경기도",
        "signguNm": "A시",
    }
    calls: list[dict | None] = []

    def fake_fetch_all(ep, rows, extra=None):
        calls.append(extra)
        return [] if extra is None else [row]

    crawler._fetch_all = fake_fetch_all
    crawler._fetch_complexes = lambda brtc, signgu: []

    stubs = list(crawler.iter_notices(None, None))
    assert calls[0] is None  # 전국 조회 먼저
    assert {"brtcCode": "41", "signguCode": "100"} in calls  # 그다음 지역 순회
    assert len(stubs) == 1 and stubs[0].notice_id == "P9"


def test_region_codes_prefers_pnu_prefix():
    from zipdao_crawlers.sources.myhome import _region_codes

    by_name = {("경기도", "A시"): ("41", "100")}
    # pnu 앞 5자리 = 시군구 코드 — 광역 공고는 signguNm 이 비어 있어도 해석 가능
    assert _region_codes(
        {"pnu": "5214011700113760001", "brtcNm": "전북특별자치도", "signguNm": ""}, by_name
    ) == ("52", "140")
    # pnu 없으면 지역명 매핑
    assert _region_codes({"brtcNm": "경기도", "signguNm": "A시"}, by_name) == ("41", "100")
    # 둘 다 안 되면 None
    assert _region_codes({"brtcNm": "새도시", "signguNm": "X구"}, by_name) is None


def test_iter_notices_falls_back_when_nationwide_raises(monkeypatch):
    from zipdao_crawlers.sources import myhome as mod

    monkeypatch.setattr(mod, "REGIONS", [("41", "100", "경기도", "A시")])
    crawler = mod.MyhomeCrawler.__new__(mod.MyhomeCrawler)
    row = {
        "pblancId": "P8",
        "pblancNm": "예외 폴백 공고",
        "rcritPblancDe": "20260701",
        "brtcNm": "경기도",
        "signguNm": "A시",
    }

    def fake_fetch_all(ep, rows, extra=None):
        if extra is None:
            raise RuntimeError("오류 응답(JSON 아님) 등")
        return [row]

    crawler._fetch_all = fake_fetch_all
    crawler._fetch_complexes = lambda brtc, signgu: []

    stubs = list(crawler.iter_notices(None, None))
    assert len(stubs) == 1 and stubs[0].notice_id == "P8"


def test_iter_notices_unknown_region_skips_complex_lookup(monkeypatch):
    from zipdao_crawlers.sources import myhome as mod

    monkeypatch.setattr(mod, "REGIONS", [("41", "100", "경기도", "A시")])
    crawler = mod.MyhomeCrawler.__new__(mod.MyhomeCrawler)
    row = {
        "pblancId": "P2",
        "pblancNm": "미등록 지역 공고",
        "rcritPblancDe": "20260701",
        "brtcNm": "새도시",
        "signguNm": "X구",
    }
    crawler._fetch_all = lambda ep, rows, extra=None: [row] if extra is None else []
    called: list[tuple] = []
    crawler._fetch_complexes = lambda *a: called.append(a) or []

    stubs = list(crawler.iter_notices(None, None))
    assert stubs[0].extra["units"] == []
    assert called == []  # 코드 매핑 없는 지역은 단지 조회 생략


def test_normalize_zero_won_is_missing():
    from zipdao_crawlers.sources.myhome import normalize

    n = normalize({"suplyTyNm": "매입임대", "rentGtn": 0, "mtRntchrg": "0"})
    assert n["depositKRW"] is None
    assert n["monthlyRentKRW"] is None


def test_lh_pan_id_parses_query_param_only():
    from zipdao_crawlers.sources.myhome import _lh_pan_id

    assert _lh_pan_id("https://apply.lh.or.kr/...?panId=2015122300020009&x=1") == "2015122300020009"
    assert _lh_pan_id("https://x/?a=1&panId=123") == "123"
    # must not match a substring like oldpanId / xpanId
    assert _lh_pan_id("https://x/?oldpanId=999") is None
    assert _lh_pan_id("") is None
    assert _lh_pan_id(None) is None
