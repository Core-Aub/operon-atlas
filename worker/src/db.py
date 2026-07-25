PAGE_SIZE = 20
MIN_GENE_COUNT = 1
MAX_GENE_COUNT = 10000
MAX_SEARCH_TEXT_LENGTH = 120

# Family-summary display thresholds.
FAMILY_FUNCTION_OCCURRENCE_SUPPORT_MIN = 0.20
FAMILY_FUNCTION_AVG_GENE_SHARE_MIN = 0.05
FAMILY_FUNCTION_STRONG_SUPPORT_MIN = 0.20
FAMILY_FUNCTION_DISPLAY_LIMIT = 3

# Occurrence-summary display thresholds.
OCCURRENCE_FUNCTION_GENE_SHARE_MIN = 0.25
OCCURRENCE_FUNCTION_MIN_SUPPORTING_GENES = 2
OCCURRENCE_FUNCTION_DISPLAY_LIMIT = 3


def parse_page(query):
    value = query.get("page", ["1"])[0]
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


def first_query_value(query, *names):
    for name in names:
        value = query.get(name, [None])[0]
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
    min_gene_count = parse_int(first_query_value(query, "min_genes", "min_gene_count"))
    max_gene_count = parse_int(first_query_value(query, "max_genes", "max_gene_count"))
    genome_key = parse_int(query.get("genome_key", [None])[0])
    organism = normalize_search_text(first_query_value(query, "organism", "organism_name"))
    product = normalize_search_text(query.get("product", [None])[0])

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
    return normalize_search_text(query.get("search", [None])[0])


def parse_occurrence_filters(query):
    return {
        "product": normalize_search_text(query.get("product", [None])[0]),
    }


def parse_operon_sort(query):
    sort = query.get("sort", ["occurrence_count"])[0]
    direction = query.get("direction", ["desc"])[0].lower()
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
    if row is None:
        return None
    if hasattr(row, "to_py"):
        row = row.to_py()
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "items"):
        return dict(row.items())
    return {key: getattr(row, key) for key in dir(row) if not key.startswith("_")}


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


async def fetch_occurrence_pathways(db, occurrence_id):
    rows = await run_all(
        db,
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
    )

    pathways_by_gene = {}
    seen_by_gene = {}
    for row in rows:
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


async def fetch_occurrence_subsystems(db, occurrence_id):
    rows = await run_all(
        db,
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
    )

    subsystems_by_gene = {}
    seen_by_gene = {}
    for row in rows:
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


async def run_all(db, sql, params=()):
    statement = db.prepare(sql)
    if params:
        statement = statement.bind(*params)
    result = await statement.run()
    rows = getattr(result, "results", [])
    if hasattr(rows, "to_py"):
        rows = rows.to_py()
    return [row_to_dict(row) for row in rows]


async def run_first(db, sql, params=()):
    rows = await run_all(db, sql, params)
    return rows[0] if rows else None


async def run_scalar(db, sql, params=()):
    row = await run_first(db, sql, params)
    if row is None:
        return 0
    return next(iter(row.values()))


async def fetch_operon_functional_summary(db, operon_id):
    coverage = await run_first(
        db,
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
    )

    subsystems = await run_all(
        db,
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
    )

    pathways = await run_all(
        db,
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
    )

    return {
        "coverage": coverage,
        "subsystems": subsystems,
        "pathways": pathways,
    }


async def stats(db):
    return {
        "genomes": await run_scalar(db, "SELECT COUNT(*) AS count FROM genomes"),
        "operons": await run_scalar(db, "SELECT COUNT(*) AS count FROM operons"),
        "occurrences": await run_scalar(db, "SELECT COUNT(*) AS count FROM occurrences"),
        "occurrence_genes": await run_scalar(db, "SELECT COUNT(*) AS count FROM occurrence_genes"),
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


async def browse_operons(db, page, filters, sort):
    offset = (page - 1) * PAGE_SIZE
    with_sql, from_sql, where_sql, filter_params = operon_query_parts(filters)
    sort_key, sort_column, sort_direction = sort
    total = await run_scalar(
        db,
        f"""
        {with_sql}
        SELECT COUNT(*) AS count
        {from_sql}
        {where_sql}
        """,
        tuple(filter_params),
    )
    items = await run_all(
        db,
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
    )
    for item in items:
        item["display_id"] = format_stable_operon_id(item["operon_id"])
        item["pgfams"] = format_pgfam_signature(item["pgfam_signature"])
        item.pop("pgfam_signature", None)
    return {
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "sort": sort_key,
        "direction": sort_direction.lower(),
        "items": items,
    }


async def organisms(db):
    items = await run_all(
        db,
        """
        SELECT
          genome_key,
          organism_name
        FROM genomes
        ORDER BY organism_name, genome_key
        """,
    )
    return {"items": items}


async def get_operon(db, operon_id, page, filters):
    operon = await run_first(
        db,
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
    )
    if operon is None:
        return None

    where_clauses = ["occ.operon_id = ?"]
    query_params = [operon_id]
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
        query_params.append(like_contains_param(filters["product"]))
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    total = await run_scalar(
        db,
        f"""
        SELECT COUNT(*) AS total
        FROM occurrences occ
        {where_sql}
        """,
        tuple(query_params),
    )
    offset = (page - 1) * PAGE_SIZE
    occurrences = await run_all(
        db,
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
        (*query_params, PAGE_SIZE, offset),
    )

    operon["display_id"] = format_stable_operon_id(operon["operon_id"])
    operon["pgfams"] = format_pgfam_signature(operon["pgfam_signature"])
    operon.pop("pgfam_signature", None)
    operon["page"] = page
    operon["pageSize"] = PAGE_SIZE
    operon["total"] = total
    operon["product"] = filters["product"] or ""
    for occurrence in occurrences:
        occurrence["display_id"] = format_occurrence_id(occurrence["occurrence_id"])
    operon["occurrences"] = occurrences
    operon["functional_summary"] = await fetch_operon_functional_summary(db, operon_id)
    return operon


async def get_occurrence(db, occurrence_id):
    occurrence = await run_first(
        db,
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
    )
    if occurrence is None:
        return None

    rows = await run_all(
        db,
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
    )

    pathways_by_gene = await fetch_occurrence_pathways(db, occurrence_id)
    subsystems_by_gene = await fetch_occurrence_subsystems(db, occurrence_id)

    genes = []
    for row in rows:
        row["gene_id"] = f"{occurrence['genome_id']}.peg.{row['peg_num']}"
        row["pgfam_display"] = format_pgfam(row["pgfam_num"])
        key = gene_annotation_key(row)
        row["pathways"] = pathways_by_gene.get(key, [])
        row["subsystems"] = subsystems_by_gene.get(key, [])
        genes.append(row)

    occurrence["stable_display_id"] = format_stable_operon_id(occurrence["operon_id"])
    occurrence["occurrence_display_id"] = format_occurrence_id(occurrence["occurrence_id"])
    occurrence["genes"] = genes
    return occurrence


async def browse_genomes(db, page, search):
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

    total = await run_scalar(
        db,
        f"SELECT COUNT(*) AS count FROM genomes {where_sql}",
        tuple(params),
    )
    items = await run_all(
        db,
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
    )
    return {
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "search": search or "",
        "items": items,
    }


async def get_genome(db, genome_key):
    genome = await run_first(
        db,
        """
        SELECT
          genome_key,
          genome_id,
          organism_name
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    )
    if genome is None:
        return None

    genome["operon_count"] = await run_scalar(
        db,
        """
        SELECT COUNT(*) AS operon_count
        FROM occurrences
        WHERE genome_key = ?
        """,
        (genome_key,),
    )
    genome["gene_count"] = await run_scalar(
        db,
        """
        SELECT COALESCE(SUM(gene_count), 0) AS gene_count
        FROM occurrences
        WHERE genome_key = ?
        """,
        (genome_key,),
    )
    return genome


def build_genome_viewer_payload(genome, contig_rows, gene_rows):
    contigs = []
    contig_lookup = {}
    contig_order = {}
    for index, contig in enumerate(contig_rows, start=1):
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
    for gene in gene_rows:
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

    genome["total_contigs"] = len(contigs)
    genome["total_occurrences"] = len(ordered_occurrences)
    genome["ordered_occurrences"] = ordered_occurrences
    genome["contigs"] = contigs
    return genome


async def get_genome_viewer(db, genome_key, filters):
    genome = await run_first(
        db,
        """
        SELECT
          genome_key,
          genome_id,
          organism_name
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    )
    if genome is None:
        return None

    contigs = await run_all(
        db,
        """
        SELECT
          c.contig_id,
          c.contig_name
        FROM contigs c
        WHERE c.genome_id = ?
        ORDER BY c.contig_id
        """,
        (genome["genome_id"],),
    )
    ctes = []
    joins = []
    query_params = []
    if filters["product"] is not None:
        ctes.extend(product_filter_ctes())
        joins.append(
            "JOIN matching_products mp ON mp.operon_id = o.operon_id"
        )
        query_params.append(like_contains_param(filters["product"]))
    with_sql = f"WITH {', '.join(ctes)}" if ctes else ""
    join_sql = "\n".join(joins)
    where_clauses = ["og.genome_key = ?"]
    query_params.append(genome_key)
    if filters["min_gene_count"] > MIN_GENE_COUNT:
        where_clauses.append("o.gene_count >= ?")
        query_params.append(filters["min_gene_count"])
    if filters["max_gene_count"] < MAX_GENE_COUNT:
        where_clauses.append("o.gene_count <= ?")
        query_params.append(filters["max_gene_count"])
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    genes = await run_all(
        db,
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
        tuple(query_params),
    )

    return build_genome_viewer_payload(genome, contigs, genes)


async def genome_operons(db, genome_key, page, sort, filters):
    genome = await run_first(
        db,
        """
        SELECT
          genome_key,
          genome_id,
          organism_name
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    )
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
    query_params = [*filter_params, genome_key]
    if filters["min_gene_count"] > MIN_GENE_COUNT:
        where_clauses.append("o.gene_count >= ?")
        query_params.append(filters["min_gene_count"])
    if filters["max_gene_count"] < MAX_GENE_COUNT:
        where_clauses.append("o.gene_count <= ?")
        query_params.append(filters["max_gene_count"])
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    total = await run_scalar(
        db,
        f"""
        {with_sql}
        SELECT COUNT(*) AS total
        {from_sql}
        {where_sql}
        """,
        tuple(query_params),
    )
    items = await run_all(
        db,
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
        (*query_params, PAGE_SIZE, offset),
    )
    for item in items:
        item["display_id"] = format_stable_operon_id(item["operon_id"])
        item["occurrence_display_id"] = format_occurrence_id(item["occurrence_id"])
        item.pop("pgfam_signature", None)
    genome["page"] = page
    genome["pageSize"] = PAGE_SIZE
    genome["total"] = total
    genome["sort"] = sort_key
    genome["direction"] = sort_direction.lower()
    genome["min_gene_count"] = filters["min_gene_count"]
    genome["max_gene_count"] = filters["max_gene_count"]
    genome["product"] = filters["product"] or ""
    genome["items"] = items
    return genome
