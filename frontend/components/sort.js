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

export function renderSortableHeader(label, sortKey, state) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = getOperonPagerParams({ ...state, sort: sortKey, direction: nextDirection });
  params.set("page", "1");
  return renderSortLink(`operons?${params.toString()}`, label, direction, isActive);
}

export function renderSortHeaderForRoute(route, label, sortKey, state) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = getSortPagerParams({ sort: sortKey, direction: nextDirection });
  params.set("page", "1");
  return renderSortLink(`${route}?${params.toString()}`, label, direction, isActive);
}

export function renderGenomeSortableHeader(route, label, sortKey, state) {
  const isActive = state.sort === sortKey;
  const direction = isActive ? state.direction : "asc";
  const nextDirection = isActive && state.direction === "asc" ? "desc" : "asc";
  const params = getGenomeOperonPagerParams({
    ...state,
    sort: sortKey,
    direction: nextDirection,
  });
  params.set("page", "1");
  return renderSortLink(`${route}?${params.toString()}`, label, direction, isActive);
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
