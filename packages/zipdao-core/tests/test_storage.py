from __future__ import annotations

from zipdao_core.models import AssetKind, Attachment, Notice
from zipdao_core.storage import Storage, sanitize_filename


def _make_notice() -> Notice:
    return Notice(
        source="lh_apply",
        notice_id="2024-0001",
        title="행복주택 입주자 모집공고",
        detail_url="https://apply.lh.or.kr/notice/2024-0001",
        posted_date="2024-03-15",
        category="행복주택",
        region="경기",
    )


def test_sanitize_filename_strips_path_separators():
    assert "/" not in sanitize_filename("a/b/c.pdf")
    assert sanitize_filename("  ..hidden  ") == "hidden"
    assert sanitize_filename("") == "file"


def test_sanitize_filename_preserves_extension_on_truncation():
    long_name = "가" * 300 + ".pdf"
    out = sanitize_filename(long_name)
    assert len(out) <= 200
    assert out.endswith(".pdf")  # 확장자 보존 → 더블클릭 시 PDF로 열림


def test_year_partition_and_manifest_roundtrip(tmp_path):
    storage = Storage(tmp_path / "raw")
    notice = _make_notice()

    assert storage.is_crawled("lh_apply", "2024-0001", "2024") is False

    path = storage.write_manifest(notice)
    assert path.exists()
    assert path.parent.parent.name == "2024"  # 연도 파티션
    assert storage.is_crawled("lh_apply", "2024-0001", "2024") is True

    restored = storage.read_manifest("lh_apply", "2024-0001", "2024")
    assert restored is not None
    assert restored.title == notice.title
    assert restored.crawled_at is not None


def test_save_asset_records_checksum_and_routes_images(tmp_path):
    storage = Storage(tmp_path / "raw")
    notice = _make_notice()
    ndir = storage.notice_dir(notice.source, notice.notice_id, "2024")

    pdf = Attachment(url="http://x/a.pdf", filename="공고문.pdf", kind=AssetKind.PDF)
    img = Attachment(url="http://x/p.jpg", filename="평면도.jpg", kind=AssetKind.IMAGE)

    storage.save_asset(ndir, pdf, b"%PDF-1.4 ...")
    storage.save_asset(ndir, img, b"\xff\xd8\xff jpeg")

    assert pdf.sha256 and pdf.bytes == len(b"%PDF-1.4 ...")
    assert pdf.local_path.endswith("attachments/공고문.pdf")
    assert img.local_path.endswith("images/평면도.jpg")
    assert (ndir / "attachments" / "공고문.pdf").exists()
    assert (ndir / "images" / "평면도.jpg").exists()


def test_save_asset_dedupes_colliding_names(tmp_path):
    storage = Storage(tmp_path / "raw")
    ndir = storage.notice_dir("lh_apply", "2024-0001", "2024")
    a = Attachment(url="http://x/1", filename="첨부.pdf", kind=AssetKind.PDF)
    b = Attachment(url="http://x/2", filename="첨부.pdf", kind=AssetKind.PDF)
    storage.save_asset(ndir, a, b"one")
    storage.save_asset(ndir, b, b"two")
    assert a.local_path != b.local_path
    assert (ndir / "attachments" / "첨부.pdf").exists()
    assert (ndir / "attachments" / "첨부 (2).pdf").exists()
