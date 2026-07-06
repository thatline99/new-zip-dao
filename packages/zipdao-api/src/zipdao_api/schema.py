"""API 요청/응답 Pydantic 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NoticeStatus = Literal["접수중", "마감", "예정", "미정"]


class Attachment(BaseModel):
    """공고 첨부파일 한 건."""

    url: str
    filename: str
    kind: str


class NoticeSummary(BaseModel):
    """공고 목록 항목 요약."""

    source: str
    noticeId: str
    title: str
    region: str | None
    category: str | None
    supplyType: str | None
    postedDate: str | None
    applyStart: str | None
    applyEnd: str | None
    depositKRW: int | None
    monthlyRentKRW: int | None
    areaM2: float | None
    detailUrl: str
    status: str


class NoticeDetail(NoticeSummary):
    """공고 상세 정보(요약 + 첨부/자격요건 등)."""

    attachments: list[Attachment]
    summary: str | None
    eligibility: str | None
    crawledAt: str | None


class NoticeList(BaseModel):
    """공고 목록 응답(총건수 + 항목)."""

    total: int
    items: list[NoticeSummary]


class SourceInfo(BaseModel):
    """소스(사이트) 구현 상태 정보."""

    key: str
    name: str
    category: str
    implemented: bool
    collected: bool


class RecommendRequest(BaseModel):
    """추천 요청 조건."""

    limit: int = Field(ge=1, le=50)
    region: str | None = None
    age: int | None = None
    maxDepositKRW: int | None = None
    maxMonthlyRentKRW: int | None = None
    supplyType: str | None = None
    status: Literal["접수중", "마감", "예정", "미정", "전체"] | None = None


class QaRequest(BaseModel):
    """자연어 질의응답 요청."""

    question: str
