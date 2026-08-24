PRAGMA foreign_keys = OFF;
PRAGMA journal_mode = OFF;
PRAGMA synchronous = OFF;
PRAGMA temp_store = MEMORY;

DROP TABLE IF EXISTS search_entities;
DROP TABLE IF EXISTS operon_role_support;
DROP TABLE IF EXISTS operon_ec_support;
DROP TABLE IF EXISTS operon_pgfams;
DROP TABLE IF EXISTS operon_taxonomy_counts;
DROP TABLE IF EXISTS genome_taxonomy;

DROP TABLE IF EXISTS operon_products;
DROP TABLE IF EXISTS occurrence_genes;
DROP TABLE IF EXISTS occurrences;
DROP TABLE IF EXISTS operons;
DROP TABLE IF EXISTS genomes;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS contigs;
DROP TABLE IF EXISTS build_info;

DROP TABLE IF EXISTS gene_pathways;
DROP TABLE IF EXISTS ec_numbers;
DROP TABLE IF EXISTS pathway_reference;
DROP TABLE IF EXISTS pathway_classes;

DROP TABLE IF EXISTS gene_subsystems;
DROP TABLE IF EXISTS subsystem_roles;
DROP TABLE IF EXISTS subsystem_reference;
DROP TABLE IF EXISTS subsystem_classes;

DROP TABLE IF EXISTS operon_function_coverage;
DROP TABLE IF EXISTS operon_subsystem_support;
DROP TABLE IF EXISTS operon_subsystem_class_support;
DROP TABLE IF EXISTS operon_pathway_support;
DROP TABLE IF EXISTS operon_pathway_class_support;

CREATE TABLE operons (
    operon_id INTEGER PRIMARY KEY,
    pgfam_signature TEXT NOT NULL UNIQUE,
    gene_count INTEGER NOT NULL,
    occurrence_count INTEGER NOT NULL
);

CREATE TABLE occurrences (
    occurrence_id INTEGER PRIMARY KEY,
    operon_id INTEGER NOT NULL,
    genome_key INTEGER NOT NULL,
    gene_count INTEGER NOT NULL,
    FOREIGN KEY (operon_id) REFERENCES operons(operon_id),
    FOREIGN KEY (genome_key) REFERENCES genomes(genome_key)
);

CREATE TABLE occurrence_genes (
    occurrence_id INTEGER NOT NULL,
    genome_key INTEGER NOT NULL,
    peg_num INTEGER NOT NULL,
    contig_id INTEGER NOT NULL,
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    strand INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    pgfam_num INTEGER NOT NULL,
    PRIMARY KEY (occurrence_id, peg_num),
    FOREIGN KEY (occurrence_id) REFERENCES occurrences(occurrence_id),
    FOREIGN KEY (genome_key) REFERENCES genomes(genome_key),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (contig_id) REFERENCES contigs(contig_id)
);

CREATE TABLE operon_products (
    operon_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    PRIMARY KEY (operon_id, product_id),
    FOREIGN KEY (operon_id) REFERENCES operons(operon_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE genomes (
    genome_key INTEGER PRIMARY KEY,
    genome_id TEXT NOT NULL UNIQUE,
    organism_name TEXT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product TEXT
);

CREATE TABLE contigs (
    contig_id INTEGER PRIMARY KEY,
    genome_id TEXT NOT NULL,
    contig_name TEXT NOT NULL
);

-- ============================================================
-- Functional annotation tables: EC / pathways
-- ============================================================

CREATE TABLE ec_numbers (
    ec_key INTEGER PRIMARY KEY,
    ec_number TEXT NOT NULL,
    ec_description TEXT
);

CREATE TABLE pathway_classes (
    pathway_class_key INTEGER PRIMARY KEY,
    pathway_class TEXT
);

CREATE TABLE pathway_reference (
    pathway_key INTEGER PRIMARY KEY,
    pathway_id TEXT NOT NULL,
    pathway_name TEXT,
    pathway_class_key INTEGER,
    FOREIGN KEY (pathway_class_key) REFERENCES pathway_classes(pathway_class_key)
);

CREATE TABLE gene_pathways (
    genome_key INTEGER NOT NULL,
    contig_id INTEGER NOT NULL,
    gene_start INTEGER NOT NULL,
    gene_end INTEGER NOT NULL,
    strand INTEGER NOT NULL,
    ec_key INTEGER NOT NULL,
    pathway_key INTEGER NOT NULL,

    PRIMARY KEY (
        genome_key,
        contig_id,
        gene_start,
        gene_end,
        strand,
        ec_key,
        pathway_key
    ),

    FOREIGN KEY (genome_key) REFERENCES genomes(genome_key),
    FOREIGN KEY (contig_id) REFERENCES contigs(contig_id),
    FOREIGN KEY (ec_key) REFERENCES ec_numbers(ec_key),
    FOREIGN KEY (pathway_key) REFERENCES pathway_reference(pathway_key)
);


-- ============================================================
-- Functional annotation tables: BV-BRC / SEED subsystems
-- ============================================================

CREATE TABLE subsystem_roles (
    role_key INTEGER PRIMARY KEY,
    role_id TEXT NOT NULL,
    role_name TEXT
);

CREATE TABLE subsystem_classes (
    subsystem_class_key INTEGER PRIMARY KEY,
    subsystem_superclass TEXT,
    subsystem_class TEXT,
    subsystem_subclass TEXT
);

CREATE TABLE subsystem_reference (
    subsystem_key INTEGER PRIMARY KEY,
    subsystem_id TEXT NOT NULL,
    subsystem_name TEXT,
    subsystem_class_key INTEGER,
    FOREIGN KEY (subsystem_class_key) REFERENCES subsystem_classes(subsystem_class_key)
);

CREATE TABLE gene_subsystems (
    genome_key INTEGER NOT NULL,
    contig_id INTEGER NOT NULL,
    gene_start INTEGER NOT NULL,
    gene_end INTEGER NOT NULL,
    strand INTEGER NOT NULL,
    role_key INTEGER NOT NULL,
    subsystem_key INTEGER NOT NULL,

    PRIMARY KEY (
        genome_key,
        contig_id,
        gene_start,
        gene_end,
        strand,
        role_key,
        subsystem_key
    ),

    FOREIGN KEY (genome_key) REFERENCES genomes(genome_key),
    FOREIGN KEY (contig_id) REFERENCES contigs(contig_id),
    FOREIGN KEY (role_key) REFERENCES subsystem_roles(role_key),
    FOREIGN KEY (subsystem_key) REFERENCES subsystem_reference(subsystem_key)
);

DROP TABLE IF EXISTS operon_function_coverage;
DROP TABLE IF EXISTS operon_subsystem_support;
DROP TABLE IF EXISTS operon_subsystem_class_support;
DROP TABLE IF EXISTS operon_pathway_support;
DROP TABLE IF EXISTS operon_pathway_class_support;


CREATE TABLE operon_function_coverage (
    operon_id INTEGER PRIMARY KEY,

    occurrence_count INTEGER NOT NULL,
    annotated_occurrence_count INTEGER NOT NULL,
    annotated_occurrence_fraction REAL NOT NULL,

    gene_count INTEGER NOT NULL,

    avg_annotated_gene_count REAL NOT NULL,
    avg_annotated_gene_fraction REAL NOT NULL,
    avg_annotated_gene_fraction_among_annotated_occurrences REAL,

    FOREIGN KEY (operon_id) REFERENCES operons(operon_id)
);


CREATE TABLE operon_subsystem_support (
    operon_id INTEGER NOT NULL,
    subsystem_key INTEGER NOT NULL,

    annotated_occurrence_count INTEGER NOT NULL,

    supporting_occurrence_count INTEGER NOT NULL,
    supporting_occurrence_fraction REAL NOT NULL,

    strong_supporting_occurrence_count INTEGER NOT NULL,
    strong_supporting_occurrence_fraction REAL NOT NULL,

    avg_annotated_gene_share REAL NOT NULL,
    max_annotated_gene_share REAL NOT NULL,

    PRIMARY KEY (operon_id, subsystem_key),

    FOREIGN KEY (operon_id) REFERENCES operons(operon_id),
    FOREIGN KEY (subsystem_key) REFERENCES subsystem_reference(subsystem_key)
);


CREATE TABLE operon_subsystem_class_support (
    operon_id INTEGER NOT NULL,
    subsystem_class_key INTEGER NOT NULL,

    annotated_occurrence_count INTEGER NOT NULL,

    supporting_occurrence_count INTEGER NOT NULL,
    supporting_occurrence_fraction REAL NOT NULL,

    strong_supporting_occurrence_count INTEGER NOT NULL,
    strong_supporting_occurrence_fraction REAL NOT NULL,

    avg_annotated_gene_share REAL NOT NULL,
    max_annotated_gene_share REAL NOT NULL,

    PRIMARY KEY (operon_id, subsystem_class_key),

    FOREIGN KEY (operon_id) REFERENCES operons(operon_id),
    FOREIGN KEY (subsystem_class_key) REFERENCES subsystem_classes(subsystem_class_key)
);


CREATE TABLE operon_pathway_support (
    operon_id INTEGER NOT NULL,
    pathway_key INTEGER NOT NULL,

    annotated_occurrence_count INTEGER NOT NULL,

    supporting_occurrence_count INTEGER NOT NULL,
    supporting_occurrence_fraction REAL NOT NULL,

    strong_supporting_occurrence_count INTEGER NOT NULL,
    strong_supporting_occurrence_fraction REAL NOT NULL,

    avg_annotated_gene_share REAL NOT NULL,
    max_annotated_gene_share REAL NOT NULL,

    PRIMARY KEY (operon_id, pathway_key),

    FOREIGN KEY (operon_id) REFERENCES operons(operon_id),
    FOREIGN KEY (pathway_key) REFERENCES pathway_reference(pathway_key)
);


CREATE TABLE operon_pathway_class_support (
    operon_id INTEGER NOT NULL,
    pathway_class_key INTEGER NOT NULL,

    annotated_occurrence_count INTEGER NOT NULL,

    supporting_occurrence_count INTEGER NOT NULL,
    supporting_occurrence_fraction REAL NOT NULL,

    strong_supporting_occurrence_count INTEGER NOT NULL,
    strong_supporting_occurrence_fraction REAL NOT NULL,

    avg_annotated_gene_share REAL NOT NULL,
    max_annotated_gene_share REAL NOT NULL,

    PRIMARY KEY (operon_id, pathway_class_key),

    FOREIGN KEY (operon_id) REFERENCES operons(operon_id),
    FOREIGN KEY (pathway_class_key) REFERENCES pathway_classes(pathway_class_key)
);

CREATE TABLE build_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ============================================================
-- Taxonomy and search support
-- ============================================================

CREATE TABLE genome_taxonomy (
    genome_key INTEGER PRIMARY KEY,
    genome_id TEXT NOT NULL UNIQUE,
    taxon_id INTEGER NOT NULL CHECK (taxon_id > 0),
    phylum_taxon_id INTEGER,
    phylum_name TEXT,
    genus_taxon_id INTEGER,
    genus_name TEXT,
    species_taxon_id INTEGER,
    species_name TEXT,
    source_date_modified TEXT,
    CHECK ((phylum_taxon_id IS NULL) = (phylum_name IS NULL)),
    CHECK ((genus_taxon_id IS NULL) = (genus_name IS NULL)),
    CHECK ((species_taxon_id IS NULL) = (species_name IS NULL)),
    FOREIGN KEY (genome_key) REFERENCES genomes(genome_key)
) WITHOUT ROWID;

CREATE TABLE operon_taxonomy_counts (
    operon_id INTEGER PRIMARY KEY,
    genome_count INTEGER NOT NULL CHECK (genome_count > 0),
    species_count INTEGER NOT NULL CHECK (species_count >= 0),
    genus_count INTEGER NOT NULL CHECK (genus_count >= 0),
    phylum_count INTEGER NOT NULL CHECK (phylum_count >= 0),
    species_unclassified_genome_count INTEGER NOT NULL CHECK (species_unclassified_genome_count >= 0),
    genus_unclassified_genome_count INTEGER NOT NULL CHECK (genus_unclassified_genome_count >= 0),
    phylum_unclassified_genome_count INTEGER NOT NULL CHECK (phylum_unclassified_genome_count >= 0),
    CHECK (species_count <= genome_count),
    CHECK (genus_count <= genome_count),
    CHECK (phylum_count <= genome_count),
    CHECK (species_unclassified_genome_count <= genome_count),
    CHECK (genus_unclassified_genome_count <= genome_count),
    CHECK (phylum_unclassified_genome_count <= genome_count),
    FOREIGN KEY (operon_id) REFERENCES operons(operon_id)
) WITHOUT ROWID;

CREATE TABLE operon_pgfams (
    pgfam_num INTEGER NOT NULL CHECK (pgfam_num >= 0),
    operon_id INTEGER NOT NULL,
    copy_count INTEGER NOT NULL CHECK (copy_count > 0),
    PRIMARY KEY (pgfam_num, operon_id),
    FOREIGN KEY (operon_id) REFERENCES operons(operon_id)
) WITHOUT ROWID;

CREATE TABLE operon_ec_support (
    ec_key INTEGER NOT NULL,
    operon_id INTEGER NOT NULL,
    supporting_occurrence_count INTEGER NOT NULL CHECK (supporting_occurrence_count > 0),
    supporting_gene_count INTEGER NOT NULL CHECK (supporting_gene_count > 0),
    CHECK (supporting_occurrence_count <= supporting_gene_count),
    PRIMARY KEY (ec_key, operon_id),
    FOREIGN KEY (ec_key) REFERENCES ec_numbers(ec_key),
    FOREIGN KEY (operon_id) REFERENCES operons(operon_id)
) WITHOUT ROWID;

CREATE TABLE operon_role_support (
    role_key INTEGER NOT NULL,
    operon_id INTEGER NOT NULL,
    supporting_occurrence_count INTEGER NOT NULL CHECK (supporting_occurrence_count > 0),
    supporting_gene_count INTEGER NOT NULL CHECK (supporting_gene_count > 0),
    CHECK (supporting_occurrence_count <= supporting_gene_count),
    PRIMARY KEY (role_key, operon_id),
    FOREIGN KEY (role_key) REFERENCES subsystem_roles(role_key),
    FOREIGN KEY (operon_id) REFERENCES operons(operon_id)
) WITHOUT ROWID;

CREATE TABLE search_entities (
    entity_type TEXT NOT NULL CHECK (
        entity_type IN (
            'product', 'ec', 'pathway', 'pathway_class', 'subsystem',
            'subsystem_class', 'role', 'genome', 'species', 'genus', 'phylum'
        )
    ),
    entity_key INTEGER NOT NULL,
    identifier TEXT NOT NULL CHECK (length(identifier) > 0),
    label TEXT NOT NULL CHECK (length(label) > 0),
    context TEXT,
    search_text TEXT NOT NULL CHECK (length(search_text) > 0),
    PRIMARY KEY (entity_type, entity_key)
) WITHOUT ROWID;

.mode tabs

.import --skip 1 sample_data/genomes.tsv genomes
.import --skip 1 sample_data/products.tsv products
.import --skip 1 sample_data/contigs.tsv contigs

.import --skip 1 sample_data/operons.tsv operons
.import --skip 1 sample_data/occurrences.tsv occurrences
.import --skip 1 sample_data/occurrence_genes.tsv occurrence_genes
.import --skip 1 sample_data/operon_products.tsv operon_products

.import --skip 1 sample_data/ec_numbers.tsv ec_numbers
.import --skip 1 sample_data/pathway_classes.tsv pathway_classes
.import --skip 1 sample_data/pathway_reference.tsv pathway_reference
.import --skip 1 sample_data/gene_pathways.tsv gene_pathways

.import --skip 1 sample_data/subsystem_roles.tsv subsystem_roles
.import --skip 1 sample_data/subsystem_classes.tsv subsystem_classes
.import --skip 1 sample_data/subsystem_reference.tsv subsystem_reference
.import --skip 1 sample_data/gene_subsystems.tsv gene_subsystems

-- Four legacy full-data rows use an empty value for this nullable foreign key.
-- Apply the same normalization in both schemas so they remain equivalent.
UPDATE subsystem_reference
SET subsystem_class_key = NULL
WHERE subsystem_class_key = '';

.import --skip 1 sample_data/operon_function_coverage.tsv operon_function_coverage
.import --skip 1 sample_data/operon_subsystem_support.tsv operon_subsystem_support
.import --skip 1 sample_data/operon_subsystem_class_support.tsv operon_subsystem_class_support
.import --skip 1 sample_data/operon_pathway_support.tsv operon_pathway_support
.import --skip 1 sample_data/operon_pathway_class_support.tsv operon_pathway_class_support

.import --skip 1 sample_data/genome_taxonomy.tsv genome_taxonomy
.import --skip 1 sample_data/operon_taxonomy_counts.tsv operon_taxonomy_counts
.import --skip 1 sample_data/operon_pgfams.tsv operon_pgfams
.import --skip 1 sample_data/operon_ec_support.tsv operon_ec_support
.import --skip 1 sample_data/operon_role_support.tsv operon_role_support
.import --skip 1 sample_data/search_entities.tsv search_entities

CREATE INDEX idx_operons_occurrence_count
ON operons(occurrence_count DESC);

CREATE INDEX idx_operons_gene_count
ON operons(gene_count);

CREATE INDEX idx_occurrences_operon
ON occurrences(operon_id);

CREATE INDEX idx_occurrences_genome_operon
ON occurrences(genome_key, operon_id);

CREATE INDEX idx_occurrence_genes_genome_contig_start
ON occurrence_genes(genome_key, contig_id, start);

CREATE INDEX idx_operon_products_product
ON operon_products(product_id);

CREATE INDEX idx_products_product
ON products(product);

CREATE INDEX idx_contigs_genome
ON contigs(genome_id);

-- Fast lookup of EC/pathway annotations by gene coordinate.
CREATE INDEX idx_gene_pathways_gene
ON gene_pathways (
    genome_key,
    contig_id,
    gene_start,
    gene_end,
    strand
);

-- Fast lookup of subsystem annotations by gene coordinate.
CREATE INDEX idx_gene_subsystems_gene
ON gene_subsystems (
    genome_key,
    contig_id,
    gene_start,
    gene_end,
    strand
);

CREATE INDEX idx_genome_taxonomy_phylum
ON genome_taxonomy(phylum_taxon_id, genome_key);

CREATE INDEX idx_genome_taxonomy_genus
ON genome_taxonomy(genus_taxon_id, genome_key);

CREATE INDEX idx_genome_taxonomy_species
ON genome_taxonomy(species_taxon_id, genome_key);

CREATE INDEX idx_search_entities_identifier
ON search_entities(identifier COLLATE NOCASE, entity_type, entity_key);

CREATE INDEX idx_search_entities_text
ON search_entities(search_text COLLATE NOCASE, entity_type, entity_key);

CREATE INDEX idx_operon_pathway_support_pathway
ON operon_pathway_support(pathway_key, operon_id);

CREATE INDEX idx_operon_pathway_class_support_class
ON operon_pathway_class_support(pathway_class_key, operon_id);

CREATE INDEX idx_operon_subsystem_support_subsystem
ON operon_subsystem_support(subsystem_key, operon_id);

CREATE INDEX idx_operon_subsystem_class_support_class
ON operon_subsystem_class_support(subsystem_class_key, operon_id);

INSERT INTO build_info (key, value) VALUES
('schema_version', 'operonatlas_v4'),
('operon_definition', 'Stable operons are PGFam multiset signatures: gene order ignored, duplicate PGFam copies preserved.'),
('occurrence_definition', 'A genome-specific predicted operon instance. occurrence_id was previously Universal_Operon_ID.'),
('included_occurrences', 'gene_count >= 2, complete PGFam annotation.'),
('source_files', 'All TSV files imported by database/build_sample_db.sql from database/sample_data/.'),
('functional_annotations', 'Gene-level EC/pathway and BV-BRC subsystem annotations are stored in normalized functional tables and joined to occurrence genes by genome_key, contig_id, start/end coordinates, and strand.'),
('search_taxonomy', 'Genome taxonomy, family breadth, PGFam/EC/role reverse support, and the search entity catalog are canonical schema tables imported from database/sample_data/.');
-- ============================================================
-- Sanity checks
-- ============================================================

SELECT 'operons', COUNT(*) FROM operons;
SELECT 'occurrences', COUNT(*) FROM occurrences;
SELECT 'occurrence_genes', COUNT(*) FROM occurrence_genes;
SELECT 'operon_products', COUNT(*) FROM operon_products;
SELECT 'genomes', COUNT(*) FROM genomes;
SELECT 'products', COUNT(*) FROM products;
SELECT 'contigs', COUNT(*) FROM contigs;

SELECT 'gene_pathways', COUNT(*) FROM gene_pathways;
SELECT 'ec_numbers', COUNT(*) FROM ec_numbers;
SELECT 'pathway_reference', COUNT(*) FROM pathway_reference;
SELECT 'pathway_classes', COUNT(*) FROM pathway_classes;

SELECT 'gene_subsystems', COUNT(*) FROM gene_subsystems;
SELECT 'subsystem_roles', COUNT(*) FROM subsystem_roles;
SELECT 'subsystem_reference', COUNT(*) FROM subsystem_reference;
SELECT 'subsystem_classes', COUNT(*) FROM subsystem_classes;

SELECT
    'genes_with_pathway_annotations',
    COUNT(DISTINCT genome_key || ':' || contig_id || ':' || gene_start || ':' || gene_end || ':' || strand)
FROM gene_pathways;

SELECT
    'genes_with_subsystem_annotations',
    COUNT(DISTINCT genome_key || ':' || contig_id || ':' || gene_start || ':' || gene_end || ':' || strand)
FROM gene_subsystems;

SELECT 'operon_function_coverage' AS table_name, COUNT(*) FROM operon_function_coverage
UNION ALL
SELECT 'operon_subsystem_support', COUNT(*) FROM operon_subsystem_support
UNION ALL
SELECT 'operon_subsystem_class_support', COUNT(*) FROM operon_subsystem_class_support
UNION ALL
SELECT 'operon_pathway_support', COUNT(*) FROM operon_pathway_support
UNION ALL
SELECT 'operon_pathway_class_support', COUNT(*) FROM operon_pathway_class_support;

SELECT 'genome_taxonomy', COUNT(*) FROM genome_taxonomy
UNION ALL
SELECT 'operon_taxonomy_counts', COUNT(*) FROM operon_taxonomy_counts
UNION ALL
SELECT 'operon_pgfams', COUNT(*) FROM operon_pgfams
UNION ALL
SELECT 'operon_ec_support', COUNT(*) FROM operon_ec_support
UNION ALL
SELECT 'operon_role_support', COUNT(*) FROM operon_role_support
UNION ALL
SELECT 'search_entities', COUNT(*) FROM search_entities;

PRAGMA foreign_keys = ON;
ANALYZE;
