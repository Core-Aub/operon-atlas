import { app, navLinks } from "../dom.js";
import { renderDownloads } from "../pages/downloads.js?v=1";
import { renderGenomes, renderGenomeDetail } from "../pages/genomes.js?v=1";
import { renderHelp } from "../pages/help.js?v=5";
import { renderHome } from "../pages/home.js?v=2";
import { renderOccurrenceDetail } from "../pages/occurrence.js?v=8";
import { renderOperons, renderOperonDetail } from "../pages/operons.js?v=8";
import { renderSearch } from "../pages/search.js?v=1";
import { getPage, parseHash } from "./hash.js";
import {
  isCurrentRoute,
  setCurrentRouteKey,
} from "./route-state.js";
import { escapeHtml } from "../utils/html.js";

export async function renderRoute() {
  const routeKey = `${window.location.pathname}${window.location.search}${window.location.hash || "#home"}`;
  setCurrentRouteKey(routeKey);

  if (!isApplicationPath()) {
    setActiveNav("");
    renderNotFound();
    return;
  }

  const { parts, params } = parseHash();
  const route = parts[0] || "home";
  setActiveNav(route);
  showLoading();

  try {
    if (route === "home") {
      await renderHome(routeKey);
    } else if (route === "help") {
      renderHelp(parts[1]);
    } else if (route === "downloads" && parts.length === 1) {
      await renderDownloads(routeKey);
    } else if (route === "search" && parts.length === 1) {
      await renderSearch(getPage(params), params, routeKey);
    } else if (route === "operons" && parts.length === 1) {
      await renderOperons(getPage(params), params, routeKey);
    } else if (route === "operons" && parts.length === 2) {
      await renderOperonDetail(parts[1], getPage(params), params, routeKey);
    } else if (route === "occurrences" && parts.length === 2) {
      await renderOccurrenceDetail(parts[1], params, routeKey);
    } else if (route === "genomes" && parts.length === 1) {
      await renderGenomes(getPage(params), params, routeKey);
    } else if (route === "genomes" && parts.length === 2) {
      await renderGenomeDetail(parts[1], getPage(params), params, routeKey);
    } else {
      renderNotFound();
    }
  } catch (error) {
    if (isCurrentRoute(routeKey)) {
      renderError(error);
    }
  }
}

function setActiveNav(route) {
  const activeRoute = route === "occurrences" ? "operons" : route;
  navLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.route === activeRoute);
  });
}

function showLoading() {
  app.innerHTML = `<div class="loading">Loading...</div>`;
}

function renderError(error) {
  app.innerHTML = `
    <div class="error">
      <strong>Unable to load this view.</strong>
      <div>${escapeHtml(error.message)}</div>
    </div>
  `;
}

function renderNotFound() {
  app.innerHTML = `
    <section class="not-found" aria-labelledby="not-found-title">
      <div class="not-found-code" aria-hidden="true">404</div>
      <h1 id="not-found-title">Page not found</h1>
      <p>The page you requested does not exist or may have moved.</p>
      <a class="button primary not-found-home" href="/#home">Back to home</a>
    </section>
  `;
}

function isApplicationPath() {
  const pathname = window.location.pathname.replace(/\/+$/, "") || "/";
  return pathname === "/" || pathname === "/index.html";
}
