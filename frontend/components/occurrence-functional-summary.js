import { escapeHtml } from "../utils/html.js";
import {
  firstPresent,
  formatNumber,
} from "../utils/format.js";
import {
  renderKeggPathwayLink,
} from "./links.js";

const FAMILY_TOOLTIP_RULES = [
  "Summarizes functional evidence across annotated occurrences in this operon family.",
  "Annotated occurrences are occurrences with at least one gene assigned a subsystem or pathway annotation.",
  "Occurrence support shows how often a function appears among annotated occurrences.",
  "Average annotated-gene share shows how much of the annotated portion of the operon is explained by that function.",
  "Displayed functions are filtered to emphasize recurring functions that explain a meaningful share of annotated genes.",
  "Annotation coverage is reported separately to show how much functional evidence is available for the family.",
];

const OCCURRENCE_TOOLTIP_RULES = [
  "Shows exact functional annotations assigned to genes in this occurrence.",
  "Annotated-gene share is the fraction of annotated genes associated with a subsystem or pathway.",
  "All exact subsystem and pathway annotations detected in this occurrence are shown.",
];

export function renderOperonFunctionalSummary(summary) {
  const normalized = normalizeOperonFunctionalSummary(summary);
  if (!normalized.coverage && !normalized.subsystems.length && !normalized.pathways.length) {
    return renderFunctionalSummaryBlock(
      "Functional Evidence Summary",
      FAMILY_TOOLTIP_RULES,
      `<div class="functional-summary-empty">No functional evidence available for this operon family.</div>`,
    );
  }

  const functionRowCount = normalized.subsystems.length + normalized.pathways.length;

  return renderFunctionalSummaryBlock(
    "Functional Evidence Summary",
    FAMILY_TOOLTIP_RULES,
    `
      <div class="functional-summary-stack">
        ${renderOperonEvidenceTable("Subsystems", "Subsystem", normalized.subsystems, subsystemName, subsystemContext)}
        ${renderOperonPathwayEvidenceTable(normalized.pathways)}
        ${functionRowCount ? "" : `<div class="functional-summary-empty">No subsystem or pathway evidence passed the display thresholds.</div>`}
      </div>
    `,
  );
}

export function renderOccurrenceFunctionalSummary(genesOrSummary) {
  const summary = isOccurrenceFunctionalSummary(genesOrSummary)
    ? genesOrSummary
    : buildOccurrenceFunctionalSummary(genesOrSummary);
  if (!summary.annotatedGeneCount) {
    return renderFunctionalSummaryBlock(
      "Functional Evidence Summary",
      OCCURRENCE_TOOLTIP_RULES,
      `<div class="functional-summary-empty">No functional annotation available for this occurrence.</div>`,
    );
  }

  const functionRowCount = summary.subsystems.length + summary.pathways.length;

  return renderFunctionalSummaryBlock(
    "Functional Evidence Summary",
    OCCURRENCE_TOOLTIP_RULES,
    `
      <div class="functional-summary-stack">
        ${renderOccurrenceEvidenceTable("Subsystems", "Subsystem", summary.subsystems, summary.annotatedGeneCount)}
        ${renderOccurrencePathwayEvidenceTable(summary.pathways, summary.annotatedGeneCount)}
        ${functionRowCount ? "" : `<div class="functional-summary-empty">No subsystem or pathway evidence available for this occurrence.</div>`}
      </div>
    `,
  );
}

export function buildOccurrenceFunctionalSummary(genes) {
  const normalizedGenes = Array.isArray(genes) ? genes : [];
  const subsystems = new Map();
  const pathways = new Map();
  let annotatedGeneCount = 0;

  normalizedGenes.forEach((gene) => {
    const geneSubsystems = Array.isArray(gene.subsystems) ? gene.subsystems : [];
    const genePathways = Array.isArray(gene.pathways) ? gene.pathways : [];

    if (geneSubsystems.length || genePathways.length) {
      annotatedGeneCount += 1;
    }

    addGeneSubsystemGroups(geneSubsystems, subsystems);
    addGenePathwayGroups(genePathways, pathways);
  });

  return {
    geneCount: normalizedGenes.length,
    annotatedGeneCount,
    annotatedGeneFraction: normalizedGenes.length ? annotatedGeneCount / normalizedGenes.length : 0,
    subsystems: finalizeOccurrenceGroups(subsystems, annotatedGeneCount),
    pathways: finalizeOccurrenceGroups(pathways, annotatedGeneCount),
  };
}

export function formatAnnotatedGeneCoverage(summary) {
  return stackCell(
    `${formatNumber(summary.annotatedGeneCount)} / ${formatNumber(summary.geneCount)}`,
    formatPercent(summary.annotatedGeneFraction),
  );
}

export function getOperonAnnotationCoverageRows(summary) {
  const coverage = normalizeOperonFunctionalSummary(summary).coverage;
  if (!coverage) {
    return [];
  }
  return [
    [
      "Annotated occurrences",
      stackCell(
        formatSupport(coverage.annotated_occurrence_count, coverage.occurrence_count),
        formatPercent(coverage.annotated_occurrence_fraction),
      ),
    ],
    [
      "Average gene annotation coverage",
      stackCell(formatPercent(coverage.avg_annotated_gene_fraction)),
    ],
    // [
    //   "Average gene annotation coverage among annotated occurrences",
    //   stackCell(formatPercent(coverage.avg_annotated_gene_fraction_among_annotated_occurrences)),
    // ],
  ];
}

function normalizeOperonFunctionalSummary(summary) {
  const normalized = summary && typeof summary === "object" ? summary : {};
  return {
    coverage: normalized.coverage || null,
    subsystems: Array.isArray(normalized.subsystems) ? normalized.subsystems : [],
    pathways: Array.isArray(normalized.pathways) ? normalized.pathways : [],
  };
}

function addGeneSubsystemGroups(geneSubsystems, subsystems) {
  const seenSubsystems = new Set();

  geneSubsystems.forEach((subsystem) => {
    const key = getFunctionalKey(subsystem.subsystem_id, subsystem.subsystem_name);
    if (!key || seenSubsystems.has(key)) {
      return;
    }
    seenSubsystems.add(key);
    addOccurrenceSupport(subsystems, key, {
      name: firstPresent(subsystem.subsystem_name, subsystem.subsystem_id, "Unnamed subsystem"),
      context: subsystemContext(subsystem),
    });
  });
}

function addGenePathwayGroups(genePathways, pathways) {
  const seenPathways = new Set();

  genePathways.forEach((pathway) => {
    const key = getFunctionalKey(pathway.pathway_id, pathway.pathway_name);
    if (!key || seenPathways.has(key)) {
      return;
    }
    seenPathways.add(key);
    addOccurrenceSupport(pathways, key, {
      name: firstPresent(pathway.pathway_name, pathway.pathway_id, "Unnamed pathway"),
      pathway_id: firstPresent(pathway.pathway_id),
      pathway_name: firstPresent(pathway.pathway_name),
      context: pathwayContext(pathway),
    });
  });
}

function addOccurrenceSupport(groups, key, evidence) {
  const current = groups.get(key);
  if (current) {
    current.supportingGeneCount += 1;
    return;
  }
  groups.set(key, {
    ...evidence,
    supportingGeneCount: 1,
  });
}

function finalizeOccurrenceGroups(groups, annotatedGeneCount) {
  if (!annotatedGeneCount) {
    return [];
  }
  return Array.from(groups.values())
    .map((row) => ({
      ...row,
      annotatedGeneShare: row.supportingGeneCount / annotatedGeneCount,
    }))
    .sort((a, b) => {
      if (b.annotatedGeneShare !== a.annotatedGeneShare) {
        return b.annotatedGeneShare - a.annotatedGeneShare;
      }
      if (b.supportingGeneCount !== a.supportingGeneCount) {
        return b.supportingGeneCount - a.supportingGeneCount;
      }
      return String(a.name).localeCompare(String(b.name), undefined, { sensitivity: "base" });
    });
}

function renderFunctionalSummaryBlock(title, tooltipRules, body) {
  return `
    <div class="functional-summary-header">
      <h2>${escapeHtml(title)}</h2>
      ${renderInfoTooltip(tooltipRules)}
    </div>
    ${body}
  `;
}

function renderInfoTooltip(rules) {
  const ariaLabel = rules.join(" ");
  return `
    <span class="info-tooltip" tabindex="0" aria-label="${escapeHtml(ariaLabel)}">
      <span class="info-icon" aria-hidden="true">i</span>
      <span class="tooltip-content" role="tooltip">
        <ul>
          ${rules.map((rule) => `<li>${escapeHtml(rule)}</li>`).join("")}
        </ul>
      </span>
    </span>
  `;
}

function renderOperonEvidenceTable(title, primaryColumnLabel, rows, nameFormatter, contextFormatter) {
  if (!rows.length) {
    return "";
  }
  return renderEvidenceTable(
    title,
    [
      primaryColumnLabel,
      "Class",
      "Occurrence support",
      "Avg annotated-gene share",
    ],
    rows.map((row) => [
      stackCell(nameFormatter(row)),
      stackCell(contextFormatter(row)),
      stackCell(
        formatSupport(row.supporting_occurrence_count, row.annotated_occurrence_count),
        formatPercent(row.supporting_occurrence_fraction),
      ),
      stackCell(formatPercent(row.avg_annotated_gene_share)),
    ]),
  );
}

function renderOperonPathwayEvidenceTable(rows) {
  if (!rows.length) {
    return "";
  }
  return renderEvidenceTable(
    "Pathways",
    [
      "Pathway",
      "Class",
      "Occurrence support",
      "Avg annotated-gene share",
    ],
    rows.map((row) => [
      stackCell(formatPathwayDisplayName(row), "", {
        primaryHtml: renderPathwayDisplay(row),
        title: formatPathwayTitle(row),
      }),
      stackCell(pathwayContext(row)),
      stackCell(
        formatSupport(row.supporting_occurrence_count, row.annotated_occurrence_count),
        formatPercent(row.supporting_occurrence_fraction),
      ),
      stackCell(formatPercent(row.avg_annotated_gene_share)),
    ]),
  );
}

function renderOccurrenceEvidenceTable(title, primaryColumnLabel, rows, annotatedGeneCount) {
  if (!rows.length) {
    return "";
  }
  return renderEvidenceTable(
    title,
    [
      primaryColumnLabel,
      "Class",
      "Gene support",
      "Annotated-gene share",
    ],
    rows.map((row) => [
      stackCell(row.name),
      stackCell(row.context),
      stackCell(formatSupport(row.supportingGeneCount, annotatedGeneCount)),
      stackCell(formatPercent(row.annotatedGeneShare)),
    ]),
  );
}

function renderOccurrencePathwayEvidenceTable(rows, annotatedGeneCount) {
  if (!rows.length) {
    return "";
  }
  return renderEvidenceTable(
    "Pathways",
    [
      "Pathway",
      "Class",
      "Gene support",
      "Annotated-gene share",
    ],
    rows.map((row) => [
      stackCell(row.name, "", {
        primaryHtml: renderPathwayDisplay(row),
        title: formatPathwayTitle(row),
      }),
      stackCell(row.context),
      stackCell(formatSupport(row.supportingGeneCount, annotatedGeneCount)),
      stackCell(formatPercent(row.annotatedGeneShare)),
    ]),
  );
}

function renderEvidenceTable(title, columns, rows, numericColumnStart = 2) {
  return `
    <section class="functional-summary-subsection">
      <h3>${escapeHtml(title)}</h3>
      <div class="panel functional-summary-panel">
        <div class="table-wrap">
          <table class="functional-summary-table">
            <thead>
              <tr>
                ${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${rows.map((cells) => `
                <tr>
                  ${cells.map((cell, index) => `<td class="${index >= numericColumnStart ? "numeric" : ""}">${cell}</td>`).join("")}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  `;
}

function stackCell(primary, secondary = "", options = {}) {
  const value = firstPresent(primary);
  const primaryHtml = firstPresent(options.primaryHtml);
  if (!value && !primaryHtml) {
    return `<span class="functional-summary-muted">--</span>`;
  }
  const title = firstPresent(options.title, value);
  return `
    <div class="functional-summary-cell">
      <span class="functional-summary-primary" title="${escapeHtml(title)}">${primaryHtml || escapeHtml(value)}</span>
      ${secondary ? `<span class="functional-summary-secondary">${escapeHtml(secondary)}</span>` : ""}
    </div>
  `;
}

function getFunctionalKey(...values) {
  const value = firstPresent(...values);
  return value ? String(value).trim() : "";
}

function subsystemName(row) {
  return firstPresent(row.subsystem_name, "Unnamed subsystem");
}

function subsystemContext(row) {
  return formatSubsystemClassPath(
    row.subsystem_superclass,
    row.subsystem_class,
    row.subsystem_subclass,
  );
}

function pathwayName(row) {
  return formatPathwayDisplayName(row);
}

function pathwayContext(row) {
  return firstPresent(row.pathway_class);
}

function formatPathwayDisplayName(pathway) {
  return firstPresent(pathway.pathway_name, pathway.pathway_id, "Unnamed pathway");
}

function formatPathwayTitle(pathway) {
  return [
    firstPresent(pathway.pathway_name, pathway.name),
    firstPresent(pathway.pathway_id),
  ].filter(Boolean).join(" ");
}

function renderPathwayDisplay(pathway) {
  const name = firstPresent(pathway.pathway_name, pathway.name, "Unnamed pathway");
  const pathwayId = firstPresent(pathway.pathway_id);
  const pathwayLink = pathwayId ? renderKeggPathwayLink(pathwayId) : "";
  if (!pathwayLink) {
    return escapeHtml(name);
  }
  if (normalizeFunctionalText(name) === normalizeFunctionalText(pathwayId)) {
    return pathwayLink;
  }
  return `${escapeHtml(name)} <span class="functional-summary-separator">-</span> <span class="functional-summary-id">${pathwayLink}</span>`;
}

function formatPercent(value, maximumFractionDigits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "";
  }
  return `${(number * 100).toLocaleString(undefined, {
    maximumFractionDigits,
  })}%`;
}

function formatSupport(count, total) {
  return `${formatNumber(count)} / ${formatNumber(total)}`;
}

function formatSubsystemClassPath(superclass, className, subclass) {
  return [
    titleCaseWords(superclass),
    firstPresent(className),
    firstPresent(subclass),
  ].filter(Boolean).join(" > ");
}

function titleCaseWords(value) {
  const text = firstPresent(value);
  if (!text) {
    return "";
  }
  return text
    .toLowerCase()
    .split(/\s+/)
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function normalizeFunctionalText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function isOccurrenceFunctionalSummary(value) {
  return Boolean(
    value
    && typeof value === "object"
    && Array.isArray(value.subsystems)
    && Array.isArray(value.pathways)
    && Object.prototype.hasOwnProperty.call(value, "annotatedGeneCount")
  );
}
