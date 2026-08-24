#!/usr/bin/env python3
"""Rebuild a canonical SQLite database and generate its D1 import SQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from prepare_d1_import import TABLE_ORDER


ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = ROOT / "database"
IMPORT_DIR = ROOT / ".wrangler" / "imports"
SCOPES = {
    "sample": {
        "mode": "single",
        "schema": DATABASE_DIR / "build_sample_db.sql",
        "database": DATABASE_DIR / "operon_atlas_sample.db",
        "sql": IMPORT_DIR / "operon_atlas_sample.sql",
        "report": IMPORT_DIR / "operon_atlas_sample.report.json",
        "data": DATABASE_DIR / "sample_data",
    },
    "full": {
        "mode": "split",
        "schema": DATABASE_DIR / "build_db.sql",
        "database": DATABASE_DIR / "operon_atlas.db",
        "parts": IMPORT_DIR / "operon_atlas_full_parts",
        "data": DATABASE_DIR / "data",
    },
}
IMPORT_PATTERN = re.compile(r"^\.import\s+--skip\s+1\s+(\S+)\s+\S+\s*$")
NORMALIZED_INPUT_HEADERS = {
    "genomes.tsv": (
        "genome_key", "genome_id", "organism_name", "operon_count",
        "gene_count",
    ),
    "occurrence_genes.tsv": (
        "gene_key", "occurrence_id", "genome_key", "peg_num", "contig_id",
        "start", "end", "strand", "product_id", "pgfam_num",
    ),
    "gene_pathways.tsv": ("gene_key", "ec_key", "pathway_key"),
    "gene_subsystems.tsv": ("gene_key", "role_key", "subsystem_key"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=sorted(SCOPES))
    return parser.parse_args()


def check_inputs(schema_path: Path) -> None:
    missing: list[Path] = []
    for line in schema_path.read_text(encoding="utf-8").splitlines():
        match = IMPORT_PATTERN.match(line.strip())
        if match:
            path = DATABASE_DIR / match.group(1)
            if not path.is_file():
                missing.append(path)
    if missing:
        formatted = "\n".join(f"  {path}" for path in missing)
        raise RuntimeError(f"Schema input files are missing:\n{formatted}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_normalized_inputs(
    data_dir: Path,
    expected_scope: str,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_path = data_dir / "release_normalization.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Missing release-normalization manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("manifest_version", -1)) != 1:
        raise RuntimeError(
            f"Unsupported release-normalization manifest: {manifest_path}"
        )
    if manifest.get("scope") != expected_scope:
        raise RuntimeError(
            "Release-normalization scope mismatch: "
            f"expected={expected_scope}, actual={manifest.get('scope')}"
        )

    gene_key = manifest.get("gene_key", {})
    if (
        gene_key.get("order") != ["occurrence_id", "peg_num"]
        or gene_key.get("coordinate_identity_unique") is not True
    ):
        raise RuntimeError(
            "Release-normalization manifest does not preserve the required "
            "deterministic gene order and unique full-coordinate identity"
        )

    expected_outputs = manifest.get("outputs", {})
    if set(expected_outputs) != set(NORMALIZED_INPUT_HEADERS):
        raise RuntimeError(
            "Release-normalization output set mismatch: "
            f"expected={sorted(NORMALIZED_INPUT_HEADERS)}, "
            f"actual={sorted(expected_outputs)}"
        )

    verified: dict[str, dict[str, object]] = {}
    for filename, expected_header in NORMALIZED_INPUT_HEADERS.items():
        path = data_dir / filename
        if not path.is_file():
            raise RuntimeError(f"Normalized authoritative TSV is missing: {path}")
        with path.open("r", encoding="utf-8", newline="") as handle:
            actual_header = tuple(handle.readline().rstrip("\r\n").split("\t"))
        if actual_header != expected_header:
            raise RuntimeError(
                f"Normalized TSV header mismatch for {path}: "
                f"expected={expected_header}, actual={actual_header}"
            )

        expected = expected_outputs[filename]
        actual_bytes = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if (
            actual_bytes != int(expected.get("bytes", -1))
            or actual_sha256 != expected.get("sha256")
        ):
            raise RuntimeError(
                f"Normalized TSV no longer matches its legacy-transform proof: {path}; "
                f"bytes={actual_bytes}/{expected.get('bytes')}, "
                f"sha256={actual_sha256}/{expected.get('sha256')}"
            )
        verified[filename] = {
            "bytes": actual_bytes,
            "sha256": actual_sha256,
            "rows": int(expected.get("rows", -1)),
        }
    return manifest, verified


def relationship_digest(
    connection: sqlite3.Connection,
    table: str,
    columns: tuple[str, str, str],
) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    column_sql = ", ".join(f'"{column}"' for column in columns)
    for row in connection.execute(
        f'SELECT {column_sql} FROM "{table}" ORDER BY {column_sql}'
    ):
        digest.update(
            ("\t".join(str(int(value)) for value in row) + "\n").encode("ascii")
        )
        count += 1
    return count, digest.hexdigest()


def verify_normalization(
    connection: sqlite3.Connection,
    manifest: dict[str, object],
    counts: dict[str, int],
    verified_inputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    gene_key = manifest.get("gene_key", {})
    gene_invariants = connection.execute(
        """
        SELECT
          COUNT(*) AS rows,
          COUNT(DISTINCT gene_key) AS unique_keys,
          MIN(gene_key) AS minimum_key,
          MAX(gene_key) AS maximum_key
        FROM occurrence_genes
        """
    ).fetchone()
    expected_gene_rows = int(gene_key.get("rows", -1))
    expected_gene_last = int(gene_key.get("last", -1))
    if (
        gene_invariants is None
        or int(gene_invariants[0]) != expected_gene_rows
        or int(gene_invariants[1]) != expected_gene_rows
        or int(gene_invariants[2]) != 1
        or int(gene_invariants[3]) != expected_gene_last
        or expected_gene_last != expected_gene_rows
    ):
        raise RuntimeError(
            "Deterministic gene_key invariants failed: "
            f"database={gene_invariants}, manifest_rows={expected_gene_rows}, "
            f"manifest_last={expected_gene_last}"
        )

    for table in ("gene_pathways", "gene_subsystems"):
        orphan_count = int(
            connection.execute(
                f"""
                SELECT COUNT(*)
                FROM "{table}" AS annotation
                LEFT JOIN occurrence_genes AS gene
                  ON gene.gene_key = annotation.gene_key
                WHERE gene.gene_key IS NULL
                """
            ).fetchone()[0]
        )
        if orphan_count:
            raise RuntimeError(f"{table} contains {orphan_count:,} orphan gene keys")

    genome_mismatches = int(
        connection.execute(
            """
            WITH direct AS (
              SELECT
                genome_key,
                COUNT(*) AS operon_count,
                COALESCE(SUM(gene_count), 0) AS gene_count
              FROM occurrences
              GROUP BY genome_key
            )
            SELECT COUNT(*)
            FROM genomes AS genome
            LEFT JOIN direct USING (genome_key)
            WHERE genome.operon_count != COALESCE(direct.operon_count, 0)
               OR genome.gene_count != COALESCE(direct.gene_count, 0)
            """
        ).fetchone()[0]
    )
    if genome_mismatches:
        raise RuntimeError(
            f"Precomputed genome summaries mismatch {genome_mismatches:,} genomes"
        )

    expected_genome_summary = manifest.get("genome_summary", {})
    actual_genome_summary = connection.execute(
        """
        SELECT
          COUNT(*),
          COALESCE(SUM(operon_count), 0),
          COALESCE(SUM(gene_count), 0)
        FROM genomes
        """
    ).fetchone()
    expected_genome_totals = (
        int(expected_genome_summary.get("genomes", -1)),
        int(expected_genome_summary.get("total_operon_count", -1)),
        int(expected_genome_summary.get("total_gene_count", -1)),
    )
    if tuple(int(value) for value in actual_genome_summary) != expected_genome_totals:
        raise RuntimeError(
            "Precomputed genome-summary totals changed from the normalization proof: "
            f"database={actual_genome_summary}, manifest={expected_genome_totals}"
        )

    relationship_columns = {
        "gene_pathways": ("gene_key", "ec_key", "pathway_key"),
        "gene_subsystems": ("gene_key", "role_key", "subsystem_key"),
    }
    verified_relationships: dict[str, object] = {}
    expected_relationships = manifest.get("relationships", {})
    for table, columns in relationship_columns.items():
        expected = expected_relationships.get(table, {})
        expected_rows = int(expected.get("rows", -1))
        expected_digest = str(expected.get("normalized_relationship_sha256", ""))
        actual_rows, actual_digest = relationship_digest(connection, table, columns)
        if (
            actual_rows != expected_rows
            or counts[table] != expected_rows
            or actual_digest != expected_digest
        ):
            raise RuntimeError(
                f"{table} relationship verification failed: "
                f"rows={actual_rows:,}/{expected_rows:,}, "
                f"digest={actual_digest}/{expected_digest}"
            )
        verified_relationships[table] = {
            "rows": actual_rows,
            "sha256": actual_digest,
        }

    return {
        "gene_keys": {
            "rows": expected_gene_rows,
            "minimum": 1,
            "maximum": expected_gene_last,
            "unique": True,
            "order": gene_key["order"],
            "mapping_tsv_sha256": verified_inputs["occurrence_genes.tsv"]["sha256"],
        },
        "genome_summary_mismatches": genome_mismatches,
        "genome_summary": {
            "genomes": expected_genome_totals[0],
            "total_operon_count": expected_genome_totals[1],
            "total_gene_count": expected_genome_totals[2],
        },
        "relationships": verified_relationships,
        "authoritative_normalized_inputs": verified_inputs,
    }


def verify_database(
    path: Path,
    normalization_manifest: dict[str, object],
    verified_inputs: dict[str, dict[str, object]],
) -> tuple[dict[str, int], dict[str, object]]:
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        foreign_keys = list(connection.execute("PRAGMA foreign_key_check"))
        if foreign_keys:
            raise RuntimeError(
                f"SQLite foreign-key check returned {len(foreign_keys)} violation(s)."
            )
        tables = {
            str(name)
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            )
            if not str(name).startswith("sqlite_")
        }
        expected = set(TABLE_ORDER)
        if tables != expected:
            missing = sorted(expected - tables)
            extra = sorted(tables - expected)
            raise RuntimeError(
                f"Canonical table mismatch; missing={missing}, extra={extra}"
            )
        counts = {
            table: int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
            for table in TABLE_ORDER
        }
        empty = [table for table, count in counts.items() if count == 0]
        if empty:
            raise RuntimeError("Canonical tables are unexpectedly empty: " + ", ".join(empty))
        version = connection.execute(
            "SELECT value FROM build_info WHERE key = 'schema_version'"
        ).fetchone()
        if not version or version[0] != "operonatlas_v5":
            raise RuntimeError(f"Unexpected schema version: {version}")
        normalization = verify_normalization(
            connection,
            normalization_manifest,
            counts,
            verified_inputs,
        )
        return counts, normalization
    finally:
        connection.close()


def main() -> int:
    args = parse_args()
    config = SCOPES[args.scope]
    schema_path = config["schema"]
    database_path = config["database"]
    building_path = database_path.with_name(database_path.name + ".building")
    mode = config["mode"]
    if mode == "single":
        sql_path = config["sql"]
        report_path = config["report"]
        building_output = sql_path.with_name(sql_path.name + ".building")
        building_report = report_path.with_name(report_path.name + ".building")
    else:
        parts_path = config["parts"]
        building_output = parts_path.with_name(parts_path.name + ".building")
        building_report = building_output / "manifest.json"
    sqlite_command = shutil.which("sqlite3")
    if not sqlite_command:
        print("sqlite3 is required to rebuild the database.", file=sys.stderr)
        return 1

    try:
        check_inputs(schema_path)
        normalization_manifest, verified_inputs = verify_normalized_inputs(
            config["data"],
            args.scope,
        )
        if building_path.exists():
            building_path.unlink()
        if building_output.exists():
            if building_output.is_dir():
                shutil.rmtree(building_output)
            else:
                building_output.unlink()
        if mode == "single" and building_report.exists():
            building_report.unlink()
        print(f"Rebuilding {args.scope} SQLite database from {schema_path.name}...")
        with schema_path.open("rb") as schema:
            completed = subprocess.run(
                [sqlite_command, "-bail", str(building_path)],
                cwd=DATABASE_DIR,
                stdin=schema,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"sqlite3 exited with status {completed.returncode}")

        counts, normalization = verify_database(
            building_path,
            normalization_manifest,
            verified_inputs,
        )
        print(
            "Core rows: "
            f"{counts['operons']:,} families; "
            f"{counts['occurrences']:,} occurrences; "
            f"{counts['occurrence_genes']:,} genes"
        )

        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        import_command = [
            sys.executable,
            str(ROOT / "tools" / "prepare_d1_import.py"),
            str(building_path),
            str(building_output),
            "--rows-per-insert",
            "1000",
            "--max-statement-bytes",
            "90000",
            "--overwrite",
        ]
        if mode == "single":
            import_command.extend(["--report", str(building_report)])
        else:
            import_command.extend([
                "--split",
                "--max-part-bytes",
                "95000000",
            ])
        completed = subprocess.run(
            import_command,
            cwd=ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"D1 SQL generation exited with status {completed.returncode}"
            )

        report = json.loads(building_report.read_text(encoding="utf-8"))
        report["normalization_verification"] = normalization
        report["source_database"] = database_path.resolve().as_posix()
        if mode == "single":
            report["output_sql"] = sql_path.resolve().as_posix()
        else:
            report["output_directory"] = parts_path.resolve().as_posix()
        building_report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        if mode == "single":
            building_output.replace(sql_path)
            building_report.replace(report_path)
        else:
            if parts_path.exists():
                shutil.rmtree(parts_path)
            building_output.replace(parts_path)
        building_path.replace(database_path)
        print(f"SQLite database ready: {database_path}")
        if mode == "single":
            print(f"D1 import ready: {sql_path}")
            print(f"D1 import report ready: {report_path}")
        else:
            print(f"D1 import parts ready: {parts_path}")
            print(f"D1 import manifest ready: {parts_path / 'manifest.json'}")
        return 0
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print(f"Database preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
