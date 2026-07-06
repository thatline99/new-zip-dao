"""수집 데이터의 dataclass 기반 모델."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class AssetKind(str, Enum):
    """다운로드 첨부 종류."""

    PDF = "pdf"
    HWP = "hwp"
    IMAGE = "image"
    ZIP = "zip"
    DOC = "doc"
    OTHER = "other"

    @classmethod
    def from_filename(cls, name: str) -> "AssetKind":
        """파일명 확장자로 AssetKind 를 추정한다."""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        mapping = {
            "pdf": cls.PDF,
            "hwp": cls.HWP,
            "hwpx": cls.HWP,
            "jpg": cls.IMAGE,
            "jpeg": cls.IMAGE,
            "png": cls.IMAGE,
            "gif": cls.IMAGE,
            "webp": cls.IMAGE,
            "bmp": cls.IMAGE,
            "tif": cls.IMAGE,
            "tiff": cls.IMAGE,
            "zip": cls.ZIP,
            "doc": cls.DOC,
            "docx": cls.DOC,
            "xls": cls.DOC,
            "xlsx": cls.DOC,
            "ppt": cls.DOC,
            "pptx": cls.DOC,
        }
        return mapping.get(ext, cls.OTHER)


@dataclass
class Attachment:
    """공고 첨부/이미지 한 건."""

    url: str
    filename: str
    kind: AssetKind = AssetKind.OTHER
    local_path: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    downloaded_at: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        """dict(JSON 직렬화용)으로 변환한다."""
        d = asdict(self)
        d["kind"] = self.kind.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Attachment":
        """dict 로부터 Attachment 를 만든다."""
        d = dict(d)
        if "kind" in d and d["kind"] is not None:
            d["kind"] = AssetKind(d["kind"])
        return cls(**d)


@dataclass
class NoticeStub:
    """목록 단계에서 얻는 공고 요약(상세 수집 전)."""

    notice_id: str
    title: str
    detail_url: str
    posted_date: str | None = None
    category: str | None = None
    region: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class Notice:
    """상세 수집까지 끝난 공고 한 건."""

    source: str
    notice_id: str
    title: str
    detail_url: str
    posted_date: str | None = None
    category: str | None = None
    region: str | None = None
    detail_html_path: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    crawled_at: str | None = None

    def to_dict(self) -> dict:
        """dict(JSON 직렬화용)으로 변환한다."""
        d = asdict(self)
        d["attachments"] = [a.to_dict() for a in self.attachments]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Notice":
        """dict 로부터 Notice 를 만든다."""
        d = dict(d)
        d["attachments"] = [Attachment.from_dict(a) for a in d.get("attachments", [])]
        return cls(**d)
