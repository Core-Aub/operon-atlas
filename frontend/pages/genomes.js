import { fetchJson } from "../api.js";
import {
  DEFAULT_GENOME_SORT,
  DEFAULT_GENOME_SORT_DIRECTION,
  FILTER_TEXT_MAX_LENGTH,
  GENOME_SORT_FIELDS,
} from "../config.js";
import { app } from "../dom.js";
import {
  getCurrentRouteKey,
  isCurrentRoute,
} from "../routing/route-state.js";
import { parseHash } from "../routing/hash.js";
import {
  buildGenomeOperonApiQuery,
  buildGenomeViewerApiQuery,
  getGenomeOperonFilters,
  getGenomeOperonPagerParams,
  renderFilterMenu,
  sanitizeFilterText,
} from "../components/filters.js";
import {
  iconClear,
  iconSearch,
} from "../components/icons.js";
import {
  pageHeader,
  renderInfoTable,
  returnLink,
  sectionHeader,
} from "../components/layout.js";
import { renderTableLink } from "../components/links.js";
import { renderPager } from "../components/pager.js";
import {
  renderGenomeListSortableHeader,
  renderGenomeSortableHeader,
} from "../components/sort.js";
import {
  COLUMN_INFO,
  renderColumnHeader,
} from "../components/table-header.js";
import {
  renderGenomeViewer,
  setGenomeViewerData,
} from "../viewers/genome-viewer.js?v=1";
import { emptyTableRow, escapeHtml } from "../utils/html.js";
import {
  formatNumber,
  formatOccurrenceId,
  formatStableOperonId,
} from "../utils/format.js";

export async function renderGenomes(page, params = new URLSearchParams(), routeKey = getCurrentRouteKey()) {
  const state = getGenomeListState(params);
  const query = getGenomeListParams(state);
  query.set("page", String(page));
  const data = await fetchJson(`/api/genomes?${query.toString()}`);
  if (!isCurrentRoute(routeKey)) {
    return;
  }
  app.innerHTML = `
    <section class="section">
      ${pageHeader("Genomes")}
      <div class="table-actions">
        ${renderGenomeSearch(state.search)}
        ${renderPager("genomes", data, getGenomeListParams(state))}
      </div>
      <div class="panel">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${renderGenomeListSortableHeader("Genome ID", "genome_id", state, COLUMN_INFO.GENOME_ACCESSION_ID)}</th>
                <th>${renderGenomeListSortableHeader("Species/Organism", "organism_name", state, COLUMN_INFO.GENOME_ORGANISM_NAME)}</th>
                <th>${renderGenomeListSortableHeader("Operons", "operon_count", state, COLUMN_INFO.PREDICTED_OPERON_COUNT)}</th>
                <th>${renderGenomeListSortableHeader("Genes", "gene_count", state, COLUMN_INFO.OPERON_ASSOCIATED_GENE_COUNT)}</th>
              </tr>
            </thead>
            <tbody>
              ${data.items.map(renderGenomeRow).join("") || emptyTableRow(4)}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;
}

export async function renderGenomeDetail(
  genomeKey,
  operonPage,
  params = new URLSearchParams(),
  routeKey = getCurrentRouteKey(),
) {
  const filters = getGenomeOperonFilters(params);
  const [genome, viewer, operons] = await Promise.all([
    fetchJson(`/api/genomes/${encodeURIComponent(genomeKey)}`),
    fetchJson(`/api/genomes/${encodeURIComponent(genomeKey)}/viewer?${buildGenomeViewerApiQuery(filters)}`),
    fetchJson(
      `/api/genomes/${encodeURIComponent(genomeKey)}/operons?${buildGenomeOperonApiQuery(operonPage, filters)}`,
    ),
  ]);
  if (!isCurrentRoute(routeKey)) {
    return;
  }
  setGenomeViewerData(viewer);

  app.innerHTML = `
    <section class="section">
      ${pageHeader(
        escapeHtml(genome.organism_name || genome.genome_id),
        returnLink("#genomes?page=1"),
      )}

      <div class="section">
        ${renderInfoTable([
          ["Genome ID", escapeHtml(genome.genome_id)],
          ["Operon count", formatNumber(genome.operon_count)],
          ["Gene count", formatNumber(genome.gene_count)],
        ])}
      </div>

      <div class="section">
        ${sectionHeader("Genome view")}
        <div class="panel">
          <div class="genome-viewer">
            ${renderGenomeViewer()}
          </div>
        </div>
      </div>

      <div class="section">
        ${sectionHeader("Operons")}
        <div class="operon-table-actions">
          ${renderFilterMenu(filters, { includeOrganism: false })}
          ${renderPager(`genomes/${genome.genome_key}`, operons, getGenomeOperonPagerParams(filters))}
        </div>
        <div class="panel">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${renderGenomeSortableHeader(`genomes/${genome.genome_key}`, "Stable Operon ID", "operon_id", filters, COLUMN_INFO.OPERON_FAMILY_ID)}</th>
                  <th>${renderColumnHeader("Occurrence ID", COLUMN_INFO.GENOME_OCCURRENCE_ID)}</th>
                  <th>${renderGenomeSortableHeader(`genomes/${genome.genome_key}`, "Gene count", "gene_count", filters, COLUMN_INFO.GENES_PER_OCCURRENCE)}</th>
                  <th>${renderGenomeSortableHeader(`genomes/${genome.genome_key}`, "Global occurrence count", "occurrence_count", filters, COLUMN_INFO.GLOBAL_GENOME_OCCURRENCES)}</th>
                </tr>
              </thead>
              <tbody>
                ${operons.items.map(renderGenomeOperonRow).join("") || emptyTableRow(4)}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderGenomeSearch(search) {
  return `
    <form class="search-form" data-genome-search>
      <label>
        <span class="sr-only">Search genomes</span>
        <input
          type="text"
          maxlength="${FILTER_TEXT_MAX_LENGTH}"
          value="${escapeHtml(search)}"
          placeholder="100.11 or Ancylobacter aquaticus strain DSM 101"
          data-genome-search-input
        >
      </label>
      <button class="icon-button" type="submit">${iconSearch()}</button>
      ${search ? `<button class="icon-button" type="button" data-genome-search-clear>${iconClear()}</button>` : ""}
    </form>
  `;
}

function getGenomeListState(params) {
  const requestedSort = params.get("sort") || DEFAULT_GENOME_SORT;
  const requestedDirection = (params.get("direction") || DEFAULT_GENOME_SORT_DIRECTION).toLowerCase();
  return {
    search: sanitizeFilterText(params.get("search")),
    sort: GENOME_SORT_FIELDS.has(requestedSort) ? requestedSort : DEFAULT_GENOME_SORT,
    direction: requestedDirection === "desc" ? "desc" : "asc",
  };
}

function getGenomeListParams(state) {
  const params = new URLSearchParams();
  params.set("sort", state.sort);
  params.set("direction", state.direction);
  if (state.search) {
    params.set("search", state.search);
  }
  return params;
}

function renderGenomeRow(item) {
  return `
    <tr>
      <td>${renderTableLink(`#genomes/${item.genome_key}?page=1`, item.genome_id)}</td>
      <td>${escapeHtml(item.organism_name || "")}</td>
      <td class="numeric">${formatNumber(item.operon_count)}</td>
      <td class="numeric">${formatNumber(item.gene_count)}</td>
    </tr>
  `;
}

function renderGenomeOperonRow(item) {
  return `
    <tr>
      <td class="numeric">${renderTableLink(`#operons/${item.operon_id}?page=1`, item.display_id || formatStableOperonId(item.operon_id))}</td>
      <td class="numeric">${renderTableLink(`#occurrences/${item.occurrence_id}`, item.occurrence_display_id || formatOccurrenceId(item.occurrence_id))}</td>
      <td class="numeric">${formatNumber(item.gene_count)}</td>
      <td class="numeric">${formatNumber(item.occurrence_count)}</td>
    </tr>
  `;
}

export function handleGenomeSearchSubmit(event) {
  const form = event.target.closest("[data-genome-search]");
  if (!form || !app.contains(form)) {
    return;
  }

  event.preventDefault();
  const search = sanitizeFilterText(form.querySelector("[data-genome-search-input]")?.value);
  setGenomeSearchRoute(search);
}

export function handleGenomeSearchClear(event) {
  const button = event.target.closest("[data-genome-search-clear]");
  if (!button || !app.contains(button)) {
    return;
  }

  event.preventDefault();
  setGenomeSearchRoute("");
}

function setGenomeSearchRoute(search) {
  const state = getGenomeListState(parseHash().params);
  state.search = search;
  const params = getGenomeListParams(state);
  params.set("page", "1");
  const query = params.toString();
  window.location.hash = query ? `#genomes?${query}` : "#genomes?page=1";
}
