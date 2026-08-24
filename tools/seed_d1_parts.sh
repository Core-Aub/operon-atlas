#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
PARTS_DIR="${2:-.wrangler/imports/operon_atlas_full_parts}"
DATABASE_NAME="${3:-DB}"
CONFIG_PATH="worker/wrangler.toml"
STATE_DIR=".wrangler/state"

case "$MODE" in
  local|remote) ;;
  *)
    echo "Usage: bash tools/seed_d1_parts.sh <local|remote> [parts-dir] [database-binding]" >&2
    exit 2
    ;;
esac

if [ ! -d "$PARTS_DIR" ]; then
  echo "D1 parts directory not found: $PARTS_DIR" >&2
  echo "Run npm run db:prepare-full first." >&2
  exit 1
fi
if [ ! -f "$PARTS_DIR/manifest.json" ] || [ ! -f "$PARTS_DIR/checksums.sha256" ]; then
  echo "D1 parts manifest or checksum file is missing in $PARTS_DIR" >&2
  exit 1
fi
if ! command -v sha256sum >/dev/null 2>&1; then
  echo "sha256sum is required to validate the D1 parts." >&2
  exit 1
fi

echo "Validating generated D1 part checksums..."
(
  cd "$PARTS_DIR"
  sha256sum --check checksums.sha256
)

shopt -s nullglob
SQL_FILES=("$PARTS_DIR"/*.sql)
if [ "${#SQL_FILES[@]}" -eq 0 ]; then
  echo "No SQL parts found in $PARTS_DIR" >&2
  exit 1
fi
mapfile -t EXPECTED_FILES < <(awk '{print $2}' "$PARTS_DIR/checksums.sha256")
if [ "${#SQL_FILES[@]}" -ne "${#EXPECTED_FILES[@]}" ]; then
  echo "SQL file count does not match checksums.sha256." >&2
  exit 1
fi
for INDEX in "${!SQL_FILES[@]}"; do
  if [ "$(basename "${SQL_FILES[$INDEX]}")" != "${EXPECTED_FILES[$INDEX]}" ]; then
    echo "SQL files do not exactly match the generated checksum list." >&2
    exit 1
  fi
done
if [ "${EXPECTED_FILES[0]}" != "01_schema.sql" ] \
  || [ "${EXPECTED_FILES[1]}" != "02_indexes.sql" ] \
  || [ "${EXPECTED_FILES[$((${#EXPECTED_FILES[@]} - 1))]}" != "99_optimize.sql" ]; then
  echo "D1 parts must begin with schema/indexes and end with PRAGMA optimize." >&2
  exit 1
fi
if find "$PARTS_DIR" -maxdepth 1 -type f -name '90_indexes.sql' | grep -q .; then
  echo "Refusing obsolete post-data 90_indexes.sql import layout." >&2
  exit 1
fi
for SQL_FILE in "${SQL_FILES[@]:2}"; do
  if grep -Eiq '^[[:space:]]*CREATE[[:space:]]+(UNIQUE[[:space:]]+)?INDEX' "$SQL_FILE"; then
    echo "Refusing post-schema index creation in $(basename "$SQL_FILE")." >&2
    exit 1
  fi
done
FINAL_OPERATION="$(awk '
  /^[[:space:]]*--/ { next }
  /^[[:space:]]*$/ { next }
  { line=$0 }
  END { gsub(/^[[:space:]]+|[[:space:]]+$/, "", line); print line }
' "${SQL_FILES[$((${#SQL_FILES[@]} - 1))]}")"
if [ "$FINAL_OPERATION" != "PRAGMA optimize;" ]; then
  echo "Final D1 import operation must be exactly PRAGMA optimize;." >&2
  exit 1
fi

human_size() {
  awk -v bytes="$1" 'BEGIN {
    split("B KiB MiB GiB", units, " ");
    value = bytes + 0;
    unit = 1;
    while (value >= 1024 && unit < 4) { value /= 1024; unit += 1 }
    if (unit == 1) printf "%d %s", value, units[unit];
    else printf "%.1f %s", value, units[unit];
  }'
}

TOTAL="${#SQL_FILES[@]}"
echo "Target mode: $MODE"
echo "Database binding: $DATABASE_NAME"
echo "Parts directory: $PARTS_DIR"
echo "Files to execute: $TOTAL"

if [ "$MODE" = "remote" ]; then
  ACTION="Uploading"
else
  ACTION="Importing"
fi

INDEX=0
for SQL_FILE in "${SQL_FILES[@]}"; do
  INDEX=$((INDEX + 1))
  BYTES="$(wc -c < "$SQL_FILE" | tr -d '[:space:]')"
  SIZE="$(human_size "$BYTES")"
  echo
  echo "[$INDEX/$TOTAL] $ACTION $(basename "$SQL_FILE") ($SIZE; $BYTES bytes)"

  if [ "$MODE" = "local" ]; then
    if ! npx wrangler d1 execute "$DATABASE_NAME" \
      --local \
      --config "$CONFIG_PATH" \
      --persist-to "$STATE_DIR" \
      --file "$SQL_FILE" \
      --yes \
      >/dev/null; then
      echo "[$INDEX/$TOTAL] FAILED $(basename "$SQL_FILE")" >&2
      exit 1
    fi
  else
    if ! npx wrangler d1 execute "$DATABASE_NAME" \
      --remote \
      --config "$CONFIG_PATH" \
      --file "$SQL_FILE" \
      --yes \
      >/dev/null; then
      echo "[$INDEX/$TOTAL] FAILED $(basename "$SQL_FILE")" >&2
      exit 1
    fi
  fi
  echo "[$INDEX/$TOTAL] Completed $(basename "$SQL_FILE")"
done

echo
echo "D1 $MODE import complete: $TOTAL files executed successfully."
