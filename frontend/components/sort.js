import {
  getGenomeOperonPagerParams,
  getOperonPagerParams,
} from "./filters.js";
import {
  iconArrowDown,
  iconArrowUp,
} from "./icons.js";
import {
  DEFAULT_OPERON_SORT,
  DEFAULT_OPERON_SORT_DIRECTION,
} from "../config.js";
import { escapeHtml } from "../utils/html.js";
import { renderColumnHeader } from "./table-header.js";

export function renderSortableHeader(label, sortKey, state, description) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = getOperonPagerParams({ ...state, sort: sortKey, direction: nextDirection });
  params.set("page", "1");
  return renderColumnHeader(label, description, {
    labelHtml: renderSortLink(`operons?${params.toString()}`, label, direction, isActive),
  });
}

export function renderSortHeaderForRoute(route, label, sortKey, state) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = getSortPagerParams({ sort: sortKey, direction: nextDirection });
  params.set("page", "1");
  return renderSortLink(`${route}?${params.toString()}`, label, direction, isActive);
}

export function renderGenomeListSortableHeader(label, sortKey, state, description) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = new URLSearchParams();
  params.set("page", "1");
  params.set("sort", sortKey);
  params.set("direction", nextDirection);
  if (state.search) {
    params.set("search", state.search);
  }
  return renderColumnHeader(label, description, {
    labelHtml: renderSortLink(`genomes?${params.toString()}`, label, direction, isActive),
  });
}

export function renderGenomeSortableHeader(route, label, sortKey, state, description) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = getGenomeOperonPagerParams({
    ...state,
    sort: sortKey,
    direction: nextDirection,
  });
  params.set("page", "1");
  return renderColumnHeader(label, description, {
    labelHtml: renderSortLink(`${route}?${params.toString()}`, label, direction, isActive),
  });
}

export function renderSortLink(href, label, direction, isActive) {
  return `
    <a class="sort-link ${isActive ? "active" : ""}" href="#${href}">
      <span>${escapeHtml(label)}</span>
      ${direction === "asc" ? iconArrowUp() : iconArrowDown()}
    </a>
  `;
}

export function getSortPagerParams(state) {
  const params = new URLSearchParams();
  params.set("sort", state.sort || DEFAULT_OPERON_SORT);
  params.set("direction", state.direction || DEFAULT_OPERON_SORT_DIRECTION);
  return params;
}
