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
| `tools/` | D1 import preparation, R2 upload, and API smoke-test scripts |
| `database/` | Local SQLite databases, TSV inputs, and schema/build scripts; intentionally ignored by Git |
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

### 1. Build the sample SQLite database when needed

If the sample TSV inputs exist but the SQLite database does not, build it from inside the database directory so the relative `.import` paths resolve correctly:

```bash
cd database
sqlite3 operon_atlas_sample.db < build_sample_db.sql
cd ..
```

This build script recreates the application tables and indexes, imports `database/sample_data/*.tsv`, writes schema metadata, and prints sanity-check counts.

### 2. Prepare and seed local D1

Convert the sample SQLite database into SQL accepted by D1, then load it into Wrangler's persistent local state:

```bash
npm run db:prepare-sample
npm run db:seed:local
```

The generated import is written below `.wrangler/imports/`; local D1 state is kept below `.wrangler/state/`. Both locations are disposable and ignored by Git.

The smoke test expects the standard sample dataset to contain:

| Table | Rows |
| --- | ---: |
| `genomes` | 1,075 |
| `operons` | 500 |
| `occurrences` | 1,154 |
| `occurrence_genes` | 3,902 |

### 3. Start the API Worker

```bash
npm run worker:dev
```

The Worker listens on `http://127.0.0.1:8787` and reuses the seeded local D1 state.

### 4. Start the Pages frontend

In a second terminal, run:

```bash
npm run pages:dev
```

Open `http://127.0.0.1:8080`. Pages serves `frontend/` and forwards same-origin `/api/*` requests to the Worker through the `API_WORKER` service binding.

The application uses URL hashes such as `#operons?page=1`, so local routing does not require fallback rewrites.

### 5. Optional local download data

If `downloads/operon_atlas_sample/` contains a complete release, seed it into the local R2 emulator:

```bash
npm run r2:seed:local
```

The downloads API also requires `DOWNLOAD_BASE_URL` to be a valid `https://` URL. Configure that Worker variable to the public host serving the files. Without it, `/api/downloads` intentionally returns an error. Seeding local R2 alone does not make the release files publicly downloadable.

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

The API is read-only. It accepts `GET` and `OPTIONS`; other methods return `405`. JSON responses include permissive CORS headers. Search values are normalized, limited to 120 characters, escaped for SQL `LIKE`, and bound as query parameters.

Pagination is fixed at 20 items per page. Invalid or missing page numbers normalize to page 1.

### Endpoints

| Endpoint | Purpose | Query parameters |
| --- | --- | --- |
| `GET /api/health` | Liveness check; returns `{ "ok": true }` | None |
| `GET /api/stats` | Counts genomes, operon families, occurrences, and occurrence-gene rows | None |
| `GET /api/organisms` | Lists genome keys and organism names for filters | None |
| `GET /api/operons` | Paginates and filters operon families | `page`, `min_genes`/`min_gene_count`, `max_genes`/`max_gene_count`, `genome_key`, `organism`/`organism_name`, `product`, `sort`, `direction` |
| `GET /api/operons/:operon_id` | Returns one family, its functional summary, and paginated occurrences | `page`, `product` |
| `GET /api/occurrences/:occurrence_id` | Returns one occurrence and its ordered, annotated genes | None |
| `GET /api/genomes` | Paginates and searches genomes | `page`, `search`, `sort`, `direction` |
| `GET /api/genomes/:genome_key` | Returns one genome and aggregate operon/gene counts | None |
| `GET /api/genomes/:genome_key/viewer` | Returns contig-grouped occurrence spans for the genome viewer | `min_genes`/`min_gene_count`, `max_genes`/`max_gene_count`, `product` |
| `GET /api/genomes/:genome_key/operons` | Returns paginated operon occurrences within a genome | `page`, gene-count filters, `product`, `sort`, `direction` |
| `GET /api/downloads` | Reads the current R2 manifest and adds public download URLs | None |

Supported operon sort fields are `operon_id`, `gene_count`, and `occurrence_count`; the default is `occurrence_count desc`. Supported genome sort fields are `genome_id`, `organism_name`, `operon_count`, and `gene_count`; the default is `genome_id asc`. All lists use a stable numeric identifier as a final tie-breaker.

Gene-count filters are clamped to `1..10000`. If the minimum exceeds the maximum, the values are swapped. Text filters use case-insensitive substring matching under SQLite's default `LIKE` behavior.

### Identifiers and annotations

- Numeric operon family IDs are displayed as `OAF` followed by six digits.
- Numeric occurrence IDs are displayed as `OAO` followed by six digits.
- PGFam values are displayed as `PGF_` followed by eight digits. A stored value of `-1` becomes `null`.
- Gene IDs are reconstructed as `<genome_id>.peg.<peg_num>`.
- Occurrence genes are ordered by contig and start coordinate.
- Pathway and subsystem annotations are joined to genes by genome, contig, coordinates, and strand. Genes without evidence return empty `pathways` and `subsystems` arrays.

### Caching and rate limiting

`/api/stats` is publicly cacheable for five minutes and `/api/organisms` for fifteen minutes. Other API responses currently do not set an explicit cache policy.

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
- `operon_function_*`, `operon_pathway_*`, and `operon_subsystem_*`: precomputed family-level functional summaries.

The schema and its indexes live in both `database/build_db.sql` and `database/build_sample_db.sql`. The two scripts differ primarily in whether they import `data/` or `sample_data/`.

### Rebuilding SQLite databases

Build the full database with:

```bash
cd database
sqlite3 operon_atlas.db < build_db.sql
cd ..
```

Build the sample database with:

```bash
cd database
sqlite3 operon_atlas_sample.db < build_sample_db.sql
cd ..
```

Both scripts drop and recreate application tables inside the target file. Back up any local database containing irreplaceable work before running them.

### Changing the schema

When adding a table or index:

1. Update both SQLite build scripts.
2. Add the corresponding TSV import to both scripts if the table is data-backed.
3. Update the explicit drop, dump, and index handling in `tools/prepare-d1-import.sh`.
4. Rebuild the sample database and regenerate the D1 import.
5. Seed fresh local Wrangler state and run the smoke tests.
6. Test the remote import against a non-production D1 database before changing production data.

`tools/prepare-d1-import.sh` emits tables in dependency order, removes SQLite-only dump statements, applies a compatibility repair for nullable subsystem classifications, and appends indexes. This explicit behavior is why a schema change must also update the script.

### Preparing the full D1 import

```bash
npm run db:prepare-full
```

The script reports both SQLite and generated SQL sizes. It warns when the SQL exceeds D1's configured single-file import threshold or the source database exceeds the configured paid-database size threshold. If the generated SQL is too large, split it into ordered files and validate the import process before using a remote database.

## Testing and verification

There is currently no unit-test suite or frontend build step. The automated checks are integration smoke tests against the standard sample dataset.

With the Worker running on port 8787:

```bash
npm run smoke:api
```

With Pages and the Worker running:

```bash
npm run smoke:pages
```

The smoke script verifies health, exact sample counts, representative family/occurrence/genome records, every genome sort mode, invalid-sort fallback, search filtering, and deterministic ordering. Because it contains fixed sample IDs and counts, update it deliberately whenever the canonical sample fixture changes.

Before deployment, also run Wrangler's Worker validation:

```bash
npm run worker:deploy:dry-run
```

For frontend changes, manually verify at least:

- home statistics and error handling;
- operon filters, sorting, pagination, and detail navigation;
- genome search, sorting, pagination, detail view, and genome viewer;
- occurrence gene graphics and functional annotations;
- back/forward navigation and copied hash URLs;
- empty and not-found states;
- downloads with the configured public file host; and
- desktop and narrow viewport layouts.

## Download release workflow

Release `1.0.0` currently expects this object layout in the `operonatlas-downloads` bucket:

```text
releases/1.0.0/downloads_manifest.json
releases/1.0.0/data_dictionary.tsv
releases/1.0.0/operon_families.tsv.gz
releases/1.0.0/operon_occurrences.tsv.gz
releases/1.0.0/operon_occurrence_genes.tsv.gz
```

The manifest contains release metadata, row counts, sizes, SHA-256 checksums, and dataset descriptions. `worker/src/downloads.py` owns the active release number and manifest key. Keep the generated files, manifest, Worker constant, upload prefix, and public download host synchronized when cutting a release.

Upload a normal-sized release with:

```bash
npm run r2:seed:remote -- downloads/operon_atlas_full
```

For large files, configure an `rclone` S3 remote named `r2` for the target bucket, inspect the operation, and then upload:

```bash
npm run r2:seed-full:remote:dry-run
npm run r2:seed-full:remote
```

After upload, verify every object, checksum, manifest URL, and browser download before announcing the release.

## Cloudflare deployment

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
npx wrangler d1 create operon_atlas_sample
npx wrangler r2 bucket create operonatlas-downloads
```

Configure `DOWNLOAD_BASE_URL` as a Worker variable in Cloudflare. It must be an HTTPS URL with no required trailing slash and should serve `releases/<release>/<filename>` from the R2 bucket, normally through an R2 custom domain.

### Seed remote data

For the sample database:

```bash
npm run db:prepare-sample
npm run db:seed:remote
```

For the full database, prepare it and execute the generated file against the intended D1 binding:

```bash
npm run db:prepare-full
cd worker
npx wrangler d1 execute operon_atlas_sample --remote --file ../.wrangler/imports/operon_atlas_full.sql
cd ..
```

The configured binding is currently named `operon_atlas_sample`; rename it consistently before a production full-data migration if the production database uses a different name. Data import is an administrative operation and should not run on every application deployment.

Seed R2 using the release workflow above.

### Deploy the Worker

Validate and deploy:

```bash
npm run worker:deploy:dry-run
npm run worker:deploy
```

Then test the deployed Worker directly before directing Pages traffic to it.

### Deploy Pages

The intended setup uses Cloudflare Pages Git integration:

- repository: `Core-Aub/operon-atlas`;
- production branch: `main`;
- root directory: repository root;
- build command: none; and
- output directory: `frontend`.

Configure the `API_WORKER` service binding for both production and preview environments as appropriate. The root `wrangler.toml` also records the Pages output directory and service binding for local development.

Pushes to the production branch can deploy the public site, while branches and pull requests can receive preview deployments. Do not use a manual Pages upload to create the project if Git-based deployments are required.

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
3. Run the Worker deployment dry run.
4. Manually verify affected UI states and routes.
5. Check that generated databases, Wrangler state, downloads, credentials, and machine-specific files remain untracked.
6. Summarize any required D1 migration, R2 upload, binding, or Cloudflare dashboard step in the pull request.

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

Updating the SQLite build scripts is not sufficient. Add the table to the ordered dump and drop lists in `tools/prepare-d1-import.sh`, regenerate the import, and seed fresh local D1 state.
