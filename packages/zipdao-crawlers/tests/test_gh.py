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


# 실측한 청약센터(apply.gh.or.kr) 목록을 축약한 픽스처 — 시군 셀 뒤 </td> 누락도 실제 그대로
APPLY_LIST_HTML = """
<table><tbody>
  <tr>
    <td>1</td>
    <td>국민임대</td>
    <td>
      <a href="#a" class="text_cut" data-previewYn="N" data-pbancNo="801"
         data-pbancKndCd="01" data-bizTyNm="국민임대">
        다산센트럴파크6단지 국민임대주택 예비입주자 모집공고
      </a>
    </td>
    <td>남양주시
    <td><img src="/images/sub/hwp.png" alt="hwp파일"></td>
    <td>2026-07-10</td>
    <td>2026-07-22
    <td>공고중
    <td>일반공고</td>
    <td>24287</td>
  </tr>
</tbody></table>
<a href="#" onclick="fn_sel_page(2)">2</a>
<a href="#" onclick="fn_sel_page(25)">끝</a>
"""


def test_parse_apply_list_extracts_rows_and_pages():
    rows, last_page = GhCrawler.parse_apply_list(APPLY_LIST_HTML)
    assert last_page == 25
    assert len(rows) == 1
    row = rows[0]
    assert row["pbancNo"] == "801"
    assert row["pbancKndCd"] == "01"
    assert row["bizTyNm"] == "국민임대"
    assert row["title"].startswith("다산센트럴파크6단지")
    assert row["district"] == "남양주시"
    assert row["posted"] == "2026-07-10"
    assert row["deadline"] == "2026-07-22"
    assert row["state"] == "공고중"


def test_parse_apply_list_empty():
    rows, last_page = GhCrawler.parse_apply_list("<table><tbody></tbody></table>")
    assert rows == []
    assert last_page == 0


APPLY_DETAIL_HTML = """
<div>
  <a href="/sr/sr7150/selectFileDown.do?pbancNo=801&amp;atchFileSn=1604944&amp;atchFileDtlSn=12&amp;mode=1">
    다산센트럴파크6단지 국민임대주택 예비입주자 모집공고.hwp</a>
  <a href="/sr/sr7150/selectFileDown.do?pbancNo=801&amp;atchFileSn=1604944&amp;atchFileDtlSn=13&amp;mode=1">
    다산센트럴파크6단지 국민임대주택 예비입주자 모집공고.pdf</a>
</div>
"""


def test_parse_apply_attachments_builds_direct_urls():
    atts = GhCrawler.parse_apply_attachments(APPLY_DETAIL_HTML)
    assert len(atts) == 2
    assert atts[0].url.startswith("https://apply.gh.or.kr/sr/sr7150/selectFileDown.do?pbancNo=801")
    assert atts[0].filename.endswith(".hwp")
    assert atts[1].filename.endswith(".pdf")


def test_normalize_raw_apply_channel():
    n = normalize_raw(
        {"channel": "apply", "bizTyNm": "국민임대", "deadline": "2026-07-22", "title": "무관"}
    )
    assert n["supplyType"] == "국민임대"
    assert n["applyEnd"] == "2026-07-22"
    # bizTyNm 없으면 제목 키워드 폴백
    n2 = normalize_raw({"channel": "apply", "title": "행복주택 입주자 모집", "bizTyNm": ""})
    assert n2["supplyType"] == "행복주택"
