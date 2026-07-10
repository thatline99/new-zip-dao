from __future__ import annotations

from zipdao_crawlers.sources.lh_apply import LhApplyCrawler

# 실측한 lhLeaseNoticeInfo1 응답 형태(축약)
SAMPLE = [
    {"dsSch": [{"PAN_ED_DT": "20261231", "PAN_ST_DT": "20210101", "PAGE": "1"}]},
    {
        "dsList": [
            {
                "PAN_ID": "2015122300020199",
                "PAN_NM": "(세종) 통합공공임대 모집공고",
                "UPP_AIS_TP_NM": "임대주택",
                "CNP_CD_NM": "세종특별자치시",
                "PAN_SS": "공고중",
                "PAN_NT_ST_DT": "2026.06.19",
                "CLSG_DT": "2026.07.09",
                "DTL_URL": "https://apply.lh.or.kr/...selectWrtancInfo.do?panId=...",
                "ALL_CNT": "236",
            }
        ],
        "resHeader": [{"RS_DTTM": "20260624023109", "SS_CODE": "Y"}],
    },
]


def test_parse_list_extracts_rows_and_total():
    rows, all_cnt = LhApplyCrawler.parse_list(SAMPLE)
    assert all_cnt == 236
    assert len(rows) == 1
    assert rows[0]["PAN_ID"] == "2015122300020199"
    assert rows[0]["DTL_URL"].startswith("https://apply.lh.or.kr")


def test_parse_list_empty_dslist():
    data = [{"dsSch": []}, {"dsList": [], "resHeader": [{"SS_CODE": "Y"}]}]
    rows, all_cnt = LhApplyCrawler.parse_list(data)
    assert rows == []
    assert all_cnt == 0


def test_parse_list_malformed_is_safe():
    assert LhApplyCrawler.parse_list([]) == ([], 0)
    assert LhApplyCrawler.parse_list([{"unexpected": 1}]) == ([], 0)


def test_normalize_uses_specific_supply_type():
    from zipdao_crawlers.sources.lh_apply import normalize

    n = normalize(
        {"AIS_TP_CD_NM": "국민임대", "UPP_AIS_TP_NM": "임대주택", "CLSG_DT": "2026.07.09"}
    )
    assert n["supplyType"] == "국민임대"
    assert n["applyEnd"] == "2026-07-09"
    assert n["depositKRW"] is None


# 실측한 상세(dsSplScdl)·공급(dsList01) 응답 행 형태(축약)
SCHEDULES = [
    {
        "SBD_LGO_NM": "대구복현 행복주택",
        "SBSC_ACP_ST_DT": "2026.07.07",
        "SBSC_ACP_CLSG_DT": "2026.07.09",
        "PZWR_ANC_DT": "2026.08.20",
    },
    {
        "SBD_LGO_NM": "대구읍내 행복주택",
        "SBSC_ACP_ST_DT": "2026.07.08",
        "SBSC_ACP_CLSG_DT": "2026.07.10",
        "PZWR_ANC_DT": "2026.08.21",
    },
]
UNITS = [
    {
        "SBD_LGO_NM": "대구복현 행복주택",
        "HTY_NNA": "16A",
        "DDO_AR": "16.74",
        "LS_GMY": "공고문 참조",
        "RFE": "공고문 참조",
        "NOW_HSH_CNT": "10",
    },
    {
        "SBD_LGO_NM": "대구복현 행복주택",
        "HTY_NNA": "26A",
        "DDO_AR": "26.85",
        "LS_GMY": "공고문 참조",
        "RFE": "공고문 참조",
        "NOW_HSH_CNT": "5",
    },
]


def test_normalize_detail_fills_dates_and_area():
    from zipdao_crawlers.sources.lh_apply import normalize

    n = normalize({"AIS_TP_CD_NM": "행복주택", "CLSG_DT": "2026.07.09"}, SCHEDULES, UNITS)
    assert n["applyStart"] == "2026-07-07"  # 단지 중 최소 시작일
    assert n["applyEnd"] == "2026-07-10"  # 단지 중 최대 마감일(CLSG_DT 대신)
    assert n["areaM2"] == 16.74  # 주택형 중 최소 전용면적
    assert n["depositKRW"] is None  # "공고문 참조"는 숫자가 아니므로 결측
    assert n["monthlyRentKRW"] is None
    assert n["winnerAnnounceDate"] == "2026-08-20"  # 단지 중 최소 발표일
    assert n["supplyHouseholds"] == 15  # 금회공급 세대수 합


def test_normalize_detail_numeric_price_is_used():
    from zipdao_crawlers.sources.lh_apply import normalize

    units = [{"DDO_AR": "59.9", "LS_GMY": "12,000,000", "RFE": "150000"}]
    n = normalize({"CLSG_DT": "2026.07.09"}, [], units)
    assert n["depositKRW"] == 12000000
    assert n["monthlyRentKRW"] == 150000
    assert n["applyEnd"] == "2026-07-09"  # 일정 없으면 공고 마감으로 폴백


def test_block_extracts_named_rows():
    from zipdao_crawlers.sources.lh_apply import _block

    payload = [{"dsSch": [{"PAGE": "1"}]}, {"dsSplScdl": SCHEDULES}]
    assert _block(payload, "dsSplScdl") == SCHEDULES
    assert _block(payload, "dsList01") == []
    assert _block("oops", "dsSplScdl") == []


def test_normalize_for_uses_stored_lh_blocks():
    from zipdao_crawlers.normalize import normalize_for

    raw = {
        "AIS_TP_CD_NM": "행복주택",
        "CLSG_DT": "2026.07.09",
        "일정목록": SCHEDULES,
        "공급목록": UNITS,
    }
    n = normalize_for("lh_apply", raw)
    assert n["applyStart"] == "2026-07-07"
    assert n["areaM2"] == 16.74
