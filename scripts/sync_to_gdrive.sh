#!/usr/bin/env bash
# 수집 원본(data/raw)을 Google Drive 백업 폴더로 동기화.
#
# 백업 대상(지정): https://drive.google.com/drive/u/0/folders/1GcJb7hMD4XmxJNdrTF3nQsuyyOUnyUDf
#   → folder id: 1GcJb7hMD4XmxJNdrTF3nQsuyyOUnyUDf
#
# 사전 준비(최초 1회):
#   1) rclone 설치:  brew install rclone   (macOS) / apt install rclone (Ubuntu)
#   2) 원격 생성:    rclone config   → 이름을 'gdrive' (drive 타입)로
#   3) 이 스크립트는 위 folder id 를 루트로 고정해 sync 한다.
#
# 사용:  ./scripts/sync_to_gdrive.sh          # 실제 동기화
#        DRY_RUN=1 ./scripts/sync_to_gdrive.sh # 변경분만 출력
set -euo pipefail

REMOTE="${GDRIVE_REMOTE:-gdrive}"
FOLDER_ID="${GDRIVE_FOLDER_ID:-1GcJb7hMD4XmxJNdrTF3nQsuyyOUnyUDf}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${DATA_DIR:-$ROOT/data}/raw"

if ! command -v rclone >/dev/null 2>&1; then
  echo "✗ rclone 미설치. 'brew install rclone' 후 'rclone config'로 '$REMOTE' 원격을 만드세요." >&2
  exit 1
fi
if ! rclone listremotes | grep -q "^${REMOTE}:$"; then
  echo "✗ rclone 원격 '${REMOTE}' 없음. 'rclone config'로 drive 타입 원격을 만드세요." >&2
  exit 1
fi
if [[ ! -d "$SRC" ]]; then
  echo "✗ 수집 데이터 없음: $SRC (먼저 'zipdao-crawl run ...' 실행)" >&2
  exit 1
fi

ARGS=(--drive-root-folder-id "$FOLDER_ID" --fast-list --transfers 8 --checkers 16 -P)
[[ "${DRY_RUN:-0}" == "1" ]] && ARGS+=(--dry-run)

echo "→ rclone sync '$SRC' → ${REMOTE}: (folder ${FOLDER_ID})"
rclone sync "$SRC" "${REMOTE}:" "${ARGS[@]}"
echo "✓ 동기화 완료"
