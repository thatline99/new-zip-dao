#!/usr/bin/env bash
# Google Drive 원격 1회 설정 — 사용자가 실행할 "마지막 한 단계".
# 실행하면 브라우저 OAuth 창이 자동으로 열립니다(구글 로그인 → 허용).
#
#   ./scripts/setup_gdrive.sh
#   ./scripts/sync_to_gdrive.sh      # 이후 업로드
set -euo pipefail

REMOTE="${GDRIVE_REMOTE:-gdrive}"
FOLDER_ID="${GDRIVE_FOLDER_ID:-1GcJb7hMD4XmxJNdrTF3nQsuyyOUnyUDf}"

if ! command -v rclone >/dev/null 2>&1; then
  echo "✗ rclone 미설치. 먼저:  brew install rclone" >&2
  exit 1
fi

if rclone listremotes 2>/dev/null | grep -q "^${REMOTE}:$"; then
  echo "✓ 원격 '${REMOTE}' 이미 존재. 바로 ./scripts/sync_to_gdrive.sh 실행 가능."
  exit 0
fi

echo "→ '${REMOTE}' (Google Drive) 원격을 만듭니다."
echo "  잠시 후 브라우저가 열리면 구글 로그인 후 접근을 허용하세요."
echo "  백업 폴더 ID: ${FOLDER_ID}"
echo
rclone config create "${REMOTE}" drive scope drive root_folder_id "${FOLDER_ID}"
echo
echo "✓ 설정 완료. 업로드:  ./scripts/sync_to_gdrive.sh"
