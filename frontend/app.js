import { app } from "./dom.js";
import {
  handleDocumentClick,
  handleFilterClick,
} from "./components/filters.js";
import {
  handleGenomeSearchClear,
  handleGenomeSearchSubmit,
} from "./pages/genomes.js";
import { handleReturnClick } from "./routing/navigation.js";
import { renderRoute } from "./routing/router.js?v=15";
import {
  handleGlobalSearchClear,
  handleGlobalSearchSubmit,
} from "./pages/search.js?v=1";
import { handleGeneViewerClick } from "./viewers/gene-viewer.js?v=1";
import { handleGenomeViewerClick } from "./viewers/genome-viewer.js?v=1";

window.addEventListener("hashchange", renderRoute);
window.addEventListener("DOMContentLoaded", renderRoute);
app.addEventListener("click", handleGeneViewerClick);
app.addEventListener("click", handleGenomeViewerClick);
app.addEventListener("click", handleFilterClick);
app.addEventListener("click", handleReturnClick);
app.addEventListener("click", handleGenomeSearchClear);
app.addEventListener("click", handleGlobalSearchClear);
app.addEventListener("submit", handleGenomeSearchSubmit);
app.addEventListener("submit", handleGlobalSearchSubmit);
document.addEventListener("click", handleDocumentClick);
