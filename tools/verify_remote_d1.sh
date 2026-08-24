#!/usr/bin/env sh
set -eu

DATABASE_NAME="${1:-DB}"
REPORT="${2:-.wrangler/imports/operon_atlas_full.report.json}"

if [ ! -f "$REPORT" ]; then
  echo "Missing local D1 preparation report: $REPORT" >&2
  echo "Run npm run db:prepare-full first." >&2
  exit 1
fi

QUERY="SELECT
  (SELECT COUNT(*) FROM genomes) AS genomes,
  (SELECT COUNT(*) FROM products) AS products,
  (SELECT COUNT(*) FROM contigs) AS contigs,
  (SELECT COUNT(*) FROM operons) AS operons,
  (SELECT COUNT(*) FROM occurrences) AS occurrences,
  (SELECT COUNT(*) FROM occurrence_genes) AS occurrence_genes,
  (SELECT COUNT(*) FROM operon_products) AS operon_products,
  (SELECT COUNT(*) FROM genome_taxonomy) AS genome_taxonomy,
  (SELECT COUNT(*) FROM operon_taxonomy_counts) AS operon_taxonomy_counts,
  (SELECT COUNT(*) FROM ec_numbers) AS ec_numbers,
  (SELECT COUNT(*) FROM pathway_classes) AS pathway_classes,
  (SELECT COUNT(*) FROM pathway_reference) AS pathway_reference,
  (SELECT COUNT(*) FROM gene_pathways) AS gene_pathways,
  (SELECT COUNT(*) FROM subsystem_roles) AS subsystem_roles,
  (SELECT COUNT(*) FROM subsystem_classes) AS subsystem_classes,
  (SELECT COUNT(*) FROM subsystem_reference) AS subsystem_reference,
  (SELECT COUNT(*) FROM gene_subsystems) AS gene_subsystems,
  (SELECT COUNT(*) FROM operon_function_coverage) AS operon_function_coverage,
  (SELECT COUNT(*) FROM operon_subsystem_support) AS operon_subsystem_support,
  (SELECT COUNT(*) FROM operon_subsystem_class_support) AS operon_subsystem_class_support,
  (SELECT COUNT(*) FROM operon_pathway_support) AS operon_pathway_support,
  (SELECT COUNT(*) FROM operon_pathway_class_support) AS operon_pathway_class_support,
  (SELECT COUNT(*) FROM operon_pgfams) AS operon_pgfams,
  (SELECT COUNT(*) FROM operon_ec_support) AS operon_ec_support,
  (SELECT COUNT(*) FROM operon_role_support) AS operon_role_support,
  (SELECT COUNT(*) FROM search_entities) AS search_entities,
  (SELECT COUNT(*) FROM build_info) AS build_info;"

RESULT="$(npx wrangler d1 execute "$DATABASE_NAME" \
  --remote \
  --config worker/wrangler.toml \
  --command "$QUERY" \
  --json)"

printf '%s' "$RESULT" | node tools/assert_d1_counts.mjs "$REPORT"
