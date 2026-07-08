"""FastAPI 앱 팩토리 — 공고 검색/추천/QA REST 엔드포인트를 등록한다."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from zipdao_api.schema import (
    NoticeDetail,
    NoticeList,
    NoticeStatus,
    QaRequest,
    RecommendRequest,
    SortOrder,
    SourceInfo,
)
from zipdao_api.store import NoticeStore
from zipdao_crawlers.registry import iter_sources


def _raw_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "./data")).expanduser().resolve() / "raw"


def create_app(store: NoticeStore) -> FastAPI:
    """FastAPI 앱을 만들고 공고 조회 라우트를 등록한다."""
    app = FastAPI(title="zipdao-api", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/notices", response_model=NoticeList)
    def search_notices(
        limit: int = Query(200, ge=1),
        offset: int = Query(0, ge=0),
        q: str | None = None,
        region: str | None = None,
        supplyType: str | None = None,
        source: str | None = None,
        since: str | None = None,
        until: str | None = None,
        status: NoticeStatus | None = None,
        sort: SortOrder | None = None,
    ) -> NoticeList:
        return store.search(
            q=q,
            region=region,
            supply_type=supplyType,
            source=source,
            since=since,
            until=until,
            status=status,
            limit=min(limit, 200),
            offset=offset,
            sort=sort,
        )

    @app.get("/notices/{source}/{notice_id}", response_model=NoticeDetail)
    def get_notice(source: str, notice_id: str) -> NoticeDetail:
        notice = store.get(source, notice_id)
        if notice is None:
            raise HTTPException(status_code=404, detail="notice not found")
        return notice

    @app.post("/recommend", response_model=NoticeList)
    def recommend_notices(req: RecommendRequest) -> NoticeList:
        return store.recommend(req)

    @app.post("/qa", response_model=NoticeList)
    def answer_question(req: QaRequest) -> NoticeList:
        return store.relevant_to_question(req.question, 5)

    @app.get("/sources", response_model=list[SourceInfo])
    def list_sources() -> list[SourceInfo]:
        collected = store.collected_sources()
        return [
            SourceInfo(
                key=s.key,
                name=s.name,
                category=s.category,
                implemented=s.implemented,
                collected=s.key in collected,
            )
            for s in iter_sources()
        ]

    return app


app = create_app(NoticeStore(_raw_dir()))
