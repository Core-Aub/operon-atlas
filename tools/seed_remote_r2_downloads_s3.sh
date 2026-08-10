#!/usr/bin/env sh
set -eu

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  shift
fi

SOURCE_DIR="${1:-downloads/operon_atlas_full}"
DESTINATION="r2:releases/1.0.0/"
TRANSFERS="4"
CHECKERS="8"
UPLOAD_CONCURRENCY="4"
CHUNK_SIZE="128M"

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone is required for large R2 uploads." >&2
  echo "Install rclone and configure an R2 remote named 'r2' that points to the operonatlas-downloads bucket." >&2
  exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
  echo "Downloads directory not found: $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/downloads_manifest.json" ]; then
  echo "Missing downloads manifest: $SOURCE_DIR/downloads_manifest.json" >&2
  exit 1
fi

echo "Source: $SOURCE_DIR"
echo "Destination: $DESTINATION"

RCLONE_DRY_RUN_FLAG=""
if [ "$DRY_RUN" -eq 1 ]; then
  RCLONE_DRY_RUN_FLAG="--dry-run"
fi

rclone copy "$SOURCE_DIR/" "$DESTINATION" \
  --progress \
  --s3-provider Cloudflare \
  --s3-region auto \
  --s3-acl private \
  --s3-no-check-bucket \
  --no-traverse \
  --transfers "$TRANSFERS" \
  --checkers "$CHECKERS" \
  --s3-upload-cutoff "$CHUNK_SIZE" \
  --s3-upload-concurrency "$UPLOAD_CONCURRENCY" \
  --s3-chunk-size "$CHUNK_SIZE" \
  $RCLONE_DRY_RUN_FLAG
