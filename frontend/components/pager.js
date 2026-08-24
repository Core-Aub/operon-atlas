import {
  iconChevronLeft,
  iconChevronRight,
} from "./icons.js";
import { formatNumber } from "../utils/format.js";

export function renderPager(
  route,
  data,
  extraParams = new URLSearchParams(),
  pageParam = "page",
) {
  const previousPage = Math.max(1, data.page - 1);
  const nextPage = data.page + 1;
  const hasPrevious = data.page > 1;
  const hasNext = data.page * data.pageSize < data.total;
  const startItem = data.total === 0 ? 0 : (data.page - 1) * data.pageSize + 1;
  const endItem = Math.min(data.page * data.pageSize, data.total);
  return `
    <div class="pager">
      <div class="pager-range">${formatNumber(startItem)}-${formatNumber(endItem)}/${formatNumber(data.total)}</div>
      <div class="button-row">
        <a class="pager-button icon-button ${hasPrevious ? "" : "disabled"}" href="${buildPagerHref(route, previousPage, extraParams, pageParam)}" aria-label="Previous page" title="Previous page">
          ${iconChevronLeft()}
        </a>
        <span class="pager-current">Page ${formatNumber(data.page)}</span>
        <a class="pager-button icon-button ${hasNext ? "" : "disabled"}" href="${buildPagerHref(route, nextPage, extraParams, pageParam)}" aria-label="Next page" title="Next page">
          ${iconChevronRight()}
        </a>
      </div>
    </div>
  `;
}

export function buildPagerHref(
  route,
  page,
  extraParams = new URLSearchParams(),
  pageParam = "page",
) {
  const params = new URLSearchParams(extraParams);
  params.set(pageParam, String(page));
  return `#${route}?${params.toString()}`;
}
