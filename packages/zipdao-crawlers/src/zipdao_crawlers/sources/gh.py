"""경기주택도시공사(GH) 크롤러 — 청약센터(최신) + 공공데이터 스냅샷(이력) 2채널.

본사(www.gh.or.kr)는 robots `Disallow: /` 전면 차단이지만, 별도 호스트인
청약센터(apply.gh.or.kr)는 `Allow: /*` 로 전면 허용이라 최신 공고를 직접 수집한다.
- 목록: POST /sb/sr/{게시판}/selectPbancRentHouseList.do (pageIndex) — 서버렌더 행에
  유형·공고명·시군·게시일·마감일·상태·pbancNo(data 속성) 포함, 게시일 내림차순.
- 상세: POST /sb/sr/{게시판}/selectPbancDetailView.do (pbancNo, pbancKndCd)
- 첨부: 상세의 selectFileDown.do 직링크(HWP/PDF).

과거 이력은 공공데이터포털 'GH주택청약 모집정보'(15119414) odcloud API 스냅샷
(연 1회 8월 갱신)으로 수집한다. 두 채널은 공유 키가 없어, 청약센터는 마지막
스냅샷 게시일(SNAPSHOT_END) 이후 공고만 수집해 중복을 피한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from zipdao_core.dates import to_iso_date, year_out_of_range
from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import DataGoKrCrawler
from zipdao_crawlers.fields import normalized_block, supply_type_from_title

APPLY_BASE = "https://apply.gh.or.kr"
# (게시판 경로 조각, 라벨) — 청약센터 임대 계열 탭
APPLY_BOARDS: list[tuple[str, str]] = [("sr7150", "임대주택"), ("sr7155", "매입임대")]
# 마지막 스냅샷의 게시일 상한 — 청약센터 채널은 이후 공고만 수집(채널 간 중복 방지).
# 매년 8월 새 스냅샷을 SNAPSHOTS 에 추가할 때 이 값도 함께 올린다.
SNAPSHOT_END = "2025-08-21"

_SVC = "https://api.odcloud.kr/api/15119414/v1"
# (스냅샷 UDDI, 판 라벨) — 최신판 먼저. 매년 8월 새 판이 등록되면 여기에 추가한다.
SNAPSHOTS: list[tuple[str, str]] = [
    (f"{_SVC}/uddi:d22eef31-f232-464a-9547-dbff71668860", "2025-08-21"),
    (f"{_SVC}/uddi:e8952a8f-35a9-4f5e-9128-babaf5fec1f4", "2024-08-21"),
    (f"{_SVC}/uddi:7e9fa983-2038-4557-bb89-c3d8ce35593c", "2023-08-21"),
]
PER_PAGE = 100

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def notice_id_of(row: dict) -> str | None:
    """스냅샷 행의 안정 식별자. 주택관리번호(연도+일련) 우선, 없으면 공고번호+게시일자."""
    manage_no = str(row.get("주택관리번호") or "").strip()
    if manage_no:
        return manage_no
    no = str(row.get("공고번호") or "").strip()
    posted = to_iso_date(row.get("게시일자") or row.get("공고일자")) or ""
    if not no:
        return None
    return f"{no}-{posted}" if posted else no


def normalize_raw(raw: dict) -> dict:
    """GH raw 를 정규화 블록으로 변환한다(청약센터/스냅샷 두 형태 대응)."""
    if raw.get("channel") == "apply":
        return normalized_block(
            supplyType=raw.get("bizTyNm") or supply_type_from_title(raw.get("title")),
            applyEnd=to_iso_date(raw.get("deadline")),
        )
    return normalized_block(
        supplyType=supply_type_from_title(raw.get("공고명")),
        applyStart=to_iso_date(raw.get("접수시작일자")),
        applyEnd=to_iso_date(raw.get("접수종료일자")),
        winnerAnnounceDate=to_iso_date(raw.get("당첨자발표일자")),
    )


class GhCrawler(DataGoKrCrawler):
    """GH 청약센터(최신)와 odcloud 스냅샷(이력)을 수집하는 크롤러."""

    key = "gh"
    name = "경기주택도시공사(청약센터+공공데이터)"
    base_url = "https://www.gh.or.kr"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """청약센터(최신) → 스냅샷(이력) 순으로 공고 요약을 순회한다."""
        for board, label in APPLY_BOARDS:
            yield from self._iter_apply_board(board, label, since, until)
        for endpoint, snapshot in SNAPSHOTS:
            yield from self._iter_snapshot(endpoint, snapshot, since, until)

    # ── 청약센터(apply.gh.or.kr) 채널 ──────────────────────────────

    def _iter_apply_board(
        self, board: str, label: str, since: int | None, until: int | None
    ) -> Iterator[NoticeStub]:
        page = 1
        while True:
            resp = self.http.post(
                f"{APPLY_BASE}/sb/sr/{board}/selectPbancRentHouseList.do",
                data={"pageIndex": page},
            )
            rows, last_page = self.parse_apply_list(resp.text)
            if not rows:
                break

            stop = False
            for row in rows:
                # 스냅샷이 커버하는 기간은 제외(채널 간 중복 방지). 목록이 최신순이라
                # 상한 이하가 나오면 이후 페이지도 전부 스냅샷 영역이다.
                if row["posted"] and row["posted"] <= SNAPSHOT_END:
                    stop = True
                    continue
                out = year_out_of_range(row["posted"], since, until)
                if out:
                    stop = stop or out == "older"
                    continue
                detail = (
                    f"{APPLY_BASE}/sb/sr/{board}/selectPbancDetailView.do"
                    f"?pbancNo={row['pbancNo']}&pbancKndCd={row['pbancKndCd']}"
                )
                yield NoticeStub(
                    notice_id=f"pbanc-{row['pbancNo']}",
                    title=row["title"],
                    detail_url=detail,
                    posted_date=row["posted"],
                    category=row["bizTyNm"] or label,
                    region=f"경기 {row['district']}" if row["district"] else "경기",
                    extra={
                        "_channel": "apply",
                        "board": board,
                        "pbancNo": row["pbancNo"],
                        "pbancKndCd": row["pbancKndCd"],
                        "bizTyNm": row["bizTyNm"],
                        "deadline": row["deadline"],
                        "state": row["state"],
                    },
                )
            if stop or page >= last_page:
                break
            page += 1

    @staticmethod
    def parse_apply_list(html: str) -> tuple[list[dict], int]:
        """청약센터 목록 HTML 에서 (행 목록, 마지막 페이지 번호)를 추출한다."""
        soup = BeautifulSoup(html, "lxml")
        rows: list[dict] = []
        for tr in soup.select("tbody tr"):
            a = tr.select_one("a[data-pbancno]")
            if a is None:
                continue
            texts = [td.get_text(strip=True) for td in tr.select("td")]
            dates = [t for t in texts if _ISO_DATE_RE.fullmatch(t)]
            title = " ".join(a.get_text(" ", strip=True).split())
            # 열 순서: 번호·유형·공고명·시군·첨부·게시일·마감일·상태·… (시군은 제목 다음 칸)
            district = ""
            tds = tr.select("td")
            for i, td in enumerate(tds):
                if td.find("a") is a and i + 1 < len(tds):
                    district = tds[i + 1].get_text(strip=True)
                    break
            state = next(
                (t for t in texts if t in ("공고중", "접수중", "접수마감", "발표완료", "마감")),
                "",
            )
            rows.append(
                {
                    "pbancNo": a.get("data-pbancno") or "",
                    "pbancKndCd": a.get("data-pbanckndcd") or "01",
                    "bizTyNm": a.get("data-biztynm") or "",
                    "title": title,
                    "district": district,
                    "posted": dates[0] if dates else None,
                    "deadline": dates[1] if len(dates) > 1 else None,
                    "state": state,
                }
            )
        pages = [int(n) for n in re.findall(r"fn_sel_page\((\d+)\)", html)]
        return rows, max(pages, default=0)

    @staticmethod
    def parse_apply_attachments(html: str) -> list[Attachment]:
        """청약센터 상세 HTML 의 selectFileDown.do 직링크에서 첨부 목록을 만든다."""
        soup = BeautifulSoup(html, "lxml")
        attachments: list[Attachment] = []
        seen: set[str] = set()
        for a in soup.select("a[href*='selectFileDown.do']"):
            url = urljoin(APPLY_BASE, a.get("href") or "")
            if url in seen:
                continue
            seen.add(url)
            attachments.append(Attachment(url=url, filename=a.get_text(" ", strip=True)))
        return attachments

    def _fetch_apply_detail(self, stub: NoticeStub) -> Notice:
        board = stub.extra.get("board") or APPLY_BOARDS[0][0]
        resp = self.http.post(
            f"{APPLY_BASE}/sb/sr/{board}/selectPbancDetailView.do",
            data={
                "pbancNo": stub.extra.get("pbancNo"),
                "pbancKndCd": stub.extra.get("pbancKndCd") or "01",
                "pageIndex": 1,
            },
        )
        attachments = self.parse_apply_attachments(resp.text)
        raw = {
            "channel": "apply",
            "pbancNo": stub.extra.get("pbancNo"),
            "bizTyNm": stub.extra.get("bizTyNm"),
            "title": stub.title,
            "deadline": stub.extra.get("deadline"),
            "state": stub.extra.get("state"),
            "postedDate": stub.posted_date,
            "_detail_html": resp.text,
        }
        raw["normalized"] = normalize_raw(raw)
        return Notice.from_stub(stub, source=self.key, attachments=attachments, raw=raw)

    # ── 공공데이터 스냅샷 채널 ─────────────────────────────────────

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
        """스냅샷 API 행을 NoticeStub 으로 변환한다. 식별자가 없으면 None."""
        nid = notice_id_of(row)
        if nid is None:
            return None
        title = str(row.get("공고명") or "").strip()
        if not title:
            return None
        return NoticeStub(
            notice_id=nid,
            title=title,
            # 스냅샷엔 상세 페이지가 없어 데이터셋 페이지를 원천으로 링크한다.
            detail_url="https://www.data.go.kr/data/15119414/fileData.do",
            posted_date=to_iso_date(row.get("게시일자") or row.get("공고일자")),
            category="GH주택청약",
            region="경기",
            extra={**row, "_snapshot": snapshot},
        )

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """채널에 맞게 상세를 만든다(청약센터는 상세 POST, 스냅샷은 행 그대로)."""
        if stub.extra.get("_channel") == "apply":
            return self._fetch_apply_detail(stub)
        raw = {k: v for k, v in stub.extra.items() if not k.startswith("_")}
        raw["snapshot"] = stub.extra.get("_snapshot")
        raw["normalized"] = normalize_raw(raw)
        return Notice.from_stub(stub, source=self.key, raw=raw)
