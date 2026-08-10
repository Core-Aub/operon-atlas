# OperonAtlas

OperonAtlas is an open web resource for exploring predicted bacterial operons across BV-BRC representative and reference genomes.

It brings operon families, their genome-specific occurrences, gene organization, and functional annotations into one searchable interface. OperonAtlas is designed for researchers who want to move from a conserved operon family to the genomes and genes in which it occurs without assembling those relationships manually.

**Explore OperonAtlas at [operonatlas.org](https://operonatlas.org/).**

> Operons in OperonAtlas are computational predictions and should not be interpreted as experimentally validated operons.

## What you can explore

- Browse predicted operon families and filter them by size, organism, genome, or gene product.
- Inspect every genome-specific occurrence of an operon family.
- View gene order, strand, genomic coordinates, PGFam assignments, and product annotations.
- Explore pathway and BV-BRC subsystem evidence associated with operon genes.
- Browse genomes and visualize predicted operons in genomic context.
- Download versioned operon-family, occurrence, and gene-level datasets.

## Operon model

OperonAtlas distinguishes between two related concepts:

- **Operon family** — a stable group defined by its PGFam multiset signature. Gene order is ignored, while duplicate PGFam copies are preserved. Family identifiers use the form `OAF000504`.
- **Operon occurrence** — one predicted instance of an operon family in a particular genome. Occurrence identifiers use the form `OAO123456`.

Only predicted occurrences with at least two genes and complete PGFam annotation are included in the current dataset.

## Data

The predictions are based on BV-BRC representative and reference bacterial genomes. Downloadable releases provide:

- one row per operon family;
- one row per genome-specific operon occurrence;
- one row per gene in each occurrence; and
- a data dictionary describing the exported columns.

Release files include checksums to support integrity verification.

## Project status

OperonAtlas is publicly available at [operonatlas.org](https://operonatlas.org/) and remains under active development.

## Developer documentation

For local setup, architecture, API behavior, database preparation, testing, deployment, and contribution guidance, see [docs.md](docs.md).

## Reference

to be added when published

## Contact

OperonAtlas is developed by [CORE at the American University of Beirut](https://core-aub.github.io/).
