import { fetchJson } from "../api.js";
import { FILTER_TEXT_MAX_LENGTH } from "../config.js";
import { app } from "../dom.js";
import { iconClear, iconSearch } from "../components/icons.js";
import { pageHeader, sectionHeader } from "../components/layout.js";
import { renderPager } from "../components/pager.js";
import { getCurrentRouteKey, isCurrentRoute } from "../routing/route-state.js";
import { sanitizeFilterText } from "../components/filters.js";
import { emptyTableRow, escapeHtml } from "../utils/html.js";
import { formatNumber } from "../utils/format.js";

export async function renderSearch(
  page,
  params = new URLSearchParams(),
  routeKey = getCurrentRouteKey(),
) {
  const q = sanitizeFilterText(params.get("q"));
  const type = sanitizeFilterText(params.get("type"));
  if (!q) {
    renderSearchLanding();
    return;
  }

  const query = new URLSearchParams({ q });
  if (type) {
    query.set("type", type);
    query.set("page", String(page));
  }
  const data = await fetchJson(`/api/search?${query.toString()}`);
  if (!isCurrentRoute(routeKey)) {
    return;
  }

  app.innerHTML = `
    <section class="section search-page">
      ${pageHeader("Search OperonAtlas")}
      ${renderGlobalSearchForm(q)}
      ${data.mode === "entities" ? renderEntityResults(data) : renderPreviewResults(data)}
    </section>
  `;
}

export function renderGlobalSearchForm(value = "", options = {}) {
  const compact = options.compact ? " search-form-compact" : "";
  return `
    <form class="search-form global-search-form${compact}" data-global-search>
      <label>
        <span class="sr-only">Search OperonAtlas</span>
        <input
          type="search"
          maxlength="${FILTER_TEXT_MAX_LENGTH}"
          value="${escapeHtml(value)}"
          placeholder="Gene ID, product, PGFam, EC, pathway, subsystem, genome, or taxon"
          autocomplete="off"
          data-global-search-input
        >
      </label>
      <button class="button primary search-submit" type="submit">${iconSearch()}<span>Search</span></button>
      ${value ? `<button class="icon-button" type="button" data-global-search-clear aria-label="Clear search" title="Clear search">${iconClear()}</button>` : ""}
    </form>
  `;
}

function renderSearchLanding() {
  app.innerHTML = `
    <section class="section search-page">
      ${pageHeader("Search OperonAtlas")}
      ${renderGlobalSearchForm()}
      <div class="panel search-help-panel">
        <div class="panel-body">
          <p>Search by the biological entity you already know. Exact identifiers are resolved first; annotation and taxonomy suggestions follow.</p>
          <p class="muted">Supported identifiers include OAF, OAO, BV-BRC/fig gene IDs, PGFams, EC numbers, pathways, subsystems, genomes, and taxon IDs.</p>
        </div>
      </div>
    </section>
  `;
}

function renderPreviewResults(data) {
  const groups = Array.isArray(data.groups) ? data.groups : [];
  const directHits = Array.isArray(data.directHits) ? data.directHits : [];
  const hasEntities = groups.some((group) => Number(group.total) > 0);
  return `
    <div class="search-results-heading">
      <p>Results for <strong>${escapeHtml(data.q || "")}</strong></p>
      ${hasEntities ? `
        <a class="button" href="#operons?search=${encodeURIComponent(data.q || "")}&page=1">
          View all matching operon families
        </a>
      ` : ""}
    </div>
    ${directHits.length ? `
      <section class="search-result-section">
        ${sectionHeader("Direct matches")}
        <div class="search-result-grid">${directHits.map(renderDirectHit).join("")}</div>
      </section>
    ` : ""}
    ${groups.map((group) => renderPreviewGroup(group, data.q || "")).join("")}
    ${!directHits.length && !hasEntities ? `
      <div class="empty search-empty">No direct identifiers or annotation entities matched this search.</div>
    ` : ""}
  `;
}

function renderPreviewGroup(group, q) {
  if (!Number(group.total)) {
    return "";
  }
  const items = Array.isArray(group.items) ? group.items : [];
  const query = new URLSearchParams({
    q: String(q),
    type: String(group.type || ""),
    page: "1",
  });
  return `
    <section class="search-result-section">
      <div class="section-header search-group-header">
        <h2>${escapeHtml(group.typeLabel || group.type || "Matches")}</h2>
        ${Number(group.total) > items.length ? `
          <a href="#search?${query.toString()}">View all ${formatNumber(group.total)}</a>
        ` : ""}
      </div>
      <div class="search-result-grid">
        ${items.map((item) => renderEntityCard({ ...item, typeLabel: group.typeLabel })).join("")}
      </div>
    </section>
  `;
}

function renderEntityResults(data) {
  const pagerParams = new URLSearchParams({ q: data.q || "", type: data.type || "" });
  return `
    <section class="search-result-section">
      <div class="search-results-heading">
        <div>
          <p class="eyebrow">${escapeHtml(data.typeLabel || data.type || "Matches")}</p>
          <h2>Entities matching “${escapeHtml(data.q || "")}”</h2>
        </div>
        <a href="#search?q=${encodeURIComponent(data.q || "")}">Back to grouped results</a>
      </div>
      <div class="table-actions">
        <span class="muted">Select an entity to view all matching operon families.</span>
        ${renderPager("search", data, pagerParams)}
      </div>
      <div class="panel">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Type</th><th>Identifier</th><th>Name</th><th>Context</th></tr></thead>
            <tbody>
              ${(data.items || []).map((item) => renderEntityRow({ ...item, typeLabel: data.typeLabel })).join("") || emptyTableRow(4)}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;
}

function renderDirectHit(hit) {
  return `
    <a class="search-result-card" href="${escapeHtml(getDirectHitHref(hit))}">
      <span class="match-badge">${escapeHtml(getDirectHitBadge(hit))}</span>
      <strong>${escapeHtml(hit.identifier || hit.label || "Match")}</strong>
      ${hit.label && hit.label !== hit.identifier ? `<span>${escapeHtml(hit.label)}</span>` : ""}
      ${hit.context ? `<small>${escapeHtml(hit.context)}</small>` : ""}
    </a>
  `;
}

function renderEntityCard(entity) {
  return `
    <a class="search-result-card" href="${escapeHtml(getEntityHref(entity))}">
      <span class="match-badge">${escapeHtml(entity.typeLabel || entity.type || "Entity")}</span>
      <strong>${escapeHtml(entity.identifier || entity.label || "")}</strong>
      ${entity.label && entity.label !== entity.identifier ? `<span>${escapeHtml(entity.label)}</span>` : ""}
      ${entity.context ? `<small>${escapeHtml(entity.context)}</small>` : ""}
    </a>
  `;
}

function renderEntityRow(entity) {
  return `
    <tr>
      <td><span class="match-badge">${escapeHtml(entity.typeLabel || entity.type || "Entity")}</span></td>
      <td><a class="table-link" href="${escapeHtml(getEntityHref(entity))}">${escapeHtml(entity.identifier || "")}</a></td>
      <td>${escapeHtml(entity.label || "")}</td>
      <td>${escapeHtml(entity.context || "")}</td>
    </tr>
  `;
}

function getEntityHref(entity) {
  if (entity.type === "genome" && entity.key != null) {
    return `#genomes/${encodeURIComponent(entity.key)}?page=1`;
  }
  const params = new URLSearchParams({
    entity_type: String(entity.type || ""),
    entity_key: String(entity.key ?? ""),
    page: "1",
  });
  return `#operons?${params.toString()}`;
}

function getDirectHitHref(hit) {
  if (hit.kind === "operon" && hit.operonId != null) {
    return `#operons/${encodeURIComponent(hit.operonId)}?page=1`;
  }
  if ((hit.kind === "occurrence" || hit.kind === "gene") && hit.occurrenceId != null) {
    const params = new URLSearchParams();
    if (hit.geneId) {
      params.set("gene", hit.geneId);
    }
    const query = params.toString();
    return `#occurrences/${encodeURIComponent(hit.occurrenceId)}${query ? `?${query}` : ""}`;
  }
  if (hit.kind === "genome" && hit.genomeKey != null) {
    return `#genomes/${encodeURIComponent(hit.genomeKey)}?page=1`;
  }
  return getEntityHref(hit);
}

function getDirectHitBadge(hit) {
  const labels = {
    operon: "Operon family",
    occurrence: "Occurrence",
    gene: "Gene",
    genome: "Genome",
    entity: hit.typeLabel || hit.type || "Entity",
  };
  return labels[hit.kind] || hit.typeLabel || hit.kind || "Match";
}

export function handleGlobalSearchSubmit(event) {
  const form = event.target.closest("[data-global-search]");
  if (!form || !app.contains(form)) {
    return;
  }
  event.preventDefault();
  const q = sanitizeFilterText(form.querySelector("[data-global-search-input]")?.value);
  window.location.hash = q ? `#search?q=${encodeURIComponent(q)}` : "#search";
}

export function handleGlobalSearchClear(event) {
  const button = event.target.closest("[data-global-search-clear]");
  if (!button || !app.contains(button)) {
    return;
  }
  event.preventDefault();
  window.location.hash = "#search";
}
