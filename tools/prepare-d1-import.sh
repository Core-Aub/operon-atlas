#!/usr/bin/env sh
set -eu

SOURCE_DB="${1:-database/operon_atlas_sample.db}"
OUTPUT_SQL="${2:-.wrangler/imports/operon_atlas_sample.sql}"
OUTPUT_DIR="$(dirname "$OUTPUT_SQL")"

if [ ! -f "$SOURCE_DB" ]; then
  echo "Database not found: $SOURCE_DB" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

cat > "$OUTPUT_SQL" <<'SQL'
PRAGMA defer_foreign_keys = true;

DROP TABLE IF EXISTS operon_pathway_class_support;
DROP TABLE IF EXISTS operon_pathway_support;
DROP TABLE IF EXISTS operon_subsystem_class_support;
DROP TABLE IF EXISTS operon_subsystem_support;
DROP TABLE IF EXISTS operon_function_coverage;
DROP TABLE IF EXISTS gene_subsystems;
DROP TABLE IF EXISTS subsystem_reference;
DROP TABLE IF EXISTS subsystem_classes;
DROP TABLE IF EXISTS subsystem_roles;
DROP TABLE IF EXISTS gene_pathways;
DROP TABLE IF EXISTS pathway_reference;
DROP TABLE IF EXISTS pathway_classes;
DROP TABLE IF EXISTS ec_numbers;
DROP TABLE IF EXISTS operon_products;
DROP TABLE IF EXISTS occurrence_genes;
DROP TABLE IF EXISTS occurrences;
DROP TABLE IF EXISTS operons;
DROP TABLE IF EXISTS contigs;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS genomes;
DROP TABLE IF EXISTS build_info;

SQL

for table in \
  genomes \
  products \
  contigs \
  operons \
  occurrences \
  occurrence_genes \
  operon_products \
  ec_numbers \
  pathway_classes \
  pathway_reference \
  gene_pathways \
  subsystem_roles \
  subsystem_classes \
  subsystem_reference \
  gene_subsystems \
  operon_function_coverage \
  operon_subsystem_support \
  operon_subsystem_class_support \
  operon_pathway_support \
  operon_pathway_class_support \
  build_info
do
  sqlite3 "$SOURCE_DB" ".dump $table" \
    | sed \
        -e '/^PRAGMA foreign_keys=OFF;$/d' \
        -e '/^BEGIN TRANSACTION;$/d' \
        -e '/^COMMIT;$/d' \
        -e '/^ANALYZE sqlite_schema;$/d' \
        -e '/^CREATE TABLE sqlite_stat1/d' \
        -e '/^INSERT INTO sqlite_stat1 /d' \
        -e "/^INSERT INTO subsystem_reference VALUES/s/,'');$/,NULL);/" \
    >> "$OUTPUT_SQL"
  printf '\n' >> "$OUTPUT_SQL"
done

cat >> "$OUTPUT_SQL" <<'SQL'
INSERT OR IGNORE INTO subsystem_classes (
  subsystem_class_key,
  subsystem_superclass,
  subsystem_class,
  subsystem_subclass
)
SELECT DISTINCT
  sr.subsystem_class_key,
  NULL,
  NULL,
  NULL
FROM subsystem_reference AS sr
LEFT JOIN subsystem_classes AS sc
  ON sc.subsystem_class_key = sr.subsystem_class_key
WHERE sr.subsystem_class_key IS NOT NULL
  AND sc.subsystem_class_key IS NULL;

SQL

sqlite3 "$SOURCE_DB" \
  "SELECT sql || ';' FROM sqlite_schema WHERE type = 'index' AND sql IS NOT NULL ORDER BY name;" \
  >> "$OUTPUT_SQL"

echo "Wrote D1 import SQL to $OUTPUT_SQL"
