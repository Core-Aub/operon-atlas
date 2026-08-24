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
  "/api/downloads",
  "/api/search?q=Glycolysis",
  "/api/search?q=Glycolysis&type=pathway&page=1",
  "/api/search?q=OAF003454",
  "/api/search?q=OAO066374",
  "/api/search?q=PGF_02517283&type=pgfam&page=1",
  "/api/search?q=1003195.11.peg.2553",
  "/api/search?q=fig%7C1003195.11.peg.2553",
  "/api/search?q=PATRIC.1003195.11.FQ859185.CDS.1051816.1052763.rev",
  "/api/search?q=2995706",
  "/api/operons?page=1",
  "/api/operons?page=1&entity_type=pgfam&entity_key=2517283",
  "/api/operons?page=1&search=PGF_02517283",
  "/api/operons/3454?page=1",
  "/api/operons/3454?page=1&entity_type=pgfam&entity_key=2517283",
  "/api/operons/3454?page=1&search=PGF_02517283",
  "/api/operons/3454/taxonomy?page=1",
  "/api/occurrences/66374",
  "/api/occurrences/66374?gene=1003195.11.peg.2553",
  "/api/occurrences/430395",
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

async function expectStatus(path, expectedStatus) {
  const response = await fetch(endpointUrl(path));
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch (error) {
    throw new Error(`${path} returned non-JSON response: ${text.slice(0, 120)}`);
  }
  if (response.status !== expectedStatus) {
    throw new Error(
      `${path} expected ${expectedStatus}, got ${response.status}: ${text.slice(0, 120)}`,
    );
  }
  if (!payload?.error) {
    throw new Error(`${path} expected a JSON error payload`);
  }
  console.log(`ok ${path} -> ${expectedStatus}`);
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
  if (path === "/api/downloads") {
    const filenames = (payload?.datasets || []).map((item) => item.filename).sort();
    const expected = [
      "operon_families.tsv.gz",
      "operon_occurrence_genes.tsv.gz",
      "operon_occurrences.tsv.gz",
    ];
    if (
      payload?.release !== "1.1.0"
      || payload?.prefix !== "releases/1.1.0/"
      || JSON.stringify(filenames) !== JSON.stringify(expected)
      || payload?.datasets?.some((item) => (
        !item.download_url?.startsWith("https://downloads.operonatlas.org/releases/1.1.0/")
        || item.object_key !== `releases/1.1.0/${item.filename}`
      ))
      || payload?.documentation?.filename !== "data_dictionary.tsv"
    ) {
      throw new Error(`${path} returned an invalid 1.1.0 release contract`);
    }
  }
  if (path === "/api/search?q=Glycolysis") {
    if (payload?.mode !== "preview" || payload?.q !== "Glycolysis") {
      throw new Error(`${path} returned an invalid preview contract`);
    }
    const pathwayGroup = (payload?.groups || []).find((group) => (
      group.type === "pathway"
    ));
    if (!pathwayGroup || pathwayGroup.total < 1 || pathwayGroup.items.length < 1) {
      throw new Error(`${path} did not return a pathway preview group`);
    }
  }
  if (path.includes("q=Glycolysis&type=pathway")) {
    if (
      payload?.mode !== "entities"
      || payload?.type !== "pathway"
      || payload?.page !== 1
      || payload?.pageSize !== 20
      || payload?.total < 1
      || !Array.isArray(payload?.items)
    ) {
      throw new Error(`${path} returned an invalid paginated entity contract`);
    }
  }
  if (path === "/api/search?q=OAF003454") {
    const direct = (payload?.directHits || []).find((hit) => (
      hit.kind === "operon" && hit.operonId === 3454
    ));
    if (!direct) {
      throw new Error(`${path} did not resolve the operon family ID`);
    }
  }
  if (path === "/api/search?q=OAO066374") {
    const direct = (payload?.directHits || []).find((hit) => (
      hit.kind === "occurrence" && hit.occurrenceId === 66374
    ));
    if (!direct) {
      throw new Error(`${path} did not resolve the occurrence ID`);
    }
  }
  if (path.includes("q=PGF_02517283&type=pgfam")) {
    if (
      payload?.type !== "pgfam"
      || payload?.total !== 1
      || payload?.items?.[0]?.key !== 2517283
    ) {
      throw new Error(`${path} did not resolve the exact PGFam`);
    }
  }
  if (path === "/api/search?q=1003195.11.peg.2553") {
    const direct = (payload?.directHits || []).find((hit) => (
      hit.kind === "gene"
      && hit.geneId === "1003195.11.peg.2553"
      && hit.occurrenceId === 66374
    ));
    if (!direct) {
      throw new Error(`${path} did not resolve the exact reconstructed gene ID`);
    }
  }
  if (
    path === "/api/search?q=fig%7C1003195.11.peg.2553"
    || path.includes("PATRIC.1003195.11.FQ859185.CDS")
  ) {
    const direct = (payload?.directHits || []).find((hit) => (
      hit.kind === "gene"
      && hit.geneId === "1003195.11.peg.2553"
      && hit.occurrenceId === 66374
    ));
    if (!direct) {
      throw new Error(`${path} did not resolve the alternate exact gene ID`);
    }
  }
  if (path === "/api/search?q=2995706") {
    const direct = (payload?.directHits || []).find((hit) => (
      hit.kind === "entity" && hit.type === "genus" && hit.key === 2995706
    ));
    if (!direct) {
      throw new Error(`${path} did not resolve the numeric taxon ID`);
    }
  }
  if (path.includes("entity_type=pgfam") && path.startsWith("/api/operons?page")) {
    if (!(payload?.items || []).some((item) => item.operon_id === 3454)) {
      throw new Error(`${path} did not return family 3454`);
    }
    if (payload?.entityFilter?.key !== 2517283) {
      throw new Error(`${path} did not echo the normalized entity filter`);
    }
  }
  if (path === "/api/operons?page=1&search=PGF_02517283") {
    const family = (payload?.items || []).find((item) => item.operon_id === 3454);
    if (!family || !(family.matchReasons || []).some((reason) => (
      reason.type === "pgfam" && reason.key === 2517283
    ))) {
      throw new Error(`${path} did not return a bounded PGFam match reason`);
    }
  }
  if (path.startsWith("/api/operons/3454?page=1&")) {
    if (payload?.total < 1 || !Array.isArray(payload?.occurrences)) {
      throw new Error(`${path} did not preserve the occurrence filter`);
    }
    if (path.includes("entity_type=pgfam") && payload?.entityFilter?.key !== 2517283) {
      throw new Error(`${path} did not echo the normalized entity filter`);
    }
    if (path.includes("search=PGF_") && payload?.search !== "PGF_02517283") {
      throw new Error(`${path} did not echo the broad search filter`);
    }
  }
  if (path === "/api/operons/3454/taxonomy?page=1") {
    if (
      payload?.operonId !== 3454
      || payload?.counts?.genomes < 1
      || !Array.isArray(payload?.phyla)
      || !Array.isArray(payload?.genera?.items)
      || typeof payload?.unclassified?.speciesGenomes !== "number"
      || typeof payload?.unclassified?.generaGenomes !== "number"
      || typeof payload?.unclassified?.phylaGenomes !== "number"
    ) {
      throw new Error(`${path} returned an invalid taxonomy summary contract`);
    }
  }
  if (path === "/api/occurrences/66374") {
    const pegNums = (payload?.genes || []).map((gene) => gene.peg_num).join(",");
    if (pegNums !== "2553,2554") {
      throw new Error(`/api/occurrences/66374 expected peg nums 2553,2554, got ${pegNums}`);
    }
  }
  if (path.includes("/api/occurrences/66374?gene=")) {
    const highlighted = (payload?.genes || []).filter((gene) => gene.highlighted);
    if (
      payload?.highlightGeneId !== "1003195.11.peg.2553"
      || highlighted.length !== 1
      || highlighted[0].gene_id !== "1003195.11.peg.2553"
    ) {
      throw new Error(`${path} did not highlight exactly the requested gene`);
    }
  }
  if (path === "/api/occurrences/430395") {
    const pathwayGene = (payload?.genes || []).find((gene) => gene.peg_num === 306);
    const subsystemGene = (payload?.genes || []).find((gene) => gene.peg_num === 307);
    if (
      pathwayGene?.pathways?.length !== 1
      || pathwayGene.pathways[0]?.ec_number !== "4.1.1.2"
      || pathwayGene.pathways[0]?.pathway_id !== "00630"
      || subsystemGene?.subsystems?.length !== 1
      || subsystemGene.subsystems[0]?.role_id !== "Cys-tRNA(Pro)_deacylase_YbaK"
      || subsystemGene.subsystems[0]?.subsystem_id !== "tRNA_aminoacylation,_Pro"
    ) {
      throw new Error(`${path} changed the representative annotation payload`);
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

const entitySearchCases = [
  ["product", "hypothetical protein"],
  ["pgfam", "PGF_02517283"],
  ["ec", "1.1.1.1"],
  ["pathway", "Glycolysis"],
  ["pathway_class", "Amino Acid Metabolism"],
  ["subsystem", "diacetamido"],
  ["subsystem_class", "Capsule and Slime layer"],
  ["role", "hydroxyacyl"],
  ["genome", "1003195.11"],
  ["species", "Streptantibioticus cattleyicolor"],
  ["genus", "Streptantibioticus"],
  ["phylum", "Actinomycetota"],
];

for (const [type, query] of entitySearchCases) {
  const searchPath = (
    `/api/search?q=${encodeURIComponent(query)}&type=${type}&page=1`
  );
  const searchPayload = await fetchJson(searchPath);
  const entity = searchPayload?.items?.[0];
  if (
    searchPayload?.mode !== "entities"
    || searchPayload?.type !== type
    || searchPayload?.total < 1
    || !entity
  ) {
    throw new Error(`${searchPath} returned no ${type} entity`);
  }
  console.log(`ok ${searchPath}`);

  const familyPath = (
    `/api/operons?page=1&entity_type=${type}&entity_key=${entity.key}`
  );
  const families = await fetchJson(familyPath);
  const family = families?.items?.[0];
  if (families?.total < 1 || !family || families?.entityFilter?.type !== type) {
    throw new Error(`${familyPath} did not return a typed family result`);
  }
  console.log(`ok ${familyPath}`);

  if (["product", "ec", "role", "species"].includes(type)) {
    const detailPath = (
      `/api/operons/${family.operon_id}?page=1&entity_type=${type}&entity_key=${entity.key}`
    );
    const detail = await fetchJson(detailPath);
    if (detail?.total < 1 || detail?.entityFilter?.type !== type) {
      throw new Error(`${detailPath} did not retain the typed occurrence filter`);
    }
    console.log(`ok ${detailPath}`);
  }
}

const taxonomy = await fetchJson("/api/operons/3454/taxonomy?page=1");
const firstPhylum = taxonomy?.phyla?.[0];
if (firstPhylum) {
  const phylumBrowsePath = (
    `/api/operons?page=1&entity_type=phylum&entity_key=${firstPhylum.taxonId}`
  );
  const phylumBrowse = await fetchJson(phylumBrowsePath);
  if (!(phylumBrowse?.items || []).some((item) => item.operon_id === 3454)) {
    throw new Error(`${phylumBrowsePath} did not return family 3454`);
  }
  console.log(`ok ${phylumBrowsePath}`);

  const phylumDetailPath = (
    `/api/operons/3454?page=1&entity_type=phylum&entity_key=${firstPhylum.taxonId}`
  );
  const phylumDetail = await fetchJson(phylumDetailPath);
  if (phylumDetail?.total < 1 || phylumDetail?.entityFilter?.type !== "phylum") {
    throw new Error(`${phylumDetailPath} did not filter family occurrences`);
  }
  console.log(`ok ${phylumDetailPath}`);
}

await expectStatus("/api/search", 400);
await expectStatus("/api/search?q=a", 400);
await expectStatus("/api/search?q=test&type=invalid", 400);
await expectStatus(`/api/search?q=${encodeURIComponent("é".repeat(25))}`, 400);
await expectStatus("/api/operons?entity_type=product", 400);
await expectStatus("/api/operons?entity_type=invalid&entity_key=1", 400);
await expectStatus("/api/occurrences/66374?gene=invalid", 400);
