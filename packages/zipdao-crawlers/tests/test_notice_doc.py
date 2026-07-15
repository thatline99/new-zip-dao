from __future__ import annotations

import json
from pathlib import Path

from zipdao_crawlers import cli
from zipdao_crawlers.normalize import normalize_for
from zipdao_crawlers.notice_doc import (
    extract_age_range,
    extract_min_deposit_rent,
    pick_notice_pdf,
)


def test_age_range_basic() -> None:
    assert extract_age_range("① 19세 이상 39세 이하인 자(1986년...)") == (19, 39)


def test_age_range_with_man_prefix_and_tilde() -> None:
    assert extract_age_range("만 19세 이상 만 39세 이하") == (19, 39)
    assert extract_age_range("만 19~39세인 무주택자") == (19, 39)


def test_age_range_one_sided_is_ignored() -> None:
    assert extract_age_range("만 18세 이상의 남성으로서 신장이 145센티미터") is None
    assert extract_age_range("만 6세 이하의 자녀를 둔 가구") is None


def test_age_range_takes_widest_across_tiers() -> None:
    text = "청년: 19세 이상 39세 이하 / 고령자: 65세 이상 99세 이하"
    assert extract_age_range(text) == (19, 99)


def test_age_range_invalid_bounds_ignored() -> None:
    assert extract_age_range("39세 이상 19세 이하") is None


_PRICE_PAGE = """1. 임대 보증금 및 월 임대료
- 청년(42세대) 임대 보증금 및 월임대료 (단위: 만원)
19.33㎡ (25) 36 5,000 48 5,900 44 6,700 41
21.21㎡ (36) 4 5,300 50 6,200 46 7,000 43
합계 42 특별공급(주변시세의 80% 이하)
"""


def test_min_deposit_rent_from_unit_marked_table() -> None:
    assert extract_min_deposit_rent([_PRICE_PAGE]) == (50_000_000, 480_000)


def test_min_deposit_rent_requires_unit_marker() -> None:
    page = _PRICE_PAGE.replace("(단위: 만원)", "")
    assert extract_min_deposit_rent([page]) is None


def test_min_deposit_rent_thousand_won_unit() -> None:
    page = "임대 보증금 월임대료 (단위: 천원)\n19.33㎡ (25) 36 50,000 480"
    assert extract_min_deposit_rent([page]) == (50_000_000, 480_000)


def test_min_deposit_rent_ignores_pages_without_area_rows() -> None:
    assert extract_min_deposit_rent(["보증금 임대료 (단위: 만원)\n합계 42 80 이하"]) is None


def test_pick_notice_pdf_prefers_gonggo_filename() -> None:
    atts = [
        {"url": "u1", "filename": "안내문.pdf", "kind": "pdf"},
        {"url": "u2", "filename": "모집공고문.pdf", "kind": "pdf"},
        {"url": "u3", "filename": "공고문.hwp", "kind": "hwp"},
    ]
    assert pick_notice_pdf(atts)["url"] == "u2"


def test_pick_notice_pdf_none_when_no_pdf() -> None:
    assert pick_notice_pdf([{"url": "u", "filename": "공고문.hwp", "kind": "hwp"}]) is None


def test_normalize_merges_doc_parse_for_youth() -> None:
    raw = {
        "gubun": "2",
        "applyDate": "2026-07-17",
        "docParse": {
            "parsedAt": "2026-07-15T04:00:00+00:00",
            "minAge": 19,
            "maxAge": 39,
            "depositKRW": 50_000_000,
            "monthlyRentKRW": 480_000,
        },
    }
    n = normalize_for("youth_seoul", raw)
    assert (n["minAge"], n["maxAge"]) == (19, 39)
    assert (n["depositKRW"], n["monthlyRentKRW"]) == (50_000_000, 480_000)


def test_apply_doc_parse_keeps_api_price() -> None:
    from zipdao_crawlers.normalize import _apply_doc_parse

    normalized = {"depositKRW": 99, "monthlyRentKRW": None}
    _apply_doc_parse(normalized, {"depositKRW": 1, "monthlyRentKRW": 2})
    assert normalized["depositKRW"] == 99
    assert normalized["monthlyRentKRW"] is None


class _FakeResp:
    content = b"%PDF-fake"


class _FakeHttp:
    def __init__(self, **kwargs) -> None:
        pass

    def __enter__(self) -> _FakeHttp:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def get(self, url: str, **kwargs) -> _FakeResp:
        return _FakeResp()


def _write_manifest(tmp_path: Path) -> Path:
    d = tmp_path / "raw" / "youth_seoul" / "2026" / "N1"
    d.mkdir(parents=True)
    manifest = {
        "source": "youth_seoul",
        "notice_id": "N1",
        "title": "테스트 공고",
        "detail_url": "u",
        "posted_date": "2026-07-01",
        "category": "임대주택 모집공고",
        "region": "서울",
        "attachments": [{"url": "http://x/f.pdf", "filename": "모집공고문.pdf", "kind": "pdf"}],
        "raw": {"gubun": "2", "applyDate": "2026-07-17"},
    }
    path = d / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def test_parse_docs_cli_backfills_manifest(tmp_path: Path, monkeypatch) -> None:
    path = _write_manifest(tmp_path)
    monkeypatch.setattr(cli, "HttpClient", _FakeHttp)
    monkeypatch.setattr(
        "zipdao_crawlers.notice_doc.parse_notice_pdf",
        lambda data: {
            "minAge": 19,
            "maxAge": 39,
            "depositKRW": 50_000_000,
            "monthlyRentKRW": 480_000,
        },
    )
    assert cli.main(["parse-docs", "youth_seoul", "--data-dir", str(tmp_path)]) == 0
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["raw"]["docParse"]["minAge"] == 19
    assert saved["raw"]["docParse"]["parsedAt"]
    normalized = saved["raw"]["normalized"]
    assert (normalized["minAge"], normalized["maxAge"]) == (19, 39)
    assert (normalized["depositKRW"], normalized["monthlyRentKRW"]) == (50_000_000, 480_000)


def test_parse_docs_cli_skips_already_parsed(tmp_path: Path, monkeypatch) -> None:
    path = _write_manifest(tmp_path)
    monkeypatch.setattr(cli, "HttpClient", _FakeHttp)
    monkeypatch.setattr(
        "zipdao_crawlers.notice_doc.parse_notice_pdf", lambda data: {"minAge": 19, "maxAge": 39}
    )
    cli.main(["parse-docs", "youth_seoul", "--data-dir", str(tmp_path)])
    monkeypatch.setattr(
        "zipdao_crawlers.notice_doc.parse_notice_pdf", lambda data: {"minAge": 1, "maxAge": 2}
    )
    cli.main(["parse-docs", "youth_seoul", "--data-dir", str(tmp_path)])
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["raw"]["docParse"]["minAge"] == 19


def test_parse_docs_cli_failure_leaves_manifest_for_retry(tmp_path: Path, monkeypatch) -> None:
    path = _write_manifest(tmp_path)

    class _BrokenHttp(_FakeHttp):
        def get(self, url: str, **kwargs) -> _FakeResp:
            raise RuntimeError("boom")

    monkeypatch.setattr(cli, "HttpClient", _BrokenHttp)
    assert cli.main(["parse-docs", "youth_seoul", "--data-dir", str(tmp_path)]) == 0
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "docParse" not in saved["raw"]
