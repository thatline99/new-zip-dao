from __future__ import annotations

from zipdao_core.models import AssetKind
from zipdao_crawlers.sources.udc import UdcCrawler, normalize_raw

# 실측한 list.do 목록을 축약한 픽스처
LIST_HTML = """
<table>
<tbody>
  <tr>
    <td class="re_blind7">146</td>
    <td class="ta_l">
      <a href="./view.do?mId=001001004000000000&amp;bbsId=BBS_0000000000000004&amp;dataId=4439" onclick="fn_view('4439');return false;">
        유홈 성안 예비입주자 모집 공고</a>
    </td>
    <td class="re_blind7">1,348</td>
    <td class="re_blind7"><img src="icon_pdf.png" alt="공고.pdf" /></td>
    <td>2026-07-10</td>
  </tr>
</tbody>
</table>
<ul class="pagination">
  <li><a href="#none" onclick="goPage(2);">2</a></li>
  <li><a href="#none" onclick="goPage(15);" title="마지막 페이지">마지막으로</a></li>
</ul>
"""


def test_parse_list_extracts_rows_and_last_page():
    rows, last_page = UdcCrawler.parse_list(LIST_HTML)
    assert last_page == 15
    assert len(rows) == 1
    row = rows[0]
    assert row["dataId"] == "4439"
    assert row["title"] == "유홈 성안 예비입주자 모집 공고"
    assert row["posted"] == "2026-07-10"


def test_parse_list_empty_when_no_rows():
    rows, last_page = UdcCrawler.parse_list("<table><tbody></tbody></table>")
    assert rows == []
    assert last_page == 0


# 실측한 view.do 첨부 영역을 축약한 픽스처
DETAIL_HTML = """
<tr><th scope="row">첨부파일</th><td><ul>
  <li>
    <a href="#fileDownload" onclick="HHBbs.DownFile('/umca', 'BBS_0000000000000004','FILE_000000000005961','0');">
      <img src="icon_pdf.png" alt="2026년 진장디플렉스 임대 공급공고 안내(게시용).pdf" />
      2026년 진장디플렉스 임대 공급공고 안내(게시용).pdf&nbsp;(227.9KByte)</a>
  </li>
  <li>
    <a href="#fileDownload" onclick="HHBbs.DownFile('/umca', 'BBS_0000000000000004','FILE_000000000005961','1');">
      2026년 진장디플렉스 공급가격(게시용).pdf (217.2KByte)</a>
  </li>
</ul></td></tr>
"""


def test_parse_attachments_builds_filedown_urls():
    atts = UdcCrawler.parse_attachments(DETAIL_HTML)
    assert len(atts) == 2
    assert atts[0].url == (
        "https://www.umca.co.kr/umca/bbs/FileDown.do"
        "?bbsId=BBS_0000000000000004&atchFileId=FILE_000000000005961&fileSn=0"
    )
    # img alt 우선, 없으면 앵커 텍스트에서 용량 표기를 제거
    assert atts[0].filename == "2026년 진장디플렉스 임대 공급공고 안내(게시용).pdf"
    assert atts[1].filename == "2026년 진장디플렉스 공급가격(게시용).pdf"
    assert AssetKind.from_filename(atts[0].filename) is AssetKind.PDF


def test_parse_attachments_empty_when_no_files():
    assert UdcCrawler.parse_attachments("<div>첨부 없음</div>") == []


def test_normalize_raw_supply_type_from_title():
    assert normalize_raw({"title": "율동 위드유 행복주택 입주자 모집"})["supplyType"] == "행복주택"
    assert normalize_raw({"title": "유홈 성안 예비입주자 모집 공고"})["supplyType"] is None
