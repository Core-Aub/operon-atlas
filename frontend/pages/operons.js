import { fetchJson } from "../api.js";
import { app } from "../dom.js";
import {
  getCurrentRouteKey,
  isCurrentRoute,
} from "../routing/route-state.js";
import {
  buildOperonApiQuery,
  buildOperonOccurrenceApiQuery,
  getOccurrenceFilters,
  getOperonFilters,
  getOperonOccurrencePagerParams,
  getOperonPagerParams,
  renderFilterMenu,
  renderOccurrenceFilterMenu,
} from "../components/filters.js";
import {
  pageHeader,
  renderInfoTable,
  returnLink,
  sectionHeader,
} from "../components/layout.js";
import { renderTableLink } from "../components/links.js";
import {
  getOperonAnnotationCoverageRows,
  renderOperonFunctionalSummary,
} from "../components/occurrence-functional-summary.js?v=8";
import { renderPager } from "../components/pager.js";
import { renderSortableHeader } from "../components/sort.js";
import {
  COLUMN_INFO,
  renderColumnHeader,
} from "../components/table-header.js";
import { emptyTableRow, escapeHtml } from "../utils/html.js";
import {
  formatNumber,
  formatOccurrenceId,
  formatPgfamContent,
  formatStableOperonId,
} from "../utils/format.js";

export async function renderOperons(page, params = new URLSearchParams(), routeKey = getCurrentRouteKey()) {
  const filters = getOperonFilters(params);
  const data = await fetchJson(`/api/operons?${buildOperonApiQuery(page, filters)}`);
  if (!isCurrentRoute(routeKey)) {
    return;
  }
  app.innerHTML = `
    <section class="section">
      ${pageHeader("Operons")}
      ${renderActiveMatch(data.entityFilter, data.search)}
      <div class="operon-table-actions">
        ${renderFilterMenu(filters)}
        ${renderPager("operons", data, getOperonPagerParams(filters))}
      </div>
      <div class="panel">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>${renderSortableHeader("Stable Operon ID", "operon_id", filters, COLUMN_INFO.OPERON_FAMILY_ID)}</th>
                <th>${renderColumnHeader("PGFam content", COLUMN_INFO.PROTEIN_FAMILY_COMPOSITION)}</th>
                <th>${renderSortableHeader("Gene count", "gene_count", filters, COLUMN_INFO.GENES_PER_OPERON)}</th>
                <th>${renderSortableHeader("Occurrence count", "occurrence_count", filters, COLUMN_INFO.GENOME_OCCURRENCE_COUNT)}</th>
                <th>Taxonomic breadth</th>
              </tr>
            </thead>
            <tbody>
              ${data.items.map((item) => renderOperonRow(item, filters)).join("") || emptyTableRow(5)}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;
}

export async function renderOperonDetail(
  operonId,
  page,
  params = new URLSearchParams(),
  routeKey = getCurrentRouteKey(),
) {
  const filters = getOccurrenceFilters(params);
  const generaPage = parsePositivePage(params.get("genera_page"));
  const [data, taxonomy] = await Promise.all([
    fetchJson(
      `/api/operons/${encodeURIComponent(operonId)}?${buildOperonOccurrenceApiQuery(page, filters)}`,
    ),
    fetchJson(`/api/operons/${encodeURIComponent(operonId)}/taxonomy?page=${generaPage}`),
  ]);
  if (!isCurrentRoute(routeKey)) {
    return;
  }

  app.innerHTML = `
    <section class="section">
      ${pageHeader(
        escapeHtml(data.display_id || formatStableOperonId(data.operon_id)),
        returnLink("#operons?page=1"),
      )}

      ${renderActiveMatch(data.entityFilter, data.search, data.operon_id)}

      <div class="section">
        ${renderInfoTable([
          ["Occurrence count", formatNumber(data.occurrence_count), "family-vs-occurrence"],
          ["Gene count", formatNumber(data.gene_count)],
          ["PGFam content", escapeHtml(formatPgfamContent(data.pgfams)), "family-vs-occurrence"],
        ])}
      </div>

      ${renderTaxonomySection(taxonomy, data.operon_id, params)}

      <div class="section functional-evidence-section">
        ${renderInfoTable(getOperonAnnotationCoverageRows(data.functional_summary))}
        ${renderOperonFunctionalSummary(data.functional_summary)}
      </div>

      <div class="section">
        ${sectionHeader("Occurrences")}
        <div class="operon-table-actions">
          ${renderOccurrenceFilterMenu(filters)}
          ${renderPager(`operons/${data.operon_id}`, data, getOperonOccurrencePagerParams(filters))}
        </div>
        <div class="panel">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>${renderColumnHeader("Occurrence ID", COLUMN_INFO.GENOME_OCCURRENCE_ID)}</th>
                  <th>${renderColumnHeader("Genome ID", COLUMN_INFO.GENOME_ACCESSION_ID)}</th>
                  <th>${renderColumnHeader("Organism", COLUMN_INFO.GENOME_ORGANISM_NAME)}</th>
                  <th>${renderColumnHeader("Gene count", COLUMN_INFO.GENES_PER_OCCURRENCE)}</th>
                </tr>
              </thead>
              <tbody>
                ${(data.occurrences || []).map(renderOperonOccurrenceRow).join("") || emptyTableRow(4)}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  `;
}

function renderOperonRow(item, filters) {
  const detailParams = getOperonOccurrencePagerParams(filters);
  detailParams.set("page", "1");
  return `
    <tr>
      <td class="numeric">${renderTableLink(`#operons/${item.operon_id}?${detailParams.toString()}`, item.display_id || formatStableOperonId(item.operon_id))}</td>
      <td>${escapeHtml(formatPgfamContent(item.pgfams, 4))}${renderMatchReasons(item.matchReasons)}</td>
      <td class="numeric">${formatNumber(item.gene_count)}</td>
      <td class="numeric">${formatNumber(item.occurrence_count)}</td>
      <td>${renderBreadth(item.taxonomyCounts)}</td>
    </tr>
  `;
}

function renderOperonOccurrenceRow(item) {
  return `
    <tr>
      <td class="numeric">${renderTableLink(`#occurrences/${item.occurrence_id}`, item.display_id || formatOccurrenceId(item.occurrence_id))}</td>
      <td>${renderTableLink(`#genomes/${item.genome_key}?page=1`, item.genome_id)}</td>
      <td>${escapeHtml(item.organism_name || "")}</td>
      <td class="numeric">${formatNumber(item.gene_count)}</td>
    </tr>
  `;
}

function renderBreadth(counts = {}) {
  return `
    <span class="breadth-summary">
      <span><strong>${formatNumber(counts.genomes || 0)}</strong> genomes</span>
      <span><strong>${formatNumber(counts.species || 0)}</strong> species</span>
      <span><strong>${formatNumber(counts.genera || 0)}</strong> genera</span>
      <span><strong>${formatNumber(counts.phyla || 0)}</strong> phyla</span>
    </span>
  `;
}

function renderActiveMatch(entityFilter, search, operonId = null) {
  if (!entityFilter && !search) {
    return "";
  }
  const label = entityFilter
    ? [entityFilter.identifier, entityFilter.label].filter(Boolean).join(" — ")
    : search;
  const type = entityFilter?.typeLabel || entityFilter?.type || "Search";
  const clearHref = operonId == null
    ? "#operons?page=1"
    : `#operons/${encodeURIComponent(operonId)}?page=1`;
  return `
    <div class="active-match panel">
      <div>
        <span class="match-badge">${escapeHtml(type)}</span>
        <span>Showing matches for <strong>${escapeHtml(label || "")}</strong></span>
      </div>
      <a href="${clearHref}">Clear match</a>
    </div>
  `;
}

function renderMatchReasons(reasons) {
  if (!Array.isArray(reasons) || !reasons.length) {
    return "";
  }
  return `
    <div class="match-reasons" aria-label="Why this family matched">
      ${reasons.slice(0, 4).map((reason) => `
        <span class="match-badge" title="${escapeHtml(reason.label || reason.identifier || "")}">
          ${escapeHtml(reason.typeLabel || reason.type || "Match")}: ${escapeHtml(reason.identifier || reason.label || "")}
        </span>
      `).join("")}
    </div>
  `;
}

function renderTaxonomySection(taxonomy, operonId, params) {
  const counts = taxonomy?.counts || {};
  const phyla = Array.isArray(taxonomy?.phyla) ? taxonomy.phyla : [];
  const genera = taxonomy?.genera || { page: 1, pageSize: 20, total: 0, items: [] };
  return `
    <section class="section taxonomy-section">
      ${sectionHeader("Taxonomic breadth")}
      <div class="taxonomy-headlines">
        ${taxonomyMetric("Genomes", counts.genomes)}
        ${taxonomyMetric("Species", counts.species)}
        ${taxonomyMetric("Genera", counts.genera)}
        ${taxonomyMetric("Phyla", counts.phyla)}
      </div>
      <div class="taxonomy-grid">
        <div>
          <h3>Phyla</h3>
          <div class="panel"><div class="table-wrap">
            <table>
              <thead><tr><th>Phylum</th><th>Genomes</th><th>Species</th></tr></thead>
              <tbody>${phyla.map(renderTaxonRow).join("") || emptyTableRow(3)}</tbody>
            </table>
          </div></div>
        </div>
        <div>
          <div class="taxonomy-subheader">
            <h3>Genera</h3>
            ${renderGeneraPager(operonId, genera, params)}
          </div>
          <div class="panel"><div class="table-wrap">
            <table>
              <thead><tr><th>Genus</th><th>Genomes</th><th>Species</th></tr></thead>
              <tbody>${(genera.items || []).map(renderTaxonRow).join("") || emptyTableRow(3)}</tbody>
            </table>
          </div></div>
        </div>
      </div>
      ${renderUnclassifiedCoverage(taxonomy?.unclassified)}
    </section>
  `;
}

function taxonomyMetric(label, value) {
  return `<div class="taxonomy-metric"><strong>${formatNumber(value || 0)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function renderTaxonRow(item) {
  return `
    <tr>
      <td>${escapeHtml(item.name || "Unclassified")}${item.taxonId != null ? `<small class="taxon-id">Taxon ${escapeHtml(item.taxonId)}</small>` : ""}</td>
      <td class="numeric">${formatNumber(item.genomeCount || 0)}</td>
      <td class="numeric">${formatNumber(item.speciesCount || 0)}</td>
    </tr>
  `;
}

function renderGeneraPager(operonId, genera, params) {
  if (Number(genera.total || 0) <= Number(genera.pageSize || 20)) {
    return `<span class="muted">Top ${formatNumber(genera.total || 0)}</span>`;
  }
  const current = Number(genera.page || 1);
  const pageSize = Number(genera.pageSize || 20);
  const total = Number(genera.total || 0);
  const nextParams = new URLSearchParams(params);
  const previousParams = new URLSearchParams(params);
  nextParams.set("genera_page", String(current + 1));
  previousParams.set("genera_page", String(Math.max(1, current - 1)));
  return `
    <span class="taxonomy-pager">
      <span>${formatNumber((current - 1) * pageSize + 1)}-${formatNumber(Math.min(current * pageSize, total))}/${formatNumber(total)}</span>
      ${current > 1 ? `<a href="#operons/${operonId}?${previousParams.toString()}">Previous</a>` : ""}
      ${current * pageSize < total ? `<a href="#operons/${operonId}?${nextParams.toString()}">Show more</a>` : ""}
    </span>
  `;
}

function renderUnclassifiedCoverage(unclassified = {}) {
  const species = Number(unclassified.speciesGenomes || 0);
  const genera = Number(unclassified.generaGenomes || unclassified.genusGenomes || 0);
  const phyla = Number(unclassified.phylaGenomes || unclassified.phylumGenomes || 0);
  if (!species && !genera && !phyla) {
    return "";
  }
  return `
    <p class="taxonomy-unclassified muted">
      Unclassified coverage: ${formatNumber(species)} genomes without species, ${formatNumber(genera)} without genus, and ${formatNumber(phyla)} without phylum assignment.
    </p>
  `;
}

function parsePositivePage(value) {
  const parsed = Number.parseInt(value || "1", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}
