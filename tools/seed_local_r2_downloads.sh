#!/usr/bin/env sh
set -eu

BUCKET="operonatlas-downloads"
PREFIX="releases/1.0.0"
STATE_DIR=".wrangler/state"

npx wrangler r2 object put "$BUCKET/$PREFIX/downloads_manifest.json" --local --persist-to "$STATE_DIR" --file downloads/downloads_manifest.json
npx wrangler r2 object put "$BUCKET/$PREFIX/data_dictionary.tsv" --local --persist-to "$STATE_DIR" --file downloads/data_dictionary.tsv
npx wrangler r2 object put "$BUCKET/$PREFIX/operon_families.tsv.gz" --local --persist-to "$STATE_DIR" --file downloads/operon_families.tsv.gz
npx wrangler r2 object put "$BUCKET/$PREFIX/operon_occurrences.tsv.gz" --local --persist-to "$STATE_DIR" --file downloads/operon_occurrences.tsv.gz
npx wrangler r2 object put "$BUCKET/$PREFIX/operon_occurrence_genes.tsv.gz" --local --persist-to "$STATE_DIR" --file downloads/operon_occurrence_genes.tsv.gz