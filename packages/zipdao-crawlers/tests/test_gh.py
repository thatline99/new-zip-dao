from __future__ import annotations

from zipdao_crawlers.sources.gh import GhCrawler, normalize_raw, notice_id_of

# 실측한 odcloud 응답 행(2025판)을 축약한 픽스처
ROW = {
    "구분": 1,
    "공고번호": 9,
    "공고명": "수원영통 경기도형 행복주택 입주자 모집",
    "게시일자": "2017-11-30",
    "공고일자": "2017-11-30",
    "접수시작일자": "2017-12-06",
    "접수종료일자": "2017-12-15",
    "당첨자발표일자": "2018-03-30",
    "입주예정년월": "2025-12",
    "주택관리번호": 2017001669,
}


def test_notice_id_prefers_house_manage_no():
    assert notice_id_of(ROW) == "2017001669"


def test_notice_id_falls_back_to_no_and_date():
    # 2023판처럼 주택관리번호가 비어 있는 행
    assert notice_id_of({"공고번호": 14, "게시일자": "2018-08-30"}) == "14-2018-08-30"
    assert notice_id_of({"공고번호": 14}) == "14"
    assert notice_id_of({}) is None


def test_stub_from_row_maps_fields():
    stub = GhCrawler.stub_from_row(ROW, snapshot="2025-08-21")
    assert stub is not None
    assert stub.notice_id == "2017001669"
    assert stub.title == "수원영통 경기도형 행복주택 입주자 모집"
    assert stub.posted_date == "2017-11-30"
    assert stub.region == "경기"
    assert stub.extra["_snapshot"] == "2025-08-21"


def test_stub_from_row_none_without_title_or_id():
    assert GhCrawler.stub_from_row({"공고명": "제목만"}, snapshot="s") is None
    assert GhCrawler.stub_from_row({"공고번호": 1}, snapshot="s") is None


def test_normalize_raw_maps_schedule_and_supply_type():
    n = normalize_raw(ROW)
    assert n["supplyType"] == "행복주택"
    assert n["applyStart"] == "2017-12-06"
    assert n["applyEnd"] == "2017-12-15"
    assert n["winnerAnnounceDate"] == "2018-03-30"


def test_fetch_detail_builds_notice_without_http():
    crawler = GhCrawler.__new__(GhCrawler)
    stub = GhCrawler.stub_from_row(ROW, snapshot="2025-08-21")
    assert stub is not None
    notice = crawler.fetch_detail(stub)
    assert notice.source == "gh"
    assert notice.raw["snapshot"] == "2025-08-21"
    assert notice.raw["normalized"]["supplyType"] == "행복주택"
    assert notice.attachments == []
