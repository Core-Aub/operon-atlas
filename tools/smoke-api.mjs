const baseUrl = process.argv[2];

if (!baseUrl) {
  console.error("Usage: node tools/smoke-api.mjs <base-url>");
  process.exit(1);
}

const expectedStats = {
  genomes: 1075,
  operons: 500,
  occurrences: 1154,
  occurrence_genes: 3902,
};

const genomeSortCases = [
  ["genome_id", "asc"],
  ["genome_id", "desc"],
  ["organism_name", "asc"],
  ["organism_name", "desc"],
  ["operon_count", "asc"],
  ["operon_count", "desc"],
  ["gene_count", "asc"],
  ["gene_count", "desc"],
];

const checks = [
  "/api/health",
  "/api/stats",
  "/api/operons?page=1",
  "/api/operons/3454?page=1",
  "/api/occurrences/66374",
  "/api/genomes?page=1",
  ...genomeSortCases.map(([sort, direction]) => (
    `/api/genomes?page=1&sort=${sort}&direction=${direction}`
  )),
  "/api/genomes?page=1&sort=invalid&direction=invalid",
  "/api/genomes?page=1&search=Streptomyces&sort=organism_name&direction=desc",
  "/api/genomes/24",
  "/api/genomes/24/operons?page=1",
];

function endpointUrl(path) {
  return new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
}

async function fetchJson(path) {
  const response = await fetch(endpointUrl(path));
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch (error) {
    throw new Error(`${path} returned non-JSON response: ${text.slice(0, 120)}`);
  }
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}: ${text.slice(0, 120)}`);
  }
  return payload;
}

function compareGenomeSortValues(left, right, sort) {
  if (sort === "operon_count" || sort === "gene_count") {
    return Number(left[sort]) - Number(right[sort]);
  }
  const leftValue = String(left[sort] || "").toLowerCase();
  const rightValue = String(right[sort] || "").toLowerCase();
  if (leftValue < rightValue) {
    return -1;
  }
  if (leftValue > rightValue) {
    return 1;
  }
  return 0;
}

function assertGenomeSort(path, payload, sort, direction) {
  if (payload?.sort !== sort || payload?.direction !== direction) {
    throw new Error(
      `${path} expected normalized sort ${sort} ${direction}, got ${payload?.sort} ${payload?.direction}`,
    );
  }
  const items = payload?.items || [];
  for (let index = 1; index < items.length; index += 1) {
    const previous = items[index - 1];
    const current = items[index];
    const comparison = compareGenomeSortValues(previous, current, sort);
    const outOfOrder = direction === "asc" ? comparison > 0 : comparison < 0;
    if (outOfOrder) {
      throw new Error(`${path} returned out-of-order ${sort} values at index ${index}`);
    }
    if (comparison === 0 && Number(previous.genome_key) > Number(current.genome_key)) {
      throw new Error(`${path} did not use genome_key ASC as a tie-breaker at index ${index}`);
    }
  }
}

for (const path of checks) {
  const payload = await fetchJson(path);
  if (path === "/api/health" && payload?.ok !== true) {
    throw new Error("/api/health did not return ok=true");
  }
  if (path === "/api/stats") {
    for (const [key, value] of Object.entries(expectedStats)) {
      if (payload?.[key] !== value) {
        throw new Error(`/api/stats expected ${key}=${value}, got ${payload?.[key]}`);
      }
    }
  }
  if (path === "/api/occurrences/66374") {
    const pegNums = (payload?.genes || []).map((gene) => gene.peg_num).join(",");
    if (pegNums !== "2553,2554") {
      throw new Error(`/api/occurrences/66374 expected peg nums 2553,2554, got ${pegNums}`);
    }
  }
  if (path.startsWith("/api/genomes?page=1&sort=")) {
    const params = new URL(path, "http://local").searchParams;
    const requestedSort = params.get("sort");
    const requestedDirection = params.get("direction");
    const sort = requestedSort === "invalid" ? "genome_id" : requestedSort;
    const direction = requestedDirection === "invalid" ? "asc" : requestedDirection;
    assertGenomeSort(path, payload, sort, direction);
  }
  if (path.includes("search=Streptomyces")) {
    const hasUnexpectedItem = (payload?.items || []).some((item) => (
      !String(item.genome_id || "").toLowerCase().includes("streptomyces")
      && !String(item.organism_name || "").toLowerCase().includes("streptomyces")
    ));
    if (hasUnexpectedItem) {
      throw new Error(`${path} returned a genome outside the search filter`);
    }
    assertGenomeSort(path, payload, "organism_name", "desc");
  }
  console.log(`ok ${path}`);
}
