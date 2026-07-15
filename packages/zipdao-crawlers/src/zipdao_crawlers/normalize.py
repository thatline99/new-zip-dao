"""저장된 raw 데이터를 소스별 정규화 함수(normalize_raw)로 보내는 dispatch.

소스 키와 모듈명이 같다는 규약(sources/<key>.py)으로 정규화 함수를 자동 탐색한다 —
새 소스를 추가할 때 이 파일을 수정할 필요가 없다.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache
from importlib import import_module

_SOURCE_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")


@cache
def _normalizer(source: str) -> Callable[[dict], dict] | None:
    """sources/<key>.py 모듈의 normalize_raw 함수를 찾는다. 없으면 None."""
    if not _SOURCE_KEY_RE.fullmatch(source):
        return None
    try:
        module = import_module(f"zipdao_crawlers.sources.{source}")
    except ModuleNotFoundError:
        return None
    return getattr(module, "normalize_raw", None)


def normalize_for(source: str, raw: dict) -> dict:
    """소스 키에 맞는 정규화 함수로 raw 데이터를 변환하고 공고문 파싱 결과를 병합한다."""
    fn = _normalizer(source)
    normalized = fn(raw) if fn else {}
    if normalized:
        _apply_doc_parse(normalized, raw.get("docParse") or {})
    return normalized


def _apply_doc_parse(normalized: dict, doc: dict) -> None:
    """나이는 항상, 가격은 API 값이 둘 다 없을 때만 공고문 값으로 채운다."""
    for key in ("minAge", "maxAge"):
        if doc.get(key) is not None:
            normalized[key] = doc[key]
    if (
        not normalized.get("depositKRW")
        and not normalized.get("monthlyRentKRW")
        and doc.get("depositKRW")
        and doc.get("monthlyRentKRW")
    ):
        normalized["depositKRW"] = doc["depositKRW"]
        normalized["monthlyRentKRW"] = doc["monthlyRentKRW"]
