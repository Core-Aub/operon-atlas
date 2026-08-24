import {
  DEFAULT_OPERON_SORT,
  DEFAULT_OPERON_SORT_DIRECTION,
  FILTER_TEXT_MAX_LENGTH,
  OPERON_FILTER_MAX,
  OPERON_FILTER_MIN,
  OPERON_ENTITY_TYPES,
  OPERON_SORT_FIELDS,
} from "../config.js";
import { app } from "../dom.js";
import { parseHash } from "../routing/hash.js";
import { iconClose, iconFilter } from "./icons.js";
import { escapeHtml } from "../utils/html.js";
import { clamp } from "../utils/format.js";

let operonFiltersOpen = false;

export function renderFilterMenu(filters, options = {}) {
  const includeOrganism = options.includeOrganism !== false;
  return `
    <div class="filters" data-filters-root>
      <button class="button filters-button" type="button" data-filter-action="open" aria-label="Filters" title="Filters">
        ${iconFilter()}
        <span>Filters</span>
      </button>
      <div class="filters-menu ${operonFiltersOpen ? "open" : ""}" data-filters-menu>
        <button class="filters-close" type="button" data-filter-action="close" aria-label="Close filters">
          ${iconClose()}
        </button>
        <div class="filters-grid">
          <label>
            <span>Min gene count</span>
            <input
              type="number"
              min="${OPERON_FILTER_MIN}"
              max="${OPERON_FILTER_MAX}"
              step="1"
              value="${filters.minGeneCount}"
              data-filter-field="min_genes"
            >
          </label>
          <label>
            <span>Max gene count</span>
            <input
              type="number"
              min="${OPERON_FILTER_MIN}"
              max="${OPERON_FILTER_MAX}"
              step="1"
              value="${filters.maxGeneCount}"
              data-filter-field="max_genes"
            >
          </label>
          ${includeOrganism ? `
            <label class="filters-organism">
              <span>Organism/species contains</span>
              <input
                type="text"
                maxlength="${FILTER_TEXT_MAX_LENGTH}"
                value="${escapeHtml(filters.organism)}"
                placeholder="100.11 or Ancylobacter aquaticus"
                data-filter-field="organism"
              >
            </label>
          ` : ""}
          <label class="filters-product">
            <span>Product contains</span>
            <input
              type="text"
              maxlength="${FILTER_TEXT_MAX_LENGTH}"
              value="${escapeHtml(filters.product)}"
              placeholder="ATP synthase, transposase, ribosomal protein"
              data-filter-field="product"
            >
          </label>
        </div>
        <div class="filters-actions">
          <button class="button" type="button" data-filter-action="clear">Clear</button>
          <button class="button primary" type="button" data-filter-action="apply">Apply</button>
        </div>
      </div>
    </div>
  `;
}

export function renderOccurrenceFilterMenu(filters) {
  return `
    <div class="filters" data-filters-root data-filter-kind="occurrences">
      <button class="button filters-button" type="button" data-filter-action="open" aria-label="Filters" title="Filters">
        ${iconFilter()}
        <span>Filters</span>
      </button>
      <div class="filters-menu ${operonFiltersOpen ? "open" : ""}" data-filters-menu>
        <button class="filters-close" type="button" data-filter-action="close" aria-label="Close filters">
          ${iconClose()}
        </button>
        <div class="filters-grid">
          <label class="filters-product">
            <span>Product contains</span>
            <input
              type="text"
              maxlength="${FILTER_TEXT_MAX_LENGTH}"
              value="${escapeHtml(filters.product)}"
              placeholder="ATP synthase, transposase, ribosomal protein"
              data-filter-field="product"
            >
          </label>
        </div>
        <div class="filters-actions">
          <button class="button" type="button" data-filter-action="clear">Clear</button>
          <button class="button primary" type="button" data-filter-action="apply">Apply</button>
        </div>
      </div>
    </div>
  `;
}

export function getOperonFilters(params) {
  let minGeneCount = sanitizeGeneCount(
    params.get("min_genes") || params.get("min_gene_count"),
    OPERON_FILTER_MIN,
  );
  let maxGeneCount = sanitizeGeneCount(
    params.get("max_genes") || params.get("max_gene_count"),
    OPERON_FILTER_MAX,
  );
  if (minGeneCount > maxGeneCount) {
    [minGeneCount, maxGeneCount] = [maxGeneCount, minGeneCount];
  }

  const genomeKey = sanitizeGenomeKey(params.get("genome_key"));
  const organism = sanitizeFilterText(params.get("organism") || params.get("organism_name"));
  const product = sanitizeFilterText(params.get("product"));
  const search = sanitizeFilterText(params.get("search"));
  const entityTypeValue = sanitizeFilterText(params.get("entity_type"));
  const entityKeyValue = Number.parseInt(params.get("entity_key"), 10);
  const entityType = OPERON_ENTITY_TYPES.has(entityTypeValue) ? entityTypeValue : "";
  const entityKey = entityType && Number.isFinite(entityKeyValue) && entityKeyValue > 0
    ? entityKeyValue
    : null;
  const sort = getOperonSort(params);
  return {
    minGeneCount,
    maxGeneCount,
    genomeKey,
    organism,
    product,
    search,
    entityType: entityKey === null ? "" : entityType,
    entityKey,
    ...sort,
  };
}

export function getOccurrenceFilters(params) {
  const operonFilters = getOperonFilters(params);
  return {
    product: sanitizeFilterText(params.get("product")),
    search: operonFilters.search,
    entityType: operonFilters.entityType,
    entityKey: operonFilters.entityKey,
  };
}

export function getGenomeOperonFilters(params) {
  const filters = getOperonFilters(params);
  return {
    ...filters,
    genomeKey: null,
    organism: "",
  };
}

export function getFilterValuesFromDom() {
  const routeParams = parseHash().params;
  const minInput = app.querySelector('[data-filter-field="min_genes"]');
  const maxInput = app.querySelector('[data-filter-field="max_genes"]');
  const organismSelect = app.querySelector('[data-filter-field="organism"]');
  const productInput = app.querySelector('[data-filter-field="product"]');
  let minGeneCount = sanitizeGeneCount(minInput?.value, OPERON_FILTER_MIN);
  let maxGeneCount = sanitizeGeneCount(maxInput?.value, OPERON_FILTER_MAX);
  if (minGeneCount > maxGeneCount) {
    [minGeneCount, maxGeneCount] = [maxGeneCount, minGeneCount];
  }
  return {
    minGeneCount,
    maxGeneCount,
    genomeKey: null,
    organism: sanitizeFilterText(organismSelect?.value),
    product: sanitizeFilterText(productInput?.value),
    search: sanitizeFilterText(routeParams.get("search")),
    entityType: getOperonFilters(routeParams).entityType,
    entityKey: getOperonFilters(routeParams).entityKey,
    ...getOperonSort(routeParams),
  };
}

export function getOccurrenceFilterValuesFromDom() {
  const routeParams = parseHash().params;
  const filters = getOccurrenceFilters(routeParams);
  const productInput = app.querySelector('[data-filter-field="product"]');
  return {
    product: sanitizeFilterText(productInput?.value),
    search: filters.search,
    entityType: filters.entityType,
    entityKey: filters.entityKey,
  };
}

export function buildOperonOccurrenceApiQuery(page, filters) {
  const params = getOperonOccurrencePagerParams(filters);
  params.set("page", String(page));
  return params.toString();
}

export function getOperonOccurrencePagerParams(filters) {
  const params = new URLSearchParams();
  if (filters.product) {
    params.set("product", filters.product);
  }
  addSearchEntityParams(params, filters);
  return params;
}

export function setOperonDetailRoute(operonId, page, filters, includeFilters = true) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  if (includeFilters) {
    const filterParams = getOperonOccurrencePagerParams(filters);
    filterParams.forEach((value, key) => params.set(key, value));
  }
  window.location.hash = `#operons/${operonId}?${params.toString()}`;
}

export function buildGenomeOperonApiQuery(page, filters) {
  const params = getGenomeOperonPagerParams(filters);
  params.set("page", String(page));
  return params.toString();
}

export function buildGenomeViewerApiQuery(filters) {
  const params = new URLSearchParams();
  addGeneCountParams(params, filters);
  if (filters.product) {
    params.set("product", filters.product);
  }
  return params.toString();
}

export function getGenomeOperonPagerParams(filters) {
  const params = new URLSearchParams();
  addGeneCountParams(params, filters);
  params.set("sort", filters.sort);
  params.set("direction", filters.direction);
  if (filters.product) {
    params.set("product", filters.product);
  }
  return params;
}

export function setGenomeOperonRoute(genomeKey, page, filters, includeFilters = true) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("sort", filters.sort || DEFAULT_OPERON_SORT);
  params.set("direction", filters.direction || DEFAULT_OPERON_SORT_DIRECTION);
  if (includeFilters) {
    addGeneCountParams(params, filters);
    if (filters.product) {
      params.set("product", filters.product);
    }
  }
  window.location.hash = `#genomes/${genomeKey}?${params.toString()}`;
}

export function sanitizeGeneCount(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return clamp(parsed, OPERON_FILTER_MIN, OPERON_FILTER_MAX);
}

export function sanitizeGenomeKey(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function sanitizeFilterText(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/[\u0000-\u001f\u007f]/g, "")
    .trim()
    .replace(/\s+/g, " ")
    .slice(0, FILTER_TEXT_MAX_LENGTH);
}

export function getOperonSort(params) {
  const requestedSort = params.get("sort") || DEFAULT_OPERON_SORT;
  const sort = OPERON_SORT_FIELDS.has(requestedSort) ? requestedSort : DEFAULT_OPERON_SORT;
  const requestedDirection = (params.get("direction") || DEFAULT_OPERON_SORT_DIRECTION).toLowerCase();
  const direction = requestedDirection === "desc" ? "desc" : "asc";
  return { sort, direction };
}

export function buildOperonApiQuery(page, filters) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  addGeneCountParams(params, filters);
  params.set("sort", filters.sort);
  params.set("direction", filters.direction);
  if (filters.genomeKey !== null) {
    params.set("genome_key", String(filters.genomeKey));
  }
  if (filters.organism) {
    params.set("organism", filters.organism);
  }
  if (filters.product) {
    params.set("product", filters.product);
  }
  addSearchEntityParams(params, filters);
  return params.toString();
}

export function getOperonPagerParams(filters) {
  const params = new URLSearchParams();
  addGeneCountParams(params, filters);
  params.set("sort", filters.sort);
  params.set("direction", filters.direction);
  if (filters.genomeKey !== null) {
    params.set("genome_key", String(filters.genomeKey));
  }
  if (filters.organism) {
    params.set("organism", filters.organism);
  }
  if (filters.product) {
    params.set("product", filters.product);
  }
  addSearchEntityParams(params, filters);
  return params;
}

export function setOperonRoute(page, filters, includeFilters = true) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("sort", filters.sort || DEFAULT_OPERON_SORT);
  params.set("direction", filters.direction || DEFAULT_OPERON_SORT_DIRECTION);
  if (includeFilters) {
    addGeneCountParams(params, filters);
    if (filters.genomeKey !== null) {
      params.set("genome_key", String(filters.genomeKey));
    }
    if (filters.organism) {
      params.set("organism", filters.organism);
    }
    if (filters.product) {
      params.set("product", filters.product);
    }
    addSearchEntityParams(params, filters);
  }
  const nextHash = `#operons?${params.toString()}`;
  if (window.location.hash === nextHash) {
    window.dispatchEvent(new Event("hashchange"));
  } else {
    window.location.hash = nextHash;
  }
}

export function addSearchEntityParams(params, filters) {
  if (filters.search) {
    params.set("search", filters.search);
  }
  if (filters.entityType && filters.entityKey !== null) {
    params.set("entity_type", filters.entityType);
    params.set("entity_key", String(filters.entityKey));
  }
}

export function addGeneCountParams(params, filters) {
  if (filters.minGeneCount > OPERON_FILTER_MIN) {
    params.set("min_genes", String(filters.minGeneCount));
  }
  if (filters.maxGeneCount < OPERON_FILTER_MAX) {
    params.set("max_genes", String(filters.maxGeneCount));
  }
}

export function handleFilterClick(event) {
  const actionButton = event.target.closest("[data-filter-action]");
  if (!actionButton || !app.contains(actionButton)) {
    return;
  }

  const action = actionButton.dataset.filterAction;
  if (action === "open") {
    operonFiltersOpen = true;
    app.querySelector("[data-filters-menu]")?.classList.add("open");
  } else if (action === "close") {
    operonFiltersOpen = false;
    app.querySelector("[data-filters-menu]")?.classList.remove("open");
  } else if (action === "apply") {
    operonFiltersOpen = true;
    if (actionButton.closest('[data-filter-kind="occurrences"]')) {
      applyCurrentOccurrenceFilterRoute(getOccurrenceFilterValuesFromDom());
    } else {
      applyCurrentFilterRoute(getFilterValuesFromDom());
    }
  } else if (action === "clear") {
    operonFiltersOpen = true;
    clearCurrentFilterRoute();
  }
}

export function handleDocumentClick(event) {
  if (!operonFiltersOpen) {
    return;
  }
  if (event.target.closest("[data-filters-root]")) {
    return;
  }
  operonFiltersOpen = false;
  app.querySelector("[data-filters-menu]")?.classList.remove("open");
}

function applyCurrentOccurrenceFilterRoute(filters) {
  const { parts } = parseHash();
  if (parts[0] === "operons" && parts.length === 2) {
    setOperonDetailRoute(parts[1], 1, filters);
  }
}

function applyCurrentFilterRoute(filters) {
  const { parts } = parseHash();
  if (parts[0] === "genomes" && parts.length === 2) {
    setGenomeOperonRoute(parts[1], 1, filters);
    return;
  }
  setOperonRoute(1, filters);
}

function clearCurrentFilterRoute() {
  const { parts, params } = parseHash();
  const filters = {
    minGeneCount: OPERON_FILTER_MIN,
    maxGeneCount: OPERON_FILTER_MAX,
    genomeKey: null,
    organism: "",
    product: "",
    search: "",
    entityType: "",
    entityKey: null,
    ...getOperonSort(params),
  };
  if (parts[0] === "operons" && parts.length === 2) {
    setOperonDetailRoute(parts[1], 1, {
      product: "",
      search: "",
      entityType: "",
      entityKey: null,
    }, false);
    return;
  }
  if (parts[0] === "genomes" && parts.length === 2) {
    setGenomeOperonRoute(parts[1], 1, filters, false);
    return;
  }
  setOperonRoute(1, filters, false);
}
