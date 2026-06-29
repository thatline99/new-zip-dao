from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NoticeStatus = Literal["접수중", "마감", "예정", "미정"]


class Attachment(BaseModel):
    url: str
    filename: str
    kind: str


class NoticeSummary(BaseModel):
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
    attachments: list[Attachment]
    summary: str | None
    eligibility: str | None
    crawledAt: str | None


class NoticeList(BaseModel):
    total: int
    items: list[NoticeSummary]


class SourceInfo(BaseModel):
    key: str
    name: str
    category: str
    implemented: bool
    collected: bool


class RecommendRequest(BaseModel):
    limit: int = Field(ge=1, le=50)
    region: str | None = None
    age: int | None = None
    maxDepositKRW: int | None = None
    maxMonthlyRentKRW: int | None = None
    supplyType: str | None = None
    status: Literal["접수중", "마감", "예정", "미정", "전체"] | None = None


class QaRequest(BaseModel):
    question: str
