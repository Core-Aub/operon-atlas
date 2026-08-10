#!/usr/bin/env sh
set -eu

SOURCE_DB="${1:-database/operon_atlas.db}"
OUTPUT_SQL="${2:-.wrangler/imports/operon_atlas_full.sql}"
D1_IMPORT_LIMIT_BYTES=5368709120
D1_PAID_DB_LIMIT_BYTES=10737418240

sh tools/prepare-d1-import.sh "$SOURCE_DB" "$OUTPUT_SQL"

SOURCE_BYTES="$(wc -c < "$SOURCE_DB" | tr -d ' ')"
SQL_BYTES="$(wc -c < "$OUTPUT_SQL" | tr -d ' ')"
SOURCE_GIB="$(awk -v bytes="$SOURCE_BYTES" 'BEGIN { printf "%.2f GiB", bytes / 1073741824 }')"
SQL_GIB="$(awk -v bytes="$SQL_BYTES" 'BEGIN { printf "%.2f GiB", bytes / 1073741824 }')"

echo "Source SQLite size: $SOURCE_GIB ($SOURCE_BYTES bytes)"
echo "Full D1 SQL size: $SQL_GIB ($SQL_BYTES bytes)"

if [ "$SQL_BYTES" -gt "$D1_IMPORT_LIMIT_BYTES" ]; then
  echo "WARNING: The SQL file is over Cloudflare D1's 5 GiB single-file import limit." >&2
  echo "Split the import into multiple SQL files before running wrangler d1 execute --file." >&2
fi

if [ "$SOURCE_BYTES" -gt "$D1_PAID_DB_LIMIT_BYTES" ]; then
  echo "WARNING: The source SQLite file is over Cloudflare D1's 10 GB paid database size limit." >&2
fi
