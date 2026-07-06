"""LH청약플러스 공공데이터포털 분양임대공고문 API 크롤러 소스."""

from __future__ import annotations

from collections.abc import Iterator

from zipdao_core.config import load_settings
from zipdao_core.dates import to_iso_date
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler

LIST_EP = "http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
PG_SZ = 100

HOUSING_TYPES: list[tuple[str, str]] = [
    ("05", "분양주택"),
    ("06", "임대주택"),
    ("13", "주거복지"),
    ("39", "신혼희망타운"),
]


def normalize(item: dict) -> dict:
    """LH 공고 item 을 정규화 블록으로 변환한다."""
    return {
        "supplyType": item.get("AIS_TP_CD_NM") or item.get("UPP_AIS_TP_NM") or None,
        "depositKRW": None,
        "monthlyRentKRW": None,
        "areaM2": None,
        "applyStart": None,
        "applyEnd": to_iso_date(item.get("CLSG_DT")),
        "summary": None,
        "eligibility": None,
    }


class LhApplyCrawler(BaseCrawler):
    """LH청약플러스 공공데이터 API 로 공고를 수집하는 크롤러."""

    key = "lh_apply"
    name = "LH청약플러스(공공데이터 API)"
    base_url = "https://apply.lh.or.kr"

    def __init__(self, http) -> None:
        super().__init__(http)
        self._key = load_settings().data_go_kr_service_key
        if not self._key:
            raise RuntimeError(
                "DATA_GO_KR_SERVICE_KEY 미설정(.env). 공공데이터포털 인증키가 필요합니다."
            )

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """주택유형별로 공고 요약을 순회한다."""
        start = f"{since or 2000}.01.01"
        close = f"{until or 2099}.12.31"
        for code, type_name in HOUSING_TYPES:
            yield from self._iter_type(code, type_name, start, close)

    def _iter_type(
        self, code: str, type_name: str, start: str, close: str
    ) -> Iterator[NoticeStub]:
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

    def _fetch_page(
        self, code: str, start: str, close: str, page: int
    ) -> tuple[list[dict], int]:
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
    def parse_list(data) -> tuple[list[dict], int]:
        """LH 응답에서 (행 목록, 전체건수)를 추출한다."""
        block = next((x for x in data if isinstance(x, dict) and "dsList" in x), None)
        rows = block.get("dsList", []) if block else []
        all_cnt = int(rows[0].get("ALL_CNT") or 0) if rows else 0
        return rows, all_cnt

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """공고 raw 데이터를 정규화해 Notice 를 만든다."""
        raw = dict(stub.extra)
        raw["normalized"] = normalize(raw)
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=stub.posted_date,
            category=stub.category,
            region=stub.region,
            attachments=[],
            raw=raw,
        )
