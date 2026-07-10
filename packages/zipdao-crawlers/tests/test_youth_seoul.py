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
    assert (
        "https://soco.seoul.go.kr/coHouse/cmmn/file/fileDown.do?atchFileId=abc123&fileSn=1" in urls
    )
    assert any(a.filename.endswith(".pdf") for a in atts)
    assert any(a.filename.endswith(".hwp") for a in atts)


def test_parse_attachments_infers_kind_from_filename():
    atts = YouthSeoulCrawler.parse_attachments(DETAIL_HTML)
    kinds = {AssetKind.from_filename(a.filename) for a in atts}
    assert AssetKind.PDF in kinds
    assert AssetKind.HWP in kinds


def test_parse_attachments_empty_when_no_files():
    assert YouthSeoulCrawler.parse_attachments("<div>첨부 없음</div>") == []


# 실측한 view.do 카테고리(자치구) 영역 축약 — 해당 자치구 option 만 텍스트가 채워져 온다
GU_HTML = """
<div class="board_view">
  <ul class="view_data">
    <li><span class="title">담당부서/사업자</span>주식회사 씨드원</li>
    <li><span class="title">공고게시일</span>2026-07-09</li>
  </ul>
  <ul class="view_data">
    <li><span class="title">카테고리</span>
      <option value="10">  </option>
      <option value="11"> 동대문구 </option>
      <option value="12">  </option>
    </li>
  </ul>
</div>
"""


def test_parse_gu_extracts_selected_district():
    assert YouthSeoulCrawler.parse_gu(GU_HTML) == "동대문구"


def test_parse_gu_none_when_absent():
    assert YouthSeoulCrawler.parse_gu("<div>본문 없음</div>") is None
    empty = GU_HTML.replace("동대문구", " ")
    assert YouthSeoulCrawler.parse_gu(empty) is None


def test_normalize_raw_maps_gubun_to_supply_type():
    from zipdao_crawlers.sources.youth_seoul import normalize_raw

    assert normalize_raw({"gubun": "2"})["supplyType"] == "민간임대"
    assert normalize_raw({"gubun": "1"})["supplyType"] == "공공임대"
    assert normalize_raw({"gubun": None})["supplyType"] is None
    assert normalize_raw({})["supplyType"] is None


def test_fetch_detail_sets_district_region_and_supply_type():
    from zipdao_core.models import NoticeStub

    class FakeResp:
        text = GU_HTML

    class FakeHttp:
        def get(self, url):
            return FakeResp()

    crawler = YouthSeoulCrawler.__new__(YouthSeoulCrawler)
    crawler.http = FakeHttp()
    stub = NoticeStub(
        notice_id="BMSR00015-6590",
        title="[민간임대] 장한평역 장안동 하트리움 추가모집공고",
        detail_url="https://soco.seoul.go.kr/youth/bbs/BMSR00015/view.do?boardId=6590",
        posted_date="2026-07-09",
        category="임대주택 모집공고",
        region="서울",
        extra={"gubun": "2", "applyDate": "2026-07-10"},
    )
    notice = crawler.fetch_detail(stub)
    assert notice.region == "서울 동대문구"
    assert notice.raw["normalized"]["supplyType"] == "민간임대"
    assert notice.raw["normalized"]["applyEnd"] == "2026-07-10"
