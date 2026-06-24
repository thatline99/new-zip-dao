"""마이홈 API 응답 파서 + 지역코드 테스트 (네트워크 불필요)."""

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
