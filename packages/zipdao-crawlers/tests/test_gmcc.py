from __future__ import annotations

from zipdao_core.models import NoticeStub
from zipdao_crawlers.sources.gmcc import GmccCrawler, normalize_raw

# 실측한 board.es 목록을 축약한 픽스처
LIST_HTML = """
<table><tbody>
  <tr>
    <td class="m_hidden" aria-label="번호">243</td>
    <td aria-label="분류">임대공고</td>
    <td class="txt_left" aria-label="제목">
      <a href="/board.es?mid=a10402040000&amp;bid=0018&amp;act=view&amp;list_no=19252&amp;tag=&amp;nPage=1"
         onclick="goView('19252'); return false;"
         title="2026년 정기 광주광역시도시공사 영구임대주택[쌍촌,우산,금호,산정] 예비입주자 대기..">
        <i class="xi-new"></i><span class="sr_only">새글</span>
        2026년 정기 광주광역시도시공사 영구임대주택[쌍촌,우산,금호,산정] 예비입주자 대기..</a>
    </td>
    <td aria-label="첨부파일"><img src="attach.png" alt="11개의 첨부파일" /></td>
    <td aria-label="등록일">2026.06.30</td>
    <td class="m_hidden" aria-label="조회수">2197</td>
  </tr>
</tbody></table>
<a href="/board.es?mid=a10402040000&amp;bid=0018&amp;act=list&amp;nPage=2">2</a>
<a href="/board.es?mid=a10402040000&amp;bid=0018&amp;act=list&amp;nPage=25">끝</a>
"""


def test_parse_list_extracts_rows_and_pages():
    rows, last_page = GmccCrawler.parse_list(LIST_HTML)
    assert last_page == 25
    assert len(rows) == 1
    row = rows[0]
    assert row["listNo"] == "19252"
    assert row["title"].startswith("2026년 정기 광주광역시도시공사 영구임대주택")
    assert "새글" not in row["title"]
    assert row["category"] == "임대공고"
    assert row["posted"] == "2026-06-30"
    assert row["detailUrl"].startswith("https://www.gmcc.co.kr/board.es?")


def test_parse_list_empty():
    rows, last_page = GmccCrawler.parse_list("<table><tbody></tbody></table>")
    assert rows == []
    assert last_page == 0


# 게시판은 분류가 섞여 있다 — 임대공고만 수집되는지 검증하는 픽스처
MIXED_LIST_HTML = """
<table><tbody>
  <tr>
    <td aria-label="분류">채용공고</td>
    <td class="txt_left" aria-label="제목"><a href="/board.es?bid=0018&amp;act=view&amp;list_no=19287">신규직원 채용</a></td>
    <td aria-label="등록일">2026.07.09</td>
  </tr>
  <tr>
    <td aria-label="분류">임대공고</td>
    <td class="txt_left" aria-label="제목"><a href="/board.es?bid=0018&amp;act=view&amp;list_no=19252">영구임대주택 예비입주자 대기</a></td>
    <td aria-label="등록일">2026.06.30</td>
  </tr>
</tbody></table>
"""


def test_iter_notices_keeps_only_rental_category():
    class FakeResp:
        text = MIXED_LIST_HTML

    class FakeHttp:
        def get(self, url, **kwargs):
            if kwargs.get("params", {}).get("nPage", 1) == 1:
                return FakeResp()
            return type("R", (), {"text": "<table><tbody></tbody></table>"})()

    crawler = GmccCrawler.__new__(GmccCrawler)
    crawler.http = FakeHttp()
    stubs = list(crawler.iter_notices(since=None, until=None))
    assert len(stubs) == 1
    assert stubs[0].notice_id == "19252"
    assert stubs[0].category == "임대공고"
    assert isinstance(stubs[0], NoticeStub)


# 실측한 상세: 상단 팝업/메뉴에도 h2.title 이 있고, 실제 제목은 article.board_view 안.
# 파일명 링크 + 같은 URL 의 "다운로드" 버튼 링크가 쌍으로 존재.
DETAIL_HTML = """
<article class="group"><h2 class="title">주요알림</h2></article>
<section id="snb"><h2 class="title">정보마당</h2></section>
<article class="board_view">
  <h2 class="title">2026년 정기 광주광역시도시공사 영구임대주택[쌍촌,우산,금호,산정] 예비입주자 대기순위 발표 공고(2026년 3월 모집분)</h2>
  <ul>
    <li>
      <a href="/boardDownload.es?bid=0018&amp;list_no=19252&amp;seq=1">영구임대 공고문.pdf</a>
      <a href="/boardDownload.es?bid=0018&amp;list_no=19252&amp;seq=1">다운로드</a>
    </li>
    <li>
      <a href="/boardDownload.es?bid=0018&amp;list_no=19252&amp;seq=2">쌍촌 예비입주자 명단.pdf</a>
      <a href="/boardDownload.es?bid=0018&amp;list_no=19252&amp;seq=2">다운로드</a>
    </li>
  </ul>
</article>
"""


def test_parse_detail_full_title_and_deduped_attachments():
    title, atts = GmccCrawler.parse_detail(DETAIL_HTML)
    assert title is not None and title.endswith("(2026년 3월 모집분)")
    assert len(atts) == 2
    assert atts[0].url == "https://www.gmcc.co.kr/boardDownload.es?bid=0018&list_no=19252&seq=1"
    assert atts[0].filename == "영구임대 공고문.pdf"
    assert atts[1].filename == "쌍촌 예비입주자 명단.pdf"


def test_normalize_raw_supply_type_from_title():
    assert normalize_raw({"title": "영구임대주택 예비입주자 모집"})["supplyType"] == "영구임대"
    assert normalize_raw({"title": "행복주택[광주역] 당첨결과"})["supplyType"] == "행복주택"
    assert normalize_raw({"title": "일반 안내"})["supplyType"] is None
