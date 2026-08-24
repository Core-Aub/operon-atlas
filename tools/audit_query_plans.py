#!/usr/bin/env python3
"""Audit OperonAtlas indexes and representative Worker query plans."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


EXPECTED_EXPLICIT_INDEXES = {
    "idx_contigs_genome",
    "idx_genome_taxonomy_genus",
    "idx_genome_taxonomy_phylum",
    "idx_genome_taxonomy_species",
    "idx_occurrence_genes_genome_contig_start",
    "idx_occurrences_genome_operon",
    "idx_occurrences_operon",
    "idx_operon_pathway_class_support_class",
    "idx_operon_pathway_support_pathway",
    "idx_operon_products_product",
    "idx_operon_subsystem_class_support_class",
    "idx_operon_subsystem_support_subsystem",
    "idx_operons_gene_count",
    "idx_operons_occurrence_count",
    "idx_search_entities_identifier",
}
FORBIDDEN_EXPLICIT_INDEXES = {
    "idx_gene_pathways_gene",
    "idx_gene_subsystems_gene",
    "idx_products_product",
    "idx_search_entities_text",
}
INDEX_NAME_PATTERN = re.compile(r"(?:INDEX|COVERING INDEX) ([^ ]+)")


@dataclass(frozen=True)
class QueryCheck:
    name: str
    sql: str
    params: tuple[object, ...] = ()
    require_all: tuple[str, ...] = ()
    forbid_full_scan_aliases: tuple[str, ...] = ()
    note: str = ""


QUERY_CHECKS = (
    QueryCheck(
        "browse operons: default occurrence-count order",
        """
        SELECT o.operon_id, o.gene_count, o.occurrence_count
        FROM operons AS o
        ORDER BY o.occurrence_count DESC, o.operon_id ASC
        LIMIT 20 OFFSET 0
        """,
        require_all=("idx_operons_occurrence_count",),
        forbid_full_scan_aliases=("o",),
    ),
    QueryCheck(
        "browse operons: gene-count order",
        """
        SELECT o.operon_id, o.gene_count, o.occurrence_count
        FROM operons AS o
        ORDER BY o.gene_count ASC, o.operon_id ASC
        LIMIT 20 OFFSET 0
        """,
        require_all=("idx_operons_gene_count",),
        forbid_full_scan_aliases=("o",),
    ),
    QueryCheck(
        "browse operons: reverse occurrence-count order",
        """
        SELECT o.operon_id, o.gene_count, o.occurrence_count
        FROM operons AS o
        ORDER BY o.occurrence_count ASC, o.operon_id ASC
        LIMIT 20 OFFSET 0
        """,
        require_all=("idx_operons_occurrence_count",),
        forbid_full_scan_aliases=("o",),
        note="The same index serves the reverse direction; SQLite may sort only equal-count ties.",
    ),
    QueryCheck(
        "browse operons: reverse gene-count order",
        """
        SELECT o.operon_id, o.gene_count, o.occurrence_count
        FROM operons AS o
        ORDER BY o.gene_count DESC, o.operon_id ASC
        LIMIT 20 OFFSET 0
        """,
        require_all=("idx_operons_gene_count",),
        forbid_full_scan_aliases=("o",),
        note="The same index serves the reverse direction; SQLite may sort only equal-count ties.",
    ),
    QueryCheck(
        "browse operons: identifier order",
        """
        SELECT o.operon_id, o.gene_count, o.occurrence_count
        FROM operons AS o
        ORDER BY o.operon_id ASC
        LIMIT 20 OFFSET 0
        """,
        note="operon_id is INTEGER PRIMARY KEY and needs no separate explicit index.",
    ),
    QueryCheck(
        "family occurrences",
        "SELECT occurrence_id FROM occurrences WHERE operon_id = ? ORDER BY occurrence_id LIMIT 20",
        (3454,),
        require_all=("idx_occurrences_operon",),
        forbid_full_scan_aliases=("occurrences",),
    ),
    QueryCheck(
        "genome-family occurrences",
        "SELECT occurrence_id FROM occurrences WHERE genome_key = ? AND operon_id = ? ORDER BY occurrence_id",
        (24, 3454),
        require_all=("idx_occurrences_genome_operon",),
        forbid_full_scan_aliases=("occurrences",),
    ),
    QueryCheck(
        "occurrence genes",
        "SELECT gene_key, peg_num FROM occurrence_genes WHERE occurrence_id = ? ORDER BY peg_num",
        (66374,),
        require_all=("sqlite_autoindex_occurrence_genes_1",),
        forbid_full_scan_aliases=("occurrence_genes",),
    ),
    QueryCheck(
        "exact coordinate gene lookup",
        """
        SELECT gene_key
        FROM occurrence_genes
        WHERE genome_key = ? AND contig_id = ? AND start = ?
          AND "end" = ? AND strand = ?
        """,
        (24, 1405, 1051816, 1052763, -1),
        require_all=("idx_occurrence_genes_genome_contig_start",),
        forbid_full_scan_aliases=("occurrence_genes",),
    ),
    QueryCheck(
        "exact reconstructed gene lookup",
        """
        SELECT gene.occurrence_id
        FROM genomes AS genome
        JOIN occurrence_genes AS gene
          ON gene.genome_key = genome.genome_key
        WHERE genome.genome_id = ? AND gene.peg_num = ?
        """,
        ("1003195.11", 2553),
        require_all=("sqlite_autoindex_genomes_1", "idx_occurrence_genes_genome_contig_start"),
        forbid_full_scan_aliases=("genome", "gene"),
    ),
    QueryCheck(
        "occurrence pathway annotations",
        """
        SELECT pathway.ec_key, pathway.pathway_key
        FROM occurrence_genes AS gene
        JOIN gene_pathways AS pathway USING (gene_key)
        WHERE gene.occurrence_id = ?
        """,
        (66374,),
        require_all=("sqlite_autoindex_occurrence_genes_1", "PRIMARY KEY"),
        forbid_full_scan_aliases=("gene", "pathway"),
    ),
    QueryCheck(
        "occurrence subsystem annotations",
        """
        SELECT subsystem.role_key, subsystem.subsystem_key
        FROM occurrence_genes AS gene
        JOIN gene_subsystems AS subsystem USING (gene_key)
        WHERE gene.occurrence_id = ?
        """,
        (66374,),
        require_all=("sqlite_autoindex_occurrence_genes_1", "PRIMARY KEY"),
        forbid_full_scan_aliases=("gene", "subsystem"),
    ),
    QueryCheck(
        "reverse product support",
        "SELECT operon_id FROM operon_products WHERE product_id = ?",
        (1632,),
        require_all=("idx_operon_products_product",),
        forbid_full_scan_aliases=("operon_products",),
    ),
    QueryCheck(
        "genome contigs",
        "SELECT contig_id FROM contigs WHERE genome_id = ? ORDER BY contig_id",
        ("1003195.11",),
        require_all=("idx_contigs_genome",),
        forbid_full_scan_aliases=("contigs",),
    ),
    QueryCheck(
        "taxonomy phylum reverse lookup",
        "SELECT genome_key FROM genome_taxonomy WHERE phylum_taxon_id = ?",
        (201174,),
        require_all=("idx_genome_taxonomy_phylum",),
        forbid_full_scan_aliases=("genome_taxonomy",),
    ),
    QueryCheck(
        "taxonomy genus reverse lookup",
        "SELECT genome_key FROM genome_taxonomy WHERE genus_taxon_id = ?",
        (2995706,),
        require_all=("idx_genome_taxonomy_genus",),
        forbid_full_scan_aliases=("genome_taxonomy",),
    ),
    QueryCheck(
        "taxonomy species reverse lookup",
        "SELECT genome_key FROM genome_taxonomy WHERE species_taxon_id = ?",
        (1003195,),
        require_all=("idx_genome_taxonomy_species",),
        forbid_full_scan_aliases=("genome_taxonomy",),
    ),
    QueryCheck(
        "exact search identifier",
        "SELECT entity_type, entity_key FROM search_entities WHERE identifier = ? COLLATE NOCASE",
        ("1003195.11",),
        require_all=("idx_search_entities_identifier",),
        forbid_full_scan_aliases=("search_entities",),
    ),
    QueryCheck(
        "reverse pathway support",
        "SELECT operon_id FROM operon_pathway_support WHERE pathway_key = ?",
        (13,),
        require_all=("idx_operon_pathway_support_pathway",),
        forbid_full_scan_aliases=("operon_pathway_support",),
    ),
    QueryCheck(
        "reverse pathway-class support",
        "SELECT operon_id FROM operon_pathway_class_support WHERE pathway_class_key = ?",
        (1,),
        require_all=("idx_operon_pathway_class_support_class",),
        forbid_full_scan_aliases=("operon_pathway_class_support",),
    ),
    QueryCheck(
        "reverse subsystem support",
        "SELECT operon_id FROM operon_subsystem_support WHERE subsystem_key = ?",
        (97,),
        require_all=("idx_operon_subsystem_support_subsystem",),
        forbid_full_scan_aliases=("operon_subsystem_support",),
    ),
    QueryCheck(
        "reverse subsystem-class support",
        "SELECT operon_id FROM operon_subsystem_class_support WHERE subsystem_class_key = ?",
        (1,),
        require_all=("idx_operon_subsystem_class_support_class",),
        forbid_full_scan_aliases=("operon_subsystem_class_support",),
    ),
    QueryCheck(
        "PGFam reverse support primary key",
        "SELECT operon_id FROM operon_pgfams WHERE pgfam_num = ?",
        (2517283,),
        require_all=("PRIMARY KEY",),
        forbid_full_scan_aliases=("operon_pgfams",),
    ),
    QueryCheck(
        "EC reverse support primary key",
        "SELECT operon_id FROM operon_ec_support WHERE ec_key = ?",
        (1,),
        require_all=("PRIMARY KEY",),
        forbid_full_scan_aliases=("operon_ec_support",),
    ),
    QueryCheck(
        "role reverse support primary key",
        "SELECT operon_id FROM operon_role_support WHERE role_key = ?",
        (1,),
        require_all=("PRIMARY KEY",),
        forbid_full_scan_aliases=("operon_role_support",),
    ),
    QueryCheck(
        "genome viewer gene access",
        "SELECT occurrence_id, start FROM occurrence_genes WHERE genome_key = ? ORDER BY occurrence_id, start",
        (24,),
        require_all=("idx_occurrence_genes_genome_contig_start",),
        forbid_full_scan_aliases=("occurrence_genes",),
    ),
    QueryCheck(
        "genome summary sort (small table, deliberate scan/sort)",
        "SELECT genome_key, operon_count FROM genomes ORDER BY operon_count DESC, genome_key ASC LIMIT 20",
        note="The full release has only about 20k genomes; no count-sort indexes are justified.",
    ),
    QueryCheck(
        "leading-wildcard product search (deliberate scan)",
        "SELECT product_id FROM products WHERE product LIKE ? ESCAPE '\\'",
        ("%hypothetical%",),
        note="A normal B-tree cannot optimize the leading wildcard.",
    ),
    QueryCheck(
        "leading-wildcard search catalog (deliberate scan)",
        "SELECT entity_type, entity_key FROM search_entities WHERE search_text LIKE ? ESCAPE '\\'",
        ("%glycolysis%",),
        note="The 131k-row catalog scan is intentional; FTS5 remains deferred.",
    ),
)


def quote_pragma(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def index_signature(
    connection: sqlite3.Connection,
    index_name: str,
) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        (str(name), str(collation).upper(), int(descending))
        for _, column_id, name, descending, collation, is_key in connection.execute(
            f"PRAGMA index_xinfo({quote_pragma(index_name)})"
        )
        if int(is_key) == 1 and int(column_id) >= 0
    )


def inspect_indexes(
    connection: sqlite3.Connection,
) -> tuple[dict[str, tuple[str, str, tuple[tuple[str, str, int], ...]]], list[str]]:
    indexes: dict[str, tuple[str, str, tuple[tuple[str, str, int], ...]]] = {}
    failures: list[str] = []
    tables = [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for table in tables:
        for _, index_name, _, origin, _ in connection.execute(
            f"PRAGMA index_list({quote_pragma(table)})"
        ):
            indexes[str(index_name)] = (
                table,
                str(origin),
                index_signature(connection, str(index_name)),
            )

    explicit_names = {name for name, (_, origin, _) in indexes.items() if origin == "c"}
    missing = sorted(EXPECTED_EXPLICIT_INDEXES - explicit_names)
    extra = sorted(explicit_names - EXPECTED_EXPLICIT_INDEXES)
    forbidden = sorted(explicit_names & FORBIDDEN_EXPLICIT_INDEXES)
    if missing:
        failures.append("missing justified explicit indexes: " + ", ".join(missing))
    if extra:
        failures.append("unexpected explicit indexes: " + ", ".join(extra))
    if forbidden:
        failures.append("forbidden redundant/substring indexes: " + ", ".join(forbidden))

    constraints_by_table: dict[str, list[tuple[str, tuple[tuple[str, str, int], ...]]]] = {}
    for name, (table, origin, signature) in indexes.items():
        if origin in {"u", "pk"}:
            constraints_by_table.setdefault(table, []).append((name, signature))
    for name, (table, origin, signature) in indexes.items():
        if origin != "c" or not signature:
            continue
        for constraint_name, constraint_signature in constraints_by_table.get(table, []):
            if constraint_signature[: len(signature)] == signature:
                failures.append(
                    f"{name} is covered by constraint index {constraint_name} on {table}"
                )
        for other_name, (other_table, other_origin, other_signature) in indexes.items():
            if (
                other_origin == "c"
                and other_name != name
                and other_table == table
                and len(other_signature) >= len(signature)
                and other_signature[: len(signature)] == signature
            ):
                failures.append(
                    f"{name} is a redundant prefix of explicit index {other_name} on {table}"
                )
    return indexes, failures


def explain(
    connection: sqlite3.Connection,
    check: QueryCheck,
) -> list[str]:
    return [
        str(row[3])
        for row in connection.execute("EXPLAIN QUERY PLAN " + check.sql, check.params)
    ]


def is_unindexed_scan(detail: str, alias: str) -> bool:
    normalized = detail.upper()
    alias_pattern = re.escape(alias.upper())
    return (
        re.search(rf"^SCAN (?:TABLE )?{alias_pattern}(?:\s|$)", normalized) is not None
        and " USING " not in normalized
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database = args.database.expanduser().resolve()
    if not database.is_file():
        print(f"Database not found: {database}", file=sys.stderr)
        return 1
    connection = sqlite3.connect(
        f"file:{database.as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.execute("PRAGMA query_only = ON")
    failures: list[str] = []
    try:
        indexes, index_failures = inspect_indexes(connection)
        failures.extend(index_failures)
        print(f"Index inventory: {database}")
        for name, (table, origin, signature) in sorted(indexes.items()):
            columns = ", ".join(
                f"{column}{' DESC' if descending else ''} {collation}"
                for column, collation, descending in signature
            )
            print(f"  {name}: table={table}, origin={origin}, keys=[{columns}]")

        print("\nRepresentative Worker query plans:")
        for check in QUERY_CHECKS:
            details = explain(connection, check)
            used_indexes = sorted(
                {
                    match.group(1)
                    for detail in details
                    for match in INDEX_NAME_PATTERN.finditer(detail)
                }
            )
            print(f"\n- {check.name}")
            for detail in details:
                print(f"    {detail}")
            print(
                "    indexes: "
                + (", ".join(used_indexes) if used_indexes else "none")
            )
            if check.note:
                print(f"    note: {check.note}")
            combined = "\n".join(details)
            if check.require_all and not all(
                required in combined for required in check.require_all
            ):
                failures.append(
                    f"{check.name}: missing required plan evidence "
                    + ", ".join(check.require_all)
                )
            for alias in check.forbid_full_scan_aliases:
                if any(is_unindexed_scan(detail, alias) for detail in details):
                    failures.append(
                        f"{check.name}: unexpected unindexed scan of {alias}"
                    )

        if failures:
            print("\nQuery-plan/index audit: FAIL", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1
        print("\nQuery-plan/index audit: PASS")
        return 0
    except sqlite3.Error as error:
        print(f"Query-plan/index audit failed: {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
