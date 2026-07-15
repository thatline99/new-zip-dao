"""manifest 를 로드해 검색/추천/QA 를 제공하는 인메모리 공고 저장소."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from zipdao_api.schema import (
    Attachment,
    NoticeDetail,
    NoticeList,
    NoticeSummary,
    RecommendRequest,
)
from zipdao_core.models import Notice

logger = logging.getLogger(__name__)


def _normalized(notice: Notice) -> dict:
    block = notice.raw.get("normalized")
    return block if isinstance(block, dict) else {}


def _price_or_none(v: object) -> int | None:
    return v if isinstance(v, int) and v > 0 else None


def _is_sale(supply_type: str | None) -> bool:
    s = supply_type or ""
    return "분양" in s and "임대" not in s


def _is_non_housing(supply_type: str | None) -> bool:
    return "어린이집" in (supply_type or "")


def _age_eligibility(min_age: int | None, max_age: int | None) -> str | None:
    if min_age is None or max_age is None:
        return None
    return f"{min_age}세 이상 {max_age}세 이하"


def compute_status(apply_start: str | None, apply_end: str | None, today: str) -> str:
    """접수 시작/종료일과 오늘 날짜로 공고 상태를 계산한다."""
    if apply_end and apply_end < today:
        return "마감"
    if apply_start and apply_start > today:
        return "예정"
    if apply_start or apply_end:
        return "접수중"
    return "미정"


def to_detail(notice: Notice, today: str) -> NoticeDetail:
    """Notice 를 API 응답용 NoticeDetail 로 변환한다."""
    n = _normalized(notice)
    apply_start = n.get("applyStart")
    apply_end = n.get("applyEnd")
    return NoticeDetail(
        source=notice.source,
        noticeId=notice.notice_id,
        title=notice.title,
        region=notice.region,
        category=notice.category,
        supplyType=n.get("supplyType") or notice.category,
        postedDate=notice.posted_date,
        applyStart=apply_start,
        applyEnd=apply_end,
        depositKRW=_price_or_none(n.get("depositKRW")),
        monthlyRentKRW=_price_or_none(n.get("monthlyRentKRW")),
        areaM2=n.get("areaM2"),
        detailUrl=notice.detail_url,
        status=compute_status(apply_start, apply_end, today),
        attachments=[
            Attachment(url=a.url, filename=a.filename, kind=a.kind.value)
            for a in notice.attachments
        ],
        summary=n.get("summary"),
        eligibility=n.get("eligibility") or _age_eligibility(n.get("minAge"), n.get("maxAge")),
        minAge=n.get("minAge"),
        maxAge=n.get("maxAge"),
        winnerAnnounceDate=n.get("winnerAnnounceDate"),
        supplyHouseholds=n.get("supplyHouseholds"),
        crawledAt=notice.crawled_at,
    )


def to_summary(detail: NoticeDetail, today: str) -> NoticeSummary:
    """NoticeDetail 을 상태 갱신 후 NoticeSummary 로 축약한다."""
    data = detail.model_dump()
    data["status"] = compute_status(detail.applyStart, detail.applyEnd, today)
    return NoticeSummary.model_validate(data)


_KST = timezone(timedelta(hours=9))


def _parse_date_filter(s: str | None, *, end: bool) -> str | None:
    """YYYY 또는 YYYY-MM-DD(구분자 -./, 비패딩 허용)를 ISO 날짜로 정규화한다. 실패 시 ValueError."""
    if not s:
        return None
    t = re.sub(r"[./]", "-", s.strip()).rstrip("-")
    if re.fullmatch(r"\d{4}", t):
        return f"{t}-12-31" if end else f"{t}-01-01"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            pass
    raise ValueError(f"날짜 형식이 잘못되었습니다: {s} (YYYY 또는 YYYY-MM-DD 로 입력하세요)")


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


# 개칭·통합된 지역의 신·구명을 별도 단어로 함께 담아 어느 이름으로 검색해도 맞게 한다.
_REGION_EXPANSIONS = [
    ("인천 서해구", "인천 서해구 서구"),
    ("인천 서구", "인천 서구 서해구"),
    ("인천 제물포구", "인천 제물포구 중구 동구"),
    ("인천 영종구", "인천 영종구 중구"),
    ("전남광주통합특별시", "전남광주통합특별시 전남 광주"),
]


def _canonicalize_region(s: str) -> str:
    for short, variants in _PROV_VARIANTS:
        for v in variants:
            s = s.replace(v, short)
    for old, expanded in _REGION_EXPANSIONS:
        if old in s and expanded not in s:
            s = s.replace(old, expanded)
    return s


def _region_query_tokens(region: str | None) -> list[str]:
    """지역 질의를 표준화해 토큰 목록으로 만든다."""
    return _canonicalize_region(region).split() if region else []


def _matches_region(tokens: list[str], region: str | None) -> bool:
    """질의 토큰이 모두 지역 단어의 어두와 일치하면 매칭으로 본다.

    어두 일치만 허용해 '서구'가 '강서구'에, '양주'가 '남양주'에 걸리는 오탐을 막는다.
    """
    if not tokens:
        return True
    words = _canonicalize_region(region or "").split()
    return all(any(w.startswith(t) for w in words) for t in tokens)


_SOURCE_TAGS = {
    "youth_seoul": "청년안심주택 청년",
    "lh_apply": "lh",
    "applyhome": "청약홈",
    "myhome": "마이홈",
}


def _haystack(d: NoticeDetail) -> str:
    """검색 대상 텍스트(제목·지역·분류·공급유형·요약·소스 태그)를 하나로 합친다."""
    return " ".join(
        [
            d.title,
            d.region or "",
            d.category or "",
            d.supplyType or "",
            d.summary or "",
            _SOURCE_TAGS.get(d.source, ""),
        ]
    ).lower()


_PARTICLE_SUFFIXES = (
    "에서는",
    "이나",
    "으로",
    "에서",
    "에는",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "도",
    "만",
    "로",
    "과",
    "와",
    "나",
    "요",
)

_EN_STOPWORDS = {
    "a",
    "an",
    "any",
    "are",
    "at",
    "do",
    "does",
    "for",
    "in",
    "is",
    "of",
    "on",
    "the",
    "there",
    "to",
}


def _clean_token(t: str) -> str:
    """질문 어절에서 문장부호와 흔한 조사 접미를 떼어낸다."""
    t = t.strip(".,?!()[]{}\"'“”‘’~·")
    for p in _PARTICLE_SUFFIXES:
        if len(t) > len(p) + 1 and t.endswith(p):
            return t[: -len(p)]
    return t


def _question_tokens(question: str) -> set[str]:
    """질문을 검색 토큰으로 정제한다(2자 미만·영어 불용어 제외)."""
    tokens = (_clean_token(t) for t in question.lower().split())
    return {t for t in tokens if len(t) >= 2 and t not in _EN_STOPWORDS}


_STATUS_RANK = {"접수중": 0, "예정": 1, "미정": 2, "마감": 3}


def _status_rank(summary: NoticeSummary) -> int:
    return _STATUS_RANK.get(summary.status, 9)


def _sort_summaries(items: list[NoticeSummary], sort: str | None) -> list[NoticeSummary]:
    """정렬 옵션에 따라 공고를 정렬한다(기본: 접수중 먼저, 그 안에서 최신순)."""
    if sort == "latest":
        return sorted(items, key=lambda d: d.postedDate or "", reverse=True)
    if sort == "deadline":
        by_end = sorted(items, key=lambda d: d.applyEnd or "9999-99-99")
        return sorted(by_end, key=_status_rank)
    by_posted = sorted(items, key=lambda d: d.postedDate or "", reverse=True)
    return sorted(by_posted, key=_status_rank)


class NoticeStore:
    """raw manifest 를 읽어 검색/추천/QA 를 제공하는 저장소."""

    def __init__(self, raw_dir: Path, today: str | None = None) -> None:
        self.raw_dir = Path(raw_dir)
        self._today_override = today
        self._items: list[NoticeDetail] = []
        self._last_updated: str | None = None
        self.reload()

    def _today(self) -> str:
        return self._today_override or datetime.now(_KST).date().isoformat()

    def reload(self) -> None:
        """raw 디렉터리의 manifest 를 다시 읽어 항목을 갱신한다."""
        loaded, skipped = self._load_manifests()
        items = self._dedup(loaded)
        self._items = items
        self._last_updated = self._compute_last_updated(items)
        logger.info("reload: %d건 로드, %d건 건너뜀", len(items), skipped)

    def _load_manifests(self) -> tuple[list[tuple[NoticeDetail, str | None, str | None]], int]:
        """manifest 를 파싱하고 비임대·공지를 걸러 (항목, supersedes, lhPanId) 목록을 만든다."""
        today = self._today()
        loaded: list[tuple[NoticeDetail, str | None, str | None]] = []
        skipped = 0
        if self.raw_dir.exists():
            for manifest in sorted(self.raw_dir.glob("*/*/*/manifest.json")):
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    detail = to_detail(Notice.from_dict(data), today)
                except Exception:
                    skipped += 1
                    logger.warning("reload: manifest 파싱 실패로 건너뜀: %s", manifest)
                    continue
                if _is_sale(detail.supplyType) or _is_non_housing(detail.supplyType):
                    continue
                if detail.category == "공지/안내":
                    continue
                normalized = data.get("raw", {}).get("normalized", {}) or {}
                loaded.append((detail, normalized.get("supersedes"), normalized.get("lhPanId")))
        return loaded, skipped

    @staticmethod
    def _dedup(loaded: list[tuple[NoticeDetail, str | None, str | None]]) -> list[NoticeDetail]:
        """대체된 마이홈 공고와, 마이홈이 같은 공고를 가리키는 LH 쌍둥이 공고를 제거한다."""
        superseded = {sup for _, sup, _ in loaded if sup}
        lh_twins = {pan for _, _, pan in loaded if pan}
        items: list[NoticeDetail] = []
        for detail, _, _ in loaded:
            if detail.source == "myhome" and detail.noticeId in superseded:
                continue
            if detail.source == "lh_apply" and detail.noticeId in lh_twins:
                continue
            items.append(detail)
        return items

    def _compute_last_updated(self, items: list[NoticeDetail]) -> str | None:
        """데이터 갱신 시각: 크롤 완료 스탬프(last_crawl) 우선, 없으면 최신 crawledAt."""
        stamp = self.raw_dir.parent / "last_crawl"
        try:
            text = stamp.read_text(encoding="utf-8").strip()
            if text:
                return text
        except OSError:
            pass
        stamps = [d.crawledAt for d in items if d.crawledAt]
        return max(stamps) if stamps else None

    def collected_sources(self) -> set[str]:
        """현재 로드된 항목들의 소스 키 집합을 반환한다."""
        return {d.source for d in self._items}

    def get(self, source: str, notice_id: str) -> NoticeDetail | None:
        """source/notice_id 로 공고 상세를 찾는다(상태는 즉시 갱신)."""
        today = self._today()
        for d in self._items:
            if d.source == source and d.noticeId == notice_id:
                return d.model_copy(
                    update={"status": compute_status(d.applyStart, d.applyEnd, today)}
                )
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
        status: str | None,
        limit: int,
        offset: int = 0,
        sort: str | None = None,
    ) -> NoticeList:
        """조건(검색어·지역·공급유형·기간·상태)에 맞는 공고를 검색한다."""
        today = self._today()
        lo = _parse_date_filter(since, end=False)
        hi = _parse_date_filter(until, end=True)
        tokens = q.lower().split() if q else []
        region_tokens = _region_query_tokens(region)
        matches: list[NoticeSummary] = []
        for d in self._items:
            if source and d.source != source:
                continue
            if not _matches_region(region_tokens, d.region):
                continue
            if supply_type and supply_type not in (d.supplyType or ""):
                continue
            if status and compute_status(d.applyStart, d.applyEnd, today) != status:
                continue
            if lo and d.postedDate and d.postedDate < lo:
                continue
            if hi and d.postedDate and d.postedDate > hi:
                continue
            if tokens:
                if not all(t in _haystack(d) for t in tokens):
                    continue
            matches.append(to_summary(d, today))
        ordered = _sort_summaries(matches, sort)
        return NoticeList(
            total=len(ordered),
            items=ordered[offset : offset + limit],
            lastUpdated=self._last_updated,
        )

    def recommend(self, req: RecommendRequest) -> NoticeList:
        """조건에 맞춰 점수를 매겨 공고를 추천한다."""
        today = self._today()
        want = req.status if req.status else "접수중"
        region_tokens = _region_query_tokens(req.region)
        scored: list[tuple[int, str, NoticeDetail]] = []
        for d in self._items:
            score = self._score(d, req, region_tokens)
            if score < 0:
                continue
            st = compute_status(d.applyStart, d.applyEnd, today)
            if want != "전체" and st != want:
                continue
            scored.append((score, st, d))
        scored.sort(key=lambda x: x[2].postedDate or "", reverse=True)
        scored.sort(key=lambda x: _STATUS_RANK.get(x[1], 9))
        scored.sort(key=lambda x: x[0], reverse=True)
        items = [to_summary(d, today) for _, _, d in scored[: req.limit]]
        return NoticeList(total=len(scored), items=items, lastUpdated=self._last_updated)

    @staticmethod
    def _score(d: NoticeDetail, req: RecommendRequest, region_tokens: list[str]) -> int:
        score = 0
        if not _matches_region(region_tokens, d.region):
            return -1
        if req.supplyType and req.supplyType not in (d.supplyType or ""):
            return -1
        if req.maxDepositKRW is not None and d.depositKRW is not None:
            if d.depositKRW > req.maxDepositKRW:
                return -1
            score += 2
        if req.maxMonthlyRentKRW is not None and d.monthlyRentKRW is not None:
            if d.monthlyRentKRW > req.maxMonthlyRentKRW:
                return -1
            score += 2
        if req.age is not None:
            if d.minAge is not None and req.age < d.minAge:
                return -1
            if d.maxAge is not None and req.age > d.maxAge:
                return -1
        if (
            req.age is not None
            and req.age <= 39
            and any(k in (d.supplyType or "") for k in ("청년", "행복"))
        ):
            score += 1
        return score

    def relevant_to_question(self, question: str, limit: int) -> NoticeList:
        """질문 토큰과 겹치는 공고를 점수순으로 찾는다."""
        today = self._today()
        tokens = _question_tokens(question)
        ranked: list[tuple[int, int, NoticeDetail]] = []
        for d in self._items:
            hay = _haystack(d)
            score = sum(1 for t in tokens if t in hay)
            if score <= 0:
                continue
            open_first = 1 if compute_status(d.applyStart, d.applyEnd, today) == "접수중" else 0
            ranked.append((score, open_first, d))
        ranked.sort(key=lambda x: x[2].postedDate or "", reverse=True)
        ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
        items = [to_summary(d, today) for _, _, d in ranked[:limit]]
        return NoticeList(total=len(ranked), items=items, lastUpdated=self._last_updated)
