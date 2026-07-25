import { escapeHtml } from "../utils/html.js";
import { firstPresent } from "../utils/format.js";
import {
  renderEcLink,
  renderKeggPathwayLink,
} from "./links.js";

export function renderAnnotationCell(gene) {
  const product = firstPresent(gene.product, "Unannotated product");
  const subsystems = getSubsystemEntries(gene);
  const pathways = getPathwayEntries(gene);
  const ecs = getEcEntries(gene);
  const roles = getRoleEntries(gene, product);
  const hasFunctionalAnnotation = subsystems.length || pathways.length || ecs.length;

  return `
    <div class="annotation-stack">
      <div class="annotation-section">
        <div class="annotation-label">Product</div>
        <div class="annotation-value primary" title="${escapeHtml(product)}">${escapeHtml(product)}</div>
      </div>
      ${hasFunctionalAnnotation ? [
        renderAnnotationSection("Subsystem", subsystems, 2),
        renderAnnotationSection("Pathway", pathways, 2),
        renderAnnotationSection("EC", ecs, 3, { inline: true }),
        renderAnnotationSection("Role", roles, 2),
      ].join("") : `<div class="annotation-empty">No functional annotation available</div>`}
    </div>
  `;
}

function getSubsystemEntries(gene) {
  const subsystems = Array.isArray(gene.subsystems) ? gene.subsystems : [];
  return uniqueEntries(subsystems.map((subsystem) => {
    const value = firstPresent(subsystem.subsystem_name, subsystem.subsystem_id);
    const secondary = [
      subsystem.subsystem_class,
      subsystem.subsystem_subclass,
    ].filter(Boolean).join(" / ") || firstPresent(subsystem.subsystem_superclass);
    return {
      value,
      secondary,
      title: [value, secondary].filter(Boolean).join("\n"),
    };
  }));
}

function getPathwayEntries(gene) {
  const pathways = Array.isArray(gene.pathways) ? gene.pathways : [];
  return uniqueEntries(pathways.map((pathway) => {
    const value = firstPresent(pathway.pathway_name, pathway.pathway_id);
    const pathwayId = firstPresent(pathway.pathway_id);
    const secondary = firstPresent(pathway.pathway_class);
    return {
      value,
      id: pathwayId,
      secondary,
      html: renderPathwayAnnotationValue(value, pathwayId),
      title: [value, secondary].filter(Boolean).join("\n"),
    };
  }));
}

function getEcEntries(gene) {
  const pathways = Array.isArray(gene.pathways) ? gene.pathways : [];
  return uniqueEntries(pathways.map((pathway) => {
    const value = firstPresent(pathway.ec_number);
    return {
      value,
      html: renderEcLink(value),
      title: [pathway.ec_number, pathway.ec_description].filter(Boolean).join(": "),
    };
  }));
}

function getRoleEntries(gene, product) {
  const subsystems = Array.isArray(gene.subsystems) ? gene.subsystems : [];
  return uniqueEntries(subsystems.map((subsystem) => ({
    value: firstPresent(subsystem.role_name, subsystem.role_id),
  }))).filter((entry) => isUsefulRole(entry.value, product));
}

function renderAnnotationSection(label, entries, limit, options = {}) {
  if (!entries.length) {
    return "";
  }
  const visible = entries.slice(0, limit);
  const hidden = entries.slice(limit);
  const hiddenTitle = hidden.map(formatAnnotationEntryTitle).join("\n");
  const hiddenHtml = hidden.map((entry, index) => renderAnnotationEntry(entry, {
    ...options,
    isLast: index === hidden.length - 1,
  })).join("");
  return `
    <div class="annotation-section">
      <div class="annotation-label">${escapeHtml(label)}</div>
      <div class="${options.inline ? "annotation-inline-values" : "annotation-values"}">
        ${visible.map((entry, index) => renderAnnotationEntry(entry, {
          ...options,
          isLast: index === visible.length - 1,
        })).join("")}
      </div>
      ${hidden.length ? `
        <details class="annotation-more">
          <summary title="${escapeHtml(hiddenTitle)}">+${hidden.length} more</summary>
          <div class="annotation-more-body ${options.inline ? "inline" : ""}">
            ${hiddenHtml}
          </div>
        </details>
      ` : ""}
    </div>
  `;
}

function renderAnnotationEntry(entry, options = {}) {
  const valueHtml = entry.html || escapeHtml(entry.value);
  if (options.inline) {
    return `<span title="${escapeHtml(formatAnnotationEntryTitle(entry))}">${valueHtml}${options.isLast ? "" : ","}</span>`;
  }
  return `
    <div class="annotation-entry">
      <div class="annotation-value" title="${escapeHtml(formatAnnotationEntryTitle(entry))}">${valueHtml}</div>
      ${entry.secondary ? `<div class="annotation-secondary">${escapeHtml(entry.secondary)}</div>` : ""}
    </div>
  `;
}

function renderPathwayAnnotationValue(value, pathwayId) {
  const pathwayLink = renderKeggPathwayLink(pathwayId);
  if (!pathwayLink) {
    return escapeHtml(value);
  }
  if (normalizeFunctionalText(value) === normalizeFunctionalText(pathwayId)) {
    return pathwayLink;
  }
  return `${escapeHtml(value)} <span class="annotation-separator">-</span> <span class="annotation-id">${pathwayLink}</span>`;
}

function formatAnnotationEntryTitle(entry) {
  return entry.title || [entry.value, entry.secondary].filter(Boolean).join("\n");
}

function uniqueEntries(entries) {
  const seen = new Set();
  return entries.filter((entry) => {
    const value = firstPresent(entry.value);
    if (!value) {
      return false;
    }
    const key = [
      normalizeFunctionalText(value),
      normalizeFunctionalText(entry.id || ""),
      normalizeFunctionalText(entry.secondary || ""),
    ].join("|");
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    entry.value = value;
    return true;
  });
}

function isUsefulRole(role, product) {
  const roleText = normalizeFunctionalText(role);
  const productText = normalizeFunctionalText(product);
  if (!roleText || !productText || roleText === productText) {
    return false;
  }
  return !(roleText.length > 16 && productText.includes(roleText))
    && !(productText.length > 16 && roleText.includes(productText));
}

function normalizeFunctionalText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}
