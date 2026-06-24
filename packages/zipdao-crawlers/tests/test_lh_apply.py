"""LH API 응답 파서 단위 테스트 (네트워크 불필요)."""

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
