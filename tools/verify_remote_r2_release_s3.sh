#!/usr/bin/env sh
set -eu

SOURCE_DIR="${1:-downloads/operon_atlas_full}"
DESTINATION="r2:releases/1.1.0/"

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone is required to verify the R2 release." >&2
  exit 1
fi
if ! command -v sha256sum >/dev/null 2>&1; then
  echo "sha256sum is required to verify the local release." >&2
  exit 1
fi
if [ ! -f "$SOURCE_DIR/checksums.sha256" ]; then
  echo "Missing local checksum file: $SOURCE_DIR/checksums.sha256" >&2
  exit 1
fi

echo "Verifying local release checksums..."
(
  cd "$SOURCE_DIR"
  sha256sum --check checksums.sha256
)

echo "Verifying local files against $DESTINATION by path and byte size..."
rclone check "$SOURCE_DIR/" "$DESTINATION" \
  --one-way \
  --size-only \
  --s3-provider Cloudflare \
  --s3-region auto \
  --s3-no-check-bucket

echo "Remote R2 release verification: PASS"
echo "The local SHA-256 manifest is valid and every release object exists remotely with the expected byte size."
