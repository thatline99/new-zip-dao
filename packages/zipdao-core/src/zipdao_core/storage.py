"""원본 수집 산출물(manifest·첨부·이미지)의 디스크 저장소."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from zipdao_core.models import AssetKind, Attachment, Notice

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, *, fallback: str = "file", max_len: int = 200) -> str:
    """경로 구분자/제어문자를 제거해 안전한 파일명으로 바꾼다."""
    name = name.strip().replace(" ", " ")
    name = _UNSAFE.sub("_", name)
    name = name.strip(". ")
    name = re.sub(r"\s+", " ", name)
    if not name:
        return fallback
    if len(name) <= max_len:
        return name
    stem, dot, ext = name.rpartition(".")
    if dot and 1 <= len(ext) <= 10:
        keep = max(1, max_len - len(ext) - 1)
        return f"{stem[:keep]}.{ext}"
    return name[:max_len]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Storage:
    """수집 산출물을 디스크에 저장/조회하는 저장소."""

    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = Path(raw_dir)

    def notice_dir(self, source: str, notice_id: str, year: str | None) -> Path:
        """공고 한 건의 저장 디렉터리 경로를 만든다."""
        year = year or "unknown"
        safe_id = sanitize_filename(notice_id, fallback="notice")
        return self.raw_dir / source / year / safe_id

    def manifest_path(self, source: str, notice_id: str, year: str | None) -> Path:
        """공고 manifest.json 의 경로를 만든다."""
        return self.notice_dir(source, notice_id, year) / "manifest.json"

    def is_crawled(self, source: str, notice_id: str, year: str | None) -> bool:
        """해당 공고가 이미 수집되었는지 확인한다."""
        return self.manifest_path(source, notice_id, year).exists()

    def save_asset(
        self,
        notice_dir: Path,
        attachment: Attachment,
        data: bytes,
    ) -> Attachment:
        """바이트를 저장하고 체크섬/크기/경로를 채운 Attachment 를 반환한다."""
        subdir = "images" if attachment.kind is AssetKind.IMAGE else "attachments"
        dest_dir = notice_dir / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)

        filename = sanitize_filename(attachment.filename, fallback="asset")
        dest = self._unique_path(dest_dir / filename)
        dest.write_bytes(data)

        attachment.local_path = str(dest.relative_to(self.raw_dir))
        attachment.sha256 = hashlib.sha256(data).hexdigest()
        attachment.bytes = len(data)
        attachment.downloaded_at = _now_iso()
        return attachment

    def save_detail_html(self, notice_dir: Path, html: str | bytes) -> str:
        """상세 페이지 HTML 스냅샷을 저장한다."""
        notice_dir.mkdir(parents=True, exist_ok=True)
        dest = notice_dir / "detail.html"
        if isinstance(html, bytes):
            dest.write_bytes(html)
        else:
            dest.write_text(html, encoding="utf-8")
        return str(dest.relative_to(self.raw_dir))

    def write_manifest(self, notice: Notice) -> Path:
        """공고를 manifest.json 으로 저장한다."""
        year = (notice.posted_date or "")[:4] or None
        ndir = self.notice_dir(notice.source, notice.notice_id, year)
        ndir.mkdir(parents=True, exist_ok=True)
        if notice.crawled_at is None:
            notice.crawled_at = _now_iso()
        path = ndir / "manifest.json"
        path.write_text(
            json.dumps(notice.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def read_manifest(self, source: str, notice_id: str, year: str | None) -> Notice | None:
        """manifest.json 을 읽어 Notice 로 되돌린다."""
        path = self.manifest_path(source, notice_id, year)
        if not path.exists():
            return None
        return Notice.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        for i in range(2, 1000):
            candidate = path.with_name(f"{stem} ({i}){suffix}")
            if not candidate.exists():
                return candidate
        return path.with_name(f"{stem} ({_now_iso()}){suffix}")
