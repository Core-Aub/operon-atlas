#!/usr/bin/env sh
set -eu

BUCKET="operonatlas-downloads"
PREFIX="releases/1.0.0"
SOURCE_DIR="${1:-downloads/operon_atlas_sample}"

npx wrangler r2 object put "$BUCKET/$PREFIX/downloads_manifest.json" --remote --file "$SOURCE_DIR/downloads_manifest.json"
npx wrangler r2 object put "$BUCKET/$PREFIX/data_dictionary.tsv" --remote --file "$SOURCE_DIR/data_dictionary.tsv"
npx wrangler r2 object put "$BUCKET/$PREFIX/operon_families.tsv.gz" --remote --file "$SOURCE_DIR/operon_families.tsv.gz"
npx wrangler r2 object put "$BUCKET/$PREFIX/operon_occurrences.tsv.gz" --remote --file "$SOURCE_DIR/operon_occurrences.tsv.gz"
npx wrangler r2 object put "$BUCKET/$PREFIX/operon_occurrence_genes.tsv.gz" --remote --file "$SOURCE_DIR/operon_occurrence_genes.tsv.gz"
