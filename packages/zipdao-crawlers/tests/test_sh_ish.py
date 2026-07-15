from __future__ import annotations

from zipdao_core.models import AssetKind, NoticeStub
from zipdao_crawlers.sources.sh_ish import ShIshCrawler, normalize_raw

# 실측한 list.do 목록(전체 게시판)을 축약한 픽스처
LIST_HTML = """
<form name="mainform" id="mainform" action="./list.do" method="post">
<table>
<tbody>
  <tr>
    <td>5513</td>
    <td class="txtL">
      <a href="#" class="ellipsis icon" onclick="javascript:getDetailView('306886');return false;">
        <span class="icoNew">NEW</span>
        [당첨자발표] 2026년 상반기 신혼·신생아 매입임대주택Ⅰ 입주대기자 모집공고
      </a>
    </td>
    <td>매입주택공급부</td>
    <td class="num">2026-07-15</td>
    <td class="num">1198</td>
  </tr>
  <tr>
    <td>5512</td>
    <td class="txtL">
      <a href="#" class="ellipsis icon" onclick="javascript:getDetailView('307073');return false;">
        2026년 1차 청년 매입임대주택 입주자 모집공고(2026.6.26.)
      </a>
    </td>
    <td>매입주택공급부</td>
    <td class="num">2026-07-15</td>
    <td class="num">2959</td>
  </tr>
</tbody>
</table>
</form>
<div class="inner"><a href="#none" onclick="getPaging(1,null);return false" class="btnFirst">첫페이지</a>
<a href="#none" onclick="getPaging(2,null);return false">2</a>
<a href="#none" onclick="getPaging(552,null);return false" class="btnLast">마지막페이지</a></div>
"""


def test_parse_list_extracts_rows_and_last_page():
    rows, last_page = ShIshCrawler.parse_list(LIST_HTML)
    assert last_page == 552
    assert len(rows) == 2
    first = rows[0]
    assert first["seq"] == "306886"
    assert first["title"].startswith("[당첨자발표] 2026년 상반기 신혼·신생아")
    assert "NEW" not in first["title"]
    assert first["posted"] == "2026-07-15"
    assert first["dept"] == "매입주택공급부"


def test_parse_list_ignores_view_count_as_date():
    # 조회수(1198)·번호(5513) 같은 숫자 셀이 날짜로 오인되지 않아야 한다
    rows, _ = ShIshCrawler.parse_list(LIST_HTML)
    assert all(r["posted"] == "2026-07-15" for r in rows)


def test_parse_list_empty_when_no_rows():
    rows, last_page = ShIshCrawler.parse_list("<table><tbody></tbody></table>")
    assert rows == []
    assert last_page == 0


# 실측한 view.do 상세의 이노릭스 첨부 초기화 스크립트를 축약한 픽스처
DETAIL_HTML = """
<script>
initParam.downList = [{"brdId":"GS0401","seq":"307073","fileSeq":"1","fileSize":"189502","oriFileNm":"인터넷 청약신청 경쟁률 (최종).pdf","fileTp":"A"}];
initInnorix();
</script>
"""


def test_parse_attachments_builds_innofd_urls():
    atts = ShIshCrawler.parse_attachments(DETAIL_HTML)
    assert len(atts) == 1
    att = atts[0]
    assert att.url == (
        "https://www.i-sh.co.kr/app/com/file/innoFD.do?brdId=GS0401&seq=307073&fileTp=A&fileSeq=1"
    )
    assert att.filename == "인터넷 청약신청 경쟁률 (최종).pdf"
    assert AssetKind.from_filename(att.filename) is AssetKind.PDF


def test_parse_attachments_empty_when_no_downlist():
    assert ShIshCrawler.parse_attachments("<div>첨부 없음</div>") == []
    assert ShIshCrawler.parse_attachments("initParam.downList = [];") == []


def test_normalize_raw_supply_type_from_title():
    assert (
        normalize_raw({"title": "2026년 1차 청년 매입임대주택 입주자 모집공고"})["supplyType"]
        == "매입임대"
    )
    assert normalize_raw({"title": "행복주택 예비당첨자 게시"})["supplyType"] == "행복주택"
    assert (
        normalize_raw({"title": "2026-2차 충신동 두레주택 잔여세대 입주자모집공고"})["supplyType"]
        == "두레주택"
    )
    assert normalize_raw({"title": "일반 공지사항"})["supplyType"] is None
    assert normalize_raw({})["supplyType"] is None


def test_fetch_detail_posts_to_board_view_and_collects_attachments():
    calls: list[tuple[str, dict]] = []

    class FakeResp:
        text = DETAIL_HTML

    class FakeHttp:
        def post(self, url, **kwargs):
            calls.append((url, kwargs.get("data") or {}))
            return FakeResp()

    crawler = ShIshCrawler.__new__(ShIshCrawler)
    crawler.http = FakeHttp()
    stub = NoticeStub(
        notice_id="307073",
        title="2026년 1차 청년 매입임대주택 입주자 모집공고(2026.6.26.)",
        detail_url="https://www.i-sh.co.kr/app/lay2/program/S1T294C297/www/brd/m_247/view.do?seq=307073",
        posted_date="2026-07-15",
        category="주택임대",
        region="서울",
        extra={
            "multiItmSeq": "2",
            "boardPath": "/app/lay2/program/S1T294C297/www/brd/m_247",
            "dept": "매입주택공급부",
        },
    )
    notice = crawler.fetch_detail(stub)

    url, data = calls[0]
    assert url == "https://www.i-sh.co.kr/app/lay2/program/S1T294C297/www/brd/m_247/view.do"
    assert data["seq"] == "307073"
    assert data["multi_itm_seq"] == "2"

    assert len(notice.attachments) == 1
    assert notice.raw["normalized"]["supplyType"] == "매입임대"
    assert notice.raw["_detail_html"] == DETAIL_HTML
    assert notice.region == "서울"
