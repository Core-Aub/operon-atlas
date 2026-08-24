#!/usr/bin/env python3
"""Create dependency-ordered Cloudflare D1 SQL imports from SQLite."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator


TABLE_ORDER = (
    "genomes", "products", "contigs", "operons", "occurrences",
    "occurrence_genes", "operon_products", "genome_taxonomy",
    "operon_taxonomy_counts", "ec_numbers", "pathway_classes",
    "pathway_reference", "gene_pathways", "subsystem_roles",
    "subsystem_classes", "subsystem_reference", "gene_subsystems",
    "operon_function_coverage", "operon_subsystem_support",
    "operon_subsystem_class_support", "operon_pathway_support",
    "operon_pathway_class_support", "operon_pgfams", "operon_ec_support",
    "operon_role_support", "search_entities", "build_info",
)

# Ordered by foreign-key dependency. Numeric prefixes make lexical execution safe.
IMPORT_GROUPS = (
    ("10", "genomes", ("genomes", "products", "contigs")),
    ("20", "operon_families", ("operons", "operon_products")),
    ("30", "operon_occurrences", ("occurrences",)),
    ("40", "genes", ("occurrence_genes",)),
    ("50", "function_references", (
        "ec_numbers", "pathway_classes", "pathway_reference",
        "subsystem_roles", "subsystem_classes", "subsystem_reference",
    )),
    ("51", "gene_pathways", ("gene_pathways",)),
    ("52", "gene_subsystems", ("gene_subsystems",)),
    ("60", "operon_function_support", (
        "operon_function_coverage", "operon_subsystem_support",
        "operon_subsystem_class_support", "operon_pathway_support",
        "operon_pathway_class_support",
    )),
    ("70", "taxonomy", ("genome_taxonomy", "operon_taxonomy_counts")),
    ("80", "search_support", (
        "operon_pgfams", "operon_ec_support", "operon_role_support",
        "search_entities",
    )),
    ("90", "build_info", ("build_info",)),
)

PROJECT_DATABASE_LIMIT_BYTES = 4_500_000_000
DEFAULT_MAX_PART_BYTES = 95_000_000


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
    nullable_index = (
        column_names.index("subsystem_class_key")
        if table == "subsystem_reference"
        else None
    )
    values: list[str] = []
    current_bytes = len(prefix.encode("utf-8")) + 2
    for raw_row in connection.execute(f"SELECT * FROM {quote_identifier(table)}"):
        row = list(raw_row)
        if nullable_index is not None and row[nullable_index] == "":
            row[nullable_index] = None
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


def validate_tables(connection: sqlite3.Connection) -> None:
    existing = {
        str(name)
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'"
        )
        if not str(name).startswith("sqlite_")
    }
    unknown = sorted(existing - set(TABLE_ORDER))
    missing = sorted(set(TABLE_ORDER) - existing)
    if unknown or missing:
        raise RuntimeError(f"Canonical table mismatch; missing={missing}, extra={unknown}")
    grouped = {table for _, _, tables in IMPORT_GROUPS for table in tables}
    grouped_count = sum(len(tables) for _, _, tables in IMPORT_GROUPS)
    if grouped != set(TABLE_ORDER) or grouped_count != len(grouped):
        raise RuntimeError(
            "Split group mismatch; "
            f"missing={sorted(set(TABLE_ORDER) - grouped)}, "
            f"extra={sorted(grouped - set(TABLE_ORDER))}, "
            f"duplicate_count={grouped_count - len(grouped)}"
        )


def table_schema(connection: sqlite3.Connection, table: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if not row or not row[0]:
        raise RuntimeError(f"Could not read CREATE TABLE SQL for {table}")
    return str(row[0]).rstrip(";\n") + ";\n"


def index_statements(connection: sqlite3.Connection) -> list[str]:
    return [
        str(sql).rstrip(";\n") + ";\n"
        for (sql,) in connection.execute(
            """
            SELECT sql FROM sqlite_schema
            WHERE type = 'index' AND sql IS NOT NULL
            ORDER BY name
            """
        )
    ]


def file_metadata(path: Path, *, kind: str, tables: Iterable[str]) -> dict[str, object]:
    return {
        "filename": path.name,
        "kind": kind,
        "tables": list(tables),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_schema_file(connection: sqlite3.Connection, output_dir: Path) -> dict[str, object]:
    path = output_dir / "01_schema.sql"
    with path.open("xb") as handle:
        write_text(handle, "-- Generated by tools/prepare_d1_import.py\n")
        for table in reversed(TABLE_ORDER):
            write_text(handle, f"DROP TABLE IF EXISTS {quote_identifier(table)};\n")
        write_text(handle, "\n")
        for table in TABLE_ORDER:
            write_text(handle, table_schema(connection, table))
        write_text(handle, "\n")
    return file_metadata(path, kind="schema", tables=TABLE_ORDER)


def write_index_file(connection: sqlite3.Connection, output_dir: Path) -> dict[str, object]:
    path = output_dir / "02_indexes.sql"
    with path.open("xb") as handle:
        write_text(handle, "-- Explicit indexes; create while all application tables are empty.\n")
        for statement in index_statements(connection):
            write_text(handle, statement)
    return file_metadata(path, kind="indexes", tables=())


def write_optimize_file(output_dir: Path) -> dict[str, object]:
    path = output_dir / "99_optimize.sql"
    with path.open("xb") as handle:
        write_text(
            handle,
            "-- Final D1 planner-statistics maintenance after all data is loaded.\n"
            "PRAGMA optimize;\n",
        )
    return file_metadata(path, kind="optimization", tables=())


def write_data_group(
    connection: sqlite3.Connection,
    output_dir: Path,
    prefix: str,
    slug: str,
    tables: tuple[str, ...],
    *,
    rows_per_insert: int,
    max_statement_bytes: int,
    max_part_bytes: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    raw_parts: list[tuple[Path, list[str]]] = []
    row_counts: dict[str, int] = {}
    part_number = 0
    handle: BinaryIO | None = None
    current_path: Path | None = None
    current_bytes = 0
    current_tables: list[str] = []

    def open_part() -> None:
        nonlocal part_number, handle, current_path, current_bytes, current_tables
        part_number += 1
        current_path = output_dir / f".{prefix}_{slug}_{part_number:03d}.sql"
        handle = current_path.open("xb")
        header = f"-- Data group {prefix}_{slug}, part {part_number:03d}.\n"
        write_text(handle, header)
        current_bytes = len(header.encode("utf-8"))
        current_tables = []

    def close_part() -> None:
        nonlocal handle, current_path
        if handle is not None and current_path is not None:
            handle.close()
            raw_parts.append((current_path, list(current_tables)))
        handle = None
        current_path = None

    try:
        for table in tables:
            row_counts[table] = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(table)}"
                ).fetchone()[0]
            )
            print(f"  {table}: {row_counts[table]:,} rows", flush=True)
            for statement in iter_insert_statements(
                connection,
                table,
                rows_per_insert=rows_per_insert,
                max_statement_bytes=max_statement_bytes,
            ):
                statement_bytes = len(statement.encode("utf-8"))
                if statement_bytes > max_part_bytes:
                    raise RuntimeError(f"One {table} statement exceeds the part limit")
                if handle is None:
                    open_part()
                if current_bytes + statement_bytes > max_part_bytes:
                    close_part()
                    open_part()
                assert handle is not None
                write_text(handle, statement)
                current_bytes += statement_bytes
                if table not in current_tables:
                    current_tables.append(table)
            if handle is not None and current_bytes < max_part_bytes:
                write_text(handle, "\n")
                current_bytes += 1
        close_part()
    except Exception:
        if handle is not None:
            handle.close()
        raise

    if not raw_parts:
        raise RuntimeError(f"Data group {slug} produced no SQL")
    files: list[dict[str, object]] = []
    multiple = len(raw_parts) > 1
    for index, (raw_path, part_tables) in enumerate(raw_parts, start=1):
        filename = (
            f"{prefix}_{slug}_part_{index:03d}.sql"
            if multiple
            else f"{prefix}_{slug}.sql"
        )
        final_path = output_dir / filename
        raw_path.replace(final_path)
        files.append(file_metadata(final_path, kind="data", tables=part_tables))
    return files, row_counts


def build_split_import(
    connection: sqlite3.Connection,
    source_database: Path,
    output_dir: Path,
    *,
    rows_per_insert: int,
    max_statement_bytes: int,
    max_part_bytes: int,
    overwrite: bool,
) -> dict[str, object]:
    staging = output_dir.with_name(output_dir.name + ".partial")
    if staging.exists():
        if not overwrite:
            raise FileExistsError(f"Partial output exists: {staging}")
        shutil.rmtree(staging)
    if output_dir.exists() and not overwrite:
        raise FileExistsError(f"Output directory exists: {output_dir}")
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir()
    try:
        files = [
            write_schema_file(connection, staging),
            write_index_file(connection, staging),
        ]
        row_counts: dict[str, int] = {}
        for prefix, slug, tables in IMPORT_GROUPS:
            group_files, group_counts = write_data_group(
                connection,
                staging,
                prefix,
                slug,
                tables,
                rows_per_insert=rows_per_insert,
                max_statement_bytes=max_statement_bytes,
                max_part_bytes=max_part_bytes,
            )
            files.extend(group_files)
            row_counts.update(group_counts)
        files.append(write_optimize_file(staging))
        files.sort(key=lambda item: str(item["filename"]))
        total_bytes = sum(int(item["bytes"]) for item in files)
        largest_bytes = max(int(item["bytes"]) for item in files)
        source_bytes = source_database.stat().st_size
        manifest = {
            "report_version": 3,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "split",
            "source_database": source_database.as_posix(),
            "source_database_bytes": source_bytes,
            "output_directory": output_dir.as_posix(),
            "rows_per_insert": rows_per_insert,
            "max_statement_bytes": max_statement_bytes,
            "max_part_bytes": max_part_bytes,
            "total_sql_bytes": total_bytes,
            "largest_part_bytes": largest_bytes,
            "tables": row_counts,
            "files": files,
            "import_order": [
                "schema",
                "explicit_indexes_on_empty_tables",
                "dependency_ordered_data",
                "build_metadata",
                "pragma_optimize",
            ],
            "limits": {
                "project_database_limit_bytes": PROJECT_DATABASE_LIMIT_BYTES,
                "source_within_project_limit": source_bytes <= PROJECT_DATABASE_LIMIT_BYTES,
                "all_parts_within_limit": largest_bytes <= max_part_bytes,
            },
        }
        with (staging / "manifest.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        with (staging / "checksums.sha256").open(
            "x", encoding="ascii", newline="\n"
        ) as handle:
            for item in files:
                handle.write(f"{item['sha256']}  {item['filename']}\n")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        staging.replace(output_dir)
        return manifest
    except Exception:
        print(f"Partial split import retained for inspection: {staging}", file=sys.stderr)
        raise


def build_single_import(
    connection: sqlite3.Connection,
    source_database: Path,
    output_sql: Path,
    report_path: Path | None,
    *,
    rows_per_insert: int,
    max_statement_bytes: int,
    overwrite: bool,
) -> dict[str, object]:
    partial = output_sql.with_name(output_sql.name + ".partial")
    conflicts = [path for path in (partial,) if path.exists()]
    if not overwrite:
        conflicts.extend(path for path in (output_sql, report_path) if path and path.exists())
    if conflicts:
        raise FileExistsError("Existing D1 artifacts: " + ", ".join(map(str, conflicts)))
    if partial.exists():
        partial.unlink()
    output_sql.parent.mkdir(parents=True, exist_ok=True)
    row_counts: dict[str, int] = {}
    with partial.open("xb") as handle:
        write_text(handle, "-- Generated by tools/prepare_d1_import.py\n")
        for table in reversed(TABLE_ORDER):
            write_text(handle, f"DROP TABLE IF EXISTS {quote_identifier(table)};\n")
        write_text(handle, "\n")
        for table in TABLE_ORDER:
            write_text(handle, table_schema(connection, table))
        write_text(handle, "\n")
        for statement in index_statements(connection):
            write_text(handle, statement)
        write_text(handle, "\n")
        for table in TABLE_ORDER:
            for statement in iter_insert_statements(
                connection,
                table,
                rows_per_insert=rows_per_insert,
                max_statement_bytes=max_statement_bytes,
            ):
                write_text(handle, statement)
            row_counts[table] = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(table)}"
                ).fetchone()[0]
            )
            write_text(handle, "\n")
            print(f"  {table}: {row_counts[table]:,} rows", flush=True)
        write_text(handle, "PRAGMA optimize;\n")
    partial.replace(output_sql)
    report = {
        "report_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "single",
        "source_database": source_database.as_posix(),
        "source_database_bytes": source_database.stat().st_size,
        "output_sql": output_sql.as_posix(),
        "output_sql_bytes": output_sql.stat().st_size,
        "rows_per_insert": rows_per_insert,
        "max_statement_bytes": max_statement_bytes,
        "tables": row_counts,
        "import_order": [
            "schema",
            "explicit_indexes_on_empty_tables",
            "dependency_ordered_data",
            "build_metadata",
            "pragma_optimize",
        ],
    }
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_partial = report_path.with_name(report_path.name + ".partial")
        if report_partial.exists():
            report_partial.unlink()
        with report_partial.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        report_partial.replace(report_path)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dependency-ordered SQL accepted by Cloudflare D1."
    )
    parser.add_argument("source_db", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--rows-per-insert", type=int, default=1000)
    parser.add_argument("--max-statement-bytes", type=int, default=90_000)
    parser.add_argument("--max-part-bytes", type=int, default=DEFAULT_MAX_PART_BYTES)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_database = resolved(args.source_db)
    output = resolved(args.output)
    report_path = resolved(args.report) if args.report else None
    if not source_database.is_file():
        print(f"Source database not found: {source_database}", file=sys.stderr)
        return 1
    if output == source_database:
        print("Source database and output paths must differ.", file=sys.stderr)
        return 1
    if args.rows_per_insert <= 0 or args.max_statement_bytes < 1024:
        print("Insert sizing arguments must be positive and at least 1024 bytes.", file=sys.stderr)
        return 1
    if args.max_part_bytes <= args.max_statement_bytes:
        print("Part size must be larger than the statement size limit.", file=sys.stderr)
        return 1
    if args.split and report_path:
        print("Split imports write <output>/manifest.json; omit --report.", file=sys.stderr)
        return 1
    connection = readonly_connection(source_database)
    try:
        validate_tables(connection)
        if args.split:
            manifest = build_split_import(
                connection,
                source_database,
                output,
                rows_per_insert=args.rows_per_insert,
                max_statement_bytes=args.max_statement_bytes,
                max_part_bytes=args.max_part_bytes,
                overwrite=args.overwrite,
            )
            print(f"Wrote {len(manifest['files'])} D1 SQL files: {output}")
            print(f"Total SQL size: {int(manifest['total_sql_bytes']):,} bytes")
            print(f"Largest file: {int(manifest['largest_part_bytes']):,} bytes")
            limits = manifest["limits"]
            return 0 if (
                limits["source_within_project_limit"]
                and limits["all_parts_within_limit"]
            ) else 2
        report = build_single_import(
            connection,
            source_database,
            output,
            report_path,
            rows_per_insert=args.rows_per_insert,
            max_statement_bytes=args.max_statement_bytes,
            overwrite=args.overwrite,
        )
        print(f"Wrote D1 SQL: {output}")
        print(f"D1 SQL size: {int(report['output_sql_bytes']):,} bytes")
        return 0 if source_database.stat().st_size <= PROJECT_DATABASE_LIMIT_BYTES else 2
    except (RuntimeError, OSError, ValueError, sqlite3.Error) as error:
        print(f"D1 import generation failed: {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
