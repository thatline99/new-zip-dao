from __future__ import annotations

from zipdao_crawlers.sources.applyhome import ApplyhomeCrawler

SAMPLE = {
    "page": 1,
    "perPage": 100,
    "totalCount": 2804,
    "currentCount": 2,
    "data": [
        {
            "PBLANC_NO": "2026000289",
            "HOUSE_NM": "신제주 동문디이스트 시그니처원Ⅱ",
            "HOUSE_SECD_NM": "APT",
            "RENT_SECD_NM": "분양주택",
            "RCRIT_PBLANC_DE": "2026-06-23",
            "SUBSCRPT_AREA_CODE_NM": "제주",
            "PBLANC_URL": "https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetail.do?house=...",
        }
    ],
}


def test_parse_page_extracts_rows_and_total():
    rows, total = ApplyhomeCrawler.parse_page(SAMPLE)
    assert total == 2804
    assert len(rows) == 1
    assert rows[0]["PBLANC_NO"] == "2026000289"


def test_parse_page_handles_missing_and_malformed():
    assert ApplyhomeCrawler.parse_page({"data": [], "totalCount": 0}) == ([], 0)
    assert ApplyhomeCrawler.parse_page({}) == ([], 0)
    assert ApplyhomeCrawler.parse_page("oops") == ([], 0)


# 실측한 공공지원민간임대(getPblPvtRentLttotPblancDetail) 행 형태(축약)
PBL_PVT_ROW = {
    "HOUSE_MANAGE_NO": "2026850038",
    "PBLANC_NO": "2026850038",
    "HOUSE_NM": "부경경마공원역 대방 디에트르 더리버(AP1BL)",
    "HOUSE_SECD_NM": "공공지원민간임대",
    "HOUSE_DETAIL_SECD_NM": "공공지원민간임대",
    "RCRIT_PBLANC_DE": "20260707",
    "SUBSCRPT_RCEPT_BGNDE": "20260713",
    "SUBSCRPT_RCEPT_ENDDE": "20260714",
    "SUBSCRPT_AREA_CODE_NM": "부산",
    "PBLANC_URL": "https://www.applyhome.co.kr/ai/aia/selectPRMOLttotPblancDetailView.do?houseManageNo=2026850038",
}


def test_normalize_public_private_rent_row():
    from zipdao_crawlers.sources.applyhome import normalize_raw as normalize_applyhome

    n = normalize_applyhome(PBL_PVT_ROW)
    assert n["supplyType"] == "공공지원민간임대"
    assert n["applyStart"] == "2026-07-13"
    assert n["applyEnd"] == "2026-07-14"


def test_normalize_apt_row_still_works():
    from zipdao_crawlers.sources.applyhome import normalize_raw as normalize_applyhome

    n = normalize_applyhome(
        {"RENT_SECD_NM": "분양주택", "RCEPT_BGNDE": "2026-08-11", "RCEPT_ENDDE": "2026-08-13"}
    )
    assert n["supplyType"] == "분양주택"
    assert n["applyStart"] == "2026-08-11"


def test_operations_include_rental():
    from zipdao_crawlers.sources.applyhome import OPERATIONS

    assert any("getPblPvtRentLttotPblancDetail" in ep for ep, _ in OPERATIONS)
    assert any("getAPTLttotPblancDetail" in ep for ep, _ in OPERATIONS)
