#!/usr/bin/env python3
"""Build a local OperonAtlas download release from a canonical SQLite DB.

The generator writes a staging directory and only replaces the requested
generated output after all datasets, dictionary, manifest, and checksums have
been completed.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


PROTECTED_RELEASES = {"1.0.0"}
MULTI_VALUE_SEPARATOR = "; "
SAFE_RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


FAMILY_COLUMNS = [
    ("operon_id", "integer", "Stable identifier for the operon family."),
    ("gene_count", "integer", "Genes in each occurrence belonging to the family."),
    ("occurrence_count", "integer", "Predicted occurrences assigned to the family."),
    ("genome_count", "integer", "Distinct genomes containing the family."),
    ("species_count", "integer", "Distinct classified species containing the family."),
    ("genus_count", "integer", "Distinct classified genera containing the family."),
    ("phylum_count", "integer", "Distinct classified phyla containing the family."),
    ("species_unclassified_genome_count", "integer", "Family genomes without a species assignment."),
    ("genus_unclassified_genome_count", "integer", "Family genomes without a genus assignment."),
    ("phylum_unclassified_genome_count", "integer", "Family genomes without a phylum assignment."),
    ("pgfam_signature", "text", "Sorted PGFam multiset defining the family; duplicate copies are preserved."),
    ("annotated_occurrence_count", "integer", "Occurrences containing structured functional annotation."),
    ("annotated_occurrence_fraction", "real", "Fraction of occurrences containing structured functional annotation."),
    ("average_annotated_gene_count", "real", "Average annotated genes per occurrence."),
    ("average_annotated_gene_fraction", "real", "Average annotated gene fraction per occurrence."),
]
OCCURRENCE_COLUMNS = [
    ("occurrence_id", "integer", "Genome-specific predicted operon occurrence identifier."),
    ("operon_id", "integer", "Stable operon family identifier."),
    ("genome_id", "text", "BV-BRC genome identifier."),
    ("organism_name", "text", "Organism and strain name."),
    ("contig", "text", "Contig containing the occurrence."),
    ("operon_start", "integer", "Smallest gene coordinate in the occurrence."),
    ("operon_end", "integer", "Largest gene coordinate in the occurrence."),
    ("strand", "text", "Occurrence orientation: +, -, or mixed."),
    ("gene_count", "integer", "Genes in the occurrence."),
]
GENE_COLUMNS = [
    ("occurrence_id", "integer", "Genome-specific predicted occurrence identifier."),
    ("operon_id", "integer", "Stable operon family identifier."),
    ("genome_id", "text", "BV-BRC genome identifier."),
    ("organism_name", "text", "Organism and strain name."),
    ("contig", "text", "Contig containing the gene."),
    ("peg_number", "integer", "BV-BRC protein-encoding gene number."),
    ("gene_order_in_operon", "integer", "One-based transcriptional order within the occurrence."),
    ("start", "integer", "Gene start coordinate."),
    ("end", "integer", "Gene end coordinate."),
    ("length", "integer", "Gene length in nucleotides."),
    ("strand", "text", "Gene orientation: + or -."),
    ("product", "text", "Predicted gene or protein product."),
    ("pgfam", "text", "Canonical BV-BRC PGFam identifier."),
    ("roles", "text", "Semicolon-separated subsystem roles."),
    ("subsystems", "text", "Semicolon-separated subsystem names."),
    ("subsystem_classes", "text", "Semicolon-separated subsystem classification paths."),
    ("ec_numbers", "text", "Semicolon-separated Enzyme Commission numbers."),
    ("pathway_ids", "text", "Semicolon-separated pathway identifiers."),
    ("pathway_names", "text", "Semicolon-separated pathway names."),
    ("pathway_classes", "text", "Semicolon-separated pathway classes."),
]
DATA_DICTIONARY = {
    "operon_families.tsv.gz": FAMILY_COLUMNS,
    "operon_occurrences.tsv.gz": OCCURRENCE_COLUMNS,
    "operon_occurrence_genes.tsv.gz": GENE_COLUMNS,
}


@dataclass
class ExportMetadata:
    dataset: str
    filename: str
    description: str
    format: str
    release: str
    generated_at: str
    rows: int
    compressed_bytes: int
    sha256: str


def resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_tables(connection: sqlite3.Connection, names: Iterable[str]) -> None:
    existing = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'"
        )
    }
    missing = sorted(set(names) - existing)
    if missing:
        raise RuntimeError(
            "Database is missing release tables:\n"
            + "\n".join(f"  - {name}" for name in missing)
        )


def export_query(
    connection: sqlite3.Connection,
    query: str,
    output_path: Path,
    *,
    fetch_size: int = 10_000,
) -> int:
    cursor = connection.execute(query)
    if cursor.description is None:
        raise RuntimeError("Release export query returned no columns.")
    header = [column[0] for column in cursor.description]
    rows_written = 0
    with output_path.open("xb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=6,
            fileobj=raw,
            mtime=0,
        ) as compressed:
            with io.TextIOWrapper(
                compressed, encoding="utf-8", newline="", write_through=True
            ) as text:
                writer = csv.writer(
                    text,
                    delimiter="\t",
                    quoting=csv.QUOTE_MINIMAL,
                    lineterminator="\n",
                )
                writer.writerow(header)
                while batch := cursor.fetchmany(fetch_size):
                    writer.writerows(batch)
                    rows_written += len(batch)
                    if rows_written % 1_000_000 < len(batch):
                        print(f"    {rows_written:,} rows", flush=True)
    return rows_written


def build_annotation_aggregates(connection: sqlite3.Connection) -> None:
    connection.executescript(
        f"""
        CREATE TEMP TABLE download_gene_subsystems AS
        WITH annotations AS (
            SELECT DISTINCT
                gs.gene_key,
                role.role_name,
                subsystem.subsystem_name,
                TRIM(
                    COALESCE(class.subsystem_superclass, '') ||
                    CASE WHEN COALESCE(class.subsystem_superclass, '') != '' AND COALESCE(class.subsystem_class, '') != '' THEN ' > ' ELSE '' END ||
                    COALESCE(class.subsystem_class, '') ||
                    CASE WHEN (COALESCE(class.subsystem_superclass, '') != '' OR COALESCE(class.subsystem_class, '') != '') AND COALESCE(class.subsystem_subclass, '') != '' THEN ' > ' ELSE '' END ||
                    COALESCE(class.subsystem_subclass, '')
                ) AS class_path
            FROM gene_subsystems AS gs
            LEFT JOIN subsystem_roles AS role USING (role_key)
            LEFT JOIN subsystem_reference AS subsystem USING (subsystem_key)
            LEFT JOIN subsystem_classes AS class USING (subsystem_class_key)
        ), keys AS (
            SELECT DISTINCT gene_key FROM annotations
        )
        SELECT
            keys.*,
            COALESCE((SELECT GROUP_CONCAT(role_name, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT role_name FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(role_name,'')!='' ORDER BY role_name)), '') AS roles,
            COALESCE((SELECT GROUP_CONCAT(subsystem_name, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT subsystem_name FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(subsystem_name,'')!='' ORDER BY subsystem_name)), '') AS subsystems,
            COALESCE((SELECT GROUP_CONCAT(class_path, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT class_path FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(class_path,'')!='' ORDER BY class_path)), '') AS subsystem_classes
        FROM keys;

        CREATE INDEX temp.idx_download_gene_subsystems
        ON download_gene_subsystems(gene_key);

        CREATE TEMP TABLE download_gene_pathways AS
        WITH annotations AS (
            SELECT DISTINCT
                gp.gene_key,
                ec.ec_number, pathway.pathway_id, pathway.pathway_name, class.pathway_class
            FROM gene_pathways AS gp
            LEFT JOIN ec_numbers AS ec USING (ec_key)
            LEFT JOIN pathway_reference AS pathway USING (pathway_key)
            LEFT JOIN main.pathway_classes AS class USING (pathway_class_key)
        ), keys AS (
            SELECT DISTINCT gene_key FROM annotations
        )
        SELECT
            keys.*,
            COALESCE((SELECT GROUP_CONCAT(ec_number, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT ec_number FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(ec_number,'')!='' ORDER BY ec_number)), '') AS ec_numbers,
            COALESCE((SELECT GROUP_CONCAT(pathway_id, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT pathway_id FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(pathway_id,'')!='' ORDER BY pathway_id)), '') AS pathway_ids,
            COALESCE((SELECT GROUP_CONCAT(pathway_name, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT pathway_name FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(pathway_name,'')!='' ORDER BY pathway_name)), '') AS pathway_names,
            COALESCE((SELECT GROUP_CONCAT(pathway_class, '{MULTI_VALUE_SEPARATOR}') FROM (SELECT DISTINCT pathway_class FROM annotations AS a WHERE a.gene_key=keys.gene_key AND COALESCE(pathway_class,'')!='' ORDER BY pathway_class)), '') AS pathway_classes
        FROM keys;

        CREATE INDEX temp.idx_download_gene_pathways
        ON download_gene_pathways(gene_key);
        """
    )


FAMILY_QUERY = """
SELECT
    operon.operon_id,
    operon.gene_count,
    operon.occurrence_count,
    taxonomy.genome_count,
    taxonomy.species_count,
    taxonomy.genus_count,
    taxonomy.phylum_count,
    taxonomy.species_unclassified_genome_count,
    taxonomy.genus_unclassified_genome_count,
    taxonomy.phylum_unclassified_genome_count,
    operon.pgfam_signature,
    COALESCE(coverage.annotated_occurrence_count, 0) AS annotated_occurrence_count,
    COALESCE(coverage.annotated_occurrence_fraction, 0) AS annotated_occurrence_fraction,
    COALESCE(coverage.avg_annotated_gene_count, 0) AS average_annotated_gene_count,
    COALESCE(coverage.avg_annotated_gene_fraction, 0) AS average_annotated_gene_fraction
FROM operons AS operon
JOIN operon_taxonomy_counts AS taxonomy USING (operon_id)
LEFT JOIN operon_function_coverage AS coverage USING (operon_id)
ORDER BY operon.operon_id
"""

OCCURRENCE_QUERY = """
SELECT
    occurrence.occurrence_id,
    occurrence.operon_id,
    genome.genome_id,
    genome.organism_name,
    contig.contig_name AS contig,
    MIN(gene.start) AS operon_start,
    MAX(gene."end") AS operon_end,
    CASE
        WHEN MIN(gene.strand) = MAX(gene.strand) AND MIN(gene.strand) = 1 THEN '+'
        WHEN MIN(gene.strand) = MAX(gene.strand) AND MIN(gene.strand) = -1 THEN '-'
        ELSE 'mixed'
    END AS strand,
    COUNT(*) AS gene_count
FROM occurrences AS occurrence
JOIN genomes AS genome USING (genome_key)
JOIN occurrence_genes AS gene USING (occurrence_id)
JOIN contigs AS contig ON contig.contig_id = gene.contig_id
GROUP BY occurrence.occurrence_id, occurrence.operon_id, genome.genome_id,
         genome.organism_name, gene.contig_id, contig.contig_name
ORDER BY occurrence.occurrence_id
"""

GENE_QUERY = """
WITH oriented_genes AS (
    SELECT
        gene.*,
        MIN(gene.strand) OVER (PARTITION BY gene.occurrence_id) AS occurrence_min_strand,
        MAX(gene.strand) OVER (PARTITION BY gene.occurrence_id) AS occurrence_max_strand
    FROM occurrence_genes AS gene
)
SELECT
    gene.occurrence_id,
    occurrence.operon_id,
    genome.genome_id,
    genome.organism_name,
    contig.contig_name AS contig,
    gene.peg_num AS peg_number,
    ROW_NUMBER() OVER (
        PARTITION BY gene.occurrence_id
        ORDER BY
            CASE
                WHEN gene.occurrence_min_strand = -1
                 AND gene.occurrence_max_strand = -1
                THEN -gene.start
                ELSE gene.start
            END,
            gene.peg_num
    ) AS gene_order_in_operon,
    gene.start,
    gene."end",
    ABS(gene."end" - gene.start) + 1 AS length,
    CASE gene.strand WHEN 1 THEN '+' WHEN -1 THEN '-' ELSE CAST(gene.strand AS TEXT) END AS strand,
    COALESCE(product.product, '') AS product,
    'PGF_' || printf('%08d', gene.pgfam_num) AS pgfam,
    COALESCE(subsystem.roles, '') AS roles,
    COALESCE(subsystem.subsystems, '') AS subsystems,
    COALESCE(subsystem.subsystem_classes, '') AS subsystem_classes,
    COALESCE(pathway.ec_numbers, '') AS ec_numbers,
    COALESCE(pathway.pathway_ids, '') AS pathway_ids,
    COALESCE(pathway.pathway_names, '') AS pathway_names,
    COALESCE(pathway.pathway_classes, '') AS pathway_classes
FROM oriented_genes AS gene
JOIN occurrences AS occurrence USING (occurrence_id)
JOIN genomes AS genome ON genome.genome_key = gene.genome_key
JOIN contigs AS contig ON contig.contig_id = gene.contig_id
LEFT JOIN products AS product USING (product_id)
LEFT JOIN temp.download_gene_subsystems AS subsystem
  ON subsystem.gene_key = gene.gene_key
LEFT JOIN temp.download_gene_pathways AS pathway
  ON pathway.gene_key = gene.gene_key
ORDER BY gene.occurrence_id, gene_order_in_operon
"""


def write_dictionary(output_dir: Path) -> tuple[int, str]:
    path = output_dir / "data_dictionary.tsv"
    multiple = {
        "roles", "subsystems", "subsystem_classes",
        "ec_numbers", "pathway_ids", "pathway_names", "pathway_classes",
    }
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["file", "column", "type", "description", "multiple_values", "multiple_value_separator"])
        for filename, columns in DATA_DICTIONARY.items():
            for name, data_type, description in columns:
                writer.writerow([
                    filename, name, data_type, description,
                    "yes" if name in multiple else "no",
                    MULTI_VALUE_SEPARATOR if name in multiple else "",
                ])
    return path.stat().st_size, sha256_file(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local download release.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_path = resolved(args.db)
    output_dir = resolved(args.output)
    staging_dir = output_dir.with_name(output_dir.name + ".partial")
    if args.release in PROTECTED_RELEASES:
        print(f"Release {args.release} is protected and cannot be regenerated.", file=sys.stderr)
        return 1
    if not SAFE_RELEASE.fullmatch(args.release):
        print("Release must be a safe 1-64 character filename token.", file=sys.stderr)
        return 1
    if not database_path.is_file():
        print(f"Database not found: {database_path}", file=sys.stderr)
        return 1
    conflicts = [path for path in (staging_dir,) if path.exists()]
    if output_dir.exists() and not args.overwrite:
        conflicts.append(output_dir)
    if conflicts:
        print("Refusing to replace an existing release or staging directory:", file=sys.stderr)
        for path in conflicts:
            print(f"  {path}", file=sys.stderr)
        return 1

    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    connection.execute("PRAGMA temp_store = FILE")
    connection.execute("PRAGMA cache_size = -262144")
    try:
        require_tables(
            connection,
            {
                "operons", "occurrences", "occurrence_genes", "genomes", "contigs", "products",
                "genome_taxonomy", "operon_taxonomy_counts", "operon_function_coverage",
                "gene_pathways", "ec_numbers", "pathway_reference", "pathway_classes",
                "gene_subsystems", "subsystem_roles", "subsystem_reference", "subsystem_classes",
            },
        )
        staging_dir.parent.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir()
        print("Building exact gene annotation aggregates...")
        build_annotation_aggregates(connection)

        generated_at = datetime.now(timezone.utc).isoformat()
        exports: list[ExportMetadata] = []
        specifications = [
            ("Operon families", "operon_families.tsv.gz", "Family composition, taxonomy breadth, and annotation coverage.", FAMILY_QUERY),
            ("Operon occurrences", "operon_occurrences.tsv.gz", "Genome-specific predicted operon occurrences.", OCCURRENCE_QUERY),
            ("Operon occurrence genes", "operon_occurrence_genes.tsv.gz", "Ordered genes, products, PGFams, and exact functional annotations.", GENE_QUERY),
        ]
        for dataset, filename, description, query in specifications:
            path = staging_dir / filename
            print(f"Generating {filename}...")
            rows = export_query(connection, query, path)
            exports.append(
                ExportMetadata(
                    dataset=dataset,
                    filename=filename,
                    description=description,
                    format="gzip-compressed TSV",
                    release=args.release,
                    generated_at=generated_at,
                    rows=rows,
                    compressed_bytes=path.stat().st_size,
                    sha256=sha256_file(path),
                )
            )

        dictionary_bytes, dictionary_sha = write_dictionary(staging_dir)
        manifest = {
            "release": args.release,
            "generated_at": generated_at,
            "datasets": [asdict(item) for item in exports],
            "documentation": {
                "filename": "data_dictionary.tsv",
                "bytes": dictionary_bytes,
                "sha256": dictionary_sha,
                "description": "Column names, data types, and definitions.",
            },
            "checksums": {"filename": "checksums.sha256", "algorithm": "SHA-256"},
        }
        manifest_path = staging_dir / "downloads_manifest.json"
        with manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        checksum_names = [
            *(item.filename for item in exports),
            "data_dictionary.tsv",
            "downloads_manifest.json",
        ]
        with (staging_dir / "checksums.sha256").open("x", encoding="ascii", newline="\n") as handle:
            for filename in sorted(checksum_names):
                handle.write(f"{sha256_file(staging_dir / filename)}  {filename}\n")

        if output_dir.exists():
            import shutil
            shutil.rmtree(output_dir)
        staging_dir.replace(output_dir)
        print(f"Download release completed: {output_dir}")
        return 0
    except (RuntimeError, OSError, sqlite3.Error, ValueError) as error:
        print(f"Download release failed: {error}", file=sys.stderr)
        if staging_dir.exists():
            print(f"Partial release retained for inspection: {staging_dir}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
