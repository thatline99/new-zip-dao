from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from zipdao_api.schema import (
    NoticeDetail,
    NoticeList,
    QaAnswer,
    QaCitation,
    QaRequest,
    RecommendRequest,
    SourceInfo,
)
from zipdao_api.store import NoticeStore
from zipdao_crawlers.registry import iter_sources


def _raw_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "./data")).expanduser().resolve() / "raw"


def create_app(store: NoticeStore) -> FastAPI:
    app = FastAPI(title="zipdao-api", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/notices", response_model=NoticeList)
    def search_notices(
        limit: int = Query(ge=1, le=200),
        q: str | None = None,
        region: str | None = None,
        supplyType: str | None = None,
        source: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> NoticeList:
        return store.search(
            q=q,
            region=region,
            supply_type=supplyType,
            source=source,
            since=since,
            until=until,
            limit=limit,
        )

    @app.get("/notices/{source}/{notice_id}", response_model=NoticeDetail)
    def get_notice(source: str, notice_id: str) -> NoticeDetail:
        notice = store.get(source, notice_id)
        if notice is None:
            raise HTTPException(status_code=404, detail="notice not found")
        return notice

    @app.post("/recommend", response_model=NoticeList)
    def recommend(req: RecommendRequest) -> NoticeList:
        return store.recommend(req)

    @app.post("/qa", response_model=QaAnswer)
    def qa(req: QaRequest) -> QaAnswer:
        hits = store.top_for_question(req.question, 3)
        return QaAnswer(
            answer=f'"{req.question}" 관련 공고 {len(hits)}건을 찾았습니다. RAG 기반 상세 답변은 추후 제공됩니다.',
            citations=[
                QaCitation(source=d.source, noticeId=d.noticeId, title=d.title, detailUrl=d.detailUrl)
                for d in hits
            ],
        )

    @app.get("/sources", response_model=list[SourceInfo])
    def sources() -> list[SourceInfo]:
        return [
            SourceInfo(key=s.key, name=s.name, category=s.category, implemented=s.implemented)
            for s in iter_sources()
        ]

    return app


app = create_app(NoticeStore(_raw_dir()))
