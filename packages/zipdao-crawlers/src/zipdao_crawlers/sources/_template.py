"""사이트별 크롤러 구현 템플릿(복사해서 사용)."""

from __future__ import annotations

from collections.abc import Iterator

from bs4 import BeautifulSoup

from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler


class TemplateCrawler(BaseCrawler):
    """새 사이트 크롤러 작성 시 참고할 예시 구현."""

    key = "template"
    name = "예시"
    base_url = "https://example.com"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        """목록 페이지를 순회하며 공고 요약을 만든다(예시)."""
        page = 1
        while True:
            resp = self.http.get(self.base_url, params={"page": page})
            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table.board tbody tr")
            if not rows:
                break
            for _row in rows:
                yield NoticeStub(
                    notice_id="...",
                    title="...",
                    detail_url="...",
                    posted_date="YYYY-MM-DD",
                )
            page += 1

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        """상세 페이지에서 첨부를 추출해 Notice 를 만든다(예시)."""
        resp = self.http.get(stub.detail_url)
        soup = BeautifulSoup(resp.text, "lxml")
        attachments: list[Attachment] = []
        for a in soup.select("a.file"):
            href = a.get("href", "")
            attachments.append(Attachment(url=href, filename=a.get_text(strip=True)))
        return Notice.from_stub(stub, source=self.key, attachments=attachments)
