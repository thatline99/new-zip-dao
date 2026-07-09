#!/bin/sh
# NewZipDao 수집: 크롤 -> 정규화 -> 스탬프 -> API 재시작
# 배포 서버(집 서버) crontab 등록: 0 9,21 * * * /home/thatline/zipdao-daily.sh (UTC = KST 06:00/18:00)
# 전제: docker 컨테이너 zipdao-api 가 /data 볼륨(~/newzipdao-data)으로 실행 중, ~/newzipdao/.env 에 서비스 키
LOG="$HOME/newzipdao-data/crawl.log"
set -a; . "$HOME/newzipdao/.env"; set +a
{
  echo "=== $(date -u +%FT%TZ) crawl start ==="
  docker exec -e DATA_GO_KR_SERVICE_KEY="$DATA_GO_KR_SERVICE_KEY" zipdao-api uv run --frozen --no-dev zipdao-crawl run all &&
  docker exec zipdao-api uv run --frozen --no-dev zipdao-crawl normalize all &&
  date -u +%FT%TZ > "$HOME/newzipdao-data/last_crawl" &&
  docker restart zipdao-api
  echo "=== $(date -u +%FT%TZ) done (exit $?) ==="
} >> "$LOG" 2>&1
