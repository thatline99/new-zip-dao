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


# 실측한 공공지원민간임대(getPblPvtRentLttotPblancDetail) 행 형태(축약)
PBL_PVT_ROW = {
    "HOUSE_MANAGE_NO": "2026850038",
    "PBLANC_NO": "2026850038",
    "HOUSE_NM": "부경경마공원역 대방 디에트르 더리버(AP1BL)",
    "HOUSE_SECD_NM": "공공지원민간임대",
    "HOUSE_DETAIL_SECD_NM": "공공지원민간임대",
    "RCRIT_PBLANC_DE": "20260707",
    "SUBSCRPT_RCEPT_BGNDE": "20260713",
    "SUBSCRPT_RCEPT_ENDDE": "20260714",
    "PRZWNER_PRESNATN_DE": "20260716",
    "TOT_SUPLY_HSHLDCO": 84,
    "SUBSCRPT_AREA_CODE_NM": "부산",
    "PBLANC_URL": "https://www.applyhome.co.kr/ai/aia/selectPRMOLttotPblancDetailView.do?houseManageNo=2026850038",
}


def test_normalize_public_private_rent_row():
    from zipdao_crawlers.sources.applyhome import normalize_raw as normalize_applyhome

    n = normalize_applyhome(PBL_PVT_ROW)
    assert n["supplyType"] == "공공지원민간임대"
    assert n["applyStart"] == "2026-07-13"
    assert n["applyEnd"] == "2026-07-14"
    assert n["winnerAnnounceDate"] == "2026-07-16"
    assert n["supplyHouseholds"] == 84


def test_normalize_apt_row_still_works():
    from zipdao_crawlers.sources.applyhome import normalize_raw as normalize_applyhome

    n = normalize_applyhome(
        {"RENT_SECD_NM": "분양주택", "RCEPT_BGNDE": "2026-08-11", "RCEPT_ENDDE": "2026-08-13"}
    )
    assert n["supplyType"] == "분양주택"
    assert n["applyStart"] == "2026-08-11"


def test_operations_include_rental():
    from zipdao_crawlers.sources.applyhome import OPERATIONS

    assert any("getPblPvtRentLttotPblancDetail" in ep for ep, _ in OPERATIONS)
    assert any("getAPTLttotPblancDetail" in ep for ep, _ in OPERATIONS)


# 실측한 주택형별 상세(Mdl) 행 형태(축약) — 민간임대는 EXCLUSE_AR, APT 는 HOUSE_TY 만 온다
MDL_ROWS = [
    {"HOUSE_MANAGE_NO": "2026850038", "MODEL_NO": "01", "EXCLUSE_AR": "59.8947", "TP": "59A-1"},
    {"HOUSE_MANAGE_NO": "2026850038", "MODEL_NO": "02", "EXCLUSE_AR": "84.9120", "TP": "84B-1"},
]


def test_normalize_fills_area_from_model_rows():
    from zipdao_crawlers.sources.applyhome import normalize_raw

    n = normalize_raw({**PBL_PVT_ROW, "주택형목록": MDL_ROWS})
    assert n["areaM2"] == 59.89  # 최솟값("~부터")


def test_normalize_area_from_apt_house_ty_prefix():
    from zipdao_crawlers.sources.applyhome import normalize_raw

    n = normalize_raw(
        {
            "RENT_SECD_NM": "공공임대",
            "주택형목록": [{"HOUSE_TY": "055.9200A"}, {"HOUSE_TY": "084.9700B"}],
        }
    )
    assert n["areaM2"] == 55.92


def test_fetch_detail_attaches_model_rows():
    from zipdao_core.models import NoticeStub
    from zipdao_crawlers.sources.applyhome import _SVC

    class FakeResp:
        @staticmethod
        def json():
            return {"currentCount": 2, "matchCount": 2, "data": MDL_ROWS}

    class FakeHttp:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None):
            self.calls.append((url, params))
            return FakeResp()

    crawler = ApplyhomeCrawler.__new__(ApplyhomeCrawler)
    crawler.http = FakeHttp()
    crawler._key = "test-key"
    stub = NoticeStub(
        notice_id="2026850038",
        title="부경경마공원역 대방 디에트르 더리버(AP1BL)",
        detail_url="https://www.applyhome.co.kr/...",
        posted_date="2026-07-07",
        extra={**PBL_PVT_ROW, "_endpoint": f"{_SVC}/getPblPvtRentLttotPblancDetail"},
    )
    notice = crawler.fetch_detail(stub)
    assert notice.raw["주택형목록"] == MDL_ROWS
    assert notice.raw["normalized"]["areaM2"] == 59.89
    url, params = crawler.http.calls[0]
    assert url.endswith("getPblPvtRentLttotPblancMdl")
    assert params["cond[HOUSE_MANAGE_NO::EQ]"] == "2026850038"


def test_fetch_detail_survives_model_api_failure():
    from zipdao_core.models import NoticeStub
    from zipdao_crawlers.sources.applyhome import _SVC

    class BrokenHttp:
        def get(self, url, params=None):
            raise RuntimeError("boom")

    crawler = ApplyhomeCrawler.__new__(ApplyhomeCrawler)
    crawler.http = BrokenHttp()
    crawler._key = "test-key"
    stub = NoticeStub(
        notice_id="2026850038",
        title="t",
        detail_url="u",
        extra={**PBL_PVT_ROW, "_endpoint": f"{_SVC}/getPblPvtRentLttotPblancDetail"},
    )
    notice = crawler.fetch_detail(stub)
    assert "주택형목록" not in notice.raw
    assert notice.raw["normalized"]["areaM2"] is None
