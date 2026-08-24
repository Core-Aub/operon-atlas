import { fetchJson } from "../api.js";
import { app } from "../dom.js";
import {
  getCurrentRouteKey,
  isCurrentRoute,
} from "../routing/route-state.js";
import {
  pageHeader,
  renderInfoTable,
  returnLink,
  sectionHeader,
} from "../components/layout.js";
import { renderTableLink } from "../components/links.js";
import {
  renderGeneTableRows,
  renderGeneViewer,
  setGeneViewerGenes,
} from "../viewers/gene-viewer.js";
import {
  buildOccurrenceFunctionalSummary,
  formatAnnotatedGeneCoverage,
  renderOccurrenceFunctionalSummary,
} from "../components/occurrence-functional-summary.js?v=8";
import {
  COLUMN_INFO,
  renderColumnHeader,
} from "../components/table-header.js";
import { escapeHtml } from "../utils/html.js";
import {
  formatNumber,
  formatOccurrenceId,
  formatStableOperonId,
} from "../utils/format.js";

export async function renderOccurrenceDetail(
  occurrenceId,
  params = new URLSearchParams(),
  routeKey = getCurrentRouteKey(),
) {
  const gene = params.get("gene") || "";
  const geneQuery = gene ? `?gene=${encodeURIComponent(gene)}` : "";
  const data = await fetchJson(`/api/occurrences/${encodeURIComponent(occurrenceId)}${geneQuery}`);
  if (!isCurrentRoute(routeKey)) {
    return;
  }
  setGeneViewerGenes(data.genes || [], data.highlightGeneId || gene);
  const functionalSummary = buildOccurrenceFunctionalSummary(data.genes || []);

  app.innerHTML = `
    <section class="section">
      ${pageHeader(
        `${data.occurrence_display_id || formatOccurrenceId(data.occurrence_id)}`,
        returnLink("#operons?page=1"),
      )}

      <div class="section">
        ${renderInfoTable([
          ["Stable Operon ID", renderTableLink(`#operons/${data.operon_id}?page=1`, data.stable_display_id || formatStableOperonId(data.operon_id)), "family-vs-occurrence"],
          ["Genome ID", renderTableLink(`#genomes/${data.genome_key}?page=1`, data.genome_id)],
          ["Organism", escapeHtml(data.organism_name || "")],
          ["Gene count", formatNumber(data.gene_count)],
          ["Annotated genes", formatAnnotatedGeneCoverage(functionalSummary)],
        ])}
      </div>

      <div class="section">
        <h2>Operon view</h2>
        <div class="panel">
          <div class="gene-viewer">
            ${renderGeneViewer()}
          </div>
        </div>
      </div>

      <div class="section functional-evidence-section">
        ${renderOccurrenceFunctionalSummary(functionalSummary)}
      </div>

      <div class="section">
        ${sectionHeader("Genes")}
        <div class="panel">
          <div class="table-wrap">
            <table class="gene-table">
              <thead>
                <tr>
                  <th>${renderColumnHeader("Gene", COLUMN_INFO.GENE_LOCUS_ID)}</th>
                  <th>${renderColumnHeader("Annotation", COLUMN_INFO.GENE_FUNCTIONAL_EVIDENCE)}</th>
                  <th>${renderColumnHeader("PGFam", COLUMN_INFO.PROTEIN_FAMILY_ID)}</th>
                  <th>${renderColumnHeader("Position", COLUMN_INFO.CONTIG_GENOMIC_COORDINATES)}</th>
                  <th>${renderColumnHeader("Length", COLUMN_INFO.GENE_LENGTH_BASES)}</th>
                </tr>
              </thead>
              <tbody data-gene-table-body>
                ${renderGeneTableRows()}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  `;
}
