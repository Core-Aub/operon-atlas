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
              </tr>
            </thead>
            <tbody>
              ${data.items.map(renderOperonRow).join("") || emptyTableRow(4)}
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
  const data = await fetchJson(
    `/api/operons/${encodeURIComponent(operonId)}?${buildOperonOccurrenceApiQuery(page, filters)}`,
  );
  if (!isCurrentRoute(routeKey)) {
    return;
  }

  app.innerHTML = `
    <section class="section">
      ${pageHeader(
        escapeHtml(data.display_id || formatStableOperonId(data.operon_id)),
        returnLink("#operons?page=1"),
      )}

      <div class="section">
        ${renderInfoTable([
          ["Occurrence count", formatNumber(data.occurrence_count), "family-vs-occurrence"],
          ["Gene count", formatNumber(data.gene_count)],
          ["PGFam content", escapeHtml(formatPgfamContent(data.pgfams)), "family-vs-occurrence"],
          ...getOperonAnnotationCoverageRows(data.functional_summary),
        ])}
      </div>

      <div class="section functional-evidence-section">
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

function renderOperonRow(item) {
  return `
    <tr>
      <td class="numeric">${renderTableLink(`#operons/${item.operon_id}?page=1`, item.display_id || formatStableOperonId(item.operon_id))}</td>
      <td>${escapeHtml(formatPgfamContent(item.pgfams, 4))}</td>
      <td class="numeric">${formatNumber(item.gene_count)}</td>
      <td class="numeric">${formatNumber(item.occurrence_count)}</td>
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
