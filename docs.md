# OperonAtlas developer guide

This document is the technical guide for programmers working on OperonAtlas. It covers the application architecture, local setup, data model, API, common development workflows, testing, and Cloudflare deployment.

## Architecture

OperonAtlas is a read-only web application composed of four deployed services:

1. **Frontend** — a build-free HTML, CSS, and JavaScript single-page application hosted on Cloudflare Pages.
2. **Pages Function** — a same-origin `/api/*` proxy that forwards requests to the API Worker through a Cloudflare service binding.
3. **API Worker** — a Python Cloudflare Worker that validates requests, queries D1, reads the download manifest from R2, and returns JSON.
4. **Storage** — Cloudflare D1 stores relational operon data; Cloudflare R2 stores versioned downloadable release files.

The request path is:

```text
Browser -> Cloudflare Pages -> /api/* Pages Function -> Python Worker -> D1 or R2
```

Dataset file links returned by `/api/downloads` point to the HTTPS base URL configured as `DOWNLOAD_BASE_URL`. The Worker does not stream the release files itself.

### Main code areas

| Area | Responsibility |
| --- | --- |
| `frontend/` | Static SPA, pages, shared UI components, hash routing, and SVG viewers |
| `functions/api/[[path]].js` | Pages-to-Worker proxy for same-origin API requests |
| `worker/src/` | Python Worker entry point, routing, D1 queries, and download-manifest handling |
| `worker/wrangler.toml` | Worker name, compatibility settings, bindings, limits, and rate limits |
| `wrangler.toml` | Pages output directory and Worker service binding |
| `tools/` | Database and release preparation, and smoke tests |
| `database/` | Tracked full/sample schema files plus ignored local SQLite databases, TSV inputs, and raw snapshots |
| `downloads/` | Generated release artifacts and manifests; intentionally ignored by Git |

## Prerequisites

Install the following before working locally:

- a current Node.js LTS release with npm;
- Python 3.12 or newer;
- `sqlite3` with its command-line shell;
- a Cloudflare account for remote D1, R2, Worker, or Pages operations; and
- `rclone` only when uploading large release datasets through the S3-compatible R2 API.

Wrangler is invoked through `npx`, so there is no required repository-level npm installation step. On its first run, `npx` may ask to download Wrangler.

The local sample database and generated release files are not version-controlled. Obtain or generate them before running the full application. The expected sample database path is:

```text
database/operon_atlas_sample.db
```

## Local development

### 1. Prepare local sample data

Activate `bio`, rebuild the sample SQLite database from `database/sample_data/`, generate its D1 SQL, seed local D1, generate the sample downloads, and seed local R2:

```bash
venv bio
npm run db:prepare-sample
npm run db:seed:local
npm run r2:prepare-sample
npm run r2:seed:local
```

`db:prepare-sample` runs `database/build_sample_db.sql`, verifies the rebuilt database, places it at `database/operon_atlas_sample.db`, and writes `.wrangler/imports/operon_atlas_sample.sql`. The R2 preparation command writes a complete release to `downloads/operon_atlas_sample/`. Local Wrangler state remains under `.wrangler/state/`.

The smoke test expects the standard sample dataset to contain:

| Table | Rows |
| --- | ---: |
| `genomes` | 1,075 |
| `operons` | 500 |
| `occurrences` | 1,154 |
| `occurrence_genes` | 3,902 |

### 2. Start the API Worker

```bash
npm run worker:dev
```

The Worker listens on `http://127.0.0.1:8787` and reuses the seeded local D1 state.

### 3. Start the Pages frontend

In a second terminal, run:

```bash
npm run pages:dev
```

Open `http://127.0.0.1:8080`. Pages serves `frontend/` and forwards same-origin `/api/*` requests to the Worker through the `API_WORKER` service binding.

The application uses URL hashes such as `#operons?page=1`, so local routing does not require fallback rewrites. The downloads API reads its manifest from the local R2 emulator; returned file URLs still use the configured HTTPS `DOWNLOAD_BASE_URL`.

## Frontend design

The frontend has no framework, bundler, transpiler, or compilation step. Browser-native ES modules are served directly from `frontend/`.

- `frontend/app.js` registers global event handlers and starts rendering on `DOMContentLoaded` and `hashchange`.
- `frontend/routing/router.js` maps parsed hash routes to page renderers.
- `frontend/pages/` contains screen-level data fetching and markup.
- `frontend/components/` contains reusable controls, tables, links, annotations, and layout helpers.
- `frontend/viewers/` contains the operon gene viewer and genome-context viewer.
- `frontend/api.js` is the shared JSON client. `API_BASE` is empty in normal operation because requests are same-origin.
- `frontend/config.js` contains UI constants, supported sort fields, identifier widths, and viewer dimensions.

All dynamic text inserted into HTML must pass through `escapeHtml`. Prefer the shared formatting, linking, paging, sorting, and layout helpers rather than duplicating markup behavior.

### Adding a frontend page

1. Add a renderer in `frontend/pages/`.
2. Import and dispatch it from `frontend/routing/router.js`.
3. Add a navigation item in `frontend/index.html` if it is a top-level page.
4. Use `fetchJson` for API access and check `isCurrentRoute(routeKey)` after asynchronous requests so a stale response cannot replace the active view.
5. Register delegated event handlers in `frontend/app.js` when the page needs interaction.
6. Test direct navigation, browser back/forward behavior, loading states, empty states, errors, and narrow-screen layouts.

Some module imports and static assets use explicit query-string versions for cache busting. Increment the relevant version when a deployment must invalidate a previously cached module or stylesheet.

## API Worker design

The Worker targets Python 3.12+ and uses Cloudflare's Python Workers runtime.

- `worker/src/main.py` exposes the `WorkerEntrypoint`.
- `worker/src/routes.py` handles method validation, URL parsing, rate limits, binding checks, status codes, CORS, and response serialization.
- `worker/src/db.py` validates query parameters, executes parameterized D1 statements, and shapes API responses.
- `worker/src/downloads.py` validates and reads the R2 manifest and constructs public file URLs.

The API is read-only. It accepts `GET` and `OPTIONS`; other methods return `405`. JSON responses include permissive CORS headers. Search values are normalized, limited to 120 characters, and always bound. Catalog searches accept at most eight whitespace-separated terms; each escaped `LIKE` pattern must remain within D1's 50-byte limit. Recognized exact identifiers are parsed before substring matching, so a valid long coordinate-form PATRIC ID is not rejected by the `LIKE` limit.

Pagination is fixed at 20 items per page. Invalid or missing page numbers normalize to page 1.

### Endpoints

| Endpoint | Purpose | Query parameters |
| --- | --- | --- |
| `GET /api/health` | Liveness check; returns `{ "ok": true }` | None |
| `GET /api/stats` | Counts genomes, operon families, occurrences, and occurrence-gene rows | None |
| `GET /api/organisms` | Lists genome keys and organism names for filters | None |
| `GET /api/search` | Direct identifier resolution plus grouped entity previews or one paginated entity category | `q`, optional `type`, `page` |
| `GET /api/operons` | Paginates and filters operon families, including compact taxonomy breadth | `page`, gene-count filters, `genome_key`, organism/product filters, `search`, `entity_type`, `entity_key`, `sort`, `direction` |
| `GET /api/operons/:operon_id` | Returns one family, functional summary, taxonomy headlines, and paginated matching occurrences | `page`, `product`, `search`, `entity_type`, `entity_key` |
| `GET /api/operons/:operon_id/taxonomy` | Returns complete phylum distribution, paginated genera, headline counts, and unclassified coverage | `page` (genera page) |
| `GET /api/occurrences/:occurrence_id` | Returns one occurrence and its ordered, annotated genes | optional `gene` exact reconstructed ID to highlight |
| `GET /api/genomes` | Paginates and searches genomes | `page`, `search`, `sort`, `direction` |
| `GET /api/genomes/:genome_key` | Returns one genome and aggregate operon/gene counts | None |
| `GET /api/genomes/:genome_key/viewer` | Returns contig-grouped occurrence spans for the genome viewer | `min_genes`/`min_gene_count`, `max_genes`/`max_gene_count`, `product` |
| `GET /api/genomes/:genome_key/operons` | Returns paginated operon occurrences within a genome | `page`, gene-count filters, `product`, `sort`, `direction` |
| `GET /api/downloads` | Reads the current R2 manifest and adds public download URLs | None |

Supported operon sort fields are `operon_id`, `gene_count`, and `occurrence_count`; the default is `occurrence_count desc`. Supported genome sort fields are `genome_id`, `organism_name`, `operon_count`, and `gene_count`; the default is `genome_id asc`. All lists use a stable numeric identifier as a final tie-breaker.

Gene-count filters are clamped to `1..10000`. If the minimum exceeds the maximum, the values are swapped. Text filters use case-insensitive substring matching under SQLite's default `LIKE` behavior.

Search category previews return at most five entities per category to keep the page readable. This is not a result cap: each category links to a 20-per-page entity list, each selected entity links to every matching family, and the cross-annotation “View all matching operon families” route expands the complete uncapped matched-entity set. FTS5 is deliberately not used. The ordinary 131,420-row full catalog is already fast locally, while the expensive operation is expanding a broad annotation into families; FTS would not remove that cost and would complicate D1 import/export.

Allowed entity types are `product`, `pgfam`, `ec`, `pathway`, `pathway_class`, `subsystem`, `subsystem_class`, `role`, `genome`, `species`, `genus`, and `phylum`. Exact resolvers also recognize OAF/OAO IDs, canonical or `fig|` gene IDs, `PGF_` IDs, numeric taxon IDs, and `PATRIC.<genome>.<contig>.CDS.<start>.<end>.<fwd|rev>` IDs.

### Identifiers and annotations

- Numeric operon family IDs are displayed as `OAF` followed by six digits.
- Numeric occurrence IDs are displayed as `OAO` followed by six digits.
- PGFam values are displayed as `PGF_` followed by eight digits. A stored value of `-1` becomes `null`.
- Gene IDs are reconstructed as `<genome_id>.peg.<peg_num>`.
- Coordinate feature IDs are resolved through genome, contig, start, end, and strand; they are not copied into a large text table.
- Occurrence genes are ordered by contig and start coordinate.
- Pathway and subsystem annotations are joined to genes by genome, contig, coordinates, and strand. Genes without evidence return empty `pathways` and `subsystems` arrays.

### Caching and rate limiting

`/api/stats` and `/api/downloads` are publicly cacheable for five minutes, and `/api/organisms` for fifteen minutes. Other API responses currently do not set an explicit cache policy.

The Worker configuration allows 120 API requests per client per 60 seconds. Query-heavy operon, occurrence, genome-viewer, and genome-operon routes have an additional limit of 30 requests per client per 60 seconds. The health endpoint bypasses these limits. A limited request returns `429` with `Retry-After: 60`.

### Adding or changing an endpoint

1. Put query and response logic in `worker/src/db.py` or another focused service module.
2. Validate all path and query inputs before building a statement.
3. Use bound parameters for values. Only select SQL fragments such as sort columns from fixed allowlists.
4. Register the route in `worker/src/routes.py` and use `json_response` for consistent CORS and serialization.
5. Decide whether the route needs cache headers or inclusion in the heavy-route limiter.
6. Add representative success, validation, not-found, and filter cases to the smoke test.
7. Update this endpoint table and any frontend consumer in the same change.

Avoid returning raw exceptions or database details to clients. The route layer logs internal failures and returns a generic error response.

## Data model and database workflow

The central entities are:

- `operons`: stable PGFam-multiset families;
- `occurrences`: genome-specific instances linked to a family and genome;
- `occurrence_genes`: ordered gene coordinates, strands, products, and PGFam assignments;
- `genomes`, `contigs`, and `products`: normalized reference data;
- `gene_pathways` plus pathway reference tables: EC/pathway evidence;
- `gene_subsystems` plus subsystem reference tables: BV-BRC/SEED subsystem evidence; and
- `operon_function_*`, `operon_pathway_*`, and `operon_subsystem_*`: precomputed family-level functional summaries;
- `genome_taxonomy` and `operon_taxonomy_counts`: rank assignments and precomputed distinct taxonomic breadth;
- `operon_pgfams`, `operon_ec_support`, and `operon_role_support`: compact reverse indexes from annotations to families; and
- `search_entities`: the ordinary search catalog for functional, genome, organism, and taxonomy entities.

The complete schemas are `database/build_db.sql` and `database/build_sample_db.sql`. They contain every table, import, normalization step, and index used by the full and sample databases. Search and taxonomy are therefore normal parts of a clean rebuild rather than migrations applied afterward.

### Authoritative inputs

For release 1.1.0, `database/data/` is the authoritative full input and `database/sample_data/` is its deterministic sample. The full input already contains exactly 5,067,861 same-contig occurrences, each with at least two genes and complete PGFam annotation. Family signatures are numerically sorted PGFam multisets: gene order is ignored, duplicate copies are preserved, and all existing OAF/OAO numeric IDs must remain unchanged.

Do not regenerate these rows from predictions, notebooks, Collab exports, or `features.tab` files for this release. New derived data is added as a new TSV in both input directories, then imported by both schema files. The taxonomy source snapshot is retained under `database/raw/taxonomy/`.

The taxonomy acquisition and derivation tools are intentionally one-off data-maintenance tools, not npm commands used during every development cycle:

1. `tools/download_bvbrc_taxonomy.py --plan` prints request and bandwidth estimates without network access.
2. The same tool downloads through the official BV-BRC HTTP `/api/genome/` and `/api/taxonomy/` endpoints with checkpoints and frozen raw TSV responses. FTP is not used.
3. `tools/build_operon_taxonomy.py` creates the taxonomy TSVs and reports their formatting, coverage, and consistency checks.
4. `tools/generate_search_support.py` creates the additive search-support TSVs and reports its own checks.

All Python commands must run in the `bio` environment. The maintenance generators use explicit paths and publish outputs only after their internal checks pass.

Taxonomy counts use taxon IDs, never parsed organism names. Family-genome links are deduplicated before counting, so each genome, species, genus, and phylum contributes at most once per family. Nullable rank coverage is recorded explicitly. Complete phylum and paginated genus distributions are calculated from `genome_taxonomy` at query time to avoid a large materialized family-by-taxon table.

### Rebuilding SQLite databases

Use `npm run db:prepare-sample` during development and `npm run db:prepare-full` when preparing production data. `tools/prepare_database.py` runs the appropriate schema against a temporary database, checks table coverage, row presence, foreign keys, and `PRAGMA integrity_check`, then replaces the canonical database only after those checks pass. It also writes the matching D1 import SQL and a count/size report under `.wrangler/imports/`.

The build SQL drops and recreates application tables inside the temporary output, never inside the current canonical database. The previous database remains untouched if preparation fails.

### Changing the schema

When adding a table or index:

1. Add the full TSV to `database/data/` and its sample equivalent to `database/sample_data/`.
2. Update both build SQL files with the same table definition, import, normalization, and indexes.
3. Add the table to the explicit dependency order in `tools/prepare_d1_import.py`.
4. Run the sample prepare/seed workflow and both smoke tests.
5. When the feature is approved, run the full database and download preparation commands and inspect their reports before remote seeding.

The D1 generator emits tables in dependency order, appends indexes, refuses unknown or missing tables, and caps SQL statements at 90,000 bytes. This explicit behavior is why a schema change must also update its table order.

### Preparing the full D1 import

Activate `bio`, then run:

```bash
npm run db:prepare-full
```

The prepared release 1.1.0 database is 3,604,107,264 bytes and its D1 SQL is 2,235,439,309 bytes. Both fit the project's 4.5 GB database target and [Cloudflare's 5 GiB D1 import-file limit](https://developers.cloudflare.com/d1/best-practices/import-export-data/). The remote seed therefore uses one SQL file; splitting is unnecessary. The 90 KB statement cap stays below D1's per-statement limit.

Do not import the full database into local Wrangler during routine development. The sample D1 exercises the same schema, ordering, statements, Worker queries, and UI logic much faster.

## Testing and verification

There is no application unit-test suite or frontend build step. `tools/tests/test_taxonomy_tools.py` provides focused standard-library tests for taxonomy parsing/reconciliation, while the canonical application checks are integration smoke tests against the standard sample D1.

Run the focused Python checks inside `bio`:

```bash
python -m unittest discover -s tools/tests -v
```

With the Worker running on port 8787:

```bash
npm run smoke:api
```

With Pages and the Worker running:

```bash
npm run smoke:pages
```

The smoke script verifies health, exact sample counts, representative family/occurrence/genome records, every genome sort mode, invalid-sort fallback, deterministic ordering, taxonomy breadth, every search entity category, exact OAF/OAO/gene/PATRIC/PGFam/taxon resolution, typed family filtering, result pagination, and occurrence-gene highlighting. Because it contains fixed sample IDs and counts, update it deliberately whenever the canonical sample fixture changes.

Routine correctness and UI testing uses the sample fixture. The database preparation commands perform structural, foreign-key, integrity, and row-presence checks before publishing either database. Do not spend hours importing the full database into local Wrangler or running performance benchmarks during ordinary development unless a specific problem requires them.

For frontend changes, manually verify at least:

- home statistics and error handling;
- operon filters, sorting, pagination, and detail navigation;
- genome search, sorting, pagination, detail view, and genome viewer;
- occurrence gene graphics and functional annotations;
- grouped search previews, every “View all” path, typed filter preservation, and exact-gene highlighting;
- taxonomy headline counts, complete phyla, paginated genera, and unclassified coverage;
- back/forward navigation and copied hash URLs;
- empty and not-found states;
- downloads with the configured public file host; and
- desktop and narrow viewport layouts.

## Download release workflow

Release `1.1.0` uses this object layout in the `operonatlas-downloads` bucket:

```text
releases/1.1.0/downloads_manifest.json
releases/1.1.0/data_dictionary.tsv
releases/1.1.0/operon_families.tsv.gz
releases/1.1.0/operon_occurrences.tsv.gz
releases/1.1.0/operon_occurrence_genes.tsv.gz
releases/1.1.0/checksums.sha256
```

The manifest contains release metadata, row counts, sizes, SHA-256 checksums, and dataset descriptions. Family rows now include distinct genome/species/genus/phylum counts and unclassified coverage, but not large delimited taxon distributions. `worker/src/downloads.py` owns the active release number and manifest key. Keep the generated files, manifest, Worker constant, upload prefix, and public download host synchronized when cutting a release.

`npm run r2:prepare-sample` writes the sample release to `downloads/operon_atlas_sample/`; `npm run r2:prepare-full` writes the production release to `downloads/operon_atlas_full/`. The builder streams query rows directly into `.tsv.gz` files—there is no intermediate plain TSV or second compression step. It records row counts, byte sizes, and SHA-256 values in the manifest/checksum files and publishes the directory only after generation succeeds. Release 1.0.0 is protected from accidental regeneration.

For the full release, configure an `rclone` S3 remote named `r2` whose root is the `operonatlas-downloads` bucket. Upload and then compare every local object with R2 by path and byte size:

```bash
npm run r2:seed:remote
npm run r2:verify:remote
```

The verifier first checks every local file against `checksums.sha256`, then compares remote paths and exact byte sizes because multipart S3/R2 ETags are not file SHA-256 hashes. Only the project owner performs remote upload. After the code is live, also verify the manifest URL and real browser downloads before announcing the release.

## Cleanup and quarantine

AppleDouble `._*` metadata copies are not project inputs. Inventory and remove them, keep the ignore rules, and run `git fsck --full --no-reflogs` afterward when copies were present inside `.git`.

Do not permanently delete other stale or failed artifacts. Use `tools/quarantine_files.py` to move reviewed items under `to_delete/<date>/` while preserving original relative paths. Its manifest records byte size, SHA-256, classification, reason, destination, and timestamp. The tool preflights all destinations before moving a multi-source batch so a collision cannot cause a partially manifested quarantine. Leave ambiguous Collab/raw inputs in place for owner review.

## Deferred comparison view

The simplified compare-region view is intentionally postponed. No comparison schema, API, or frontend placeholder is included in release 1.1.0. A future implementation should begin by confirming that occurrence genes provide all required ordered coordinates, orientations, products, and PGFams, then define the desired alignment/selection behavior before adding storage or UI.

## Cloudflare deployment

Deployment and every production mutation are owner-managed. Coding agents prepare local artifacts only: they must not execute remote D1 commands, upload R2 objects, change bindings, deploy the Worker, deploy Pages, or push Git commits. The commands in this section are handoff instructions for the project owner.

Seed the new D1 database and R2 release before pushing the 1.1.0 application code. The new API requires the new tables, and `/api/downloads` expects the 1.1.0 manifest.

### Bindings

The Worker requires:

| Binding | Type | Purpose |
| --- | --- | --- |
| `DB` | D1 database | Application queries |
| `DOWNLOADS` | R2 bucket | Download manifest lookup |
| `API_RATE_LIMITER` | Rate limit | General API traffic |
| `HEAVY_API_RATE_LIMITER` | Rate limit | Query-heavy endpoints |
| `DOWNLOAD_BASE_URL` | String variable | HTTPS origin for public release files |

Pages requires the `API_WORKER` service binding pointed at the deployed Worker named `operonatlas-api`.

Treat the names and IDs in the Wrangler files as environment-specific configuration. Confirm them in the target Cloudflare account before deployment. Do not copy a production database ID into a development environment accidentally.

### First-time Cloudflare setup

Authenticate Wrangler:

```bash
npx wrangler login
```

Create or select the D1 database and R2 bucket, then update `worker/wrangler.toml` with their names and IDs:

```bash
npx wrangler d1 create operon_atlas_1_1_0 --config worker/wrangler.toml
npx wrangler r2 bucket create operonatlas-downloads
```

Configure `DOWNLOAD_BASE_URL` as a Worker variable in Cloudflare. It must be an HTTPS URL with no required trailing slash and should serve `releases/<release>/<filename>` from the R2 bucket, normally through an R2 custom domain.

### Prepare and seed release 1.1.0 data

Activate `bio`, prepare the canonical full artifacts, seed them, and verify the remote object/count coverage:

```bash
venv bio
npm run db:prepare-full
npm run db:seed:remote
npm run db:verify:remote
npm run r2:prepare-full
npm run r2:seed:remote
npm run r2:verify:remote
```

`db:seed:remote` imports the single `.wrangler/imports/operon_atlas_full.sql` file into the `DB` binding configured in `worker/wrangler.toml`; it does not create a database or change a binding. Confirm that this binding points to the intended new database before running the command. The SQL rebuilds application tables, so never aim it at a database that must remain live and unchanged.

The full D1 SQL is about 2.24 GB, below Cloudflare's 5 GiB import-file limit, so it is not split. The largest release archive is about 698 MB, above [Wrangler's 315 MB direct R2 upload limit](https://developers.cloudflare.com/r2/objects/upload-objects/); `r2:seed:remote` therefore uses `rclone` and the configured `r2` remote.

### Deploy the Worker and Pages

The owner commits and pushes after D1 and R2 are ready. The configured Cloudflare Git integrations deploy the Worker from `worker/wrangler.toml` and the Pages application from the repository; there is no manual Worker or Pages deployment command in `package.json`.

The Pages Git integration uses:

- repository: `Core-Aub/operon-atlas`;
- production branch: `main`;
- root directory: repository root;
- build command: none; and
- output directory: `frontend`.

Configure the `API_WORKER` service binding for both production and preview environments as appropriate. The root `wrangler.toml` also records the Pages output directory and service binding for local development.

Branches and pull requests can receive preview deployments according to the Cloudflare project settings.

### Post-deployment checklist

1. Request `/api/health` through both the Worker and Pages URLs.
2. Run the smoke test against the production origin, `https://operonatlas.org`.
3. Check statistics against the intended database release.
4. Exercise a family, occurrence, genome, and viewer route.
5. Confirm `/api/downloads` and download every published file through its returned URL.
6. Confirm Pages preview and production bindings point to the intended Worker and data environment.
7. Review Worker logs for database, binding, rate-limit, or manifest errors.

## Contribution workflow

Keep changes focused and include documentation and test updates with behavior changes.

Before opening a pull request:

1. Rebuild and reseed local data if the schema or fixtures changed.
2. Run both smoke targets when the change crosses frontend and API boundaries.
3. Manually verify affected UI states and routes.
4. Check that generated databases, Wrangler state, downloads, credentials, and machine-specific files remain untracked.
5. Summarize any required D1 seed, R2 upload, binding, or Cloudflare dashboard step in the pull request.

There is no license file in the repository at present. Do not add third-party code or assets until their license is compatible with the license chosen for OperonAtlas.

## Troubleshooting

### The API reports that the database binding is not configured

Start the Worker through the repository script and confirm the `DB` binding exists in `worker/wrangler.toml`. For Pages requests, also confirm `API_WORKER` points to the running or deployed Worker.

### Queries fail after a fresh checkout

The database is intentionally ignored by Git. Restore `database/operon_atlas_sample.db`, regenerate the D1 SQL, and seed local state again.

### Smoke tests report unexpected counts or IDs

The test targets the canonical sample fixture. Confirm that you built from `database/sample_data/`, not the full data directory. If the fixture changed intentionally, review and update every hard-coded expectation in `tools/smoke-api.mjs`.

### The downloads page fails

Confirm all three parts: the `DOWNLOADS` R2 binding, the manifest at the release key, and an HTTPS `DOWNLOAD_BASE_URL`. Also verify that each filename is a plain basename; path separators and `..` are rejected.

### The frontend loads but API requests fail

Confirm the Worker is running on port 8787 before starting Pages, and that the `API_WORKER` service binding is active. Access the site through port 8080 rather than opening `frontend/index.html` directly.

### A new database table is missing in D1

Add the table and TSV import to both SQLite build scripts, add it to `TABLE_ORDER` in `tools/prepare_d1_import.py`, then rerun `db:prepare-sample` and `db:seed:local`.
