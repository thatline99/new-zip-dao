"""저장된 raw 데이터를 소스별 정규화 함수(normalize_raw)로 보내는 dispatch."""

from __future__ import annotations

from zipdao_crawlers.sources.applyhome import normalize_raw as _applyhome
from zipdao_crawlers.sources.gndc import normalize_raw as _gndc
from zipdao_crawlers.sources.lh_apply import normalize_raw as _lh_apply
from zipdao_crawlers.sources.myhome import normalize_raw as _myhome
from zipdao_crawlers.sources.sh_ish import normalize_raw as _sh_ish
from zipdao_crawlers.sources.youth_seoul import normalize_raw as _youth_seoul

_DISPATCH = {
    "myhome": _myhome,
    "applyhome": _applyhome,
    "gndc": _gndc,
    "lh_apply": _lh_apply,
    "sh_ish": _sh_ish,
    "youth_seoul": _youth_seoul,
}


def normalize_for(source: str, raw: dict) -> dict:
    """소스 키에 맞는 정규화 함수로 raw 데이터를 변환하고 공고문 파싱 결과를 병합한다."""
    fn = _DISPATCH.get(source)
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
