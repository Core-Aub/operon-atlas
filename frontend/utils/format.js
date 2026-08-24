import {
  OCCURRENCE_ID_DIGITS,
  STABLE_OPERON_ID_DIGITS,
} from "../config.js";

export function formatStableOperonId(value) {
  const number = Number.parseInt(value, 10);
  if (!Number.isFinite(number)) {
    return "OAF";
  }
  return `OAF${String(number).padStart(STABLE_OPERON_ID_DIGITS, "0")}`;
}

export function formatOccurrenceId(value) {
  const number = Number.parseInt(value, 10);
  if (!Number.isFinite(number)) {
    return "OAO";
  }
  return `OAO${String(number).padStart(OCCURRENCE_ID_DIGITS, "0")}`;
}

export function formatPgfamContent(pgfams, limit = null) {
  if (!Array.isArray(pgfams)) {
    return "";
  }
  if (limit !== null && pgfams.length > limit) {
    return `${pgfams.slice(0, limit).join(", ")} ...`;
  }
  return pgfams.join(", ");
}

export function formatStrand(value) {
  const number = Number(value);
  if (number === 1) {
    return "+";
  }
  if (number === -1) {
    return "-";
  }
  return "";
}

export function formatNumber(value, withGrouping = true) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "";
  }
  return withGrouping ? number.toLocaleString() : String(number);
}

export function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "";
  }
  if (bytes < 1024) {
    return `${formatNumber(bytes)} ${pluralize(bytes, "byte")}`;
  }

  const units = ["KiB", "MiB", "GiB", "TiB"];
  let scaled = bytes;
  let unitIndex = -1;
  do {
    scaled /= 1024;
    unitIndex += 1;
  } while (scaled >= 1024 && unitIndex < units.length - 1);

  return `${scaled.toLocaleString(undefined, {
    maximumFractionDigits: 1,
  })} ${units[unitIndex]}`;
}

export function pluralize(value, singular, plural = `${singular}s`) {
  return Number(value) === 1 ? singular : plural;
}

export function formatCount(value, singular, plural = `${singular}s`) {
  return `${formatNumber(value)} ${pluralize(value, singular, plural)}`;
}

export function formatPercent(value, maximumFractionDigits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "";
  }
  return `${(number * 100).toLocaleString(undefined, {
    maximumFractionDigits,
  })}%`;
}

export function formatSupport(count, total) {
  return `${formatNumber(count)} / ${formatNumber(total)}`;
}

export function formatGeneSupport(count, annotatedGeneCount) {
  return `${formatSupport(count, annotatedGeneCount)} annotated ${pluralize(annotatedGeneCount, "gene")}`;
}

export function formatClassPath(...parts) {
  return parts
    .map((part) => firstPresent(part))
    .filter(Boolean)
    .join(" > ");
}

export function formatSvgNumber(value) {
  return Number(value).toFixed(2).replace(/\.?0+$/, "");
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function firstPresent(...values) {
  return values.find((value) => value !== null && value !== undefined && String(value).trim() !== "") || "";
}
