"""청약홈(한국부동산원) odcloud 공공데이터 API 크롤러 소스."""

from __future__ import annotations

from collections.abc import Iterator

from zipdao_core.dates import to_iso_date
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import DataGoKrCrawler
from zipdao_crawlers.normalize import normalize_applyhome

_SVC = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
# (오퍼레이션 URL, 이름) — APT 는 분양 위주지만 분양전환 가능임대가 섞여 있고,
# 공공지원민간임대는 전부 임대라 새집다오의 주 수집 대상이다.
OPERATIONS: list[tuple[str, str]] = [
    (f"{_SVC}/getAPTLttotPblancDetail", "APT 분양/임대"),
    (f"{_SVC}/getPblPvtRentLttotPblancDetail", "공공지원민간임대"),
]
PER_PAGE = 100


class ApplyhomeCrawler(DataGoKrCrawler):
    """청약홈 odcloud API 로 공고를 수집하는 크롤러."""

    key = "applyhome"
    name = "청약홈(공공데이터 API)"
    base_url = "https://www.applyhome.co.kr"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """오퍼레이션별로 odcloud API 를 페이지 순회하며 공고 요약을 만든다."""
        for endpoint, _name in OPERATIONS:
            yield from self._iter_operation(endpoint, since, until)

    def _iter_operation(
        self, endpoint: str, since: int | None, until: int | None
    ) -> Iterator[NoticeStub]:
        page = 1
        while True:
            rows, total = self._fetch_page(endpoint, page)
            if not rows:
                break
            stop = False
            for r in rows:
                posted = to_iso_date(r.get("RCRIT_PBLANC_DE"))
                year = int(posted[:4]) if posted and posted[:4].isdigit() else None
                if year is not None:
                    if until is not None and year > until:
                        continue
                    if since is not None and year < since:
                        stop = True
                        continue
                pan_no = str(r.get("PBLANC_NO") or r.get("HOUSE_MANAGE_NO") or "").strip()
                if not pan_no:
                    continue
                category = " ".join(
                    x for x in (r.get("HOUSE_SECD_NM"), r.get("RENT_SECD_NM")) if x
                )
                yield NoticeStub(
                    notice_id=pan_no,
                    title=(r.get("HOUSE_NM") or "").strip(),
                    detail_url=(r.get("PBLANC_URL") or "").strip(),
                    posted_date=posted,
                    category=category or None,
                    region=r.get("SUBSCRPT_AREA_CODE_NM"),
                    extra=dict(r),
                )
            if stop or page * PER_PAGE >= total:
                break
            page += 1

    def _fetch_page(self, endpoint: str, page: int) -> tuple[list[dict], int]:
        resp = self.http.get(
            endpoint,
            params={"serviceKey": self._key, "page": page, "perPage": PER_PAGE},
        )
        return self.parse_page(resp.json())

    @staticmethod
    def parse_page(data) -> tuple[list[dict], int]:
        """odcloud 응답에서 (행 목록, 전체건수)를 추출한다."""
        if not isinstance(data, dict):
            return [], 0
        rows = data.get("data") or []
        total = int(data.get("totalCount") or 0)
        return rows, total

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """공고 raw 데이터를 정규화해 Notice 를 만든다."""
        raw = dict(stub.extra)
        raw["normalized"] = normalize_applyhome(raw)
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
