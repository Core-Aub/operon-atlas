import { app } from "../dom.js";

export function handleReturnClick(event) {
  const link = event.target.closest("[data-return-link]");
  if (!link || !app.contains(link)) {
    return;
  }

  event.preventDefault();
  if (window.history.length > 1) {
    window.history.back();
    return;
  }
  window.location.hash = link.getAttribute("href") || "#home";
}
