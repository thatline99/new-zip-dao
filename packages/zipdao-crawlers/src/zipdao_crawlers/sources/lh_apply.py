"""LH청약플러스 — 공공데이터포털 분양임대공고문 API 소스.

LH는 robots.txt가 첨부 다운로드 endpoint(/lhapply/lhFile.do)를 Disallow 하므로
웹 크롤링 대신 **공식 채널인 공공데이터 API**로 공고 메타데이터를 수집한다.

서비스: 한국토지주택공사_분양임대공고문 조회 (data.go.kr 15058530)
  엔드포인트: http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1
  필수: ServiceKey, PG_SZ, PAGE, PAN_NT_ST_DT(공고게시일 YYYY.MM.DD), CLSG_DT(공고마감일)
  선택: UPP_AIS_TP_CD(유형), CNP_CD(지역), PAN_NM, PAN_SS
  응답: [{"dsSch":[...]}, {"dsList":[{PAN_ID,PAN_NM,UPP_AIS_TP_NM,CNP_CD_NM,PAN_SS,
        PAN_NT_ST_DT,CLSG_DT,DTL_URL,ALL_CNT,...}], "resHeader":[{SS_CODE}]}]

원본 공고문 PDF/HWP는 robots 제한으로 수집하지 않는다(메타데이터 + DTL_URL 만).
"""

from __future__ import annotations

from collections.abc import Iterator

from zipdao_core.config import load_settings
from zipdao_core.dates import to_iso_date
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler

LIST_EP = "http://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"
PG_SZ = 100

# 주거 관련 상위공고유형 (01 토지·22 상가는 제외)
HOUSING_TYPES: list[tuple[str, str]] = [
    ("05", "분양주택"),
    ("06", "임대주택"),
    ("13", "주거복지"),
    ("39", "신혼희망타운"),
]


class LhApplyCrawler(BaseCrawler):
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
        """LH 응답 [{dsSch}, {dsList, resHeader}] 에서 (행 목록, 전체건수) 추출. 순수 함수."""
        block = next((x for x in data if isinstance(x, dict) and "dsList" in x), None)
        rows = block.get("dsList", []) if block else []
        all_cnt = int(rows[0].get("ALL_CNT") or 0) if rows else 0
        return rows, all_cnt

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        # API 목록이 이미 메타데이터를 제공. 원본 PDF는 robots 제한으로 수집 안 함.
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=stub.posted_date,
            category=stub.category,
            region=stub.region,
            attachments=[],
            raw=dict(stub.extra),
        )
