#!/usr/bin/env python3
"""Create a dependency-ordered Cloudflare D1 SQL import using stdlib SQLite.

The tool is read-only with respect to the source database and atomically
replaces recurring generated SQL.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Sequence


TABLE_ORDER = (
    "genomes",
    "products",
    "contigs",
    "operons",
    "occurrences",
    "occurrence_genes",
    "operon_products",
    "genome_taxonomy",
    "operon_taxonomy_counts",
    "ec_numbers",
    "pathway_classes",
    "pathway_reference",
    "gene_pathways",
    "subsystem_roles",
    "subsystem_classes",
    "subsystem_reference",
    "gene_subsystems",
    "operon_function_coverage",
    "operon_subsystem_support",
    "operon_subsystem_class_support",
    "operon_pathway_support",
    "operon_pathway_class_support",
    "operon_pgfams",
    "operon_ec_support",
    "operon_role_support",
    "search_entities",
    "build_info",
)
OPTIONAL_TABLES: set[str] = set()
IGNORED_SQLITE_TABLES = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}
PROJECT_DATABASE_LIMIT_BYTES = 4_500_000_000
D1_SINGLE_IMPORT_LIMIT_BYTES = 5_000_000_000


def resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value: object | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError(f"Cannot export non-finite SQLite value: {value!r}")
        return repr(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise RuntimeError(f"Unsupported SQLite value type: {type(value).__name__}")


def write_text(handle: BinaryIO, value: str) -> None:
    handle.write(value.encode("utf-8"))


def readonly_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True
    )
    connection.execute("PRAGMA query_only = ON")
    return connection


def iter_insert_statements(
    connection: sqlite3.Connection,
    table: str,
    *,
    rows_per_insert: int,
    max_statement_bytes: int,
) -> Iterator[str]:
    prefix = f"INSERT INTO {quote_identifier(table)} VALUES "
    column_names = [
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table)})"
        )
    ]
    nullable_subsystem_class_index = (
        column_names.index("subsystem_class_key")
        if table == "subsystem_reference"
        else None
    )
    values: list[str] = []
    current_bytes = len(prefix.encode("utf-8")) + 2
    for raw_row in connection.execute(f"SELECT * FROM {quote_identifier(table)}"):
        row = list(raw_row)
        # Older SQLite sources can contain four empty strings in this nullable
        # integer FK. The canonical schema already normalizes them, but keep
        # this guard so D1 never receives an empty string in the key path.
        if (
            nullable_subsystem_class_index is not None
            and row[nullable_subsystem_class_index] == ""
        ):
            row[nullable_subsystem_class_index] = None
        encoded = "(" + ",".join(sql_literal(value) for value in row) + ")"
        encoded_bytes = len(encoded.encode("utf-8")) + (1 if values else 0)
        if values and (
            len(values) >= rows_per_insert
            or current_bytes + encoded_bytes > max_statement_bytes
        ):
            yield prefix + ",".join(values) + ";\n"
            values = []
            current_bytes = len(prefix.encode("utf-8")) + 2
        values.append(encoded)
        current_bytes += encoded_bytes
    if values:
        yield prefix + ",".join(values) + ";\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dependency-ordered SQL accepted by Cloudflare D1."
    )
    parser.add_argument("source_db", type=Path)
    parser.add_argument("output_sql", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--rows-per-insert", type=int, default=1000)
    parser.add_argument("--max-statement-bytes", type=int, default=90_000)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_database = resolved(args.source_db)
    output_sql = resolved(args.output_sql)
    partial_sql = output_sql.with_name(output_sql.name + ".partial")
    report_path = resolved(args.report) if args.report else None

    if not source_database.is_file():
        print(f"Source database not found: {source_database}", file=sys.stderr)
        return 1
    if source_database in (output_sql, partial_sql):
        print("Source DB and SQL output paths must differ.", file=sys.stderr)
        return 1
    conflicts = [path for path in (partial_sql,) if path.exists()]
    if not args.overwrite:
        conflicts.extend(
            path for path in (output_sql, report_path) if path and path.exists()
        )
    if conflicts:
        print("Refusing to replace existing D1 artifacts:", file=sys.stderr)
        for path in conflicts:
            print(f"  {path}", file=sys.stderr)
        return 1
    if args.rows_per_insert <= 0 or args.max_statement_bytes < 1024:
        print("Insert sizing arguments must be positive and at least 1024 bytes.", file=sys.stderr)
        return 1

    output_sql.parent.mkdir(parents=True, exist_ok=True)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)

    connection = readonly_connection(source_database)
    try:
        existing_tables = {
            str(name)
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
            if not str(name).startswith("sqlite_")
        }
        unknown_tables = sorted(existing_tables - set(TABLE_ORDER))
        if unknown_tables:
            raise RuntimeError(
                "Explicit D1 order is missing application tables: "
                + ", ".join(unknown_tables)
            )
        missing_required = sorted(
            set(TABLE_ORDER) - OPTIONAL_TABLES - existing_tables
        )
        if missing_required:
            raise RuntimeError(
                "Source DB is missing required application tables: "
                + ", ".join(missing_required)
            )
        emitted_tables = [table for table in TABLE_ORDER if table in existing_tables]

        row_counts: dict[str, int] = {}
        with partial_sql.open("xb") as handle:
            write_text(
                handle,
                "-- Generated by tools/prepare_d1_import.py\n"
                "PRAGMA defer_foreign_keys = true;\n\n",
            )
            for table in reversed(TABLE_ORDER):
                write_text(handle, f"DROP TABLE IF EXISTS {quote_identifier(table)};\n")
            write_text(handle, "\n")

            for table in emitted_tables:
                schema_row = connection.execute(
                    "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?",
                    (table,),
                ).fetchone()
                if not schema_row or not schema_row[0]:
                    raise RuntimeError(f"Could not read CREATE TABLE SQL for {table}")
                write_text(handle, str(schema_row[0]).rstrip(";\n") + ";\n")
                count = 0
                for statement in iter_insert_statements(
                    connection,
                    table,
                    rows_per_insert=args.rows_per_insert,
                    max_statement_bytes=args.max_statement_bytes,
                ):
                    write_text(handle, statement)
                    count += statement.count("),(") + 1
                row_counts[table] = count
                write_text(handle, "\n")
                print(f"  {table}: {count:,} rows", flush=True)

            for (index_sql,) in connection.execute(
                """
                SELECT sql
                FROM sqlite_schema
                WHERE type = 'index' AND sql IS NOT NULL
                ORDER BY name
                """
            ):
                write_text(handle, str(index_sql).rstrip(";\n") + ";\n")
            write_text(handle, "\n")

        partial_sql.replace(output_sql)
        source_bytes = source_database.stat().st_size
        sql_bytes = output_sql.stat().st_size
        report = {
            "report_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_database": source_database.as_posix(),
            "source_database_bytes": source_bytes,
            "output_sql": output_sql.as_posix(),
            "output_sql_bytes": sql_bytes,
            "rows_per_insert": args.rows_per_insert,
            "max_statement_bytes": args.max_statement_bytes,
            "tables": row_counts,
            "limits": {
                "project_database_limit_bytes": PROJECT_DATABASE_LIMIT_BYTES,
                "source_within_project_limit": source_bytes <= PROJECT_DATABASE_LIMIT_BYTES,
                "project_d1_import_limit_bytes": D1_SINGLE_IMPORT_LIMIT_BYTES,
                "sql_within_single_import_limit": sql_bytes <= D1_SINGLE_IMPORT_LIMIT_BYTES,
            },
        }
        if report_path:
            report_partial = report_path.with_name(report_path.name + ".partial")
            if report_partial.exists():
                report_partial.unlink()
            with report_partial.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(report, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            report_partial.replace(report_path)

        print(f"Wrote D1 SQL: {output_sql}")
        print(f"Source SQLite size: {source_bytes:,} bytes")
        print(f"D1 SQL size: {sql_bytes:,} bytes")
        if source_bytes > PROJECT_DATABASE_LIMIT_BYTES:
            print("ERROR: source database exceeds project 4.5 GB gate.", file=sys.stderr)
        if sql_bytes > D1_SINGLE_IMPORT_LIMIT_BYTES:
            print("ERROR: SQL exceeds project 5,000,000,000-byte import gate.", file=sys.stderr)
        return 0 if (
            source_bytes <= PROJECT_DATABASE_LIMIT_BYTES
            and sql_bytes <= D1_SINGLE_IMPORT_LIMIT_BYTES
        ) else 2
    except (RuntimeError, OSError, sqlite3.Error) as error:
        print(f"D1 import generation failed: {error}", file=sys.stderr)
        if partial_sql.exists():
            print(f"Partial SQL retained for inspection: {partial_sql}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
