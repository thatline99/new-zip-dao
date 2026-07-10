"""크롤러 베이스 추상화와 수집 엔진(다운로드·체크섬·manifest 기록)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from zipdao_core.config import load_settings
from zipdao_core.http import HttpClient
from zipdao_core.models import AssetKind, Notice, NoticeStub
from zipdao_core.storage import Storage

logger = logging.getLogger("zipdao.crawl")


class BaseCrawler(ABC):
    """사이트별 크롤러가 상속하는 베이스 클래스."""

    key: str = ""
    name: str = ""
    base_url: str = ""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    @abstractmethod
    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """[since, until] 연도 범위의 공고 요약을 순회한다."""
        raise NotImplementedError

    @abstractmethod
    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지를 받아 첨부/이미지 URL이 채워진 Notice 를 만든다."""
        raise NotImplementedError


class DataGoKrCrawler(BaseCrawler):
    """공공데이터포털(data.go.kr) 인증키를 요구하는 크롤러 베이스."""

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        key = load_settings().data_go_kr_service_key
        if not key:
            raise RuntimeError(
                "DATA_GO_KR_SERVICE_KEY 미설정(.env). 공공데이터포털 인증키가 필요합니다."
            )
        self._key: str = key


@dataclass
class CrawlStats:
    """한 소스 수집 실행 결과 통계."""

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
    """크롤러를 구동해 다운로드·저장·중복 스킵을 처리하는 엔진."""

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
        """크롤러를 실행해 신규 공고를 수집하고 통계를 반환한다."""
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
            except Exception as exc:
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

        detail_html = notice.raw.pop("_detail_html", None)
        if detail_html:
            notice.detail_html_path = self.storage.save_detail_html(ndir, detail_html)

        for att in notice.attachments:
            if not att.filename:
                att.filename = _filename_from_url(att.url)
            if att.kind is AssetKind.OTHER:
                att.kind = AssetKind.from_filename(att.filename)
            if att.link_only:
                continue
            try:
                data = self.crawler.http.get(att.url).content
                self.storage.save_asset(ndir, att, data)
                stats.assets_downloaded += 1
            except Exception as exc:
                att.note = f"download_failed: {exc}"
                stats.assets_failed += 1
                logger.warning("첨부 다운로드 실패 %s — %s", att.url, exc)

        self.storage.write_manifest(notice)
