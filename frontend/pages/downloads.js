import { fetchJson } from "../api.js";
import { pageHeader, renderInfoTable, sectionHeader } from "../components/layout.js";
import { renderTableLink } from "../components/links.js";
import { app } from "../dom.js";
import { isCurrentRoute } from "../routing/route-state.js";
import { formatBytes, formatNumber } from "../utils/format.js?v=3";
import { emptyTableRow, escapeHtml } from "../utils/html.js";
import {
  COLUMN_INFO,
  renderColumnHeader,
} from "../components/table-header.js";


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
                  <th>${renderColumnHeader("Dataset", COLUMN_INFO.EXPORT_DATASET_NAME)}</th>
                  <th>${renderColumnHeader("Description", COLUMN_INFO.DATASET_CONTENTS_SUMMARY)}</th>
                  <th>${renderColumnHeader("Format", COLUMN_INFO.ARCHIVE_FILE_FORMAT)}</th>
                  <th>${renderColumnHeader("Rows", COLUMN_INFO.EXPORTED_ROW_COUNT)}</th>
                  <th>${renderColumnHeader("Size", COLUMN_INFO.COMPRESSED_FILE_SIZE)}</th>
                  <th>${renderColumnHeader("SHA-256", COLUMN_INFO.FILE_INTEGRITY_CHECKSUM)}</th>
                  <th>${renderColumnHeader("Download", COLUMN_INFO.DATASET_DOWNLOAD_LINK)}</th>
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
                  <th>${renderColumnHeader("File", COLUMN_INFO.DOCUMENTATION_FILE_NAME)}</th>
                  <th>${renderColumnHeader("Description", COLUMN_INFO.FILE_CONTENTS_SUMMARY)}</th>
                  <th>${renderColumnHeader("Download", COLUMN_INFO.DOCUMENTATION_DOWNLOAD_LINK)}</th>
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
  const exactBytes = formatNumber(item.compressed_bytes);
  const sizeTitle = exactBytes
    ? ` title="${escapeHtml(`${exactBytes} bytes`)}"`
    : "";
  return `
    <tr>
      <td>${escapeHtml(item.dataset || "")}</td>
      <td>${escapeHtml(item.description || "")}</td>
      <td>${escapeHtml(item.format || "")}</td>
      <td class="numeric">${formatNumber(item.rows)}</td>
      <td class="numeric"${sizeTitle}>${escapeHtml(formatBytes(item.compressed_bytes))}</td>
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
