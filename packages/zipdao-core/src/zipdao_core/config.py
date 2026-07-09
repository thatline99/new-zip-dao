"""환경설정(.env 포함) 로딩."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass
class Settings:
    """크롤러/설정 환경변수 값 모음."""

    data_dir: Path
    user_agent: str
    request_timeout: float
    rate_limit_per_sec: float
    data_go_kr_service_key: str | None = None


def load_settings(dotenv: Path | None = None) -> Settings:
    """환경변수(필요시 .env)에서 Settings 를 만든다."""
    if dotenv is None:
        cwd = Path.cwd()
        for parent in (cwd, *cwd.parents):
            candidate = parent / ".env"
            if candidate.exists():
                dotenv = candidate
                break
    if dotenv is not None:
        _load_dotenv(dotenv)

    data_dir = Path(os.environ.get("DATA_DIR", "./data")).expanduser().resolve()
    return Settings(
        data_dir=data_dir,
        user_agent=os.environ.get(
            "CRAWL_USER_AGENT",
            "Mozilla/5.0 (compatible; new-zip-dao/0.1; +https://github.com/thatline99/new-zip-dao)",
        ),
        request_timeout=float(os.environ.get("CRAWL_TIMEOUT", "30")),
        rate_limit_per_sec=float(os.environ.get("CRAWL_RATE_LIMIT", "2")),
        data_go_kr_service_key=os.environ.get("DATA_GO_KR_SERVICE_KEY") or None,
    )
