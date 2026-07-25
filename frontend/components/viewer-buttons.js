import { escapeHtml } from "../utils/html.js";

export function viewerButton(action, label, icon, disabled = false) {
  return `
    <button
      class="viewer-button icon-button"
      type="button"
      data-gene-nav="${escapeHtml(action)}"
      aria-label="${escapeHtml(label)}"
      title="${escapeHtml(label)}"
      ${disabled ? "disabled" : ""}
    >
      ${icon}
      <span class="sr-only">${escapeHtml(label)}</span>
    </button>
  `;
}

export function genomeViewerButton(action, label, icon, disabled = false) {
  return `
    <button
      class="viewer-button icon-button"
      type="button"
      data-genome-nav="${escapeHtml(action)}"
      aria-label="${escapeHtml(label)}"
      title="${escapeHtml(label)}"
      ${disabled ? "disabled" : ""}
    >
      ${icon}
      <span class="sr-only">${escapeHtml(label)}</span>
    </button>
  `;
}
