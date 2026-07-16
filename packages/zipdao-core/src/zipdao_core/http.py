"""재시도와 레이트리밋을 갖춘 HTTP 클라이언트 래퍼."""

from __future__ import annotations

import logging
import ssl
import time
from pathlib import Path

import certifi
import httpx

logger = logging.getLogger("zipdao.http")

_CERTS_DIR = Path(__file__).parent / "certs"


def _ssl_context() -> ssl.SSLContext:
    """공공기관 서버 호환 TLS 컨텍스트.

    - 일부 기관 서버(apply.gh.or.kr 등)는 구식 암호군만 지원해 OpenSSL 보안수준을
      1로 낮춘다(TLS 1.2 미만은 계속 거부).
    - 중간 인증서를 안 보내주는 서버가 있어 certs/ 에 동봉한 잘 알려진 중간
      인증서(Sectigo 등)를 신뢰 목록에 보탠다.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    for pem in sorted(_CERTS_DIR.glob("*.pem")):
        ctx.load_verify_locations(pem)
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class HttpClient:
    """재시도·레이트리밋이 내장된 HTTP 클라이언트."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float = 30.0,
        rate_limit_per_sec: float = 1.0,
        max_retries: int = 3,
    ) -> None:
        self._min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0.0
        self._last_request = 0.0
        self._max_retries = max_retries
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
            verify=_ssl_context(),
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
                wait = min(2.0**attempt, 30.0)
                logger.warning(
                    "요청 실패 (%s/%s) %s %s — %s; %.1fs 후 재시도",
                    attempt,
                    self._max_retries,
                    method,
                    url,
                    exc,
                    wait,
                )
                if attempt < self._max_retries:
                    time.sleep(wait)
        assert last_exc is not None
        raise last_exc

    def get(self, url: str, **kwargs) -> httpx.Response:
        """GET 요청을 보낸다(재시도 내장)."""
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        """POST 요청을 보낸다(재시도 내장)."""
        return self._request("POST", url, **kwargs)

    def close(self) -> None:
        """내부 HTTP 클라이언트를 닫는다."""
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
