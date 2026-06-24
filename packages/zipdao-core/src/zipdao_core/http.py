"""HTTP 클라이언트 래퍼 — 재시도 + 단순 레이트리밋.

크롤러는 이 클라이언트로 목록/상세 HTML과 첨부(바이너리)를 가져온다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx

logger = logging.getLogger("zipdao.http")


class HttpClient:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 30.0,
        rate_limit_per_sec: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        self._min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._last_request = 0.0
        self._max_retries = max_retries
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            self._throttle()
            try:
                resp = self._client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.HTTPError, httpx.StreamError) as exc:
                last_exc = exc
                wait = min(2.0 ** attempt, 30.0)
                logger.warning(
                    "요청 실패 (%s/%s) %s %s — %s; %.1fs 후 재시도",
                    attempt, self._max_retries, method, url, exc, wait,
                )
                if attempt < self._max_retries:
                    time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self._request("POST", url, **kwargs)

    @contextmanager
    def stream(self, method: str, url: str, **kwargs) -> Iterator[httpx.Response]:
        """대용량 첨부를 청크로 받기 위한 스트리밍 요청."""
        self._throttle()
        with self._client.stream(method, url, **kwargs) as resp:
            resp.raise_for_status()
            yield resp

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
