"""소스(공고 사이트) 레지스트리를 선언적으로 등록한다."""

from __future__ import annotations

from dataclasses import dataclass

from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.sources.applyhome import ApplyhomeCrawler
from zipdao_crawlers.sources.gndc import GndcCrawler
from zipdao_crawlers.sources.lh_apply import LhApplyCrawler
from zipdao_crawlers.sources.myhome import MyhomeCrawler
from zipdao_crawlers.sources.sh_ish import ShIshCrawler
from zipdao_crawlers.sources.youth_seoul import YouthSeoulCrawler


@dataclass(frozen=True)
class SourceInfo:
    """소스(사이트) 한 곳의 메타데이터와 크롤러 연결 정보."""

    key: str
    name: str
    category: str
    base_url: str
    notes: str = ""
    crawler: type[BaseCrawler] | None = None

    @property
    def implemented(self) -> bool:
        """크롤러 구현체가 연결되어 있는지 여부."""
        return self.crawler is not None


PORTAL = "전국 통합 청약 포털"
LOCAL = "지역 도시·개발공사"
PRIVATE = "민간임대·공공지원 통합"

SOURCES: list[SourceInfo] = [
    SourceInfo(
        key="lh_apply",
        name="LH청약플러스",
        category=PORTAL,
        base_url="https://apply.lh.or.kr",
        notes=(
            "공공데이터 API(15058530)로 공고 메타데이터+DTL_URL 수집. "
            "원본 PDF는 robots 제한으로 제외."
        ),
        crawler=LhApplyCrawler,
    ),
    SourceInfo(
        key="sh_ish",
        name="SH 인터넷청약시스템",
        category=PORTAL,
        base_url="https://www.i-sh.co.kr/app",
        notes=(
            "서울주택도시개발공사. 사회주택·예술인마을·협동조합주택 등. "
            "공고 게시판(주택임대·주택분양) POST 순회 + innoFD.do 첨부 다운로드."
        ),
        crawler=ShIshCrawler,
    ),
    SourceInfo(
        key="applyhome",
        name="청약홈",
        category=PORTAL,
        base_url="https://www.applyhome.co.kr",
        notes="한국부동산원 odcloud API(15098547). APT 분양/임대 2804건 2020~2026 메타+PBLANC_URL.",
        crawler=ApplyhomeCrawler,
    ),
    SourceInfo(
        key="youth_seoul",
        name="서울 청년안심주택",
        category=PORTAL,
        base_url="https://soco.seoul.go.kr/youth",
        notes=(
            "서울시 공동체주택플랫폼. 청년안심주택 민간임대 공고. (bbsListJson AJAX + view.do 첨부)"
        ),
        crawler=YouthSeoulCrawler,
    ),
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
        base_url="https://www.umca.co.kr",
        notes="율동 위드유아파트 등. 구 udc.or.kr 에서 도메인 이전(2026-07).",
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
        notes=(
            "거북이집 셰어하우스 등. getBbsArticleList.do JSON 목록(임대·분양 분류) + "
            "download.do 첨부. 분양 게시판은 주택 제목만 필터."
        ),
        crawler=GndcCrawler,
    ),
    SourceInfo(
        key="myhome",
        name="마이홈포털",
        category=PRIVATE,
        base_url="https://www.myhome.go.kr",
        notes=(
            "국토부 마이홈 API(15108420, HWSPR02 rsdtRcritNtcList). "
            "전국 공공임대 모집공고(보증금·월세·공급유형)."
        ),
        crawler=MyhomeCrawler,
    ),
]

_BY_KEY = {s.key: s for s in SOURCES}


def iter_sources() -> list[SourceInfo]:
    """등록된 전체 소스 목록을 반환한다."""
    return list(SOURCES)


def get_source(key: str) -> SourceInfo:
    """key 에 해당하는 소스 정보를 찾는다. 없으면 KeyError."""
    try:
        return _BY_KEY[key]
    except KeyError:
        raise KeyError(f"알 수 없는 소스: {key!r}. 사용 가능: {', '.join(_BY_KEY)}") from None
