"""소스(공고 사이트) 레지스트리.

문서(한국 주택 공고 사이트 분류)에 정리된 모든 출처를 선언적으로 등록한다.
`crawler`가 None이면 아직 사이트별 구현(셀렉터/엔드포인트)이 채워지지 않은 상태로,
실측(probing) 후 sources/ 아래에 구현체를 추가하고 여기 연결한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from zipdao_crawlers.base import BaseCrawler


@dataclass(frozen=True)
class SourceInfo:
    key: str
    name: str
    category: str
    base_url: str
    notes: str = ""
    crawler: type[BaseCrawler] | None = None

    @property
    def implemented(self) -> bool:
        return self.crawler is not None


# 카테고리 라벨
PORTAL = "전국 통합 청약 포털"
LOCAL = "지역 도시·개발공사"
PRIVATE = "민간임대·공공지원 통합"

SOURCES: list[SourceInfo] = [
    # ── 전국 통합 청약 포털 (핵심) ──
    SourceInfo(
        key="lh_apply",
        name="LH청약플러스",
        category=PORTAL,
        base_url="https://apply.lh.or.kr",
        notes="국민·공공·행복·매입임대·든든전세 등 LH 공고 대부분. 공고문 PDF/HWP 첨부.",
    ),
    SourceInfo(
        key="sh_ish",
        name="SH 인터넷청약시스템",
        category=PORTAL,
        base_url="https://www.i-sh.co.kr/app",
        notes="서울주택도시개발공사. 사회주택·예술인마을·협동조합주택 등.",
    ),
    SourceInfo(
        key="applyhome",
        name="청약홈",
        category=PORTAL,
        base_url="https://www.applyhome.co.kr",
        notes="한국부동산원. 분양·공공임대 통합 청약. API(청약홈 분양정보 15098547) 병행 검토.",
    ),
    SourceInfo(
        key="youth_seoul",
        name="서울 청년안심주택",
        category=PORTAL,
        base_url="https://soco.seoul.go.kr/youth",
        notes="서울시 공동체주택플랫폼. 청년안심주택 민간임대 공고.",
    ),
    # ── 지역 도시·개발공사 ──
    SourceInfo(
        key="gh",
        name="경기주택도시공사(GH)",
        category=LOCAL,
        base_url="https://www.gh.or.kr",
        notes="다산 포레스트·김포한강 등.",
    ),
    SourceInfo(
        key="udc",
        name="울산도시공사(UDC)",
        category=LOCAL,
        base_url="https://www.udc.or.kr",
        notes="율동 위드유아파트 등.",
    ),
    SourceInfo(
        key="daejeon",
        name="대전도시공사",
        category=LOCAL,
        base_url="https://www.dcco.kr",
        notes="청년매입임대 등.",
    ),
    SourceInfo(
        key="gndc",
        name="경남개발공사",
        category=LOCAL,
        base_url="https://www.gndc.co.kr",
        notes="거북이집 셰어하우스 등.",
    ),
    # ── 민간임대·공공지원 통합 ──
    SourceInfo(
        key="myhome",
        name="마이홈포털",
        category=PRIVATE,
        base_url="https://www.myhome.go.kr",
        notes="국토부 주거복지 통합 포털. LH·SH·지자체·민간 공고 통합 검색(공공지원 민간임대 포함).",
    ),
]

_BY_KEY = {s.key: s for s in SOURCES}


def iter_sources() -> list[SourceInfo]:
    return list(SOURCES)


def get_source(key: str) -> SourceInfo:
    try:
        return _BY_KEY[key]
    except KeyError:
        raise KeyError(
            f"알 수 없는 소스: {key!r}. 사용 가능: {', '.join(_BY_KEY)}"
        ) from None
