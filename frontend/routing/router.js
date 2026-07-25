import { app, navLinks } from "../dom.js";
import { renderDownloads } from "../pages/downloads.js";
import { renderGenomes, renderGenomeDetail } from "../pages/genomes.js";
import { renderHome } from "../pages/home.js?v=1";
import { renderOccurrenceDetail } from "../pages/occurrence.js?v=6";
import { renderOperons, renderOperonDetail } from "../pages/operons.js?v=6";
import { getPage, parseHash } from "./hash.js";
import {
  isCurrentRoute,
  setCurrentRouteKey,
} from "./route-state.js";
import { escapeHtml } from "../utils/html.js";

export async function renderRoute() {
  const routeKey = window.location.hash || "#home";
  setCurrentRouteKey(routeKey);
  const { parts, params } = parseHash();
  const route = parts[0] || "home";
  setActiveNav(route);
  showLoading();

  try {
    if (route === "home") {
      await renderHome(routeKey);
    } else if (route === "downloads" && parts.length === 1) {
      await renderDownloads(routeKey);
    } else if (route === "operons" && parts.length === 1) {
      await renderOperons(getPage(params), params, routeKey);
    } else if (route === "operons" && parts.length === 2) {
      await renderOperonDetail(parts[1], getPage(params), params, routeKey);
    } else if (route === "occurrences" && parts.length === 2) {
      await renderOccurrenceDetail(parts[1], routeKey);
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
  app.innerHTML = `<div class="empty">The requested view was not found.</div>`;
}
