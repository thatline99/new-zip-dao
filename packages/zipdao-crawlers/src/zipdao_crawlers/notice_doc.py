"""공고문 PDF에서 나이 자격과 임대 조건을 보수적으로 추출한다."""

from __future__ import annotations

import io
import logging
import re

logger = logging.getLogger("zipdao.notice_doc")

_AGE_RANGE_PATTERNS = [
    re.compile(r"(?:만\s*)?(\d{1,2})\s*세\s*이상\s*(?:만\s*)?(\d{1,2})\s*세\s*이하"),
    re.compile(r"만\s*(\d{1,2})\s*세?\s*[~∼〜]\s*(?:만\s*)?(\d{1,2})\s*세"),
]

_UNIT_MARKER = re.compile(r"단위\s*[:：]?\s*(만원|천원)")
_UNIT_KRW = {"만원": 10_000, "천원": 1_000}
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d+)?")

_MIN_DEPOSIT_KRW = 5_000_000
_RENT_RANGE_KRW = (10_000, 3_000_000)


_MIN_ADULT_MAX_AGE = 19
_CHILD_CONTEXT = ("자녀", "영유아", "아동", "어린이")


def extract_age_range(text: str) -> tuple[int, int] | None:
    """상·하한이 모두 명시된 입주자 나이 범위를 찾는다(없으면 None).

    상한이 19세 미만이거나 주변에 자녀 문맥이 있으면 입주자 자격이 아니라고 보고 버린다.
    """
    lows: list[int] = []
    highs: list[int] = []
    for pattern in _AGE_RANGE_PATTERNS:
        for m in pattern.finditer(text):
            lo, hi = int(m.group(1)), int(m.group(2))
            if not (1 <= lo < hi <= 120):
                continue
            if hi < _MIN_ADULT_MAX_AGE:
                continue
            context = text[max(0, m.start() - 15) : m.end() + 15]
            if any(word in context for word in _CHILD_CONTEXT):
                continue
            lows.append(lo)
            highs.append(hi)
    if not lows:
        return None
    return min(lows), max(highs)


def extract_min_deposit_rent(pages: list[str]) -> tuple[int, int] | None:
    """단위가 표기된 임대조건 표에서 최저 보증금과 짝 월임대료를 원 단위로 찾는다."""
    best: tuple[int, int] | None = None
    for text in pages:
        marker = _UNIT_MARKER.search(text)
        if not marker or "보증금" not in text or "임대료" not in text:
            continue
        unit = _UNIT_KRW[marker.group(1)]
        for line in text.splitlines():
            if "㎡" not in line:
                continue
            tail = line.split("㎡", 1)[1]
            nums = [float(n.replace(",", "")) for n in _NUMBER.findall(tail)]
            for a, b in zip(nums, nums[1:], strict=False):
                deposit = int(round(a * unit))
                rent = int(round(b * unit))
                if deposit < _MIN_DEPOSIT_KRW or rent >= deposit:
                    continue
                if not _RENT_RANGE_KRW[0] <= rent <= _RENT_RANGE_KRW[1]:
                    continue
                if best is None or (deposit, rent) < best:
                    best = (deposit, rent)
    return best


def parse_notice_pdf(data: bytes) -> dict:
    """PDF 본문에서 확신할 수 있는 필드만 담은 dict 를 돌려준다."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    out: dict = {}
    age = extract_age_range("\n".join(pages))
    if age:
        out["minAge"], out["maxAge"] = age
    price = extract_min_deposit_rent(pages)
    if price:
        out["depositKRW"], out["monthlyRentKRW"] = price
    return out


def pick_notice_pdf(attachments: list[dict]) -> dict | None:
    """첨부 중 파싱할 공고문 PDF 하나를 고른다 — '공고' 파일명 우선."""
    pdfs = [
        a
        for a in attachments
        if a.get("kind") == "pdf" or str(a.get("filename") or "").lower().endswith(".pdf")
    ]
    if not pdfs:
        return None
    for a in pdfs:
        if "공고" in str(a.get("filename") or ""):
            return a
    return pdfs[0]
