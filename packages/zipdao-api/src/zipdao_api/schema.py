from __future__ import annotations

from pydantic import BaseModel, Field


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
    monthlyIncomeKRW: int | None = None
    householdSize: int | None = None
    maxDepositKRW: int | None = None
    maxMonthlyRentKRW: int | None = None
    supplyType: str | None = None


class QaRequest(BaseModel):
    question: str


class QaCitation(BaseModel):
    source: str
    noticeId: str
    title: str
    detailUrl: str


class QaAnswer(BaseModel):
    answer: str
    citations: list[QaCitation]
