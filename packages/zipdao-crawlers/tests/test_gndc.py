from __future__ import annotations

from zipdao_core.models import AssetKind
from zipdao_crawlers.sources.gndc import GndcCrawler, normalize_raw

# 실측한 getBbsArticleList.do 응답 행을 축약한 픽스처
ROW = {
    "IPDS_IDX": "9e5333be-24ef-4345-bbcd-3667e8371eef",
    "CPDS_SUBJECT": "청년매입임대주택(창원) 예비 입주자모집 공고",
    "COLM1_VAL": "분양",
    "COLM3_VAL": "기타",
    "RGST_DTM": "2026-06-24 10:03",
    "CPDS_WDATE": "2026-06-24 10:03",
    "MUST_LVL": 1,
    "ATTACH_CNT": 2,
    "orgFileNameStr": "[붙임1_ 청년매입임대주택 예비입주자 모집공고.hwp|[붙임2_ 신청서류 양식 _1).pdf",
    "sysFileNameStr": (
        "/privatefiles/board/B491A490314446318099F9D828047900/e2608a90.hwp"
        "|/privatefiles/board/B491A490314446318099F9D828047900/8601d178.pdf"
    ),
}


def test_stub_from_row_maps_fields():
    stub = GndcCrawler.stub_from_row(ROW, seq_id="0000006190", colm1="notice_01", category="분양")
    assert stub is not None
    assert stub.notice_id == "9e5333be-24ef-4345-bbcd-3667e8371eef"
    assert stub.title == "청년매입임대주택(창원) 예비 입주자모집 공고"
    assert stub.posted_date == "2026-06-24"
    assert stub.category == "분양"
    assert stub.region == "경남"  # COLM3_VAL "기타" 는 시군 아님
    assert "IPDS_IDX=9e5333be-24ef-4345-bbcd-3667e8371eef" in stub.detail_url
    assert "COLM1=notice_01" in stub.detail_url


def test_stub_from_row_appends_district_region():
    row = {**ROW, "COLM3_VAL": "창원"}
    stub = GndcCrawler.stub_from_row(row, seq_id="0000006202", colm1="notice_06", category="임대")
    assert stub is not None
    assert stub.region == "경남 창원"


def test_stub_from_row_none_without_idx():
    assert GndcCrawler.stub_from_row({}, seq_id="1", colm1="c", category="임대") is None


def test_parse_attachments_pairs_paths_with_names():
    atts = GndcCrawler.parse_attachments(ROW)
    assert len(atts) == 2
    assert atts[0].url.startswith("https://www.gndc.co.kr/common/download.do?fileVirtualPath=")
    assert "%2Fprivatefiles%2Fboard%2F" in atts[0].url
    assert atts[0].filename == "[붙임1_ 청년매입임대주택 예비입주자 모집공고.hwp"
    assert AssetKind.from_filename(atts[0].filename) is AssetKind.HWP
    assert AssetKind.from_filename(atts[1].filename) is AssetKind.PDF


def test_parse_attachments_empty_when_no_files():
    assert GndcCrawler.parse_attachments({"sysFileNameStr": "", "orgFileNameStr": ""}) == []
    assert GndcCrawler.parse_attachments({}) == []


def test_normalize_raw_supply_type_from_subject():
    assert normalize_raw(ROW)["supplyType"] == "매입임대"
    assert (
        normalize_raw({"CPDS_SUBJECT": "진주강남 청년머뭄센터 통합공공임대주택 입주자모집"})[
            "supplyType"
        ]
        == "통합공공임대"
    )
    assert normalize_raw({"CPDS_SUBJECT": "무연분묘 개장공고"})["supplyType"] is None
