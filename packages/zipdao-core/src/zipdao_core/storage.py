"""원본 산출물 저장소.

디스크 레이아웃 (자세한 내용은 docs/data-layout.md):

    {data_dir}/raw/{source}/{YYYY}/{notice_id}/
        manifest.json          # 공고 메타 + 첨부 목록 + 체크섬 + 수집시각
        detail.html            # 상세 페이지 스냅샷(있을 때)
        attachments/<파일명>   # PDF·HWP·ZIP 등
        images/<파일명>        # 공고 내 이미지

manifest.json 존재 = 수집 완료로 간주(멱등 재실행 시 스킵).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from zipdao_core.models import AssetKind, Attachment, Notice

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, *, fallback: str = "file") -> str:
    """경로 구분자/제어문자를 제거해 안전한 파일명으로. 한글은 유지."""
    name = name.strip().replace(" ", " ")
    name = _UNSAFE.sub("_", name)
    name = name.strip(". ")
    name = re.sub(r"\s+", " ", name)
    return name[:200] if name else fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = Path(raw_dir)

    def notice_dir(self, source: str, notice_id: str, year: str | None) -> Path:
        year = year or "unknown"
        safe_id = sanitize_filename(notice_id, fallback="notice")
        return self.raw_dir / source / year / safe_id

    def manifest_path(self, source: str, notice_id: str, year: str | None) -> Path:
        return self.notice_dir(source, notice_id, year) / "manifest.json"

    def is_crawled(self, source: str, notice_id: str, year: str | None) -> bool:
        return self.manifest_path(source, notice_id, year).exists()

    def save_asset(
        self,
        notice_dir: Path,
        attachment: Attachment,
        data: bytes,
    ) -> Attachment:
        """바이트를 저장하고 체크섬/크기/경로를 채운 Attachment를 반환."""
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
        notice_dir.mkdir(parents=True, exist_ok=True)
        dest = notice_dir / "detail.html"
        if isinstance(html, bytes):
            dest.write_bytes(html)
        else:
            dest.write_text(html, encoding="utf-8")
        return str(dest.relative_to(self.raw_dir))

    def write_manifest(self, notice: Notice) -> Path:
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
        path = self.manifest_path(source, notice_id, year)
        if not path.exists():
            return None
        return Notice.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _unique_path(path: Path) -> Path:
        """같은 이름이 있으면 ` (2)`, ` (3)` … 을 붙여 충돌 회피."""
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        for i in range(2, 1000):
            candidate = path.with_name(f"{stem} ({i}){suffix}")
            if not candidate.exists():
                return candidate
        return path.with_name(f"{stem} ({_now_iso()}){suffix}")
