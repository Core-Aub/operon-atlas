import {
  GENE_MIN_ARROW_WIDTH,
  GENE_VIEWBOX_HEIGHT,
  GENE_VIEWBOX_PADDING_X,
  GENE_VIEWBOX_WIDTH,
  GENE_VIEWER_MAX_SIZE,
  GENE_VIEWER_MIN_SIZE,
  GENE_VIEWER_NAV_STEP,
  GENE_VIEWER_ZOOM_STEP,
} from "../config.js";
import { app } from "../dom.js";
import {
  iconChevronLeft,
  iconChevronRight,
  iconMinus,
  iconPlus,
  iconRestart,
} from "../components/icons.js";
import { renderAnnotationCell } from "../components/gene-annotations.js";
import { viewerButton } from "../components/viewer-buttons.js";
import { emptyTableRow, escapeHtml } from "../utils/html.js";
import {
  clamp,
  firstPresent,
  formatSvgNumber,
} from "../utils/format.js";

let currentGeneViewerGenes = [];
let currentGeneViewerStart = 0;
let currentGeneViewerSize = GENE_VIEWER_MIN_SIZE;
let currentHighlightedGene = "";

export function setGeneViewerGenes(genes, highlightedGene = "") {
  currentGeneViewerGenes = Array.isArray(genes) ? genes : [];
  currentGeneViewerSize = GENE_VIEWER_MIN_SIZE;
  currentHighlightedGene = String(highlightedGene || "").trim();
  const highlightedIndex = currentGeneViewerGenes.findIndex(isHighlightedGene);
  currentGeneViewerStart = highlightedIndex < 0
    ? 0
    : clamp(
        highlightedIndex - Math.floor(currentGeneViewerSize / 2),
        0,
        Math.max(0, currentGeneViewerGenes.length - currentGeneViewerSize),
      );
}

export function renderGeneViewer(genes = currentGeneViewerGenes) {
  if (!genes.length) {
    return `<div class="empty">No genes found for this operon.</div>`;
  }

  const end = Math.min(currentGeneViewerStart + currentGeneViewerSize, genes.length);
  const hasNext = currentGeneViewerStart < getMaxGeneViewerStart();
  return `
    <div class="gene-viewer-toolbar">
      <div class="button-row">
        ${viewerButton("backward", "Backward", iconChevronLeft(), true)}
        ${viewerButton("forward", "Forward", iconChevronRight(), !hasNext)}
        ${viewerButton("restart", "Restart", iconRestart(), true)}
        ${viewerButton("zoom-in", "Zoom in", iconPlus(), currentGeneViewerSize <= GENE_VIEWER_MIN_SIZE)}
        ${viewerButton("zoom-out", "Zoom out", iconMinus(), !canZoomOut())}
      </div>
      <div class="viewer-status-group">
        <span class="viewer-status gene-contig-status" data-gene-contig-status>${escapeHtml(formatGeneViewerContigLabel())}</span>
        <span class="viewer-status" data-gene-status>${formatGeneViewerStatus(currentGeneViewerStart, end, genes.length)}</span>
      </div>
    </div>
    <div class="gene-window" data-gene-window>
      ${renderGeneWindow(genes, currentGeneViewerStart)}
    </div>
  `;
}

function formatGeneViewerStatus(start, end, total) {
  if (total === 1) {
    return "Gene 1 of 1";
  }
  return `Genes ${start + 1}-${end} of ${total}`;
}

function renderGeneWindow(genes, start) {
  const visibleGenes = genes.slice(start, start + currentGeneViewerSize);
  const height = GENE_VIEWBOX_HEIGHT;
  const centerLineY = 86;
  const arrowHeight = 38;
  const availableWidth = Math.max(
    1,
    GENE_VIEWBOX_WIDTH - GENE_VIEWBOX_PADDING_X * 2,
  );
  const starts = visibleGenes.map((gene) => getGeneBounds(gene).start);
  const ends = visibleGenes.map((gene) => getGeneBounds(gene).end);
  const windowStart = Math.min(...starts);
  const windowEnd = Math.max(...ends);
  const coordinateSpan = Math.max(1, windowEnd - windowStart + 1);
  const coordinateScale = availableWidth / coordinateSpan;
  const shapes = [];

  visibleGenes.forEach((gene, localIndex) => {
    const bounds = getGeneBounds(gene);
    const geneX = GENE_VIEWBOX_PADDING_X + (bounds.start - windowStart) * coordinateScale;
    const maxWidth = Math.max(3, GENE_VIEWBOX_WIDTH - GENE_VIEWBOX_PADDING_X - geneX);
    const width = Math.min(Math.max(GENE_MIN_ARROW_WIDTH, bounds.length * coordinateScale), maxWidth);
    shapes.push(renderGeneArrow(gene, localIndex, geneX, width, centerLineY, arrowHeight));
  });

  return `
    <svg class="gene-svg" viewBox="0 0 ${GENE_VIEWBOX_WIDTH} ${height}" role="img" aria-label="Operon gene direction viewer">
      <line class="gene-track" x1="0" y1="${centerLineY}" x2="${GENE_VIEWBOX_WIDTH}" y2="${centerLineY}"></line>
      ${shapes.join("")}
    </svg>
  `;
}

function getGeneBounds(gene) {
  const start = Number(gene.start) || 0;
  const end = Number(gene.end) || start;
  const lower = Math.min(start, end);
  const upper = Math.max(start, end);
  return {
    start: lower,
    end: upper,
    length: Math.max(1, upper - lower + 1),
  };
}

function renderGeneArrow(gene, localIndex, x, width, centerLineY, arrowHeight) {
  const isForward = Number(gene.strand) === 1;
  const y = isForward ? centerLineY - arrowHeight : centerLineY;
  const tip = Math.min(26, Math.max(8, width * 0.28), Math.max(4, width * 0.6));
  const points =
    isForward
      ? [
          [x, y],
          [x + width - tip, y],
          [x + width, y + arrowHeight / 2],
          [x + width - tip, y + arrowHeight],
          [x, y + arrowHeight],
        ]
      : [
          [x + width, y],
          [x + tip, y],
          [x, y + arrowHeight / 2],
          [x + tip, y + arrowHeight],
          [x + width, y + arrowHeight],
        ];
  const pointString = points.map((point) => point.map(formatSvgNumber).join(",")).join(" ");
  const colorIndex = localIndex % 10;
  const label = isForward
    ? `<text class="gene-label gene-label-forward" x="${formatSvgNumber(x + 4)}" y="${formatSvgNumber(y - 7)}">${escapeHtml(gene.gene_id)}</text>`
    : `<text class="gene-label gene-label-reverse" x="${formatSvgNumber(x + width - 4)}" y="${formatSvgNumber(y + arrowHeight + 16)}" text-anchor="end">${escapeHtml(gene.gene_id)}</text>`;

  const highlightClass = isHighlightedGene(gene) ? " gene-arrow-highlight" : "";
  return `
    <polygon class="gene-arrow gene-color-${colorIndex}${highlightClass}" points="${pointString}">
      <title>${escapeHtml(gene.gene_id)}</title>
    </polygon>
    ${label}
  `;
}

function renderGeneRow(gene, showContigInPosition = false) {
  const geneLabel = formatGeneLabel(gene);
  const position = formatGenePosition(gene, showContigInPosition);
  return `
    <tr class="${isHighlightedGene(gene) ? "gene-row-highlight" : ""}">
      <td class="gene-name">
        <span title="${escapeHtml(gene.gene_id || geneLabel)}">${escapeHtml(geneLabel)}</span>
      </td>
      <td class="annotation-cell">${renderAnnotationCell(gene)}</td>
      <td class="numeric">${escapeHtml(gene.pgfam_display || "")}</td>
      <td class="numeric gene-position" title="${escapeHtml(position)}">${escapeHtml(position)}</td>
      <td class="numeric">${escapeHtml(formatGeneLength(gene))}</td>
    </tr>
  `;
}

function isHighlightedGene(gene) {
  if (!currentHighlightedGene) {
    return false;
  }
  const geneId = String(gene?.gene_id || "");
  const pegNum = String(gene?.peg_num ?? "");
  return geneId === currentHighlightedGene
    || pegNum === currentHighlightedGene
    || geneId.endsWith(`.peg.${currentHighlightedGene}`);
}

export function renderGeneTableRows(genes = getVisibleGeneViewerGenes()) {
  const showContigInPosition = hasMultipleGeneContigs(currentGeneViewerGenes);
  return genes.map((gene) => renderGeneRow(gene, showContigInPosition)).join("") || emptyTableRow(5);
}

function getVisibleGeneViewerGenes() {
  return currentGeneViewerGenes.slice(
    currentGeneViewerStart,
    currentGeneViewerStart + currentGeneViewerSize,
  );
}

function formatGeneViewerContigLabel(genes = currentGeneViewerGenes) {
  const contigs = getGeneContigs(genes);
  if (!contigs.length) {
    return "Contig unknown";
  }
  if (contigs.length === 1) {
    return `Contig ${contigs[0].label}`;
  }
  return `${contigs.length} contigs`;
}

function getGeneContigs(genes) {
  const contigs = [];
  const seen = new Set();
  genes.forEach((gene) => {
    const key = String(gene.contig_id ?? gene.contig_name ?? "");
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    contigs.push({
      key,
      label: String(gene.contig_name || gene.contig_id || "unknown"),
    });
  });
  return contigs;
}

function hasMultipleGeneContigs(genes) {
  return getGeneContigs(genes).length > 1;
}

function formatGeneLabel(gene) {
  if (gene.peg_num !== null && gene.peg_num !== undefined && gene.peg_num !== "") {
    return `peg.${gene.peg_num}`;
  }
  return String(gene.gene_id || "");
}

function formatGenePosition(gene, includeContig = false) {
  const start = formatCoordinate(gene.start);
  const end = formatCoordinate(gene.end);
  const position = start && end ? `${start}..${end}` : firstPresent(start, end);
  if (includeContig) {
    const contig = firstPresent(gene.contig_name, gene.contig_id);
    return contig && position ? `${contig}:${position}` : firstPresent(contig, position);
  }
  return position;
}

function formatGeneLength(gene) {
  const length = formatCoordinate(gene.length);
  return length ? `${length} bp` : "";
}

function formatCoordinate(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "";
  }
  return String(number);
}

export function handleGeneViewerClick(event) {
  const button = event.target.closest("[data-gene-nav]");
  if (!button || !app.contains(button)) {
    return;
  }

  const action = button.dataset.geneNav;
  const maxStart = getMaxGeneViewerStart();
  let nextStart = currentGeneViewerStart;

  if (action === "backward") {
    nextStart = Math.max(0, currentGeneViewerStart - GENE_VIEWER_NAV_STEP);
  } else if (action === "forward") {
    nextStart = Math.min(maxStart, currentGeneViewerStart + GENE_VIEWER_NAV_STEP);
  } else if (action === "restart") {
    nextStart = 0;
  } else if (action === "zoom-in") {
    currentGeneViewerSize = Math.max(
      GENE_VIEWER_MIN_SIZE,
      currentGeneViewerSize - GENE_VIEWER_ZOOM_STEP,
    );
  } else if (action === "zoom-out") {
    currentGeneViewerSize = Math.min(
      getUsefulGeneViewerMaxSize(),
      currentGeneViewerSize + GENE_VIEWER_ZOOM_STEP,
    );
  }

  updateGeneViewer(nextStart);
}

function updateGeneViewer(start) {
  currentGeneViewerStart = clamp(start, 0, getMaxGeneViewerStart());
  const windowEl = app.querySelector("[data-gene-window]");
  const statusEl = app.querySelector("[data-gene-status]");
  const contigStatusEl = app.querySelector("[data-gene-contig-status]");
  const tableBodyEl = app.querySelector("[data-gene-table-body]");
  const backwardButton = app.querySelector('[data-gene-nav="backward"]');
  const forwardButton = app.querySelector('[data-gene-nav="forward"]');
  const restartButton = app.querySelector('[data-gene-nav="restart"]');
  const zoomInButton = app.querySelector('[data-gene-nav="zoom-in"]');
  const zoomOutButton = app.querySelector('[data-gene-nav="zoom-out"]');

  if (!windowEl || !statusEl) {
    return;
  }

  const end = Math.min(currentGeneViewerStart + currentGeneViewerSize, currentGeneViewerGenes.length);
  windowEl.innerHTML = renderGeneWindow(currentGeneViewerGenes, currentGeneViewerStart);
  statusEl.textContent = formatGeneViewerStatus(
    currentGeneViewerStart,
    end,
    currentGeneViewerGenes.length,
  );
  if (contigStatusEl) {
    contigStatusEl.textContent = formatGeneViewerContigLabel();
  }
  if (tableBodyEl) {
    tableBodyEl.innerHTML = renderGeneTableRows();
  }

  if (backwardButton) {
    backwardButton.disabled = currentGeneViewerStart === 0;
  }
  if (forwardButton) {
    forwardButton.disabled = currentGeneViewerStart >= getMaxGeneViewerStart();
  }
  if (restartButton) {
    restartButton.disabled = currentGeneViewerStart === 0;
  }
  if (zoomInButton) {
    zoomInButton.disabled = currentGeneViewerSize <= GENE_VIEWER_MIN_SIZE;
  }
  if (zoomOutButton) {
    zoomOutButton.disabled = !canZoomOut();
  }
}

function getMaxGeneViewerStart() {
  return Math.max(0, currentGeneViewerGenes.length - currentGeneViewerSize);
}

function canZoomOut() {
  return currentGeneViewerSize < getUsefulGeneViewerMaxSize();
}

function getUsefulGeneViewerMaxSize() {
  return Math.min(
    GENE_VIEWER_MAX_SIZE,
    Math.max(GENE_VIEWER_MIN_SIZE, currentGeneViewerGenes.length),
  );
}
