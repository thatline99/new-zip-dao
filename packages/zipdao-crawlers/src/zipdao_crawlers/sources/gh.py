"""경기주택도시공사(GH) 공공데이터 odcloud API 크롤러 소스.

GH 사이트는 robots.txt `Disallow: /` 전면 차단이라, 합법 채널은 공공데이터포털의
'GH주택청약 모집정보' 파일데이터(15119414)를 노출한 odcloud API 뿐이다.
연 1회(8월) 스냅샷 갱신 — 최신 공고는 없고 과거 이력용. 스냅샷 간 중복은
최신판부터 순회해 같은 notice_id 를 엔진이 스킵하는 방식으로 정리한다.
"""

from __future__ import annotations

from collections.abc import Iterator

from zipdao_core.dates import to_iso_date, year_out_of_range
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import DataGoKrCrawler
from zipdao_crawlers.fields import normalized_block, supply_type_from_title

_SVC = "https://api.odcloud.kr/api/15119414/v1"
# (스냅샷 UDDI, 판 라벨) — 최신판 먼저. 매년 8월 새 판이 등록되면 여기에 추가한다.
SNAPSHOTS: list[tuple[str, str]] = [
    (f"{_SVC}/uddi:d22eef31-f232-464a-9547-dbff71668860", "2025-08-21"),
    (f"{_SVC}/uddi:e8952a8f-35a9-4f5e-9128-babaf5fec1f4", "2024-08-21"),
    (f"{_SVC}/uddi:7e9fa983-2038-4557-bb89-c3d8ce35593c", "2023-08-21"),
]
PER_PAGE = 100


def notice_id_of(row: dict) -> str | None:
    """행의 안정 식별자. 주택관리번호(연도+일련) 우선, 없으면 공고번호+게시일자."""
    manage_no = str(row.get("주택관리번호") or "").strip()
    if manage_no:
        return manage_no
    no = str(row.get("공고번호") or "").strip()
    posted = to_iso_date(row.get("게시일자") or row.get("공고일자")) or ""
    if not no:
        return None
    return f"{no}-{posted}" if posted else no


def normalize_raw(raw: dict) -> dict:
    """GH raw 행을 정규화 블록으로 변환한다."""
    return normalized_block(
        supplyType=supply_type_from_title(raw.get("공고명")),
        applyStart=to_iso_date(raw.get("접수시작일자")),
        applyEnd=to_iso_date(raw.get("접수종료일자")),
        winnerAnnounceDate=to_iso_date(raw.get("당첨자발표일자")),
    )


class GhCrawler(DataGoKrCrawler):
    """GH주택청약 모집정보 odcloud API 로 공고 이력을 수집하는 크롤러."""

    key = "gh"
    name = "경기주택도시공사(공공데이터 API)"
    base_url = "https://www.gh.or.kr"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """스냅샷(최신판 먼저)별로 API 를 페이지 순회하며 공고 요약을 만든다."""
        for endpoint, snapshot in SNAPSHOTS:
            yield from self._iter_snapshot(endpoint, snapshot, since, until)

    def _iter_snapshot(
        self, endpoint: str, snapshot: str, since: int | None, until: int | None
    ) -> Iterator[NoticeStub]:
        page = 1
        while True:
            resp = self.http.get(
                endpoint,
                params={"serviceKey": self._key, "page": page, "perPage": PER_PAGE},
            )
            data = resp.json() if isinstance(resp.json(), dict) else {}
            rows = data.get("data") or []
            total = int(data.get("totalCount") or 0)
            if not rows:
                break
            for row in rows:
                stub = self.stub_from_row(row, snapshot=snapshot)
                if stub is None:
                    continue
                if year_out_of_range(stub.posted_date, since, until):
                    continue
                yield stub
            if page * PER_PAGE >= total:
                break
            page += 1

    @staticmethod
    def stub_from_row(row: dict, *, snapshot: str) -> NoticeStub | None:
        """API 행을 NoticeStub 으로 변환한다. 식별자가 없으면 None."""
        nid = notice_id_of(row)
        if nid is None:
            return None
        title = str(row.get("공고명") or "").strip()
        if not title:
            return None
        return NoticeStub(
            notice_id=nid,
            title=title,
            # 공고 상세 페이지는 robots 차단 영역이라 링크하지 않는다(원천: 공공데이터셋).
            detail_url="https://www.data.go.kr/data/15119414/fileData.do",
            posted_date=to_iso_date(row.get("게시일자") or row.get("공고일자")),
            category="GH주택청약",
            region="경기",
            extra={**row, "_snapshot": snapshot},
        )

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """공고 raw 행을 정규화해 Notice 를 만든다(추가 요청 없음)."""
        raw = {k: v for k, v in stub.extra.items() if not k.startswith("_")}
        raw["snapshot"] = stub.extra.get("_snapshot")
        raw["normalized"] = normalize_raw(raw)
        return Notice.from_stub(stub, source=self.key, raw=raw)
