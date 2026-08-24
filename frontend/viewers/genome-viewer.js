import {
  GENOME_OCCURRENCE_GAP,
  GENOME_OCCURRENCE_HEIGHT,
  GENOME_OCCURRENCE_MIN_WIDTH,
  GENOME_OCCURRENCE_WIDTH_RATIO,
  GENOME_VIEWBOX_HEIGHT,
  GENOME_VIEWBOX_PADDING_X,
  GENOME_VIEWBOX_PADDING_Y,
  GENOME_VIEWBOX_WIDTH,
  GENOME_VIEWER_MAX_OCCURRENCES,
  GENOME_VIEWER_MIN_OCCURRENCES,
  GENOME_VIEWER_ZOOM_FACTOR,
} from "../config.js";
import { app } from "../dom.js";
import {
  iconChevronLeft,
  iconChevronRight,
  iconDoubleChevronLeft,
  iconDoubleChevronRight,
  iconMinus,
  iconPlus,
  iconRestart,
} from "../components/icons.js";
import { genomeViewerButton } from "../components/viewer-buttons.js";
import { escapeHtml } from "../utils/html.js";
import {
  clamp,
  formatNumber,
  formatOccurrenceId,
  formatStableOperonId,
  formatSvgNumber,
} from "../utils/format.js";

let currentGenomeViewerData = null;
let currentGenomeViewerContigIndex = 0;
let currentGenomeViewerOccurrenceOffset = 0;
let currentGenomeViewerSize = GENOME_VIEWER_MAX_OCCURRENCES;

export function setGenomeViewerData(viewer) {
  currentGenomeViewerData = viewer;
  resetGenomeViewerCursor();
}

export function renderGenomeViewer(viewer = currentGenomeViewerData) {
  const orderedOccurrences = getGenomeViewerOrderedOccurrences(viewer);
  if (!orderedOccurrences.length) {
    return `<div class="empty">No occurrences match the current filters.</div>`;
  }

  const range = getGenomeViewerVisibleRange(viewer);
  const total = getGenomeViewerCurrentContigTotal(viewer);
  return `
    <div class="gene-viewer-toolbar genome-viewer-toolbar">
      <div class="button-row">
        ${genomeViewerButton("contig-backward", "Previous contig", iconDoubleChevronLeft(), !canMoveGenomeViewerContigBackward())}
        ${genomeViewerButton("backward", "Previous occurrence", iconChevronLeft(), !canMoveGenomeViewerBackward())}
        ${genomeViewerButton("forward", "Next occurrence", iconChevronRight(), !canMoveGenomeViewerForward())}
        ${genomeViewerButton("contig-forward", "Next contig", iconDoubleChevronRight(), !canMoveGenomeViewerContigForward())}
        ${genomeViewerButton("restart", "Restart", iconRestart(), true)}
        ${genomeViewerButton("zoom-in", "Zoom in", iconPlus(), currentGenomeViewerSize <= GENOME_VIEWER_MIN_OCCURRENCES)}
        ${genomeViewerButton("zoom-out", "Zoom out", iconMinus(), !canGenomeZoomOut())}
      </div>
      <span class="viewer-status genome-contig-status" data-genome-contig-status>${escapeHtml(formatGenomeViewerContigLabel())}</span>
      <span class="viewer-status" data-genome-status>${formatGenomeViewerStatus(range, total)}</span>
    </div>
    <div class="genome-window" data-genome-window>
      ${renderGenomeWindow(viewer)}
    </div>
  `;
}

function renderGenomeWindow(viewer) {
  const visibleContig = getVisibleGenomeViewerContig(viewer);
  if (!visibleContig || !visibleContig.occurrences.length) {
    return `<div class="empty">No occurrences match the current filters.</div>`;
  }

  const visibleOccurrenceCount = getVisibleGenomeViewerOccurrences(viewer).length;
  const height = GENOME_VIEWBOX_HEIGHT;
  const availableWidth = Math.max(
    1,
    GENOME_VIEWBOX_WIDTH - GENOME_VIEWBOX_PADDING_X * 2,
  );
  const top = GENOME_VIEWBOX_PADDING_Y;
  const layout = layoutGenomeOccurrences(visibleContig.occurrences || []);
  const metrics = getGenomeOccurrenceVisualMetrics(visibleOccurrenceCount);

  return `
    <svg class="genome-svg" viewBox="0 0 ${GENOME_VIEWBOX_WIDTH} ${formatSvgNumber(height)}" role="img" aria-label="${escapeHtml(`${formatGenomeContigName(visibleContig)} occurrence viewer`)}">
      ${renderGenomeContig(visibleContig, layout, GENOME_VIEWBOX_PADDING_X, top, availableWidth, height - GENOME_VIEWBOX_PADDING_Y * 2, metrics)}
    </svg>
  `;
}

function getGenomeViewerOrderedOccurrences(viewer = currentGenomeViewerData) {
  const ordered = Array.isArray(viewer?.ordered_occurrences)
    ? viewer.ordered_occurrences
    : getGenomeViewerContigs(viewer).flatMap((contig) => (
      (contig.occurrences || []).map((occurrence) => ({
        ...occurrence,
        contig_id: contig.contig_id,
        contig_name: contig.contig_name,
        order: contig.order,
      }))
    ));
  return ordered.map((occurrence, index) => ({
    ...occurrence,
    contig_name: occurrence.contig_name || getGenomeViewerContigName(occurrence.contig_id, viewer),
    index: index + 1,
  }));
}

function getGenomeViewerContigs(viewer = currentGenomeViewerData) {
  return Array.isArray(viewer?.contigs) ? viewer.contigs : [];
}

function getGenomeViewerContigOccurrences(contigIndex, viewer = currentGenomeViewerData) {
  const contig = getGenomeViewerContigs(viewer)[contigIndex];
  if (!contig) {
    return [];
  }
  return getGenomeViewerOrderedOccurrences(viewer).filter((occurrence) => (
    String(occurrence.contig_id) === String(contig.contig_id)
  ));
}

function getFirstGenomeViewerContigIndex(viewer = currentGenomeViewerData) {
  const contigs = getGenomeViewerContigs(viewer);
  return Math.max(
    0,
    contigs.findIndex((contig) => (
      getGenomeViewerOrderedOccurrences(viewer).some((occurrence) => (
        String(occurrence.contig_id) === String(contig.contig_id)
      ))
    )),
  );
}

function resetGenomeViewerCursor() {
  currentGenomeViewerSize = GENOME_VIEWER_MAX_OCCURRENCES;
  currentGenomeViewerContigIndex = getFirstGenomeViewerContigIndex();
  currentGenomeViewerOccurrenceOffset = 0;
}

function normalizeGenomeViewerCursor() {
  const orderedOccurrences = getGenomeViewerOrderedOccurrences();
  if (!orderedOccurrences.length) {
    currentGenomeViewerContigIndex = 0;
    currentGenomeViewerOccurrenceOffset = 0;
    return;
  }

  const contigs = getGenomeViewerContigs();
  currentGenomeViewerContigIndex = clamp(
    currentGenomeViewerContigIndex,
    0,
    Math.max(0, contigs.length - 1),
  );
  if (!getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex).length) {
    currentGenomeViewerContigIndex = getFirstGenomeViewerContigIndex();
  }
  const contigOccurrences = getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex);
  currentGenomeViewerOccurrenceOffset = clamp(
    currentGenomeViewerOccurrenceOffset,
    0,
    Math.max(0, contigOccurrences.length - 1),
  );
}

function getGenomeViewerCursorOccurrence(viewer = currentGenomeViewerData) {
  normalizeGenomeViewerCursor();
  return getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex, viewer)[currentGenomeViewerOccurrenceOffset] || null;
}

function getGenomeViewerCursorIndex(viewer = currentGenomeViewerData) {
  const cursorOccurrence = getGenomeViewerCursorOccurrence(viewer);
  if (!cursorOccurrence) {
    return 0;
  }
  return Math.max(0, Number(cursorOccurrence.index || 1) - 1);
}

function getGenomeViewerVisibleRange(viewer = currentGenomeViewerData) {
  const visibleOccurrences = getVisibleGenomeViewerOccurrences(viewer);
  const start = visibleOccurrences.length ? getGenomeViewerVisibleStartOffset(viewer) : 0;
  return {
    start,
    end: visibleOccurrences.length ? start + visibleOccurrences.length : 0,
  };
}

function getVisibleGenomeViewerOccurrences(viewer = currentGenomeViewerData) {
  const contigOccurrences = getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex, viewer);
  const start = getGenomeViewerVisibleStartOffset(viewer);
  return contigOccurrences.slice(
    start,
    start + currentGenomeViewerSize,
  );
}

function getGenomeViewerVisibleStartOffset(viewer = currentGenomeViewerData) {
  const contigOccurrences = getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex, viewer);
  const maxStart = Math.max(0, contigOccurrences.length - currentGenomeViewerSize);
  return clamp(currentGenomeViewerOccurrenceOffset, 0, maxStart);
}

function getVisibleGenomeViewerContig(viewer = currentGenomeViewerData) {
  const contig = getGenomeViewerContigs(viewer)[currentGenomeViewerContigIndex];
  if (!contig) {
    return null;
  }
  const visibleOccurrenceIds = new Set(
    getVisibleGenomeViewerOccurrences(viewer).map((occurrence) => String(occurrence.occurrence_id)),
  );
  if (!visibleOccurrenceIds.size) {
    return null;
  }
  return {
    ...contig,
    occurrences: (contig.occurrences || []).filter((occurrence) => (
      visibleOccurrenceIds.has(String(occurrence.occurrence_id))
    )),
  };
}

function formatGenomeViewerStatus(range, total) {
  if (!total) {
    return "No occurrences";
  }
  if (total === 1) {
    return "Occurrence 1 of 1";
  }
  return `Occurrences ${formatNumber(range.start + 1)}-${formatNumber(range.end)} of ${formatNumber(total)}`;
}

function getGenomeViewerCurrentContigTotal(viewer = currentGenomeViewerData) {
  return getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex, viewer).length;
}

function formatGenomeViewerContigLabel(viewer = currentGenomeViewerData) {
  const contig = getGenomeViewerContigs(viewer)[currentGenomeViewerContigIndex];
  if (!contig) {
    return "No contig";
  }
  return formatGenomeContigName(contig);
}

function getGenomeViewerContigName(contigId, viewer = currentGenomeViewerData) {
  const contig = getGenomeViewerContigs(viewer).find((item) => String(item.contig_id) === String(contigId));
  return contig?.contig_name || contig?.contig_id || contigId;
}

function formatGenomeContigName(contig) {
  return `Contig ${contig?.contig_name || contig?.contig_id || "unknown"}`;
}

function getGenomeOccurrenceVisualMetrics(visibleCount) {
  const normalized = Math.max(GENOME_VIEWER_MIN_OCCURRENCES, visibleCount);
  return {
    height: GENOME_OCCURRENCE_HEIGHT,
    gap: GENOME_OCCURRENCE_GAP,
    minWidthRatio: GENOME_OCCURRENCE_WIDTH_RATIO / Math.max(1, normalized),
    minWidth: GENOME_OCCURRENCE_MIN_WIDTH,
    labelSize: 10,
  };
}

function layoutGenomeOccurrences(occurrences) {
  const lanes = [];
  const segments = [...occurrences]
    .map((occurrence) => {
      const rawStart = Number(occurrence.start) || 0;
      const rawEnd = Number(occurrence.end) || rawStart;
      return {
        ...occurrence,
        startCoord: Math.min(rawStart, rawEnd),
        endCoord: Math.max(rawStart, rawEnd),
      };
    })
    .sort((a, b) => (
      a.startCoord - b.startCoord
      || a.endCoord - b.endCoord
      || Number(a.occurrence_id) - Number(b.occurrence_id)
    ))
    .map((occurrence) => {
      let laneIndex = lanes.findIndex((laneEnd) => occurrence.startCoord > laneEnd);
      if (laneIndex === -1) {
        laneIndex = lanes.length;
        lanes.push(occurrence.endCoord);
      } else {
        lanes[laneIndex] = occurrence.endCoord;
      }
      return { ...occurrence, laneIndex };
    });

  return {
    laneCount: lanes.length,
    segments,
  };
}

function renderGenomeContig(contig, layout, x, y, width, height, metrics) {
  const coordinateSpan = getVisibleGenomeCoordinateSpan(layout.segments);
  const occurrenceTop = y + 2;
  const occurrences = layout.segments.map((segment) => (
    renderGenomeOccurrenceSegment(segment, contig, coordinateSpan, x, occurrenceTop, width, metrics)
  ));

  return `
    <g class="genome-contig">
      ${occurrences.join("")}
    </g>
  `;
}

function getVisibleGenomeCoordinateSpan(segments) {
  const starts = segments.map((segment) => segment.startCoord);
  const ends = segments.map((segment) => segment.endCoord);
  const start = Math.min(...starts);
  const end = Math.max(...ends);
  return {
    start,
    end,
    length: Math.max(1, end - start + 1),
  };
}

function renderGenomeOccurrenceSegment(segment, contig, coordinateSpan, contigX, occurrenceTop, contigWidth, metrics) {
  const coordinateScale = contigWidth / coordinateSpan.length;
  const segmentStart = Math.max(0, segment.startCoord - coordinateSpan.start);
  const segmentLength = Math.max(1, segment.endCoord - segment.startCoord + 1);
  const x = contigX + segmentStart * coordinateScale;
  const minimumWidth = Math.max(metrics.minWidth, contigWidth * metrics.minWidthRatio);
  const maxWidth = Math.max(minimumWidth, contigX + contigWidth - x);
  const width = Math.min(
    Math.max(minimumWidth, segmentLength * coordinateScale),
    maxWidth,
  );
  const y = occurrenceTop + segment.laneIndex * (metrics.height + metrics.gap);
  const colorIndex = Math.abs(Number(segment.occurrence_id) || 0) % 10;
  const titleParts = [
    `Occurrence ${segment.occurrence_display_id || formatOccurrenceId(segment.occurrence_id)}`,
    `Stable operon ${segment.stable_display_id || formatStableOperonId(segment.operon_id)}`,
    `Contig ${contig.contig_name || contig.contig_id}`,
    `Coordinates ${formatNumber(segment.startCoord)}-${formatNumber(segment.endCoord)}`,
  ];

  return `
    <a class="genome-occurrence-link" href="#occurrences/${encodeURIComponent(segment.occurrence_id)}">
      <title>${escapeHtml(titleParts.join(" | "))}</title>
      <rect
        class="genome-occurrence genome-occurrence-color-${colorIndex}"
        x="${formatSvgNumber(x)}"
        y="${formatSvgNumber(y)}"
        width="${formatSvgNumber(width)}"
        height="${formatSvgNumber(metrics.height)}"
        rx="2"
      ></rect>
    </a>
  `;
}

export function handleGenomeViewerClick(event) {
  const button = event.target.closest("[data-genome-nav]");
  if (!button || !app.contains(button)) {
    return;
  }

  const action = button.dataset.genomeNav;
  if (action === "backward") {
    moveGenomeViewerOccurrence(-1);
  } else if (action === "forward") {
    moveGenomeViewerOccurrence(1);
  } else if (action === "contig-backward") {
    moveGenomeViewerContig(-1);
  } else if (action === "contig-forward") {
    moveGenomeViewerContig(1);
  } else if (action === "restart") {
    resetGenomeViewerCursor();
  } else if (action === "zoom-in") {
    currentGenomeViewerSize = getNextGenomeViewerZoomInSize();
  } else if (action === "zoom-out") {
    currentGenomeViewerSize = getNextGenomeViewerZoomOutSize();
  }

  updateGenomeViewer();
}

function updateGenomeViewer() {
  normalizeGenomeViewerCursor();
  const windowEl = app.querySelector("[data-genome-window]");
  const statusEl = app.querySelector("[data-genome-status]");
  const contigStatusEl = app.querySelector("[data-genome-contig-status]");
  const contigBackwardButton = app.querySelector('[data-genome-nav="contig-backward"]');
  const backwardButton = app.querySelector('[data-genome-nav="backward"]');
  const forwardButton = app.querySelector('[data-genome-nav="forward"]');
  const contigForwardButton = app.querySelector('[data-genome-nav="contig-forward"]');
  const restartButton = app.querySelector('[data-genome-nav="restart"]');
  const zoomInButton = app.querySelector('[data-genome-nav="zoom-in"]');
  const zoomOutButton = app.querySelector('[data-genome-nav="zoom-out"]');

  if (!windowEl || !statusEl || !currentGenomeViewerData) {
    return;
  }

  const total = getGenomeViewerCurrentContigTotal();
  const range = getGenomeViewerVisibleRange();
  windowEl.innerHTML = renderGenomeWindow(currentGenomeViewerData);
  statusEl.textContent = formatGenomeViewerStatus(range, total);
  if (contigStatusEl) {
    contigStatusEl.textContent = formatGenomeViewerContigLabel();
  }

  if (contigBackwardButton) {
    contigBackwardButton.disabled = !canMoveGenomeViewerContigBackward();
  }
  if (backwardButton) {
    backwardButton.disabled = !canMoveGenomeViewerBackward();
  }
  if (forwardButton) {
    forwardButton.disabled = !canMoveGenomeViewerForward();
  }
  if (contigForwardButton) {
    contigForwardButton.disabled = !canMoveGenomeViewerContigForward();
  }
  if (restartButton) {
    restartButton.disabled = !canRestartGenomeViewer();
  }
  if (zoomInButton) {
    zoomInButton.disabled = currentGenomeViewerSize <= GENOME_VIEWER_MIN_OCCURRENCES;
  }
  if (zoomOutButton) {
    zoomOutButton.disabled = !canGenomeZoomOut();
  }
}

function getGenomeViewerTotal(viewer = currentGenomeViewerData) {
  return getGenomeViewerOrderedOccurrences(viewer).length;
}

function isGenomeViewerCurrentContigFullyVisible(viewer = currentGenomeViewerData) {
  const total = getGenomeViewerCurrentContigTotal(viewer);
  return total > 0 && currentGenomeViewerSize >= total;
}

function findGenomeViewerContigIndex(direction) {
  const contigs = getGenomeViewerContigs();
  for (
    let index = currentGenomeViewerContigIndex + direction;
    index >= 0 && index < contigs.length;
    index += direction
  ) {
    if (getGenomeViewerContigOccurrences(index).length) {
      return index;
    }
  }
  return -1;
}

function moveGenomeViewerOccurrence(direction) {
  normalizeGenomeViewerCursor();
  const contigOccurrences = getGenomeViewerContigOccurrences(currentGenomeViewerContigIndex);
  if (!contigOccurrences.length) {
    return;
  }
  if (isGenomeViewerCurrentContigFullyVisible()) {
    const nextContigIndex = findGenomeViewerContigIndex(direction);
    if (nextContigIndex !== -1) {
      const nextOccurrences = getGenomeViewerContigOccurrences(nextContigIndex);
      currentGenomeViewerContigIndex = nextContigIndex;
      currentGenomeViewerOccurrenceOffset = 0;
      currentGenomeViewerSize = Math.max(currentGenomeViewerSize, nextOccurrences.length);
    }
    return;
  }
  if (direction > 0) {
    if (currentGenomeViewerOccurrenceOffset < contigOccurrences.length - 1) {
      currentGenomeViewerOccurrenceOffset += 1;
      return;
    }
    const nextContigIndex = findGenomeViewerContigIndex(1);
    if (nextContigIndex !== -1) {
      currentGenomeViewerContigIndex = nextContigIndex;
      currentGenomeViewerOccurrenceOffset = 0;
    }
    return;
  }

  if (currentGenomeViewerOccurrenceOffset > 0) {
    currentGenomeViewerOccurrenceOffset -= 1;
    return;
  }
  const previousContigIndex = findGenomeViewerContigIndex(-1);
  if (previousContigIndex !== -1) {
    const previousOccurrences = getGenomeViewerContigOccurrences(previousContigIndex);
    currentGenomeViewerContigIndex = previousContigIndex;
    currentGenomeViewerOccurrenceOffset = Math.max(0, previousOccurrences.length - 1);
  }
}

function moveGenomeViewerContig(direction) {
  normalizeGenomeViewerCursor();
  const wasFullyVisible = isGenomeViewerCurrentContigFullyVisible();
  const nextContigIndex = findGenomeViewerContigIndex(direction);
  if (nextContigIndex !== -1) {
    const nextOccurrences = getGenomeViewerContigOccurrences(nextContigIndex);
    currentGenomeViewerContigIndex = nextContigIndex;
    currentGenomeViewerOccurrenceOffset = 0;
    if (wasFullyVisible) {
      currentGenomeViewerSize = Math.max(currentGenomeViewerSize, nextOccurrences.length);
    }
  }
}

function canMoveGenomeViewerBackward() {
  return getGenomeViewerCursorIndex() > 0;
}

function canMoveGenomeViewerForward() {
  if (isGenomeViewerCurrentContigFullyVisible()) {
    return findGenomeViewerContigIndex(1) !== -1;
  }
  return getGenomeViewerCursorIndex() < getGenomeViewerTotal() - 1;
}

function canMoveGenomeViewerContigBackward() {
  normalizeGenomeViewerCursor();
  return findGenomeViewerContigIndex(-1) !== -1;
}

function canMoveGenomeViewerContigForward() {
  normalizeGenomeViewerCursor();
  return findGenomeViewerContigIndex(1) !== -1;
}

function canRestartGenomeViewer() {
  return (
    currentGenomeViewerSize !== GENOME_VIEWER_MAX_OCCURRENCES
    || getGenomeViewerCursorIndex() !== 0
  );
}

function getGenomeViewerUsefulMaxSize() {
  return Math.max(
    GENOME_VIEWER_MIN_OCCURRENCES,
    getGenomeViewerCurrentContigTotal(),
  );
}

function canGenomeZoomOut() {
  return currentGenomeViewerSize < getGenomeViewerUsefulMaxSize();
}

function getNextGenomeViewerZoomInSize() {
  return Math.max(
    GENOME_VIEWER_MIN_OCCURRENCES,
    Math.floor(currentGenomeViewerSize / GENOME_VIEWER_ZOOM_FACTOR),
  );
}

function getNextGenomeViewerZoomOutSize() {
  const maximum = getGenomeViewerUsefulMaxSize();
  return Math.min(
    maximum,
    Math.max(
      currentGenomeViewerSize + 1,
      Math.ceil(currentGenomeViewerSize * GENOME_VIEWER_ZOOM_FACTOR),
    ),
  );
}
