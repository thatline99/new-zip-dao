from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from zipdao_api.app import create_app
from zipdao_api.store import NoticeStore

TODAY = "2026-06-28"


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
    return TestClient(create_app(NoticeStore(raw, today=TODAY)))


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
    by_key = {s["key"]: s for s in r.json()}
    assert "lh_apply" in by_key
    assert "myhome" in by_key
    assert by_key["myhome"]["collected"] is True
    assert by_key["lh_apply"]["collected"] is True
    assert by_key["youth_seoul"]["implemented"] is True
    assert by_key["youth_seoul"]["collected"] is False


def test_qa_returns_relevant_notices(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/qa", json={"question": "서울 국민임대"})
    assert r.status_code == 200
    out = r.json()
    assert "items" in out
    assert out["items"][0]["noticeId"] == "SEOUL-1"
    assert out["items"][0]["status"]


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
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
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
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
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
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    r = c.post("/recommend", json={"region": "경기", "maxMonthlyRentKRW": 150000, "limit": 5})
    assert r.json()["total"] == 0


def test_sale_notices_excluded_but_rental_convertible_kept(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw,
        "applyhome",
        "2026",
        "SALE",
        {
            "source": "applyhome",
            "notice_id": "SALE",
            "title": "서울 APT 분양",
            "detail_url": "u",
            "posted_date": "2026-06-01",
            "category": "APT 분양주택",
            "region": "서울",
            "attachments": [],
            "raw": {"normalized": {"supplyType": "APT 분양주택"}},
        },
    )
    _write(
        raw,
        "myhome",
        "2026",
        "CONV",
        {
            "source": "myhome",
            "notice_id": "CONV",
            "title": "서울 분양전환 임대",
            "detail_url": "u",
            "posted_date": "2026-06-01",
            "category": "APT 분양전환 가능임대",
            "region": "서울",
            "attachments": [],
            "raw": {"normalized": {"supplyType": "APT 분양전환 가능임대"}},
        },
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    data = c.get("/notices", params={"limit": 10}).json()
    assert data["total"] == 1
    assert data["items"][0]["noticeId"] == "CONV"
    assert c.get("/notices/applyhome/SALE").status_code == 404


def test_recommend_region_is_hard_filter(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw,
        "myhome",
        "2026",
        "GG",
        {
            "source": "myhome",
            "notice_id": "GG",
            "title": "경기 행복주택",
            "detail_url": "u",
            "posted_date": "2026-06-01",
            "category": "행복주택",
            "region": "경기도",
            "attachments": [],
            "raw": {"normalized": {"supplyType": "행복주택", "depositKRW": 10000000, "monthlyRentKRW": 100000}},
        },
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    r = c.post("/recommend", json={"region": "서울", "maxMonthlyRentKRW": 500000, "limit": 5})
    assert r.json()["total"] == 0
    assert r.json()["items"] == []


def test_zero_price_shown_as_null(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw,
        "myhome",
        "2026",
        "ZERO",
        {
            "source": "myhome",
            "notice_id": "ZERO",
            "title": "서울 매입임대",
            "detail_url": "u",
            "posted_date": "2026-06-01",
            "category": "매입임대",
            "region": "서울",
            "attachments": [],
            "raw": {"normalized": {"supplyType": "매입임대", "depositKRW": 0, "monthlyRentKRW": 0}},
        },
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    d = c.get("/notices/myhome/ZERO").json()
    assert d["depositKRW"] is None
    assert d["monthlyRentKRW"] is None


def _notice(notice_id: str, normalized: dict) -> dict:
    return {
        "source": "myhome",
        "notice_id": notice_id,
        "title": f"공고 {notice_id}",
        "detail_url": "u",
        "posted_date": "2026-06-01",
        "category": "행복주택",
        "region": "경기도",
        "attachments": [],
        "raw": {"normalized": {"supplyType": "행복주택", **normalized}},
    }


def test_status_is_computed_from_dates(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "CLOSED", _notice("CLOSED", {"applyEnd": "2026-05-01"}))
    _write(
        raw, "myhome", "2026", "UPCOMING",
        _notice("UPCOMING", {"applyStart": "2026-12-01", "applyEnd": "2026-12-31"}),
    )
    _write(
        raw, "myhome", "2026", "OPEN",
        _notice("OPEN", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31"}),
    )
    _write(raw, "myhome", "2026", "UNKNOWN", _notice("UNKNOWN", {}))
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    assert c.get("/notices/myhome/CLOSED").json()["status"] == "마감"
    assert c.get("/notices/myhome/UPCOMING").json()["status"] == "예정"
    assert c.get("/notices/myhome/OPEN").json()["status"] == "접수중"
    assert c.get("/notices/myhome/UNKNOWN").json()["status"] == "미정"


def test_search_filters_by_status(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "CLOSED", _notice("CLOSED", {"applyEnd": "2026-05-01"}))
    _write(
        raw, "myhome", "2026", "OPEN",
        _notice("OPEN", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31"}),
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    assert c.get("/notices", params={"limit": 10}).json()["total"] == 2
    open_only = c.get("/notices", params={"limit": 10, "status": "접수중"}).json()
    assert open_only["total"] == 1
    assert open_only["items"][0]["noticeId"] == "OPEN"


def test_recommend_defaults_to_open_and_can_override(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw, "myhome", "2026", "CLOSED",
        _notice("CLOSED", {"applyEnd": "2026-05-01", "depositKRW": 1000, "monthlyRentKRW": 100}),
    )
    _write(
        raw, "myhome", "2026", "OPEN",
        _notice("OPEN", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31", "depositKRW": 1000, "monthlyRentKRW": 100}),
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    default = c.post("/recommend", json={"region": "경기", "limit": 10}).json()
    assert [i["noticeId"] for i in default["items"]] == ["OPEN"]
    all_status = c.post("/recommend", json={"region": "경기", "limit": 10, "status": "전체"}).json()
    assert all_status["total"] == 2


def test_superseded_notice_is_dropped(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "OLD", _notice("OLD", {"applyEnd": "2026-07-31"}))
    _write(
        raw, "myhome", "2026", "NEW",
        _notice("NEW", {"applyEnd": "2026-07-31", "supersedes": "OLD"}),
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    data = c.get("/notices", params={"limit": 10}).json()
    assert data["total"] == 1
    assert data["items"][0]["noticeId"] == "NEW"
    assert c.get("/notices/myhome/OLD").status_code == 404


def _lh(notice_id: str, normalized: dict) -> dict:
    return {
        "source": "lh_apply",
        "notice_id": notice_id,
        "title": f"LH {notice_id}",
        "detail_url": "u",
        "posted_date": "2026-06-01",
        "category": "행복주택",
        "region": "경기도",
        "attachments": [],
        "raw": {"normalized": {"supplyType": "행복주택", "applyEnd": "2026-07-31", **normalized}},
    }


def test_cross_source_lh_twin_dropped_keeps_myhome(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "M1", _notice("M1", {"applyEnd": "2026-07-31", "lhPanId": "LH-1"}))
    _write(raw, "lh_apply", "2026", "LH-1", _lh("LH-1", {}))
    _write(raw, "lh_apply", "2026", "LH-9", _lh("LH-9", {}))
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    ids = sorted(i["noticeId"] for i in c.get("/notices", params={"limit": 10}).json()["items"])
    assert ids == ["LH-9", "M1"]
    assert c.get("/notices/lh_apply/LH-1").status_code == 404


def test_non_housing_daycare_excluded(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "lh_apply", "2026", "DC", _lh("DC", {"supplyType": "가정어린이집"}))
    _write(raw, "lh_apply", "2026", "OK", _lh("OK", {"supplyType": "국민임대"}))
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    data = c.get("/notices", params={"limit": 10}).json()
    assert data["total"] == 1
    assert data["items"][0]["noticeId"] == "OK"
    assert c.get("/notices/lh_apply/DC").status_code == 404


def test_supersede_does_not_cross_source(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    # myhome head whose supersedes id collides with an unrelated lh_apply id
    _write(raw, "myhome", "2026", "MA", _notice("MA", {"applyEnd": "2026-07-31", "supersedes": "X1"}))
    _write(raw, "lh_apply", "2026", "X1", _lh("X1", {"supplyType": "국민임대"}))
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    ids = sorted(i["noticeId"] for i in c.get("/notices", params={"limit": 10}).json()["items"])
    assert ids == ["MA", "X1"]
    assert c.get("/notices/lh_apply/X1").status_code == 200


def test_invalid_status_is_rejected(tmp_path: Path) -> None:
    c = _client(tmp_path)
    assert c.get("/notices", params={"limit": 10, "status": "접수"}).status_code == 422
    assert c.post("/recommend", json={"limit": 5, "status": "접수"}).status_code == 422


def test_cross_source_drops_full_lh_chain(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "MOLD", _notice("MOLD", {"applyEnd": "2026-07-31", "lhPanId": "LH-A"}))
    _write(
        raw, "myhome", "2026", "MNEW",
        _notice("MNEW", {"applyEnd": "2026-07-31", "lhPanId": "LH-B", "supersedes": "MOLD"}),
    )
    _write(raw, "lh_apply", "2026", "LH-A", _lh("LH-A", {}))
    _write(raw, "lh_apply", "2026", "LH-B", _lh("LH-B", {}))
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    ids = sorted(i["noticeId"] for i in c.get("/notices", params={"limit": 10}).json()["items"])
    assert ids == ["MNEW"]


def _dated(notice_id: str, posted: str, normalized: dict) -> dict:
    return {
        "source": "myhome",
        "notice_id": notice_id,
        "title": f"공고 {notice_id}",
        "detail_url": "u",
        "posted_date": posted,
        "category": "행복주택",
        "region": "경기도",
        "attachments": [],
        "raw": {"normalized": {"supplyType": "행복주택", **normalized}},
    }


def test_search_default_sort_open_then_newest(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "CLOSED_OLD", _dated("CLOSED_OLD", "2026-04-01", {"applyEnd": "2026-05-01"}))
    _write(
        raw, "myhome", "2026", "OPEN_OLD",
        _dated("OPEN_OLD", "2026-06-02", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31"}),
    )
    _write(
        raw, "myhome", "2026", "OPEN_NEW",
        _dated("OPEN_NEW", "2026-06-20", {"applyStart": "2026-06-10", "applyEnd": "2026-07-31"}),
    )
    _write(
        raw, "myhome", "2026", "UPCOMING",
        _dated("UPCOMING", "2026-06-15", {"applyStart": "2026-12-01", "applyEnd": "2026-12-31"}),
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    ids = [i["noticeId"] for i in c.get("/notices", params={"limit": 10}).json()["items"]]
    assert ids == ["OPEN_NEW", "OPEN_OLD", "UPCOMING", "CLOSED_OLD"]


def test_search_offset_paginates(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    for i in range(3):
        _write(
            raw, "myhome", "2026", f"N{i}",
            _dated(f"N{i}", f"2026-06-0{i + 1}", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31"}),
        )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    page1 = c.get("/notices", params={"limit": 1, "offset": 0}).json()
    page2 = c.get("/notices", params={"limit": 1, "offset": 1}).json()
    assert page1["total"] == 3 and page2["total"] == 3
    assert page1["items"][0]["noticeId"] == "N2"
    assert page2["items"][0]["noticeId"] == "N1"


def test_search_limit_over_200_is_clamped_not_rejected(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/notices", params={"limit": 5000})
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_search_sort_latest_ignores_status(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(raw, "myhome", "2026", "CLOSED_NEW", _dated("CLOSED_NEW", "2026-06-25", {"applyEnd": "2026-05-01"}))
    _write(
        raw, "myhome", "2026", "OPEN_OLD",
        _dated("OPEN_OLD", "2026-06-01", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31"}),
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    default = [i["noticeId"] for i in c.get("/notices", params={"limit": 10}).json()["items"]]
    assert default == ["OPEN_OLD", "CLOSED_NEW"]
    latest = [i["noticeId"] for i in c.get("/notices", params={"limit": 10, "sort": "latest"}).json()["items"]]
    assert latest == ["CLOSED_NEW", "OPEN_OLD"]


def test_search_sort_deadline_open_first_soonest(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write(
        raw, "myhome", "2026", "OPEN_LATER",
        _dated("OPEN_LATER", "2026-06-10", {"applyStart": "2026-06-01", "applyEnd": "2026-08-31"}),
    )
    _write(
        raw, "myhome", "2026", "OPEN_SOON",
        _dated("OPEN_SOON", "2026-06-05", {"applyStart": "2026-06-01", "applyEnd": "2026-07-05"}),
    )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    ids = [i["noticeId"] for i in c.get("/notices", params={"limit": 10, "sort": "deadline"}).json()["items"]]
    assert ids == ["OPEN_SOON", "OPEN_LATER"]


def test_invalid_sort_is_rejected(tmp_path: Path) -> None:
    c = _client(tmp_path)
    assert c.get("/notices", params={"limit": 10, "sort": "bogus"}).status_code == 422


def test_search_offset_past_end_keeps_total(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    for i in range(3):
        _write(
            raw, "myhome", "2026", f"N{i}",
            _dated(f"N{i}", f"2026-06-0{i + 1}", {"applyStart": "2026-06-01", "applyEnd": "2026-07-31"}),
        )
    c = TestClient(create_app(NoticeStore(raw, today=TODAY)))
    r = c.get("/notices", params={"limit": 5, "offset": 100}).json()
    assert r["total"] == 3
    assert r["items"] == []
