"""크롤러 베이스 추상화 + 수집 엔진.

사이트별 크롤러는 `BaseCrawler`를 상속해 두 가지만 구현하면 된다:

    iter_notices(since, until)  →  NoticeStub 목록(목록/검색 페이지에서)
    fetch_detail(stub)          →  Notice (상세 + 첨부 URL 채움)

다운로드/체크섬/manifest 기록/멱등 스킵은 `CrawlEngine`이 공통 처리한다.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from zipdao_core.http import HttpClient
from zipdao_core.models import AssetKind, Attachment, Notice, NoticeStub
from zipdao_core.storage import Storage

logger = logging.getLogger("zipdao.crawl")


class BaseCrawler(ABC):
    #: 레지스트리 키와 동일한 소스 식별자 (저장 경로에 사용)
    key: str = ""
    #: 사람이 읽는 이름
    name: str = ""
    #: 목록/검색 시작 URL
    base_url: str = ""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    @abstractmethod
    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """[since, until] 연도 범위의 공고 요약을 순회한다."""
        raise NotImplementedError

    @abstractmethod
    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지를 받아 첨부/이미지 URL이 채워진 Notice를 만든다."""
        raise NotImplementedError


@dataclass
class CrawlStats:
    source: str
    notices_seen: int = 0
    notices_new: int = 0
    notices_skipped: int = 0
    assets_downloaded: int = 0
    assets_failed: int = 0
    errors: list[str] = field(default_factory=list)


def _filename_from_url(url: str) -> str:
    path = urlsplit(url).path
    name = unquote(path.rsplit("/", 1)[-1]) if path else ""
    return name or "asset"


class CrawlEngine:
    def __init__(self, crawler: BaseCrawler, storage: Storage) -> None:
        self.crawler = crawler
        self.storage = storage

    def run(
        self,
        *,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> CrawlStats:
        stats = CrawlStats(source=self.crawler.key)
        for stub in self.crawler.iter_notices(since, until):
            stats.notices_seen += 1
            year = (stub.posted_date or "")[:4] or None
            if not force and self.storage.is_crawled(self.crawler.key, stub.notice_id, year):
                stats.notices_skipped += 1
                logger.debug("스킵(이미 수집됨): %s/%s", self.crawler.key, stub.notice_id)
                continue
            try:
                self._collect_one(stub, stats)
                stats.notices_new += 1
            except Exception as exc:  # noqa: BLE001 — 한 건 실패가 전체를 막지 않도록
                msg = f"{stub.notice_id}: {exc}"
                stats.errors.append(msg)
                logger.exception("공고 수집 실패: %s", msg)
            if limit is not None and stats.notices_new >= limit:
                break
        return stats

    def _collect_one(self, stub: NoticeStub, stats: CrawlStats) -> None:
        notice = self.crawler.fetch_detail(stub)
        year = (notice.posted_date or "")[:4] or None
        ndir = self.storage.notice_dir(notice.source, notice.notice_id, year)

        for att in notice.attachments:
            try:
                if not att.filename:
                    att.filename = _filename_from_url(att.url)
                if att.kind is AssetKind.OTHER:
                    att.kind = AssetKind.from_filename(att.filename)
                data = self.crawler.http.get(att.url).content
                self.storage.save_asset(ndir, att, data)
                stats.assets_downloaded += 1
            except Exception as exc:  # noqa: BLE001
                att.note = f"download_failed: {exc}"
                stats.assets_failed += 1
                logger.warning("첨부 다운로드 실패 %s — %s", att.url, exc)

        self.storage.write_manifest(notice)
