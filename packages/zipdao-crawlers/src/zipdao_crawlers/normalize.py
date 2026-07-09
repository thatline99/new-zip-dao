"""저장된 raw 데이터를 소스별 정규화 함수(normalize_raw)로 보내는 dispatch."""

from __future__ import annotations

from zipdao_crawlers.sources.applyhome import normalize_raw as _applyhome
from zipdao_crawlers.sources.lh_apply import normalize_raw as _lh_apply
from zipdao_crawlers.sources.myhome import normalize_raw as _myhome
from zipdao_crawlers.sources.youth_seoul import normalize_raw as _youth_seoul

_DISPATCH = {
    "myhome": _myhome,
    "applyhome": _applyhome,
    "lh_apply": _lh_apply,
    "youth_seoul": _youth_seoul,
}


def normalize_for(source: str, raw: dict) -> dict:
    """소스 키에 맞는 정규화 함수로 raw 데이터를 변환한다."""
    fn = _DISPATCH.get(source)
    return fn(raw) if fn else {}
