import { iconArrowUpRight } from "./icons.js";
import { escapeHtml } from "../utils/html.js";

export function renderTableLink(href, label, options = {}) {
  const className = options.className || "table-link";
  const attrs = [
    `class="${escapeHtml(className)}"`,
    `href="${escapeHtml(href)}"`,
  ];
  if (options.title) {
    attrs.push(`title="${escapeHtml(options.title)}"`);
  }
  if (options.external) {
    attrs.push('target="_blank"');
    attrs.push('rel="noopener noreferrer"');
  }
  return `<a ${attrs.join(" ")}><span>${escapeHtml(label)}</span>${iconArrowUpRight()}</a>`;
}

export function renderEcLink(ecNumber) {
  const value = normalizeLinkId(ecNumber);
  if (!value) {
    return "";
  }
  return renderTableLink(`https://enzyme.expasy.org/EC/${encodeURIComponent(value)}`, value, {
    external: true,
  });
}

export function renderKeggPathwayLink(pathwayId) {
  const value = normalizeLinkId(pathwayId);
  if (!value) {
    return "";
  }
  return renderTableLink(`https://www.kegg.jp/pathway/map${encodeURIComponent(value)}`, value, {
    external: true,
  });
}

function normalizeLinkId(value) {
  const normalized = value == null ? "" : String(value).trim();
  return normalized || "";
}
