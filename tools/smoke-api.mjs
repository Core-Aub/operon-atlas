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

const checks = [
  "/api/health",
  "/api/stats",
  "/api/operons?page=1",
  "/api/operons/3454?page=1",
  "/api/occurrences/66374",
  "/api/genomes?page=1",
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
  console.log(`ok ${path}`);
}
