"""사이트별 크롤러 구현 템플릿 (복사해서 사용).

실측(probing) 후 채울 것:
  - 목록/검색 엔드포인트와 페이지네이션 방식 (GET 쿼리? POST? 연도 필터?)
  - 공고 1건의 detail_url 패턴과 notice_id 추출 규칙
  - 상세 페이지에서 첨부(PDF/HWP/ZIP)·이미지 링크 셀렉터

HTML 파싱은 bs4(lxml)를, 요청은 `self.http`(재시도·레이트리밋 내장)를 쓴다.
"""

from __future__ import annotations

from collections.abc import Iterator

from bs4 import BeautifulSoup

from zipdao_core.models import Attachment, Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler


class TemplateCrawler(BaseCrawler):
    key = "template"
    name = "예시"
    base_url = "https://example.com"

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        page = 1
        while True:
            resp = self.http.get(self.base_url, params={"page": page})
            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("table.board tbody tr")  # TODO: 실제 셀렉터
            if not rows:
                break
            for row in rows:
                # TODO: 행에서 제목/링크/날짜 추출
                yield NoticeStub(
                    notice_id="...",
                    title="...",
                    detail_url="...",
                    posted_date="YYYY-MM-DD",
                )
            page += 1

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        resp = self.http.get(stub.detail_url)
        soup = BeautifulSoup(resp.text, "lxml")
        attachments: list[Attachment] = []
        for a in soup.select("a.file"):  # TODO: 실제 첨부 셀렉터
            href = a.get("href", "")
            attachments.append(Attachment(url=href, filename=a.get_text(strip=True)))
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=stub.posted_date,
            category=stub.category,
            region=stub.region,
            attachments=attachments,
            raw={},
        )
