from __future__ import annotations

import json
from pathlib import Path

from zipdao_core.models import Notice

from zipdao_api.schema import (
    Attachment,
    NoticeDetail,
    NoticeList,
    NoticeSummary,
    RecommendRequest,
)


def _normalized(notice: Notice) -> dict:
    block = notice.raw.get("normalized")
    return block if isinstance(block, dict) else {}


def _price(v: object) -> int | None:
    return v if isinstance(v, int) and v > 0 else None


def _is_sale(supply_type: str | None) -> bool:
    s = supply_type or ""
    return "분양" in s and "임대" not in s


def to_detail(notice: Notice) -> NoticeDetail:
    n = _normalized(notice)
    return NoticeDetail(
        source=notice.source,
        noticeId=notice.notice_id,
        title=notice.title,
        region=notice.region,
        category=notice.category,
        supplyType=n.get("supplyType") or notice.category,
        postedDate=notice.posted_date,
        applyStart=n.get("applyStart"),
        applyEnd=n.get("applyEnd"),
        depositKRW=_price(n.get("depositKRW")),
        monthlyRentKRW=_price(n.get("monthlyRentKRW")),
        areaM2=n.get("areaM2"),
        detailUrl=notice.detail_url,
        attachments=[
            Attachment(url=a.url, filename=a.filename, kind=a.kind.value) for a in notice.attachments
        ],
        summary=n.get("summary"),
        eligibility=n.get("eligibility"),
        crawledAt=notice.crawled_at,
    )


def to_summary(detail: NoticeDetail) -> NoticeSummary:
    return NoticeSummary.model_validate(detail.model_dump())


def _expand_since(s: str | None) -> str | None:
    if not s:
        return None
    return f"{s}-01-01" if len(s) == 4 else s


def _expand_until(s: str | None) -> str | None:
    if not s:
        return None
    return f"{s}-12-31" if len(s) == 4 else s


_PROV_VARIANTS: list[tuple[str, tuple[str, ...]]] = [
    ("강원", ("강원특별자치도", "강원도")),
    ("전북", ("전북특별자치도", "전라북도")),
    ("전남", ("전라남도",)),
    ("경북", ("경상북도",)),
    ("경남", ("경상남도",)),
    ("충북", ("충청북도",)),
    ("충남", ("충청남도",)),
    ("제주", ("제주특별자치도", "제주도")),
    ("세종", ("세종특별자치시", "세종시")),
    ("서울", ("서울특별시",)),
    ("부산", ("부산광역시",)),
    ("인천", ("인천광역시",)),
    ("대구", ("대구광역시",)),
    ("대전", ("대전광역시",)),
    ("광주", ("광주광역시",)),
    ("울산", ("울산광역시",)),
    ("경기", ("경기도",)),
]


def _canon_region(s: str) -> str:
    for short, variants in _PROV_VARIANTS:
        for v in variants:
            s = s.replace(v, short)
    return s


class NoticeStore:
    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = Path(raw_dir)
        self._items: list[NoticeDetail] = []
        self.reload()

    def reload(self) -> None:
        items: list[NoticeDetail] = []
        if self.raw_dir.exists():
            for manifest in sorted(self.raw_dir.glob("*/*/*/manifest.json")):
                try:
                    detail = to_detail(Notice.from_dict(json.loads(manifest.read_text(encoding="utf-8"))))
                except Exception:
                    continue
                if _is_sale(detail.supplyType):
                    continue
                items.append(detail)
        self._items = items

    def get(self, source: str, notice_id: str) -> NoticeDetail | None:
        for d in self._items:
            if d.source == source and d.noticeId == notice_id:
                return d
        return None

    def search(
        self,
        *,
        q: str | None,
        region: str | None,
        supply_type: str | None,
        source: str | None,
        since: str | None,
        until: str | None,
        limit: int,
    ) -> NoticeList:
        lo = _expand_since(since)
        hi = _expand_until(until)
        needle = q.lower() if q else None
        matches: list[NoticeSummary] = []
        for d in self._items:
            if source and d.source != source:
                continue
            if region and _canon_region(region) not in _canon_region(d.region or ""):
                continue
            if supply_type and supply_type not in (d.supplyType or ""):
                continue
            if lo and d.postedDate and d.postedDate < lo:
                continue
            if hi and d.postedDate and d.postedDate > hi:
                continue
            if needle:
                hay = " ".join(
                    [d.title, d.region or "", d.category or "", d.supplyType or "", d.summary or ""]
                ).lower()
                if needle not in hay:
                    continue
            matches.append(to_summary(d))
        return NoticeList(total=len(matches), items=matches[:limit])

    def recommend(self, req: RecommendRequest) -> NoticeList:
        scored: list[tuple[int, NoticeDetail]] = []
        for d in self._items:
            score = self._score(d, req)
            if score < 0:
                continue
            scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        items = [to_summary(d) for _, d in scored[: req.limit]]
        return NoticeList(total=len(scored), items=items)

    @staticmethod
    def _score(d: NoticeDetail, req: RecommendRequest) -> int:
        score = 0
        if req.region and _canon_region(req.region) not in _canon_region(d.region or ""):
            return -1
        budget_set = req.maxDepositKRW is not None or req.maxMonthlyRentKRW is not None
        if budget_set and not (d.depositKRW or d.monthlyRentKRW):
            return -1
        if req.maxDepositKRW is not None:
            if d.depositKRW is None or d.depositKRW > req.maxDepositKRW:
                return -1
            score += 2
        if req.maxMonthlyRentKRW is not None:
            if d.monthlyRentKRW is None or d.monthlyRentKRW > req.maxMonthlyRentKRW:
                return -1
            score += 2
        if req.supplyType and req.supplyType in (d.supplyType or ""):
            score += 2
        if req.age is not None and req.age <= 39 and any(
            k in (d.supplyType or "") for k in ("청년", "행복")
        ):
            score += 1
        return score

    def top_for_question(self, question: str, n: int) -> list[NoticeDetail]:
        tokens = {t for t in question.lower().split() if t}
        ranked: list[tuple[int, NoticeDetail]] = []
        for d in self._items:
            hay = " ".join(
                [d.title, d.region or "", d.category or "", d.supplyType or "", d.summary or ""]
            ).lower()
            score = sum(1 for t in tokens if t in hay)
            ranked.append((score, d))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [d for score, d in ranked if score > 0][:n]
