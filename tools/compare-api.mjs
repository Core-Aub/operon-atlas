const [leftBaseUrl, rightBaseUrl] = process.argv.slice(2);

if (!leftBaseUrl || !rightBaseUrl) {
  console.error("Usage: node tools/compare-api.mjs <left-base-url> <right-base-url>");
  process.exit(1);
}

const paths = [
  "/api/health",
  "/api/stats",
  "/api/operons?page=1",
  "/api/operons/3454?page=1",
  "/api/occurrences/66374",
  "/api/genomes?page=1",
  "/api/genomes?page=1&sort=genome_id&direction=desc",
  "/api/genomes?page=1&sort=organism_name&direction=asc",
  "/api/genomes?page=1&sort=operon_count&direction=desc",
  "/api/genomes?page=1&sort=gene_count&direction=asc",
  "/api/genomes?page=1&sort=invalid&direction=invalid",
  "/api/genomes?page=1&search=Streptomyces&sort=organism_name&direction=desc",
  "/api/genomes/24",
  "/api/genomes/24/operons?page=1",
];

function endpointUrl(baseUrl, path) {
  return new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
}

async function fetchPayload(baseUrl, path) {
  const response = await fetch(endpointUrl(baseUrl, path));
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${baseUrl}${path} returned ${response.status}: ${text.slice(0, 120)}`);
  }
  return JSON.parse(text);
}

for (const path of paths) {
  const [left, right] = await Promise.all([
    fetchPayload(leftBaseUrl, path),
    fetchPayload(rightBaseUrl, path),
  ]);
  const leftJson = JSON.stringify(left);
  const rightJson = JSON.stringify(right);
  if (leftJson !== rightJson) {
    console.error(`mismatch ${path}`);
    console.error(`left:  ${leftJson.slice(0, 500)}`);
    console.error(`right: ${rightJson.slice(0, 500)}`);
    process.exit(1);
  }
  console.log(`match ${path}`);
}
