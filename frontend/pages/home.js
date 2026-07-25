import { fetchJson } from "../api.js";
import { app } from "../dom.js";
import { isCurrentRoute } from "../routing/route-state.js";
import { escapeHtml } from "../utils/html.js";
import { formatNumber } from "../utils/format.js";

export async function renderHome(routeKey) {
  app.innerHTML = `
    <section class="section home-section home-intro">
      <div class="section-header">
        <h2>Welcome to OperonAtlas</h2>
      </div>
      <p class="lede">
        OperonAtlas is a database and web interface for browsing predicted bacterial operons.
        The predictions are based on BV-BRC representative/reference bacterial genomes, and
        this interface allows browsing predicted operons, genomes, and gene-level operon
        structures. These are predicted operons, not experimentally validated operons.
      </p>
    </section>

    <section class="section home-section">
      <div class="section-header">
        <h2>Statistics</h2>
      </div>
      <div class="panel home-panel">
        <div class="table-wrap">
          <table>
            <tbody data-stats-body>
              ${statsLoadingRow()}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;

  try {
    const stats = await fetchJson("/api/stats");
    if (!isCurrentRoute(routeKey)) {
      return;
    }
    const statsBody = app.querySelector("[data-stats-body]");
    if (statsBody) {
      statsBody.innerHTML = renderStatsRows(stats);
    }
  } catch (error) {
    if (!isCurrentRoute(routeKey)) {
      return;
    }
    const statsBody = app.querySelector("[data-stats-body]");
    if (statsBody) {
      statsBody.innerHTML = statsErrorRow(error);
    }
  }
}

function renderStatsRows(stats) {
  return `
    ${statRow("Number of genomes", stats.genomes)}
    ${statRow("Number of operons", stats.operons)}
    ${statRow("Number of occurrences", stats.occurrences)}
    ${statRow("Number of occurrence-gene rows", stats.occurrence_genes)}
  `;
}

function statsLoadingRow() {
  return `
    <tr>
      <td colspan="2">Loading statistics...</td>
    </tr>
  `;
}

function statsErrorRow(error) {
  return `
    <tr>
      <td colspan="2">Unable to load statistics: ${escapeHtml(error.message)}</td>
    </tr>
  `;
}

function statRow(label, value) {
  return `
    <tr>
      <th>${escapeHtml(label)}</th>
      <td class="numeric">${formatNumber(value)}</td>
    </tr>
  `;
}
