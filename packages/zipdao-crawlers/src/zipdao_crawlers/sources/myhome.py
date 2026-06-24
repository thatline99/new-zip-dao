"""마이홈포털 공공주택 모집공고(공공임대주택 단지·세대 정보) — 공공데이터 API.

서비스: 국토교통부_마이홈포털 공공주택 모집공고 조회 (data.go.kr 15108420)
  엔드포인트: http://apis.data.go.kr/1613000/HWSPR04/rentalHouseGwList
  필수: serviceKey, brtcCode(광역시도 2자리), signguCode(시군구 3자리)
  선택: numOfRows, pageNo, houseTy(주택유형), suplyTy(공급유형), 전세형여부, 월임대료구분
  응답: response.body.item[] — 단지/세대 단위(기관·주소·공급유형·면적·보증금·월임대료).

지역코드는 참고문서에서 추출해 _myhome_regions.REGIONS 에 임베드(255개 시군구).
PDF 공고문이 아니라 **구조화된 공공임대주택 데이터**를 단지별 manifest로 저장한다.
"""

from __future__ import annotations

from collections.abc import Iterator

from zipdao_core.config import load_settings
from zipdao_core.models import Notice, NoticeStub
from zipdao_crawlers.base import BaseCrawler
from zipdao_crawlers.sources._myhome_regions import REGIONS

LIST_EP = "http://apis.data.go.kr/1613000/HWSPR04/rentalHouseGwList"
NUM_ROWS = 1000


class MyhomeCrawler(BaseCrawler):
    key = "myhome"
    name = "마이홈 공공주택(공공데이터 API)"
    base_url = "https://www.myhome.go.kr"

    def __init__(self, http) -> None:
        super().__init__(http)
        self._key = load_settings().data_go_kr_service_key
        if not self._key:
            raise RuntimeError(
                "DATA_GO_KR_SERVICE_KEY 미설정(.env). 공공데이터포털 인증키가 필요합니다."
            )

    def iter_notices(self, since: int | None, until: int | None) -> Iterator[NoticeStub]:
        # 단지정보 API라 게시일이 없어 연도 필터(since/until)는 적용하지 않는다.
        for brtc, signgu, sido_nm, sgg_nm in REGIONS:
            rows = self._fetch_region(brtc, signgu)
            if not rows:
                continue
            by_complex: dict[str, list[dict]] = {}
            for it in rows:
                key = str(it.get("hsmpSn") or it.get("hsmpNm") or "").strip()
                by_complex.setdefault(key, []).append(it)
            for hsmp_sn, units in by_complex.items():
                head = units[0]
                yield NoticeStub(
                    notice_id=f"{brtc}{signgu}-{hsmp_sn}",
                    title=(head.get("hsmpNm") or "").strip(),
                    detail_url="",
                    posted_date=None,
                    category=head.get("suplyTyNm"),
                    region=f"{sido_nm} {sgg_nm}",
                    extra={"head": head, "units": units},
                )

    def _fetch_region(self, brtc: str, signgu: str) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while True:
            resp = self.http.get(
                LIST_EP,
                params={
                    "serviceKey": self._key,
                    "brtcCode": brtc,
                    "signguCode": signgu,
                    "numOfRows": NUM_ROWS,
                    "pageNo": page,
                },
            )
            items, total = self.parse_items(resp.json())
            if not items:
                break
            rows.extend(items)
            if page * NUM_ROWS >= total:
                break
            page += 1
        return rows

    @staticmethod
    def parse_items(data) -> tuple[list[dict], int]:
        """response.body.item[] 와 totalCount 추출. NODATA/오류 시 ([],0). 순수 함수."""
        if not isinstance(data, dict):
            return [], 0
        body = data.get("response", {}).get("body") or {}
        items = body.get("item") or []
        if isinstance(items, dict):
            items = [items]
        total = int(body.get("totalCount") or 0)
        return items, total

    def fetch_detail(self, stub: NoticeStub) -> Notice:
        return Notice(
            source=self.key,
            notice_id=stub.notice_id,
            title=stub.title,
            detail_url=stub.detail_url,
            posted_date=None,
            category=stub.category,
            region=stub.region,
            attachments=[],
            raw={"단지": stub.extra["head"], "세대목록": stub.extra["units"]},
        )
