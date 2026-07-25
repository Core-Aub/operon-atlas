export const API_BASE = "http://localhost:8787";

export const STABLE_OPERON_ID_DIGITS = 6;
export const OCCURRENCE_ID_DIGITS = 6;

export const DEFAULT_OPERON_SORT = "occurrence_count";
export const DEFAULT_OPERON_SORT_DIRECTION = "desc";
export const OPERON_SORT_FIELDS = new Set(["operon_id", "gene_count", "occurrence_count"]);

export const GENE_VIEWER_MIN_SIZE = 2;
export const GENE_VIEWER_MAX_SIZE = 60;
export const GENE_VIEWER_ZOOM_STEP = 2;
export const GENE_VIEWER_NAV_STEP = 1;
export const GENE_VIEWBOX_WIDTH = 1000;
export const GENE_VIEWBOX_HEIGHT = 166;
export const GENE_VIEWBOX_PADDING_X = 24;
export const GENE_MIN_ARROW_WIDTH = 8;

export const GENOME_VIEWER_MIN_OCCURRENCES = 2;
export const GENOME_VIEWER_MAX_OCCURRENCES = 20;
export const GENOME_VIEWER_ZOOM_FACTOR = 2;
export const GENOME_VIEWBOX_WIDTH = 1000;
export const GENOME_VIEWBOX_HEIGHT = 164;
export const GENOME_VIEWBOX_PADDING_X = 24;
export const GENOME_VIEWBOX_PADDING_Y = 24;
export const GENOME_OCCURRENCE_HEIGHT = 30;
export const GENOME_OCCURRENCE_GAP = 7;
export const GENOME_OCCURRENCE_MIN_WIDTH = 6;
export const GENOME_OCCURRENCE_WIDTH_RATIO = 0.52;

export const OPERON_FILTER_MIN = 1;
export const OPERON_FILTER_MAX = 10000;
export const FILTER_TEXT_MAX_LENGTH = 120;
