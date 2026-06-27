# new-zip-dao

**공공임대 공고 수집 모노레포 (크롤러 + 파이프라인)**

국내 공공·지원 임대주택 공고를 **사이트별로 5년치 전부**(공고문 PDF·HWP, 공고 내 이미지 포함) 수집·정규화하여,
공공임대 MCP 서버가 검색·추천·RAG·법령 응답에 쓸 데이터를 만든다. (MCP 서버 본체는 별도 저장소)

> AGENTIC PLAYER 10 (카카오 × 과기정통부 PlayMCP 공모전) 출품작. 벤치마크: [내집다오](https://myzipdao.com/)
>
> 현재 단계: **로컬에서 크롤링 가능한 기반** 구축. (홈/OCI 서버 배포는 추후)

## 구조 (uv 워크스페이스)

```
new-zip-dao/
├── pyproject.toml                # 워크스페이스 루트
├── packages/
│   ├── zipdao-core/              # 공통: 설정·HTTP(재시도/레이트리밋)·저장소(manifest)·모델
│   ├── zipdao-crawlers/          # 베이스/엔진·소스 레지스트리·사이트별 크롤러·CLI
│   └── zipdao-api/               # 서빙 API(FastAPI) — MCP 서버가 호출하는 엔드포인트
├── scripts/sync_to_gdrive.sh     # 수집 원본 → Google Drive 백업(rclone)
├── docs/
│   ├── sources.md                # 공고 출처 카탈로그
│   └── data-layout.md            # data/ 디렉터리 레이아웃
└── data/                         # 수집 원본 (gitignore)
```

## 빠른 시작

```bash
uv sync                              # 의존성 설치(워크스페이스 전체)
uv run zipdao-crawl list             # 등록된 소스 목록 + 구현 상태(✅/⬜)
uv run zipdao-crawl run lh_apply --since 2021 --until 2026   # 한 소스 수집
uv run zipdao-crawl run lh_apply --limit 3                   # 소량 시범 수집
uv run pytest                        # 코어 단위 테스트
```

수집 결과는 `data/raw/<source>/<연도>/<공고id>/` 에 `manifest.json`·`attachments/`·`images/` 로 저장된다
(레이아웃: [docs/data-layout.md](docs/data-layout.md)).

## 서빙 API (zipdao-api)

수집한 공고를 MCP 서버(별도 저장소)가 검색·조회하도록 HTTP로 제공한다.

```bash
uv run uvicorn zipdao_api.app:app --port 9000   # 서빙 API 기동 (DATA_DIR 기본 ./data)
uv run pytest packages/zipdao-api -q            # API 테스트
```

엔드포인트: `GET /notices`, `GET /notices/{source}/{notice_id}`, `POST /recommend`, `POST /qa`,
`GET /sources`. 구조화 필드(보증금·월세·면적·공급유형·접수일)는 각 manifest 의 `raw.normalized`
블록에서 읽는다. 크롤러가 아직 이 블록을 채우지 않으므로, 소스별 정규화 단계 추가 전에는 해당
필드가 null 이다.

## 수집 대상

전국 통합 청약 포털(LH청약플러스·SH·청약홈·청년안심주택), 지역 도시·개발공사(GH·UDC·대전·경남), 마이홈포털.
전체 목록·URL은 [docs/sources.md](docs/sources.md). 각 사이트는 실측 후 `sources/<key>.py` 에 구현해 연결한다.

## 백업

수집 원본은 Google Drive 폴더로 동기화한다(rclone, 야간 배치 예정).
대상 폴더: <https://drive.google.com/drive/u/0/folders/1GcJb7hMD4XmxJNdrTF3nQsuyyOUnyUDf>

```bash
brew install rclone && rclone config   # 최초 1회: 'gdrive'(drive 타입) 원격 생성
DRY_RUN=1 ./scripts/sync_to_gdrive.sh   # 변경분 미리보기
./scripts/sync_to_gdrive.sh             # 실제 동기화
```

## 주의

- API 키·OC키 등 모든 시크릿은 `.env` 에만 두고 커밋하지 않는다(`.env.example` 참고).
- 수집 원본(PDF/HWP/이미지)·DB·벡터 인덱스는 `.gitignore` 처리.
