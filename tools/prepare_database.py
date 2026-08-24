#!/usr/bin/env python3
"""Rebuild a canonical SQLite database and generate its D1 import SQL."""

from __future__ import annotations

import argparse
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
        "schema": DATABASE_DIR / "build_sample_db.sql",
        "database": DATABASE_DIR / "operon_atlas_sample.db",
        "sql": IMPORT_DIR / "operon_atlas_sample.sql",
        "report": IMPORT_DIR / "operon_atlas_sample.report.json",
    },
    "full": {
        "schema": DATABASE_DIR / "build_db.sql",
        "database": DATABASE_DIR / "operon_atlas.db",
        "sql": IMPORT_DIR / "operon_atlas_full.sql",
        "report": IMPORT_DIR / "operon_atlas_full.report.json",
    },
}
IMPORT_PATTERN = re.compile(r"^\.import\s+--skip\s+1\s+(\S+)\s+\S+\s*$")


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


def verify_database(path: Path) -> dict[str, int]:
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
        if not version or version[0] != "operonatlas_v4":
            raise RuntimeError(f"Unexpected schema version: {version}")
        return counts
    finally:
        connection.close()


def main() -> int:
    args = parse_args()
    config = SCOPES[args.scope]
    schema_path = config["schema"]
    database_path = config["database"]
    building_path = database_path.with_name(database_path.name + ".building")
    sql_path = config["sql"]
    report_path = config["report"]
    building_sql = sql_path.with_name(sql_path.name + ".building")
    building_report = report_path.with_name(report_path.name + ".building")
    sqlite_command = shutil.which("sqlite3")
    if not sqlite_command:
        print("sqlite3 is required to rebuild the database.", file=sys.stderr)
        return 1

    try:
        check_inputs(schema_path)
        for path in (building_path, building_sql, building_report):
            if path.exists():
                path.unlink()
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

        counts = verify_database(building_path)
        print(
            "Core rows: "
            f"{counts['operons']:,} families; "
            f"{counts['occurrences']:,} occurrences; "
            f"{counts['occurrence_genes']:,} genes"
        )

        IMPORT_DIR.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "prepare_d1_import.py"),
                str(building_path),
                str(building_sql),
                "--report",
                str(building_report),
                "--rows-per-insert",
                "1000",
                "--max-statement-bytes",
                "90000",
                "--overwrite",
            ],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"D1 SQL generation exited with status {completed.returncode}"
            )

        report = json.loads(building_report.read_text(encoding="utf-8"))
        report["source_database"] = database_path.resolve().as_posix()
        report["output_sql"] = sql_path.resolve().as_posix()
        building_report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        building_sql.replace(sql_path)
        building_report.replace(report_path)
        building_path.replace(database_path)
        print(f"SQLite database ready: {database_path}")
        return 0
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        print(f"Database preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
