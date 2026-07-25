#!/usr/bin/env python3
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PAGE_SIZE = 20
MIN_GENE_COUNT = 1
MAX_GENE_COUNT = 10000
MAX_SEARCH_TEXT_LENGTH = 120

# Family-summary display thresholds.
# A function must appear in a meaningful fraction of annotated occurrences
# and explain a meaningful share of annotated genes. Strong support is kept
# as an internal fallback signal, but it should not be displayed as a main column.
FAMILY_FUNCTION_OCCURRENCE_SUPPORT_MIN = 0.20
FAMILY_FUNCTION_AVG_GENE_SHARE_MIN = 0.05
FAMILY_FUNCTION_STRONG_SUPPORT_MIN = 0.20
FAMILY_FUNCTION_DISPLAY_LIMIT = 3

# Occurrence-summary display thresholds.
OCCURRENCE_FUNCTION_GENE_SHARE_MIN = 0.25
OCCURRENCE_FUNCTION_MIN_SUPPORTING_GENES = 2
OCCURRENCE_FUNCTION_DISPLAY_LIMIT = 3

DEFAULT_DB_PATH = (Path(__file__).resolve().parent / "../database/operons_sample.db").resolve()
DB_PATH = Path(os.environ.get("DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
if not DB_PATH.is_absolute():
    DB_PATH = (Path.cwd() / DB_PATH).resolve()


def connect_db():
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_page(query):
    value = parse_qs(query).get("page", ["1"])[0]
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


def first_query_value(values, *names):
    for name in names:
        value = values.get(name, [None])[0]
        if value is not None:
            return value
    return None


def normalize_search_text(value):
    if value is None:
        return None
    cleaned = " ".join(
        "".join(char for char in str(value) if char.isprintable()).strip().split()
    )
    if not cleaned:
        return None
    return cleaned[:MAX_SEARCH_TEXT_LENGTH]


def escape_like(value):
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def like_contains_param(value):
    return f"%{escape_like(value)}%"


def parse_operon_filters(query):
    values = parse_qs(query)
    min_gene_count = parse_int(first_query_value(values, "min_genes", "min_gene_count"))
    max_gene_count = parse_int(first_query_value(values, "max_genes", "max_gene_count"))
    genome_key = parse_int(values.get("genome_key", [None])[0])
    organism = normalize_search_text(first_query_value(values, "organism", "organism_name"))
    product = normalize_search_text(values.get("product", [None])[0])

    min_gene_count = MIN_GENE_COUNT if min_gene_count is None else clamp(
        min_gene_count,
        MIN_GENE_COUNT,
        MAX_GENE_COUNT,
    )
    max_gene_count = MAX_GENE_COUNT if max_gene_count is None else clamp(
        max_gene_count,
        MIN_GENE_COUNT,
        MAX_GENE_COUNT,
    )
    if min_gene_count > max_gene_count:
        min_gene_count, max_gene_count = max_gene_count, min_gene_count

    return {
        "min_gene_count": min_gene_count,
        "max_gene_count": max_gene_count,
        "genome_key": genome_key if genome_key is not None and genome_key > 0 else None,
        "organism": organism,
        "product": product,
    }


def parse_genome_search(query):
    values = parse_qs(query)
    return normalize_search_text(values.get("search", [None])[0])


def parse_occurrence_filters(query):
    values = parse_qs(query)
    return {
        "product": normalize_search_text(values.get("product", [None])[0]),
    }


def parse_operon_sort(query):
    values = parse_qs(query)
    sort = values.get("sort", ["occurrence_count"])[0]
    direction = values.get("direction", ["desc"])[0].lower()
    sort_columns = {
        "occurrence_count": "o.occurrence_count",
        "gene_count": "o.gene_count",
        "operon_id": "o.operon_id",
    }
    if sort not in sort_columns:
        sort = "occurrence_count"
    if direction not in {"asc", "desc"}:
        direction = "desc"
    return sort, sort_columns[sort], direction.upper()


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_dicts(rows):
    return [row_to_dict(row) for row in rows]


def format_pgfam(pgfam_num):
    if pgfam_num is None or int(pgfam_num) == -1:
        return None
    return f"PGF_{int(pgfam_num):08d}"


def format_stable_operon_id(operon_id):
    return f"OAF{int(operon_id):06d}"


def format_occurrence_id(occurrence_id):
    return f"OAO{int(occurrence_id):06d}"


def format_pgfam_signature(signature):
    if not signature:
        return []
    pgfams = []
    for value in str(signature).split("|"):
        try:
            formatted = format_pgfam(int(value))
        except ValueError:
            formatted = None
        if formatted is not None:
            pgfams.append(formatted)
    return pgfams


def gene_annotation_key(row, start_field="start", end_field="end"):
    return (
        f"{row['genome_key']}|{row['contig_id']}|"
        f"{row[start_field]}|{row[end_field]}|{row['strand']}"
    )


def fetch_occurrence_pathways(conn, occurrence_id):
    rows = conn.execute(
        """
        SELECT
          og.genome_key,
          og.contig_id,
          og.start AS gene_start,
          og.end AS gene_end,
          og.strand,
          e.ec_number,
          e.ec_description,
          pr.pathway_id,
          pr.pathway_name,
          pc.pathway_class
        FROM occurrence_genes AS og
        JOIN gene_pathways AS gp
          ON gp.genome_key = og.genome_key
         AND gp.contig_id = og.contig_id
         AND gp.gene_start = og.start
         AND gp.gene_end = og.end
         AND gp.strand = og.strand
        LEFT JOIN ec_numbers AS e
          ON e.ec_key = gp.ec_key
        LEFT JOIN pathway_reference AS pr
          ON pr.pathway_key = gp.pathway_key
        LEFT JOIN pathway_classes AS pc
          ON pc.pathway_class_key = pr.pathway_class_key
        WHERE og.occurrence_id = ?
        ORDER BY og.start, pr.pathway_name, e.ec_number
        """,
        (occurrence_id,),
    ).fetchall()

    pathways_by_gene = {}
    seen_by_gene = {}
    for row in rows:
        row = row_to_dict(row)
        key = gene_annotation_key(row, "gene_start", "gene_end")
        annotation_key = (row["ec_number"], row["pathway_id"])
        seen = seen_by_gene.setdefault(key, set())
        if annotation_key in seen:
            continue
        seen.add(annotation_key)
        pathways_by_gene.setdefault(key, []).append({
            "ec_number": row["ec_number"],
            "ec_description": row["ec_description"],
            "pathway_id": row["pathway_id"],
            "pathway_name": row["pathway_name"],
            "pathway_class": row["pathway_class"],
        })
    return pathways_by_gene


def fetch_occurrence_subsystems(conn, occurrence_id):
    rows = conn.execute(
        """
        SELECT
          og.genome_key,
          og.contig_id,
          og.start AS gene_start,
          og.end AS gene_end,
          og.strand,
          sr.role_id,
          sr.role_name,
          sref.subsystem_id,
          sref.subsystem_name,
          sc.subsystem_superclass,
          sc.subsystem_class,
          sc.subsystem_subclass
        FROM occurrence_genes AS og
        JOIN gene_subsystems AS gs
          ON gs.genome_key = og.genome_key
         AND gs.contig_id = og.contig_id
         AND gs.gene_start = og.start
         AND gs.gene_end = og.end
         AND gs.strand = og.strand
        LEFT JOIN subsystem_roles AS sr
          ON sr.role_key = gs.role_key
        LEFT JOIN subsystem_reference AS sref
          ON sref.subsystem_key = gs.subsystem_key
        LEFT JOIN subsystem_classes AS sc
          ON sc.subsystem_class_key = sref.subsystem_class_key
        WHERE og.occurrence_id = ?
        ORDER BY og.start, sref.subsystem_name, sr.role_name
        """,
        (occurrence_id,),
    ).fetchall()

    subsystems_by_gene = {}
    seen_by_gene = {}
    for row in rows:
        row = row_to_dict(row)
        key = gene_annotation_key(row, "gene_start", "gene_end")
        annotation_key = (row["role_id"], row["subsystem_id"])
        seen = seen_by_gene.setdefault(key, set())
        if annotation_key in seen:
            continue
        seen.add(annotation_key)
        subsystems_by_gene.setdefault(key, []).append({
            "role_id": row["role_id"],
            "role_name": row["role_name"],
            "subsystem_id": row["subsystem_id"],
            "subsystem_name": row["subsystem_name"],
            "subsystem_superclass": row["subsystem_superclass"],
            "subsystem_class": row["subsystem_class"],
            "subsystem_subclass": row["subsystem_subclass"],
        })
    return subsystems_by_gene


def fetch_operon_functional_summary(conn, operon_id):
    coverage = row_to_dict(conn.execute(
        """
        SELECT
          occurrence_count,
          annotated_occurrence_count,
          annotated_occurrence_fraction,
          gene_count,
          avg_annotated_gene_count,
          avg_annotated_gene_fraction,
          avg_annotated_gene_fraction_among_annotated_occurrences
        FROM operon_function_coverage
        WHERE operon_id = ?
        """,
        (operon_id,),
    ).fetchone())

    subsystems = rows_to_dicts(conn.execute(
        """
        SELECT
          sr.subsystem_name,
          sc.subsystem_superclass,
          sc.subsystem_class,
          sc.subsystem_subclass,
          oss.supporting_occurrence_count,
          oss.annotated_occurrence_count,
          oss.supporting_occurrence_fraction,
          oss.avg_annotated_gene_share,
          oss.max_annotated_gene_share
        FROM operon_subsystem_support AS oss
        JOIN subsystem_reference AS sr
          ON sr.subsystem_key = oss.subsystem_key
        LEFT JOIN subsystem_classes AS sc
          ON sc.subsystem_class_key = sr.subsystem_class_key
        WHERE oss.operon_id = ?
          AND oss.supporting_occurrence_fraction >= ?
          AND (
                oss.avg_annotated_gene_share >= ?
                OR oss.strong_supporting_occurrence_fraction >= ?
              )
        ORDER BY
          oss.avg_annotated_gene_share DESC,
          oss.supporting_occurrence_fraction DESC,
          oss.strong_supporting_occurrence_fraction DESC
        LIMIT ?
        """,
        (
            operon_id,
            FAMILY_FUNCTION_OCCURRENCE_SUPPORT_MIN,
            FAMILY_FUNCTION_AVG_GENE_SHARE_MIN,
            FAMILY_FUNCTION_STRONG_SUPPORT_MIN,
            FAMILY_FUNCTION_DISPLAY_LIMIT,
        ),
    ).fetchall())

    pathways = rows_to_dicts(conn.execute(
        """
        SELECT
          pr.pathway_id,
          pr.pathway_name,
          pc.pathway_class,
          ops.supporting_occurrence_count,
          ops.annotated_occurrence_count,
          ops.supporting_occurrence_fraction,
          ops.avg_annotated_gene_share,
          ops.max_annotated_gene_share
        FROM operon_pathway_support AS ops
        JOIN pathway_reference AS pr
          ON pr.pathway_key = ops.pathway_key
        LEFT JOIN pathway_classes AS pc
          ON pc.pathway_class_key = pr.pathway_class_key
        WHERE ops.operon_id = ?
          AND ops.supporting_occurrence_fraction >= ?
          AND (
                ops.avg_annotated_gene_share >= ?
                OR ops.strong_supporting_occurrence_fraction >= ?
              )
        ORDER BY
          ops.avg_annotated_gene_share DESC,
          ops.supporting_occurrence_fraction DESC,
          ops.strong_supporting_occurrence_fraction DESC
        LIMIT ?
        """,
        (
            operon_id,
            FAMILY_FUNCTION_OCCURRENCE_SUPPORT_MIN,
            FAMILY_FUNCTION_AVG_GENE_SHARE_MIN,
            FAMILY_FUNCTION_STRONG_SUPPORT_MIN,
            FAMILY_FUNCTION_DISPLAY_LIMIT,
        ),
    ).fetchall())

    return {
        "coverage": coverage,
        "subsystems": subsystems,
        "pathways": pathways,
    }


def stats(conn):
    return {
        "genomes": conn.execute("SELECT COUNT(*) FROM genomes").fetchone()[0],
        "operons": conn.execute("SELECT COUNT(*) FROM operons").fetchone()[0],
        "occurrences": conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0],
        "occurrence_genes": conn.execute("SELECT COUNT(*) FROM occurrence_genes").fetchone()[0],
        # "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
    }


def product_filter_ctes():
    return [
        """
        matching_product_ids AS (
          SELECT product_id
          FROM products
          WHERE product LIKE ? ESCAPE '\\'
        )
        """,
        """
        matching_products AS (
          SELECT DISTINCT op_filter.operon_id
          FROM matching_product_ids mpi
          JOIN operon_products op_filter INDEXED BY idx_operon_products_product
            ON mpi.product_id = op_filter.product_id
        )
        """,
    ]


def operon_query_parts(filters):
    ctes = []
    joins = []
    where_clauses = []
    params = []

    if filters["genome_key"] is not None:
        ctes.append(
            """
            matching_genomes AS (
              SELECT DISTINCT operon_id
              FROM occurrences
              WHERE genome_key = ?
            )
            """
        )
        joins.append(
            "JOIN matching_genomes mg ON mg.operon_id = o.operon_id"
        )
        params.append(filters["genome_key"])
    if filters["organism"] is not None:
        ctes.append(
            """
            matching_organisms AS (
              SELECT DISTINCT occ_organism.operon_id
              FROM genomes g_organism
              JOIN occurrences occ_organism
                ON g_organism.genome_key = occ_organism.genome_key
              WHERE g_organism.genome_id LIKE ? ESCAPE '\\'
                 OR g_organism.organism_name LIKE ? ESCAPE '\\'
            )
            """
        )
        joins.append(
            "JOIN matching_organisms mo ON mo.operon_id = o.operon_id"
        )
        organism_param = like_contains_param(filters["organism"])
        params.extend([organism_param, organism_param])
    if filters["product"] is not None:
        ctes.extend(product_filter_ctes())
        joins.append(
            "JOIN matching_products mp ON mp.operon_id = o.operon_id"
        )
        params.append(like_contains_param(filters["product"]))

    if filters["min_gene_count"] > MIN_GENE_COUNT:
        where_clauses.append("o.gene_count >= ?")
        params.append(filters["min_gene_count"])
    if filters["max_gene_count"] < MAX_GENE_COUNT:
        where_clauses.append("o.gene_count <= ?")
        params.append(filters["max_gene_count"])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    with_sql = f"WITH {', '.join(ctes)}" if ctes else ""
    from_sql = "FROM operons o"
    if joins:
        from_sql = f"{from_sql}\n" + "\n".join(joins)
    return with_sql, from_sql, where_sql, params


def browse_operons(conn, page, filters, sort):
    offset = (page - 1) * PAGE_SIZE
    with_sql, from_sql, where_sql, filter_params = operon_query_parts(filters)
    sort_key, sort_column, sort_direction = sort
    total = conn.execute(
        f"""
        {with_sql}
        SELECT COUNT(*)
        {from_sql}
        {where_sql}
        """,
        filter_params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        {with_sql}
        SELECT
          o.operon_id,
          o.pgfam_signature,
          o.gene_count,
          o.occurrence_count
        {from_sql}
        {where_sql}
        ORDER BY {sort_column} {sort_direction}, o.operon_id ASC
        LIMIT ? OFFSET ?
        """,
        (*filter_params, PAGE_SIZE, offset),
    ).fetchall()
    items = []
    for row in rows:
        item = row_to_dict(row)
        item["display_id"] = format_stable_operon_id(item["operon_id"])
        item["pgfams"] = format_pgfam_signature(item["pgfam_signature"])
        item.pop("pgfam_signature", None)
        items.append(item)
    return {
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "sort": sort_key,
        "direction": sort_direction.lower(),
        "items": items,
    }


def organisms(conn):
    rows = conn.execute(
        """
        SELECT
          genome_key,
          organism_name
        FROM genomes
        ORDER BY organism_name, genome_key
        """
    ).fetchall()
    return {"items": [row_to_dict(row) for row in rows]}


def get_operon(conn, operon_id, page, filters):
    operon = conn.execute(
        """
        SELECT
          operon_id,
          pgfam_signature,
          gene_count,
          occurrence_count
        FROM operons
        WHERE operon_id = ?
        """,
        (operon_id,),
    ).fetchone()
    if operon is None:
        return None

    offset = (page - 1) * PAGE_SIZE
    where_clauses = ["occ.operon_id = ?"]
    params = [operon_id]
    if filters["product"] is not None:
        where_clauses.append(
            """
            EXISTS (
              SELECT 1
              FROM occurrence_genes og
              JOIN products p
                ON og.product_id = p.product_id
              WHERE og.occurrence_id = occ.occurrence_id
                AND p.product LIKE ? ESCAPE '\\'
            )
            """
        )
        params.append(like_contains_param(filters["product"]))
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    total = conn.execute(
        f"""
        SELECT COUNT(*) AS total
        FROM occurrences occ
        {where_sql}
        """,
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT
          occ.occurrence_id,
          occ.operon_id,
          occ.genome_key,
          occ.gene_count,
          g.genome_id,
          g.organism_name
        FROM occurrences occ
        JOIN genomes g
          ON occ.genome_key = g.genome_key
        {where_sql}
        ORDER BY occ.occurrence_id
        LIMIT ? OFFSET ?
        """,
        (*params, PAGE_SIZE, offset),
    ).fetchall()

    payload = row_to_dict(operon)
    payload["display_id"] = format_stable_operon_id(payload["operon_id"])
    payload["pgfams"] = format_pgfam_signature(payload["pgfam_signature"])
    payload.pop("pgfam_signature", None)
    payload["page"] = page
    payload["pageSize"] = PAGE_SIZE
    payload["total"] = total
    payload["product"] = filters["product"] or ""
    occurrences = []
    for row in rows:
        occurrence = row_to_dict(row)
        occurrence["display_id"] = format_occurrence_id(occurrence["occurrence_id"])
        occurrences.append(occurrence)
    payload["occurrences"] = occurrences
    payload["functional_summary"] = fetch_operon_functional_summary(conn, operon_id)
    return payload


def get_occurrence(conn, occurrence_id):
    occurrence = conn.execute(
        """
        SELECT
          occ.occurrence_id,
          occ.operon_id,
          occ.genome_key,
          g.genome_id,
          g.organism_name,
          occ.gene_count
        FROM occurrences occ
        JOIN genomes g
          ON occ.genome_key = g.genome_key
        WHERE occ.occurrence_id = ?
        """,
        (occurrence_id,),
    ).fetchone()
    if occurrence is None:
        return None

    genes = conn.execute(
        """
        SELECT
          og.occurrence_id,
          og.genome_key,
          og.peg_num,
          og.contig_id,
          c.contig_name,
          og.start,
          og.end,
          ABS(og.end - og.start) + 1 AS length,
          og.strand,
          og.product_id,
          p.product,
          og.pgfam_num
        FROM occurrence_genes og
        LEFT JOIN products p
          ON og.product_id = p.product_id
        LEFT JOIN contigs c
          ON og.contig_id = c.contig_id
        WHERE og.occurrence_id = ?
        ORDER BY og.contig_id, og.start
        """,
        (occurrence_id,),
    ).fetchall()

    pathways_by_gene = fetch_occurrence_pathways(conn, occurrence_id)
    subsystems_by_gene = fetch_occurrence_subsystems(conn, occurrence_id)

    payload = row_to_dict(occurrence)
    payload["stable_display_id"] = format_stable_operon_id(payload["operon_id"])
    payload["occurrence_display_id"] = format_occurrence_id(payload["occurrence_id"])
    payload["genes"] = []
    for row in genes:
        gene = row_to_dict(row)
        gene["gene_id"] = f"{payload['genome_id']}.peg.{gene['peg_num']}"
        gene["pgfam_display"] = format_pgfam(gene["pgfam_num"])
        key = gene_annotation_key(gene)
        gene["pathways"] = pathways_by_gene.get(key, [])
        gene["subsystems"] = subsystems_by_gene.get(key, [])
        payload["genes"].append(gene)
    return payload


def browse_genomes(conn, page, search):
    offset = (page - 1) * PAGE_SIZE
    where_sql = ""
    params = []
    if search is not None:
        where_sql = """
        WHERE genome_id LIKE ? ESCAPE '\\'
           OR organism_name LIKE ? ESCAPE '\\'
        """
        search_param = like_contains_param(search)
        params.extend([search_param, search_param])

    total = conn.execute(
        f"SELECT COUNT(*) FROM genomes {where_sql}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT
          gi.genome_key,
          gi.genome_id,
          gi.organism_name,
          (
            SELECT COUNT(*)
            FROM occurrences occ
            WHERE occ.genome_key = gi.genome_key
          ) AS operon_count,
          (
            SELECT COALESCE(SUM(occ.gene_count), 0)
            FROM occurrences occ
            WHERE occ.genome_key = gi.genome_key
          ) AS gene_count
        FROM genomes gi
        {where_sql}
        ORDER BY gi.genome_key
        LIMIT ? OFFSET ?
        """,
        (*params, PAGE_SIZE, offset),
    ).fetchall()
    return {
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "search": search or "",
        "items": [row_to_dict(row) for row in rows],
    }


def get_genome(conn, genome_key):
    genome = conn.execute(
        """
        SELECT
          genome_key,
          genome_id,
          organism_name
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    ).fetchone()
    if genome is None:
        return None

    operon_count = conn.execute(
        """
        SELECT COUNT(*) AS operon_count
        FROM occurrences
        WHERE genome_key = ?
        """,
        (genome_key,),
    ).fetchone()[0]
    gene_count = conn.execute(
        """
        SELECT COALESCE(SUM(gene_count), 0) AS gene_count
        FROM occurrences
        WHERE genome_key = ?
        """,
        (genome_key,),
    ).fetchone()[0]

    payload = row_to_dict(genome)
    payload["operon_count"] = operon_count
    payload["gene_count"] = gene_count
    return payload


def build_genome_viewer_payload(genome, contig_rows, gene_rows):
    payload = row_to_dict(genome)
    contigs = []
    contig_lookup = {}
    contig_order = {}
    for index, row in enumerate(contig_rows, start=1):
        contig = row_to_dict(row)
        item = {
            "contig_id": contig["contig_id"],
            "contig_name": contig["contig_name"],
            "order": index,
            "coordinate_end": 1,
            "occurrences": [],
        }
        contigs.append(item)
        contig_lookup[item["contig_id"]] = item
        contig_order[item["contig_id"]] = index

    occurrence_genes = {}
    for row in gene_rows:
        gene = row_to_dict(row)
        occurrence_genes.setdefault(gene["occurrence_id"], []).append(gene)

    ordered_occurrences = []
    for occurrence_id, genes in occurrence_genes.items():
        genes.sort(
            key=lambda gene: (
                contig_order.get(gene["contig_id"], 0),
                gene["gene_start"],
                gene["gene_end"],
                gene["peg_num"],
            )
        )
        first_gene = genes[0]
        segment = {
            "occurrence_id": occurrence_id,
            "occurrence_display_id": format_occurrence_id(occurrence_id),
            "operon_id": first_gene["operon_id"],
            "stable_display_id": format_stable_operon_id(first_gene["operon_id"]),
            "contig_id": first_gene["contig_id"],
            "start": min(gene["gene_start"] for gene in genes),
            "end": max(gene["gene_end"] for gene in genes),
        }

        contig = contig_lookup.get(segment["contig_id"])
        if contig is None:
            continue
        contig["coordinate_end"] = max(contig["coordinate_end"], segment["end"])
        contig["occurrences"].append(segment)

        ordered_occurrences.append(
            {
                "occurrence_id": occurrence_id,
                "occurrence_display_id": format_occurrence_id(occurrence_id),
                "operon_id": segment["operon_id"],
                "stable_display_id": segment["stable_display_id"],
                "contig_id": segment["contig_id"],
                "order": contig_order.get(segment["contig_id"], 0),
                "start": segment["start"],
                "end": segment["end"],
            }
        )

    for contig in contigs:
        contig["occurrences"].sort(
            key=lambda occurrence: (
                occurrence["start"],
                occurrence["end"],
                occurrence["occurrence_id"],
            )
        )
    ordered_occurrences.sort(
        key=lambda occurrence: (
            occurrence["order"],
            occurrence["start"],
            occurrence["end"],
            occurrence["occurrence_id"],
        )
    )
    for index, occurrence in enumerate(ordered_occurrences, start=1):
        occurrence["index"] = index

    payload["total_contigs"] = len(contigs)
    payload["total_occurrences"] = len(ordered_occurrences)
    payload["ordered_occurrences"] = ordered_occurrences
    payload["contigs"] = contigs
    return payload


def get_genome_viewer(conn, genome_key, filters):
    genome = conn.execute(
        """
        SELECT
          genome_key,
          genome_id,
          organism_name
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    ).fetchone()
    if genome is None:
        return None

    contigs = conn.execute(
        """
        SELECT
          c.contig_id,
          c.contig_name
        FROM contigs c
        WHERE c.genome_id = ?
        ORDER BY c.contig_id
        """,
        (genome["genome_id"],),
    ).fetchall()
    ctes = []
    joins = []
    params = []
    if filters["product"] is not None:
        ctes.extend(product_filter_ctes())
        joins.append(
            "JOIN matching_products mp ON mp.operon_id = o.operon_id"
        )
        params.append(like_contains_param(filters["product"]))
    with_sql = f"WITH {', '.join(ctes)}" if ctes else ""
    join_sql = "\n".join(joins)
    where_clauses = ["og.genome_key = ?"]
    params.append(genome_key)
    if filters["min_gene_count"] > MIN_GENE_COUNT:
        where_clauses.append("o.gene_count >= ?")
        params.append(filters["min_gene_count"])
    if filters["max_gene_count"] < MAX_GENE_COUNT:
        where_clauses.append("o.gene_count <= ?")
        params.append(filters["max_gene_count"])
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    genes = conn.execute(
        f"""
        {with_sql}
        SELECT
          og.occurrence_id,
          occ.operon_id,
          occ.gene_count AS occurrence_gene_count,
          og.peg_num,
          og.contig_id,
          CASE
            WHEN og.start <= og.end THEN og.start
            ELSE og.end
          END AS gene_start,
          CASE
            WHEN og.start <= og.end THEN og.end
            ELSE og.start
          END AS gene_end
        FROM occurrence_genes og
        JOIN occurrences occ
          ON og.occurrence_id = occ.occurrence_id
        JOIN operons o
          ON occ.operon_id = o.operon_id
        {join_sql}
        {where_sql}
        ORDER BY og.occurrence_id, og.contig_id, gene_start, og.peg_num
        """,
        params,
    ).fetchall()

    return build_genome_viewer_payload(genome, contigs, genes)


def genome_operons(conn, genome_key, page, sort, filters):
    genome = conn.execute(
        """
        SELECT
          genome_key,
          genome_id,
          organism_name
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    ).fetchone()
    if genome is None:
        return None

    offset = (page - 1) * PAGE_SIZE
    sort_key, sort_column, sort_direction = sort
    ctes = []
    joins = []
    filter_params = []
    if filters["product"] is not None:
        ctes.extend(product_filter_ctes())
        joins.append(
            "JOIN matching_products mp ON mp.operon_id = o.operon_id"
        )
        filter_params.append(like_contains_param(filters["product"]))
    with_sql = f"WITH {', '.join(ctes)}" if ctes else ""
    from_sql = """
        FROM occurrences occ
        JOIN operons o
          ON occ.operon_id = o.operon_id
    """
    if joins:
        from_sql = f"{from_sql}\n" + "\n".join(joins)
    where_clauses = ["occ.genome_key = ?"]
    params = [*filter_params, genome_key]
    if filters["min_gene_count"] > MIN_GENE_COUNT:
        where_clauses.append("o.gene_count >= ?")
        params.append(filters["min_gene_count"])
    if filters["max_gene_count"] < MAX_GENE_COUNT:
        where_clauses.append("o.gene_count <= ?")
        params.append(filters["max_gene_count"])
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    total = conn.execute(
        f"""
        {with_sql}
        SELECT COUNT(*) AS total
        {from_sql}
        {where_sql}
        """,
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        {with_sql}
        SELECT
          occ.occurrence_id,
          occ.operon_id,
          occ.gene_count AS occurrence_gene_count,
          o.gene_count,
          o.occurrence_count,
          o.pgfam_signature
        {from_sql}
        {where_sql}
        ORDER BY {sort_column} {sort_direction}, occ.occurrence_id ASC
        LIMIT ? OFFSET ?
        """,
        (*params, PAGE_SIZE, offset),
    ).fetchall()

    payload = row_to_dict(genome)
    payload["page"] = page
    payload["pageSize"] = PAGE_SIZE
    payload["total"] = total
    payload["sort"] = sort_key
    payload["direction"] = sort_direction.lower()
    payload["min_gene_count"] = filters["min_gene_count"]
    payload["max_gene_count"] = filters["max_gene_count"]
    payload["product"] = filters["product"] or ""
    items = []
    for row in rows:
        item = row_to_dict(row)
        item["display_id"] = format_stable_operon_id(item["operon_id"])
        item["occurrence_display_id"] = format_occurrence_id(item["occurrence_id"])
        item.pop("pgfam_signature", None)
        items.append(item)
    payload["items"] = items
    return payload


class OperonAtlasHandler(BaseHTTPRequestHandler):
    server_version = "OperonAtlasLocalAPI/0.1"

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path_parts = [part for part in parsed.path.split("/") if part]

        if path_parts == ["api", "health"]:
            self.send_json(200, {"ok": True})
            return

        if not DB_PATH.exists():
            self.send_json(
                500,
                {
                    "error": "Database file not found",
                    "db_path": str(DB_PATH),
                },
            )
            return

        try:
            with connect_db() as conn:
                payload, status = self.route(conn, path_parts, parsed.query)
        except sqlite3.Error as exc:
            self.send_json(500, {"error": "Database error", "detail": str(exc)})
            return

        self.send_json(status, payload)

    def route(self, conn, path_parts, query):
        page = parse_page(query)

        if path_parts == ["api", "stats"]:
            return stats(conn), 200

        if path_parts == ["api", "organisms"]:
            return organisms(conn), 200

        if path_parts == ["api", "operons"]:
            return browse_operons(
                conn,
                page,
                parse_operon_filters(query),
                parse_operon_sort(query),
            ), 200

        if len(path_parts) == 3 and path_parts[:2] == ["api", "operons"]:
            operon_id = parse_int(path_parts[2])
            if operon_id is None:
                return {"error": "Invalid operon_id"}, 400
            payload = get_operon(conn, operon_id, page, parse_occurrence_filters(query))
            if payload is None:
                return {"error": "Stable operon not found"}, 404
            return payload, 200

        if len(path_parts) == 3 and path_parts[:2] == ["api", "occurrences"]:
            occurrence_id = parse_int(path_parts[2])
            if occurrence_id is None:
                return {"error": "Invalid occurrence_id"}, 400
            payload = get_occurrence(conn, occurrence_id)
            if payload is None:
                return {"error": "Occurrence not found"}, 404
            return payload, 200

        if path_parts == ["api", "genomes"]:
            return browse_genomes(conn, page, parse_genome_search(query)), 200

        if len(path_parts) == 3 and path_parts[:2] == ["api", "genomes"]:
            genome_key = parse_int(path_parts[2])
            if genome_key is None:
                return {"error": "Invalid genome_key"}, 400
            payload = get_genome(conn, genome_key)
            if payload is None:
                return {"error": "Genome not found"}, 404
            return payload, 200

        if (
            len(path_parts) == 4
            and path_parts[:2] == ["api", "genomes"]
            and path_parts[3] == "viewer"
        ):
            genome_key = parse_int(path_parts[2])
            if genome_key is None:
                return {"error": "Invalid genome_key"}, 400
            payload = get_genome_viewer(conn, genome_key, parse_operon_filters(query))
            if payload is None:
                return {"error": "Genome not found"}, 404
            return payload, 200

        if (
            len(path_parts) == 4
            and path_parts[:2] == ["api", "genomes"]
            and path_parts[3] == "operons"
        ):
            genome_key = parse_int(path_parts[2])
            if genome_key is None:
                return {"error": "Invalid genome_key"}, 400
            payload = genome_operons(
                conn,
                genome_key,
                page,
                parse_operon_sort(query),
                parse_operon_filters(query),
            )
            if payload is None:
                return {"error": "Genome not found"}, 404
            return payload, 200

        return {"error": "Not found"}, 404

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8787"))
    server = ThreadingHTTPServer((host, port), OperonAtlasHandler)
    print(f"OperonAtlas local API listening on http://{host}:{port}")
    print(f"Using database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
