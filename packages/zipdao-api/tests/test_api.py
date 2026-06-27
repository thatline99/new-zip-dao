from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from zipdao_api.app import create_app
from zipdao_api.store import NoticeStore


def _write(raw_dir: Path, source: str, year: str, notice_id: str, body: dict) -> None:
    d = raw_dir / source / year / notice_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")


def _client(tmp_path: Path) -> TestClient:
    raw = tmp_path / "raw"
    _write(
        raw,
        "myhome",
        "2026",
        "SEOUL-1",
        {
            "source": "myhome",
            "notice_id": "SEOUL-1",
            "title": "서울 강서구 국민임대 모집",
            "detail_url": "https://x/1",
            "posted_date": "2026-06-05",
            "category": "국민임대",
            "region": "서울",
            "attachments": [],
            "raw": {
                "normalized": {
                    "supplyType": "국민임대",
                    "depositKRW": 48000000,
                    "monthlyRentKRW": 180000,
                    "areaM2": 46,
                    "applyStart": "2026-06-18",
                    "applyEnd": "2026-07-02",
                    "summary": "마곡 국민임대",
                    "eligibility": "무주택",
                }
            },
            "crawled_at": "2026-06-24T05:00:00+00:00",
        },
    )
    _write(
        raw,
        "lh_apply",
        "2026",
        "2026-1",
        {
            "source": "lh_apply",
            "notice_id": "2026-1",
            "title": "경기 위례 행복주택",
            "detail_url": "https://x/2",
            "posted_date": "2026-06-10",
            "category": "행복주택",
            "region": "경기",
            "attachments": [],
            "raw": {
                "normalized": {
                    "supplyType": "행복주택",
                    "depositKRW": 32000000,
                    "monthlyRentKRW": 250000,
                    "areaM2": 39,
                    "applyEnd": "2026-07-20",
                }
            },
            "crawled_at": "2026-06-24T05:00:00+00:00",
        },
    )
    return TestClient(create_app(NoticeStore(raw)))


def test_search_by_region(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/notices", params={"region": "서울", "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["noticeId"] == "SEOUL-1"
    assert data["items"][0]["depositKRW"] == 48000000


def test_get_notice(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/notices/lh_apply/2026-1")
    assert r.status_code == 200
    assert r.json()["supplyType"] == "행복주택"
    assert c.get("/notices/lh_apply/none").status_code == 404


def test_recommend(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/recommend", json={"region": "서울", "maxMonthlyRentKRW": 200000, "limit": 5})
    assert r.status_code == 200
    out = r.json()
    assert out["items"][0]["noticeId"] == "SEOUL-1"


def test_sources(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/sources")
    assert r.status_code == 200
    keys = [s["key"] for s in r.json()]
    assert "lh_apply" in keys
    assert "myhome" in keys


def test_qa(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/qa", json={"question": "서울 국민임대"})
    assert r.status_code == 200
    assert "citations" in r.json()


def test_limit_validation(tmp_path: Path) -> None:
    c = _client(tmp_path)
    assert c.get("/notices", params={"limit": 0}).status_code == 422
    assert c.post("/recommend", json={"limit": -1}).status_code == 422


def test_bad_manifest_is_skipped(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    good = raw / "myhome" / "2026" / "OK"
    good.mkdir(parents=True)
    (good / "manifest.json").write_text(
        json.dumps(
            {
                "source": "myhome",
                "notice_id": "OK",
                "title": "서울 국민임대",
                "detail_url": "u",
                "posted_date": "2026-06-01",
                "category": "국민임대",
                "region": "서울",
                "attachments": [],
                "raw": {},
            }
        ),
        encoding="utf-8",
    )
    bad = raw / "lh_apply" / "2026" / "BAD"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text("{ broken json", encoding="utf-8")
    c = TestClient(create_app(NoticeStore(raw)))
    r = c.get("/notices", params={"limit": 10})
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_recommend_excludes_unknown_price_when_budget_set(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/recommend", json={"limit": 5, "maxDepositKRW": 1000})
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []


def test_region_alias_special_province(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw,
        "lh_apply",
        "2026",
        "K1",
        {
            "source": "lh_apply",
            "notice_id": "K1",
            "title": "원주 국민임대",
            "detail_url": "u",
            "posted_date": "2026-06-01",
            "category": "임대주택",
            "region": "강원특별자치도",
            "attachments": [],
            "raw": {"normalized": {"supplyType": "국민임대"}},
        },
    )
    c = TestClient(create_app(NoticeStore(raw)))
    assert c.get("/notices", params={"region": "강원도", "limit": 10}).json()["total"] == 1
    assert c.get("/notices", params={"region": "강원", "limit": 10}).json()["total"] == 1


def test_recommend_excludes_zero_price_when_budget_set(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw,
        "myhome",
        "2026",
        "Z",
        {
            "source": "myhome",
            "notice_id": "Z",
            "title": "경기 매입임대",
            "detail_url": "u",
            "posted_date": "2026-06-01",
            "category": "매입임대",
            "region": "경기도",
            "attachments": [],
            "raw": {"normalized": {"supplyType": "매입임대", "depositKRW": 0, "monthlyRentKRW": 0}},
        },
    )
    c = TestClient(create_app(NoticeStore(raw)))
    r = c.post("/recommend", json={"region": "경기", "maxMonthlyRentKRW": 150000, "limit": 5})
    assert r.json()["total"] == 0
