import { escapeHtml } from "../utils/html.js";

export const COLUMN_INFO = Object.freeze({
  OPERON_FAMILY_ID: "Operon family identifier",
  PROTEIN_FAMILY_COMPOSITION: "Protein-family composition",
  GENES_PER_OPERON: "Genes per operon",
  GENOME_OCCURRENCE_COUNT: "Genome occurrence count",
  GENOME_OCCURRENCE_ID: "Genome occurrence identifier",
  GENOME_ACCESSION_ID: "Genome accession identifier",
  GENOME_ORGANISM_NAME: "Genome organism name",
  GENES_PER_OCCURRENCE: "Genes per occurrence",
  PREDICTED_OPERON_COUNT: "Predicted operon count",
  OPERON_ASSOCIATED_GENE_COUNT: "Operon-associated gene count",
  GLOBAL_GENOME_OCCURRENCES: "Global genome occurrences",
  GENE_LOCUS_ID: "Gene locus identifier",
  GENE_FUNCTIONAL_EVIDENCE: "Gene functional evidence",
  PROTEIN_FAMILY_ID: "Protein-family identifier",
  CONTIG_GENOMIC_COORDINATES: "Contig genomic coordinates",
  GENE_LENGTH_BASES: "Gene length bases",
  SUBSYSTEM_FUNCTION_NAME: "Subsystem function name",
  KEGG_PATHWAY_NAME: "KEGG pathway name",
  FUNCTIONAL_CLASSIFICATION_PATH: "Functional classification path",
  SUPPORTING_OCCURRENCE_RATIO: "Supporting occurrence ratio",
  MEAN_ANNOTATED_GENE_SHARE: "Mean annotated-gene share",
  SUPPORTING_GENE_RATIO: "Supporting gene ratio",
  FUNCTION_GENE_PROPORTION: "Function gene proportion",
  EXPORT_DATASET_NAME: "Export dataset name",
  DATASET_CONTENTS_SUMMARY: "Dataset contents summary",
  ARCHIVE_FILE_FORMAT: "Archive file format",
  EXPORTED_ROW_COUNT: "Exported row count",
  COMPRESSED_FILE_SIZE: "Compressed file size",
  FILE_INTEGRITY_CHECKSUM: "File integrity checksum",
  DATASET_DOWNLOAD_LINK: "Dataset download link",
  DOCUMENTATION_FILE_NAME: "Documentation file name",
  FILE_CONTENTS_SUMMARY: "File contents summary",
  DOCUMENTATION_DOWNLOAD_LINK: "Documentation download link",
});

const HELP_BY_DESCRIPTION = Object.freeze({
  [COLUMN_INFO.OPERON_FAMILY_ID]: "family-vs-occurrence",
  [COLUMN_INFO.PROTEIN_FAMILY_COMPOSITION]: "family-vs-occurrence",
  [COLUMN_INFO.GENOME_OCCURRENCE_COUNT]: "family-vs-occurrence",
  [COLUMN_INFO.GENOME_OCCURRENCE_ID]: "family-vs-occurrence",
  [COLUMN_INFO.GLOBAL_GENOME_OCCURRENCES]: "family-vs-occurrence",
  [COLUMN_INFO.GENE_FUNCTIONAL_EVIDENCE]: "annotations",
  [COLUMN_INFO.PROTEIN_FAMILY_ID]: "annotations",
  [COLUMN_INFO.SUBSYSTEM_FUNCTION_NAME]: "annotations",
  [COLUMN_INFO.KEGG_PATHWAY_NAME]: "annotations",
  [COLUMN_INFO.FUNCTIONAL_CLASSIFICATION_PATH]: "annotations",
  [COLUMN_INFO.SUPPORTING_OCCURRENCE_RATIO]: "annotations",
  [COLUMN_INFO.MEAN_ANNOTATED_GENE_SHARE]: "annotations",
  [COLUMN_INFO.SUPPORTING_GENE_RATIO]: "annotations",
  [COLUMN_INFO.FUNCTION_GENE_PROPORTION]: "annotations",
  [COLUMN_INFO.EXPORT_DATASET_NAME]: "downloads",
  [COLUMN_INFO.DATASET_CONTENTS_SUMMARY]: "downloads",
  [COLUMN_INFO.ARCHIVE_FILE_FORMAT]: "downloads",
  [COLUMN_INFO.FILE_INTEGRITY_CHECKSUM]: "downloads",
});

export function renderColumnHeader(label, description, options = {}) {
  const labelHtml = options.labelHtml || escapeHtml(label);
  return `
    <span class="column-header">
      <span class="column-header-label">${labelHtml}</span>
      ${renderColumnInfo(label, description)}
    </span>
  `;
}

function renderColumnInfo(label, description) {
  const helpAnchor = HELP_BY_DESCRIPTION[description];
  return `
    <span
      class="info-tooltip column-info-tooltip"
      tabindex="0"
      aria-label="${escapeHtml(`${label}: ${description}`)}"
    >
      <span class="info-icon" aria-hidden="true">?</span>
      <span class="tooltip-content">
        <span>${escapeHtml(description)}</span>
        ${helpAnchor ? `<a class="tooltip-help-link" href="#help/${helpAnchor}">Learn more</a>` : ""}
      </span>
    </span>
  `;
}
