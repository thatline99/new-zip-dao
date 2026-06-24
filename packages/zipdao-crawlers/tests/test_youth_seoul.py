"""youth_seoul 첨부 파서 단위 테스트 (네트워크 불필요)."""

from __future__ import annotations

from zipdao_core.models import AssetKind
from zipdao_crawlers.sources.youth_seoul import YouthSeoulCrawler

# 실측한 view.do 상세의 첨부 영역을 축약한 픽스처
DETAIL_HTML = """
<ul class="view_data">
  <li>
    <span class="title">첨부파일</span>
    <span class="file">
      <a href="/coHouse/cmmn/file/fileDown.do?atchFileId=abc123&fileSn=1">민간_260618_연신내역_루미노816_청년안심주택 추가모집공고문.pdf</a>
      <a href="javascript:void(0);" onclick="previewAjax('/coHouse/cmmn/file/fileDown.do?atchFileId=abc123&fileSn=1','x.pdf')" title="바로보기">바로보기</a>
      <a href="/coHouse/cmmn/file/fileDown.do?atchFileId=abc123&fileSn=2">신청서양식.hwp</a>
    </span>
  </li>
</ul>
"""


def test_parse_attachments_extracts_real_files_and_dedupes():
    atts = YouthSeoulCrawler.parse_attachments(DETAIL_HTML)
    # 직접 fileDown.do 링크 2개만 추출. 프리뷰 링크는 href=javascript:void(0)+onclick 이라
    # a[href*="fileDown.do"] 셀렉터에 안 걸린다(실제 페이지 형태와 동일).
    assert len(atts) == 2
    urls = {a.url for a in atts}
    assert "https://soco.seoul.go.kr/coHouse/cmmn/file/fileDown.do?atchFileId=abc123&fileSn=1" in urls
    assert any(a.filename.endswith(".pdf") for a in atts)
    assert any(a.filename.endswith(".hwp") for a in atts)


def test_parse_attachments_infers_kind_from_filename():
    atts = YouthSeoulCrawler.parse_attachments(DETAIL_HTML)
    kinds = {AssetKind.from_filename(a.filename) for a in atts}
    assert AssetKind.PDF in kinds
    assert AssetKind.HWP in kinds


def test_parse_attachments_empty_when_no_files():
    assert YouthSeoulCrawler.parse_attachments("<div>첨부 없음</div>") == []
