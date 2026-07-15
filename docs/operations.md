# 배포·운영

## Docker 서빙

이미지는 uv 워크스페이스를 그대로 담고 8080 포트로 uvicorn 을 띄운다(`Dockerfile`).
공고 데이터는 이미지에 포함하지 않고 `/data` 볼륨으로 마운트한다(`DATA_DIR=/data`).

```bash
docker build -t zipdao-api:latest .
docker run -d --name zipdao-api --restart unless-stopped \
  -p 8080:8080 -e DATA_DIR=/data -v <데이터경로>:/data zipdao-api:latest
```

배포 = `git pull` 후 이미지 재빌드 → 컨테이너 교체(`docker rm -f zipdao-api && docker run ...`).

## 일일 수집 크론

`scripts/zipdao-daily.sh` 를 서버 crontab 에 등록한다(스크립트 상단 주석의 등록 라인 참고,
UTC 0 9,21 = KST 06/18시). 동작:

1. `docker exec` 로 컨테이너 안에서 `zipdao-crawl run all` (서비스 키는 호스트 `.env` 에서 주입)
2. `zipdao-crawl normalize all`
3. `data/last_crawl` 에 완료 시각(UTC) 기록 — API 응답의 `lastUpdated` 가 이 값을 읽는다
4. `docker restart zipdao-api`

로그는 데이터 볼륨의 `crawl.log` 에 append 된다.

주의: 크론에 **`parse-docs` 는 포함되어 있지 않다** — 공고문 PDF 기반 나이 자격·청년 가격
(`raw.docParse`)은 `zipdao-crawl parse-docs all` 수동 실행으로만 채워진다.

컨테이너의 API 는 `RELOAD_INTERVAL_SECONDS`(기본 600초) 주기로 store 를 자동 리로드하므로,
재시작 없이도 새 데이터가 최대 10분 안에 반영된다(크론의 restart 는 확실성용).

## 백업 (Google Drive)

- 최초 1회: `scripts/setup_gdrive.sh` 로 rclone 원격 생성(브라우저 OAuth), 또는 수동 `rclone config`.
- 동기화: `scripts/sync_to_gdrive.sh` (`DRY_RUN=1` 로 미리보기). 대상 폴더 ID 는 `.env` 의
  `GDRIVE_FOLDER_ID`.

## CI

`.github/workflows/ci.yml` — main push 와 모든 PR 에서 `ruff check` + `ruff format --check` +
`pytest` 를 실행한다.
