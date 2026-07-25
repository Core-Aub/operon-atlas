import { fetchJson } from "../api.js";
import { pageHeader, renderInfoTable, sectionHeader } from "../components/layout.js";
import { renderTableLink } from "../components/links.js";
import { app } from "../dom.js";
import { isCurrentRoute } from "../routing/route-state.js";
import { formatNumber } from "../utils/format.js";
import { emptyTableRow, escapeHtml } from "../utils/html.js";


export async function renderDownloads(routeKey) {
  const manifest = await fetchJson("/api/downloads");
  if (!isCurrentRoute(routeKey)) {
    return;
  }

  app.innerHTML = `
    <section class="section">
      ${pageHeader("Downloads")}

      <div class="section downloads-summary">
        ${renderInfoTable([
          ["Release", escapeHtml(manifest.release || "")],
          ["Generated", escapeHtml(formatDateTime(manifest.generated_at))],
        ])}
      </div>

      <div class="section">
        ${sectionHeader("Datasets")}
        <div class="panel">
          <div class="table-wrap">
            <table class="downloads-table">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Description</th>
                  <th>Format</th>
                  <th>Rows</th>
                  <th>Size</th>
                  <th>SHA-256</th>
                  <th>Download</th>
                </tr>
              </thead>
              <tbody>
                ${(manifest.datasets || []).map(renderDatasetRow).join("") || emptyTableRow(7)}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="section">
        ${sectionHeader("Documentation")}
        <div class="panel">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Description</th>
                  <th>Download</th>
                </tr>
              </thead>
              <tbody>
                ${renderDocumentationRow(manifest.documentation)}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  `;
}


function renderDatasetRow(item) {
  return `
    <tr>
      <td>${escapeHtml(item.dataset || "")}</td>
      <td>${escapeHtml(item.description || "")}</td>
      <td>${escapeHtml(item.format || "")}</td>
      <td class="numeric">${formatNumber(item.rows)}</td>
      <td class="numeric">${escapeHtml(item.compressed_size || "")}</td>
      <td><code class="checksum">${escapeHtml(item.sha256 || "")}</code></td>
      <td>${renderDownloadLink(item.download_url, item.filename)}</td>
    </tr>
  `;
}


function renderDocumentationRow(documentation) {
  if (!documentation || !documentation.filename) {
    return emptyTableRow(3);
  }

  return `
    <tr>
      <td>${escapeHtml(documentation.filename)}</td>
      <td>${escapeHtml(documentation.description || "")}</td>
      <td>${renderDownloadLink(documentation.download_url, documentation.filename)}</td>
    </tr>
  `;
}


function renderDownloadLink(url, filename) {
  if (!url || !filename) {
    return "";
  }
  return renderTableLink(url, "Link", {
    title: `Link ${filename}`,
  });
}


function formatDateTime(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    // hour: "2-digit",
    // minute: "2-digit",
  });
}
