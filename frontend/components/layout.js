import { iconChevronLeft } from "./icons.js";
import { escapeHtml } from "../utils/html.js";

export function pageHeader(title, action = "") {
  return `
    <div class="page-header">
      <h1>${title}</h1>
      ${action}
    </div>
  `;
}

export function sectionHeader(title) {
  return `
    <div class="section-header">
      <h2>${escapeHtml(title)}</h2>
    </div>
  `;
}

export function returnLink(href) {
  return `
    <a class="return-link" href="${href}" data-return-link>
      ${iconChevronLeft()}
      <span>Return to list</span>
    </a>
  `;
}

export function renderInfoTable(rows) {
  return `
    <div class="panel summary-panel">
      <div class="table-wrap">
        <table>
          <tbody>
            ${rows.map(([label, value, helpAnchor]) => summaryRow(label, value, helpAnchor)).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function summaryRow(label, value, helpAnchor = "") {
  return `
    <tr>
      <th>
        <span class="summary-label">
          <span>${escapeHtml(label)}</span>
          ${helpAnchor ? `<a class="concept-help-link" href="#help/${helpAnchor}" aria-label="Help about ${escapeHtml(label)}" title="Learn more">?</a>` : ""}
        </span>
      </th>
      <td>${value}</td>
    </tr>
  `;
}
