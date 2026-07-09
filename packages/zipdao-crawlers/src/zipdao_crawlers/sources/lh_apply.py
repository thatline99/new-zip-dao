"""LH청약플러스 공공데이터포털 분양임대공고문 API 크롤러 소스."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from zipdao_core.dates import to_iso_date
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import DataGoKrCrawler
from zipdao_crawlers.fields import _area, _won

logger = logging.getLogger(__name__)

LIST_EP = "http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
DTL_EP = "http://apis.data.go.kr/B552555/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1"
SPL_EP = "http://apis.data.go.kr/B552555/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1"
PG_SZ = 100

HOUSING_TYPES: list[tuple[str, str]] = [
    ("05", "분양주택"),
    ("06", "임대주택"),
    ("13", "주거복지"),
    ("39", "신혼희망타운"),
]

# 상세/공급 API 는 목록 행의 코드 필드를 그대로 요구한다
_DETAIL_PARAM_KEYS = ("CCR_CNNT_SYS_DS_CD", "SPL_INF_TP_CD", "UPP_AIS_TP_CD", "AIS_TP_CD")


def _block(payload, key: str) -> list[dict]:
    """LH 응답([{...}, {"ds...": [...]}]) 에서 key 블록의 행 목록을 꺼낸다."""
    if not isinstance(payload, list):
        return []
    for part in payload:
        if isinstance(part, dict) and key in part:
            return part.get(key) or []
    return []


def normalize(
    item: dict, schedules: list[dict] | None = None, units: list[dict] | None = None
) -> dict:
    """LH 공고 item(+단지 일정/공급 정보)을 정규화 블록으로 변환한다.

    - 접수기간: 단지별 청약 일정의 최소 시작일~최대 마감일, 없으면 공고 마감(CLSG_DT)
    - 면적: 주택형별 전용면적(DDO_AR)의 최솟값
    - 금액: LH 는 대부분 "공고문 참조" 텍스트라 숫자일 때만 채운다
    """
    schedules = schedules or []
    units = units or []
    starts = [d for d in (to_iso_date(s.get("SBSC_ACP_ST_DT")) for s in schedules) if d]
    closes = [d for d in (to_iso_date(s.get("SBSC_ACP_CLSG_DT")) for s in schedules) if d]
    areas = [a for a in (_area(u.get("DDO_AR")) for u in units) if a]
    deposits = [d for d in (_won(u.get("LS_GMY")) for u in units) if d]
    rents = [r for r in (_won(u.get("RFE")) for u in units) if r]
    return {
        "supplyType": item.get("AIS_TP_CD_NM") or item.get("UPP_AIS_TP_NM") or None,
        "depositKRW": min(deposits) if deposits else None,
        "monthlyRentKRW": min(rents) if rents else None,
        "areaM2": min(areas) if areas else None,
        "applyStart": min(starts) if starts else None,
        "applyEnd": (max(closes) if closes else None) or to_iso_date(item.get("CLSG_DT")),
        "summary": None,
        "eligibility": None,
    }


def normalize_raw(raw: dict) -> dict:
    """저장된 raw(공고행 + 일정·공급 블록)를 정규화 블록으로 변환한다."""
    return normalize(raw, raw.get("일정목록"), raw.get("공급목록"))


class LhApplyCrawler(DataGoKrCrawler):
    """LH청약플러스 공공데이터 API 로 공고를 수집하는 크롤러."""

    key = "lh_apply"
    name = "LH청약플러스(공공데이터 API)"
    base_url = "https://apply.lh.or.kr"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """주택유형별로 공고 요약을 순회한다."""
        start = f"{since or 2000}.01.01"
        close = f"{until or 2099}.12.31"
        for code, type_name in HOUSING_TYPES:
            yield from self._iter_type(code, type_name, start, close)

    def _iter_type(self, code: str, type_name: str, start: str, close: str) -> Iterator[NoticeStub]:
        page = 1
        while True:
            rows, all_cnt = self._fetch_page(code, start, close, page)
            if not rows:
                break
            for r in rows:
                pan_id = str(r.get("PAN_ID") or "").strip()
                if not pan_id:
                    continue
                yield NoticeStub(
                    notice_id=pan_id,
                    title=(r.get("PAN_NM") or "").strip(),
                    detail_url=(r.get("DTL_URL") or "").strip(),
                    posted_date=to_iso_date(r.get("PAN_NT_ST_DT") or r.get("PAN_DT")),
                    category=r.get("UPP_AIS_TP_NM") or type_name,
                    region=r.get("CNP_CD_NM"),
                    extra=dict(r),
                )
            if page * PG_SZ >= int(all_cnt or 0):
                break
            page += 1

    def _fetch_page(self, code: str, start: str, close: str, page: int) -> tuple[list[dict], int]:
        resp = self.http.get(
            LIST_EP,
            params={
                "serviceKey": self._key,
                "PG_SZ": PG_SZ,
                "PAGE": page,
                "UPP_AIS_TP_CD": code,
                "PAN_NT_ST_DT": start,
                "CLSG_DT": close,
            },
        )
        return self.parse_list(resp.json())

    @staticmethod
    def parse_list(data: object) -> tuple[list[dict], int]:
        """LH 응답에서 (행 목록, 전체건수)를 추출한다."""
        block = next((x for x in data if isinstance(x, dict) and "dsList" in x), None)
        rows = block.get("dsList", []) if block else []
        all_cnt = int(rows[0].get("ALL_CNT") or 0) if rows else 0
        return rows, all_cnt

    def _fetch_notice_detail(self, row: dict) -> tuple[list[dict], list[dict]]:
        """공고별 청약 일정(상세)·주택형 공급정보를 가져온다. 실패해도 크롤은 계속."""
        params = {"serviceKey": self._key, "PG_SZ": 100, "PAGE": 1, "PAN_ID": row.get("PAN_ID")}
        for k in _DETAIL_PARAM_KEYS:
            if row.get(k):
                params[k] = row[k]
        try:
            schedules = _block(self.http.get(DTL_EP, params=params).json(), "dsSplScdl")
            payload = self.http.get(SPL_EP, params=params).json()
            units = (
                _block(payload, "dsList01")
                or _block(payload, "dsList02")
                or _block(payload, "dsList")
            )
        except Exception:
            logger.warning("LH 상세/공급정보 조회 실패: PAN_ID=%s", row.get("PAN_ID"))
            return [], []
        return schedules, units

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """공고 raw 데이터(+단지 일정/공급정보)를 정규화해 Notice 를 만든다."""
        raw = dict(stub.extra)
        schedules, units = self._fetch_notice_detail(raw)
        if schedules:
            raw["일정목록"] = schedules
        if units:
            raw["공급목록"] = units
        raw["normalized"] = normalize(raw, schedules, units)
        return Notice.from_stub(stub, source=self.key, raw=raw)
