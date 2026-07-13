from __future__ import annotations

import json
from pathlib import Path

from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_core.storage import Storage
from zipdao_crawlers.base import BaseCrawler, CrawlEngine


class _NoDownloadHttp:
    """다운로드가 일어나면 실패하는 HTTP 스텁."""

    def get(self, url, **kwargs):
        raise AssertionError(f"link_only 첨부는 다운로드하면 안 된다: {url}")


class _OneNoticeCrawler(BaseCrawler):
    key = "fake"
    name = "가짜 소스"
    base_url = "https://example.com"

    def iter_notices(self, since, until):
        yield NoticeStub(
            notice_id="N1",
            title="공고",
            detail_url="https://example.com/n1",
            posted_date="2026-07-01",
        )

    def fetch_detail(self, stub):
        return Notice.from_stub(
            stub,
            source=self.key,
            attachments=[
                Attachment(
                    url="https://example.com/공고문.pdf", filename="공고문.pdf", link_only=True
                )
            ],
        )


class _DetailFailCrawler(_OneNoticeCrawler):
    def fetch_detail(self, stub):
        raise RuntimeError("상세 API 403")


def test_force_recrawl_keeps_manifest_when_detail_fails(tmp_path: Path):
    storage = Storage(tmp_path / "raw")
    CrawlEngine(_OneNoticeCrawler(_NoDownloadHttp()), storage).run()
    manifest_path = tmp_path / "raw" / "fake" / "2026" / "N1" / "manifest.json"
    before = manifest_path.read_text(encoding="utf-8")

    stats = CrawlEngine(_DetailFailCrawler(_NoDownloadHttp()), storage).run(force=True)

    assert stats.notices_new == 0
    assert len(stats.errors) == 1
    assert manifest_path.read_text(encoding="utf-8") == before


def test_engine_skips_download_for_link_only_attachments(tmp_path: Path):
    engine = CrawlEngine(_OneNoticeCrawler(_NoDownloadHttp()), Storage(tmp_path / "raw"))
    stats = engine.run()
    assert stats.notices_new == 1
    assert stats.assets_downloaded == 0
    assert stats.assets_failed == 0

    manifest = json.loads(
        (tmp_path / "raw" / "fake" / "2026" / "N1" / "manifest.json").read_text(encoding="utf-8")
    )
    att = manifest["attachments"][0]
    assert att["link_only"] is True
    assert att["kind"] == "pdf"  # 파일명 기반 종류 추론은 유지
    assert att["local_path"] is None  # 파일 저장 없음
