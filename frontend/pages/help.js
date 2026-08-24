import { app } from "../dom.js";
import { pageHeader } from "../components/layout.js";

const HELP_SECTIONS = new Set([
  "about",
  "prediction-method",
  "getting-started",
  "family-vs-occurrence",
  "visualizations",
  "site-views",
  "search-filtering",
  "annotations",
  "downloads",
  "scope-limitations",
]);

export function renderHelp(sectionId = "") {
  app.innerHTML = `
    <article class="help-page">
      ${pageHeader("Help")}

      <section class="help-intro" id="about">
        <p class="lede">
          OperonAtlas is an open resource for exploring predicted bacterial operons across
          BV-BRC representative and reference genomes. It connects operon families to their
          genome-specific occurrences, gene organization, and functional annotations.
        </p>
      </section>

      <nav class="help-contents panel" aria-label="Help page contents">
        <h2>On this page</h2>
        <ol class="help-contents-list">
          ${helpContentsLink("prediction-method", "Prediction method")}
          ${helpContentsLink("getting-started", "Getting started")}
          ${helpContentsLink("family-vs-occurrence", "Families and occurrences")}
          ${helpContentsLink("visualizations", "Operon visualizations")}
          ${helpContentsLink("site-views", "Site views")}
          ${helpContentsLink("search-filtering", "Search and filtering")}
          ${helpContentsLink("annotations", "Functional annotations")}
          ${helpContentsLink("downloads", "Choosing a download")}
          ${helpContentsLink("scope-limitations", "Scope and limitations")}
        </ol>
      </nav>

      <section class="help-section" id="prediction-method">
        ${helpHeading("Prediction method")}
        <p>
          The operon predictions in OperonAtlas were generated using the transformer-based
          approach described in the following paper. It provides details on the prediction model,
          input features, validation and benchmark metrics, ablation and resilience analyses,
          and methodological limitations.
        </p>
        <div class="panel help-reference">
          <p>
            Assaf, R., &amp; Fakhri, B. (2026). Transformer-based operon prediction using textual
            representations of gene pairs. <em>Bioinformatics Advances</em>, <em>6</em>(1), vbag140.
            <a href="https://doi.org/10.1093/bioadv/vbag140" target="_blank" rel="noopener noreferrer">https://doi.org/10.1093/bioadv/vbag140</a>
          </p>
        </div>
      </section>

      <section class="help-section" id="getting-started">
        ${helpHeading("Getting started")}
        <div class="help-steps">
          ${helpStep("1", "Start with an operon family", `
            Open <a href="#search">Search</a> and enter the biological entity you already know,
            such as a gene ID, product, PGFam, EC number, pathway, subsystem, genome, or taxon.
            Select a result to reach all matching operon families and occurrences.
          `)}
          ${helpStep("2", "Inspect a genome-specific occurrence", `
            Select an <code>OAO</code> identifier to view the predicted gene arrangement,
            coordinates, strands, products, PGFams, subsystem evidence, and pathway evidence
            for that occurrence.
          `)}
          ${helpStep("3", "Or begin with an organism", `
            Open <a href="#genomes?page=1">Genomes</a>, search by BV-BRC genome ID or organism
            name, and select a genome to browse its predicted operons in genomic context.
          `)}
        </div>
      </section>

      <section class="help-section" id="family-vs-occurrence">
        ${helpHeading("Operon family vs. operon occurrence")}
        <p>
          OperonAtlas separates a reusable family definition from each predicted instance found
          in a genome. This distinction is central to the site.
        </p>
        <div class="help-concept-grid">
          <div class="panel help-concept-card">
            <p class="help-eyebrow">Operon family</p>
            <h3><code>OAF000504</code></h3>
            <p>
              A group defined by a PGFam <strong>multiset</strong> signature. Gene order is ignored,
              but repeated copies of the same PGFam are preserved. Two predictions with the same
              PGFam membership and copy counts belong to the same family even if their displayed
              gene order differs.
            </p>
          </div>
          <div class="panel help-concept-card">
            <p class="help-eyebrow">Operon occurrence</p>
            <h3><code>OAO123456</code></h3>
            <p>
              One predicted instance of a family in a particular genome. An occurrence carries
              the genome, contig, gene coordinates, strand, products, and available functional
              evidence for that specific instance.
            </p>
          </div>
        </div>
        <dl class="help-definitions">
          <div>
            <dt>Stable Operon ID</dt>
            <dd>The displayed <code>OAF</code> identifier for an operon family.</dd>
          </div>
          <div>
            <dt>PGFam content</dt>
            <dd>The family-defining list of BV-BRC cross-genus protein-family IDs. Duplicate IDs are meaningful.</dd>
          </div>
          <div>
            <dt>Occurrence count</dt>
            <dd>The number of genome-specific predicted occurrences assigned to that family in the current dataset.</dd>
          </div>
          <div>
            <dt>Global occurrence count</dt>
            <dd>On a genome page, the total number of occurrences assigned to that family across the complete current dataset, not only within the selected genome.</dd>
          </div>
          <div>
            <dt>Gene count</dt>
            <dd>The number of genes in each occurrence belonging to the family.</dd>
          </div>
        </dl>
      </section>

      <section class="help-section" id="visualizations">
        ${helpHeading("Understanding operon visualizations")}
        <div class="help-two-column">
          <div>
            <h3>Operon view</h3>
            <p>
              Each arrow represents a gene. The arrow direction follows the gene strand, and its
              width reflects gene length relative to the displayed window. Labels identify BV-BRC
              protein-encoding genes. Colors distinguish neighboring items in the current view;
              they do not encode a functional category and should not be compared across views.
            </p>
          </div>
          <div>
            <h3>Genome view</h3>
            <p>
              Each colored block is a predicted occurrence positioned on a contig and scaled to
              its genomic coordinates. Hover or focus a block for its occurrence, family, contig,
              and coordinate range; select it to open the occurrence page.
            </p>
          </div>
        </div>
        <p>
          Use the arrow controls to move through genes, occurrences, or contigs. Use <strong>+</strong>
          and <strong>−</strong> to show fewer or more items, and the restart control to return to the
          beginning. On narrow screens, scroll the visualization horizontally.
        </p>
      </section>

      <section class="help-section" id="site-views">
        ${helpHeading("What each site view shows")}
        <div class="panel help-view-list">
          ${viewRow("Home", "Current dataset totals for genomes, operon families, occurrences, and occurrence-gene rows.", "#home")}
          ${viewRow("Search", "Grouped identifier, annotation, genome, and taxonomy matches with paginated paths to all matching families.", "#search")}
          ${viewRow("Operons", "A sortable, filterable list of operon families with PGFam content, gene count, occurrence count, and compact taxonomic breadth.", "#operons?page=1")}
          ${viewRow("Operon family detail", "One family’s composition, taxonomic breadth and distribution, annotation coverage, family-level functional evidence, and genome-specific occurrences.")}
          ${viewRow("Occurrence detail", "The genes and annotations for one predicted occurrence, including its operon diagram and gene table.")}
          ${viewRow("Genomes", "A searchable list of BV-BRC genomes with counts of predicted operons and operon-associated genes.", "#genomes?page=1")}
          ${viewRow("Genome detail", "A contig-based occurrence viewer and a sortable, filterable table of predicted operons in one genome.")}
          ${viewRow("Downloads", "The current versioned release files, row counts, compressed sizes, SHA-256 checksums, and data dictionary.", "#downloads")}
        </div>
      </section>

      <section class="help-section" id="search-filtering">
        ${helpHeading("Search and filtering")}
        <div class="help-table-wrap panel">
          <table class="help-table">
            <thead>
              <tr>
                <th>Where</th>
                <th>Available controls</th>
                <th>Examples</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><a href="#search">Global search</a></td>
                <td>Direct OAF, OAO, gene, feature, genome, PGFam, EC, pathway, subsystem, and taxon resolution; grouped annotation and taxonomy suggestions; paginated entity and family results.</td>
                <td><code>fig|100.11.peg.328</code>, <code>PGF_08225224</code>, <code>EC 1.1.1.1</code>, <code>DNA repair</code>, or <code>Bacillus</code></td>
              </tr>
              <tr>
                <td><a href="#operons?page=1">Operons</a></td>
                <td>Minimum and maximum gene count; genome ID or organism-name text; product text; sortable ID, gene count, and occurrence count.</td>
                <td><code>ATP synthase</code>, <code>transposase</code>, <code>100.11</code>, or <code>Ancylobacter aquaticus</code></td>
              </tr>
              <tr>
                <td>Family occurrences</td>
                <td>Product text within the genes of each occurrence.</td>
                <td><code>ribosomal protein</code></td>
              </tr>
              <tr>
                <td><a href="#genomes?page=1">Genomes</a></td>
                <td>Genome ID or organism-name text; sortable genome ID, organism, operon count, and gene count.</td>
                <td><code>100.11</code> or a species, strain, or partial organism name</td>
              </tr>
              <tr>
                <td>Genome operons</td>
                <td>Minimum and maximum gene count; product text; sortable family ID, gene count, and global occurrence count.</td>
                <td><code>ATP synthase</code></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="help-note">
          Search suggestions show five uncluttered previews per category; “View all” opens the full
          20-per-page entity list, and selecting an entity opens every matching family with pagination.
          Text controls use case-insensitive token/substring matching. Multiple active filters are combined, and applying
          or clearing filters returns the list to page 1. On the Operons and genome-detail views,
          the product filter selects families with at least one matching product annotation in the
          family data; on a family-detail page, it selects occurrences whose own genes match. Product
          filtering is not a free-text search across PGFam, subsystem, or pathway fields.
        </p>
      </section>

      <section class="help-section" id="annotations">
        ${helpHeading("Functional annotations")}
        <dl class="help-definitions">
          <div>
            <dt>Product</dt>
            <dd>The BV-BRC gene or protein product annotation shown for each gene.</dd>
          </div>
          <div>
            <dt>PGFam</dt>
            <dd>A BV-BRC PATRIC cross-genus protein-family assignment, displayed as <code>PGF_</code> followed by eight digits.</dd>
          </div>
          <div>
            <dt>Subsystem and role</dt>
            <dd>BV-BRC/SEED subsystem evidence, including available role names and superclass/class/subclass context.</dd>
          </div>
          <div>
            <dt>Pathway and EC</dt>
            <dd>Pathway names, identifiers, classes, and Enzyme Commission numbers when available. Pathway IDs link to KEGG; EC numbers link to ExPASy.</dd>
          </div>
          <div>
            <dt>Taxonomic breadth</dt>
            <dd>Distinct genomes and distinct BV-BRC taxon IDs represented by a family at species, genus, and phylum rank. Repeated occurrences in the same genome or taxon are counted once.</dd>
          </div>
        </dl>
        <p>
          Family-level summaries aggregate structured subsystem and pathway evidence across annotated
          occurrences. <strong>Occurrence support</strong> is the number and fraction of annotated
          occurrences supporting an item. <strong>Average annotated-gene share</strong> is the mean
          share of annotated genes supporting it. To keep the summary focused on evidence that is
          recurrent across the family, a subsystem or pathway must occur in at least 20% of annotated
          occurrences. It must also have either an average annotated-gene share of at least 5% or
          strong support in at least 20% of annotated occurrences. <strong>Strong support</strong>
          means that the item accounts for at least 25% of the annotated genes in an occurrence. The
          summary ranks qualifying items by annotated-gene share and occurrence support and shows at
          most the top three subsystems and top three pathways. These are display thresholds, not
          biological cutoffs: evidence may exist below them, and the absence of a displayed row does
          not mean that a function is biologically absent.
        </p>
      </section>

      <section class="help-section" id="downloads">
        ${helpHeading("Downloads: which file should I choose?")}
        <div class="panel help-download-list">
          ${downloadRow("operon_families.tsv.gz", "Compare families", "One row per operon family, including PGFam signature, prevalence, and annotation coverage.")}
          ${downloadRow("operon_occurrences.tsv.gz", "Locate instances in genomes", "One row per genome-specific occurrence, including family, genome, contig, span, strand, and gene count.")}
          ${downloadRow("operon_occurrence_genes.tsv.gz", "Analyze genes and annotations", "One row per gene in every occurrence, including order, coordinates, product, PGFam, subsystem, EC, and pathway fields. This is the largest file.")}
          ${downloadRow("data_dictionary.tsv", "Interpret exported columns", "Column names, data types, and definitions for all three datasets.")}
        </div>
        <p>
          Files are gzip-compressed tab-separated values. Use the release number and generated date
          on the <a href="#downloads">Downloads page</a> to record provenance, and verify a file
          against its SHA-256 checksum when transfer integrity matters.
        </p>
      </section>

      <section class="help-section" id="scope-limitations">
        ${helpHeading("Data scope and limitations")}
        <ul class="help-list">
          <li>The dataset is based on BV-BRC representative and reference bacterial genomes.</li>
          <li>Only same-contig predicted occurrences with at least two genes and complete PGFam annotation are included.</li>
          <li>Family membership uses PGFam composition and copy count, not gene order.</li>
          <li>Genome selection, gene prediction, product labels, PGFam assignments, and structured annotations inherit limitations and changes from their source data.</li>
          <li>Not every gene or occurrence has subsystem or pathway evidence.</li>
          <li>Counts and memberships describe the displayed release and may change when source genomes, annotations, or prediction methods are updated.</li>
        </ul>
      </section>

    </article>
  `;

  if (HELP_SECTIONS.has(sectionId)) {
    requestAnimationFrame(() => {
      const target = document.getElementById(sectionId);
      target?.scrollIntoView({ block: "start" });
    });
  } else {
    window.scrollTo({ top: 0 });
  }
}

function helpContentsLink(id, label) {
  return `<li><a href="#help/${id}">${label}</a></li>`;
}

function helpHeading(title) {
  return `<div class="section-header"><h2>${title}</h2></div>`;
}

function helpStep(number, title, body) {
  return `
    <div class="help-step">
      <span class="help-step-number" aria-hidden="true">${number}</span>
      <div>
        <h3>${title}</h3>
        <p>${body}</p>
      </div>
    </div>
  `;
}

function viewRow(title, description, href = "") {
  const titleHtml = href ? `<a href="${href}">${title}</a>` : title;
  return `<div class="help-view-row"><h3>${titleHtml}</h3><p>${description}</p></div>`;
}

function downloadRow(filename, purpose, description) {
  return `
    <div class="help-download-row">
      <code>${filename}</code>
      <div><strong>${purpose}</strong><p>${description}</p></div>
    </div>
  `;
}
