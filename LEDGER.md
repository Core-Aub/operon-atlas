# OperonAtlas Development Ledger

This ledger records the important scientific, methodological, data-processing, architectural, and product decisions made while developing OperonAtlas. It is intended as a human-readable record of **what we did, what alternatives we considered or tried, what happened, and why we ultimately made each decision**.

It is not a changelog. Routine code changes, styling adjustments, refactors, and minor bug fixes do not belong here unless they revealed something important about the data or methodology.

---


## Preserve contig identity when reconstructing operons

- Gene order is meaningful only within a contig.
- During development we encountered boundary records that appeared problematic when considered using genome-wide gene ordering alone, because adjacent-looking peg numbers could in fact belong to different contigs.
- The final operon-gene data therefore explicitly retains `contig_id` and genes are sorted and checked using genomic coordinates within their contig.
- Operons must not be reconstructed across contig boundaries simply because gene identifiers or global ordering happen to be consecutive.
- This was treated as a data-integrity issue rather than merely a visualization issue because joining genes across contigs would create biologically impossible operon occurrences.

---

## Use genomic coordinates rather than assuming peg numbers are genomic order

- BV-BRC peg identifiers are useful identifiers but they should not be treated as the authoritative representation of physical genomic order.
- The final operon gene tables therefore retain genomic start/end coordinates and strand information.
- Genes within occurrences are ordered from their actual genomic coordinates.
- The numeric peg component is still retained because it is useful for referencing BV-BRC features and compact storage, but genomic relationships are determined using the genomic information itself.

---

## Compute codon bias for prediction but do not store the full values in the production database

- Codon-bias information was generated at gene level using an RSCU-based approach because it was required by the prediction pipeline.
- Computing it across the complete genome collection produced an extremely large intermediate dataset, approximately **86 GB**.
- Keeping that complete dataset in the production database would have added substantial storage and processing complexity for information that is primarily useful as a model feature rather than as a core OperonAtlas browsing field.
- We therefore used the codon-bias values for inference but did not import the complete per-gene codon-bias dataset into the deployed atlas.
- The decision was driven by both practical storage constraints and product relevance: OperonAtlas is intended primarily for exploring predicted operons, their genes, their conservation, and their functional annotations, not for acting as a browser for every internal feature supplied to the prediction model.

---


## Use PGFams as the basis for cross-genome operon identity

- Individual BV-BRC gene IDs are genome-specific and therefore cannot be used to identify equivalent operons across different genomes.
- BV-BRC PGFams provide gene-family assignments that can be compared across genomes.
- We therefore defined an operon family using the **PGFam composition** of the genes in an operon occurrence.
- This lets occurrences from different genomes be grouped according to their conserved gene-family content rather than according to genome-specific gene identifiers or product strings.
- Product annotations were not used as the primary family identifier because textual product annotations are less standardized and can vary even for homologous genes.

---

## Define an operon-family signature from the complete PGFam set

- Operon families were defined from their PGFam composition.
- The matching is based on the complete PGFam signature of an occurrence rather than fuzzy similarity between product names.
- Duplicate copies of the same PGFam are meaningful and are therefore preserved in the family signature rather than collapsing the signature to a simple set.
- Gene order was not used as the primary family identifier, allowing equivalent PGFam compositions to belong to the same family even when their orientation/order representation differs in a way that does not change the family composition.
- This produces a simple and reproducible definition of family membership: two occurrences assigned to the same family have the same required PGFam composition.
- More permissive similarity can still be calculated separately when comparing related operons; it does not need to be built into the definition of family identity itself.

---

## Exclude operons with missing PGFam assignments from operon-family construction

- A complete PGFam signature cannot be created for an occurrence if one or more of its genes has no PGFam assignment.
- Because operon-family identity is based on exact PGFam composition, assigning such an occurrence to a family would require guessing what the missing family assignment should have been.
- We therefore excluded occurrences with incomplete PGFam annotation from the operon-family dataset rather than treating the missing value as a real family component.
- This removed a large number of otherwise predicted operon occurrences, so we explicitly investigated whether a more permissive rule could recover them.

---

## Relaxed PGFam set matching doesn't work

- To reduce the number of predicted occurrences lost because of missing PGFam annotations, we tested a relaxed matching rule.
- Under this approach, an occurrence containing a missing PGFam could be assigned to an existing operon family when all of its known PGFams matched a subset of that family's PGFam composition.
- Conceptually, this assumes that the unannotated gene may correspond to the missing member of an otherwise matching family.
- The approach worked technically, but recovered only a relatively small number of additional occurrences—on the order of tens of thousands to roughly a hundred thousand—compared with the **millions** of occurrences affected by incomplete PGFam annotation.
- It therefore did not solve the underlying coverage problem.
- More importantly, it made the definition of an operon family ambiguous. An incompletely annotated occurrence could potentially be compatible with multiple larger families, requiring additional arbitrary rules to decide which family it belongs to.
- The small gain in coverage was not worth weakening the otherwise clear family definition and adding substantial matching complexity.
- We therefore kept the stricter rule: **only occurrences with complete PGFam annotation participate in operon-family construction**.
- The excluded occurrences remain an annotation-coverage limitation of the atlas rather than being forced into uncertain families.

---

## Require at least two genes for an operon occurrence

- A one-gene region is not useful as a predicted operon for the purposes of OperonAtlas.
- The resource therefore retains predicted occurrences containing at least two genes.
- This also follows naturally from the pairwise prediction framework, since an operon begins from evidence that adjacent genes belong together.
- Single genes are still relevant genomic features but are outside the scope of the operon-family resource.

---

## Give operon families and individual occurrences separate identities

- A conserved operon family and a genome-specific occurrence of that family are different biological/database entities and needed separate identifiers.
- Operon families therefore receive their own stable atlas identifiers (`OAF...`), while individual genome-specific occurrences use separate occurrence identifiers (`OAO...`).
- This makes it possible to discuss one conserved family independently from the potentially many occurrences of that family across genomes.
- It also supports the UI structure: users can begin from a family and inspect its occurrences, or begin from a genome and see the occurrences found there.

---


## Include functional annotation aggregates at the operon level

- Individual genes can carry BV-BRC subsystem and pathway annotations.
- Showing only raw per-gene annotations would make it harder to understand the functional evidence associated with an entire operon.
- During preparation of downloadable and database-derived information we therefore generated aggregate representations of subsystem and pathway annotations associated with operon genes.
- These aggregates are supplementary evidence rather than the definition of the operon or operon family.
- Annotations can be incomplete, so their absence should not be interpreted as evidence that an operon has no biological function.

---


## Use integer/compact identifiers where possible in the production data

- Repeating long textual identifiers tens of millions of times wastes database space.
- Where possible, values such as genome identifiers and peg numbers were stored in compact numeric form while preserving enough information to reconstruct links or human-readable identifiers when needed.
- This was a deliberate production optimization made after the much larger processing datasets had already served their purpose.
- The principle was to preserve biological information while avoiding repeated textual overhead that provides no additional meaning.

---


## Keep the frontend lightweight rather than introduce a large framework

- The website was built using straightforward HTML, CSS, and JavaScript rather than introducing a heavyweight frontend framework solely because the dataset is large.
- Most of the complexity is in the data and API, not in client-side application state.
- Keeping the frontend lightweight made deployment through static hosting simple and reduced build/runtime dependencies.
- New interface work should follow the existing architecture unless the requirements genuinely outgrow it; introducing a framework for an isolated feature would create more complexity than it removes.

---

## Keep the Worker API separate from large file delivery

- The Worker is appropriate for small structured requests such as querying database records or returning download metadata.
- It is unnecessary and inefficient to proxy multi-gigabyte downloadable datasets through the Worker.
- Large files stored in R2 can instead be delivered directly from the bucket through its public/custom domain.
- The frontend can request metadata from the API where necessary while the actual download link points directly at the R2 object.
- This reduces Worker involvement and avoids making the API an unnecessary bottleneck for bulk downloads.

---

## Store bulk downloadable datasets in R2 rather than D1

- The downloadable release files can be large and are fundamentally objects rather than relational records that need interactive SQL queries.
- D1 is therefore not the appropriate storage layer for them.
- We created an R2 bucket for generated download files and uploaded the release artifacts there.
- D1 remains responsible for the structured data needed by the interactive site, while R2 is responsible for bulk distribution.
- This separation also makes it easier to regenerate downloadable releases without restructuring the interactive database.

---


## Add a Help page rather than expect users to infer terminology from the interface

- As the website became more complete, it was clear that terms such as operon family, occurrence, PGFam, predicted operon, and conservation evidence would not be self-explanatory to every user.
- The project README already contained useful information, but simply copying the README into the website would produce documentation organized around the software rather than around the user.
- We therefore chose to add a dedicated **Help** page organized around how to use OperonAtlas and how to interpret what is shown.
- The Help page should explain browsing, searching, family versus occurrence terminology, gene diagrams, annotations, downloads, and the fact that predictions are computational.
- Small contextual explanations/tooltips can still appear next to individual controls, while the Help page provides the complete explanation.

---

## 2026-08-23 — Search and taxonomic breadth candidate release 1.1.0

- Declared `database/data/` the immutable authoritative input for this release: 1,854,929 PGFam-multiset families, 5,067,861 same-contig multi-gene occurrences, and 15,335,420 completely PGFam-annotated genes. Candidate construction is additive and preserves every existing OAF/OAO ID and unchanged legacy row byte-for-byte in the assembled TSV set.
- Added BV-BRC taxonomy from frozen HTTP API responses for all 20,625 final genomes. Counts use rank-specific taxon IDs after deduplicating each `(operon_id, genome)` pair; organism names are never parsed to infer taxonomy. Two stale species lineage IDs were accepted only after the canonical taxonomy endpoint returned an exact matching name. Missing coverage is explicit (107 genomes without genus and 13 without phylum).
- Chose an ordinary 131,420-row search entity catalog plus compact reverse support tables instead of FTS5. Final full-candidate warm medians were sub-millisecond for catalog and exact PGFam/EC/role lookups, 12.31 ms for pathway expansion, 987.21 ms for broad hypothetical-product expansion, 181.64 ms for a broad live phylum expansion, 64.97 ms for the widest-family taxonomy breakdown, and 0.03 ms for exact gene lookup. FTS would not accelerate annotation-to-family expansion and would complicate D1 behavior.
- Added distinct genome/species/genus/phylum headline counts to every family. Complete phylum and paginated genus distributions remain live joins against `genome_taxonomy`; a large materialized family-by-taxon distribution was rejected to preserve storage and reduce UI/data clutter.
- The full candidate SQLite database is 3,617,091,584 bytes, below the 4.5 GB project gate. Deep validation passed stable-ID, invariant, legacy-table comparison, derived-count, and integrity checks. Four inherited empty-string nullable subsystem-class foreign keys remain in the immutable baseline; D1 export explicitly normalizes only those values to `NULL`.
- Wrangler 4.123.0 rejected a 2.256 GB local SQL input before import because it exceeded 2 GiB, and an annotation-heavy insert capped at 512 KB later produced `SQLITE_TOOBIG`. The final exporter therefore caps statements at 90,000 bytes and provides a 2,235,598,136-byte canonical SQL file plus 23 checksummed parts below 100 MB. By owner decision, full-size data/search validation runs against SQLite while D1 import/API/UI logic is proven with the canonical sample, avoiding a redundant hours-long full local Wrangler import.
- Generated and independently validated release 1.1.0 archives: 1,854,929 family rows, 5,067,861 occurrence rows, and 15,335,420 gene rows. Family downloads include taxonomy headline counts and unclassified coverage, not repeated delimited phylum/genus distributions.
- Kept the compare-region viewer postponed. Release 1.1.0 adds no comparison schema, API, or frontend placeholder.
