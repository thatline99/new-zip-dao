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
