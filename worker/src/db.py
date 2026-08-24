import re


PAGE_SIZE = 20
TAXONOMY_PAGE_SIZE = 5
SEARCH_PREVIEW_SIZE = 5
MIN_GENE_COUNT = 1
MAX_GENE_COUNT = 10000
MAX_SEARCH_TEXT_LENGTH = 120
MAX_SEARCH_TOKENS = 8
MAX_D1_LIKE_PATTERN_BYTES = 50

SEARCH_ENTITY_TYPE_LABELS = {
    "product": "Products",
    "pgfam": "PGFams",
    "ec": "EC numbers",
    "pathway": "Pathways",
    "pathway_class": "Pathway classes",
    "subsystem": "Subsystems",
    "subsystem_class": "Subsystem classes",
    "role": "Subsystem roles",
    "genome": "Genomes",
    "species": "Species",
    "genus": "Genera",
    "phylum": "Phyla",
}
SEARCH_ENTITY_TYPES = tuple(SEARCH_ENTITY_TYPE_LABELS)
CATALOG_ENTITY_TYPES = {
    "product",
    "pgfam",
    "ec",
    "pathway",
    "pathway_class",
    "subsystem",
    "subsystem_class",
    "role",
}

STABLE_OPERON_PATTERN = re.compile(r"^OAF(\d+)$", re.IGNORECASE)
OCCURRENCE_PATTERN = re.compile(r"^OAO(\d+)$", re.IGNORECASE)
GENE_PATTERN = re.compile(r"^(?:fig\|)?(.+)\.peg\.(\d+)$", re.IGNORECASE)
PGFAM_PATTERN = re.compile(r"^PGF[_-]?(\d{1,8})$", re.IGNORECASE)
PATRIC_FEATURE_PATTERN = re.compile(
    r"^PATRIC\.([0-9]+\.[0-9]+)\.(.+)\.CDS\."
    r"(\d+)\.(\d+)\.(fwd|rev)$",
    re.IGNORECASE,
)


class ValidationError(Exception):
    pass

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


def validate_like_pattern(pattern, field_name="Search term"):
    if len(pattern.encode("utf-8")) > MAX_D1_LIKE_PATTERN_BYTES:
        raise ValidationError(
            f"{field_name} is too long for substring matching; "
            f"each term must produce at most {MAX_D1_LIKE_PATTERN_BYTES} UTF-8 bytes"
        )
    return pattern


def normalize_like_search_text(value, field_name="Search term"):
    normalized = normalize_search_text(value)
    if normalized is not None:
        validate_like_pattern(like_contains_param(normalized), field_name)
    return normalized


def parse_search_terms(value, required=False):
    normalized = normalize_search_text(value)
    if normalized is None:
        if required:
            raise ValidationError("Search query is required")
        return None, [], []
    if len(normalized) < 2:
        raise ValidationError("Search query must contain at least 2 characters")

    tokens = normalized.lower().split()
    if len(tokens) > MAX_SEARCH_TOKENS:
        raise ValidationError(
            f"Search query may contain at most {MAX_SEARCH_TOKENS} terms"
        )
    patterns = [
        validate_like_pattern(like_contains_param(token))
        for token in tokens
    ]
    return normalized, tokens, patterns


def parse_entity_filter(query):
    entity_type = first_query_value(query, "entity_type")
    entity_key_value = first_query_value(query, "entity_key")
    if entity_type is None and entity_key_value is None:
        return None
    if entity_type is None or entity_key_value is None:
        raise ValidationError("entity_type and entity_key must be provided together")

    entity_type = str(entity_type).strip().lower()
    if entity_type not in SEARCH_ENTITY_TYPE_LABELS:
        raise ValidationError("Invalid entity_type")
    entity_key = parse_int(entity_key_value)
    if entity_key is None or entity_key <= 0:
        raise ValidationError("Invalid entity_key")
    return {"type": entity_type, "key": entity_key}


def parse_search_request(query):
    raw_value = first_query_value(query, "q", "search")
    normalized = normalize_search_text(raw_value)
    if normalized is None:
        raise ValidationError("Search query is required")
    if len(normalized) < 2:
        raise ValidationError("Search query must contain at least 2 characters")
    is_direct_identifier = any(pattern.fullmatch(normalized) for pattern in (
        STABLE_OPERON_PATTERN,
        OCCURRENCE_PATTERN,
        GENE_PATTERN,
        PGFAM_PATTERN,
        PATRIC_FEATURE_PATTERN,
    ))
    if is_direct_identifier:
        tokens, patterns = [], []
    else:
        _, tokens, patterns = parse_search_terms(normalized, required=True)
    entity_type = first_query_value(query, "type", "entity_type")
    if entity_type is not None:
        entity_type = str(entity_type).strip().lower()
        if entity_type not in SEARCH_ENTITY_TYPE_LABELS:
            raise ValidationError("Invalid search type")
    return {
        "q": normalized,
        "tokens": tokens,
        "patterns": patterns,
        "type": entity_type,
    }


def parse_gene_highlight(query):
    value = normalize_search_text(first_query_value(query, "gene", "gene_id"))
    if value is None:
        return None
    match = GENE_PATTERN.fullmatch(value)
    if match is None:
        raise ValidationError("Invalid gene ID")
    return f"{match.group(1)}.peg.{int(match.group(2))}"


def parse_operon_filters(query):
    min_gene_count = parse_int(first_query_value(query, "min_genes", "min_gene_count"))
    max_gene_count = parse_int(first_query_value(query, "max_genes", "max_gene_count"))
    genome_key = parse_int(query.get("genome_key", [None])[0])
    organism = normalize_like_search_text(
        first_query_value(query, "organism", "organism_name"),
        "Organism filter",
    )
    product = normalize_like_search_text(
        query.get("product", [None])[0],
        "Product filter",
    )
    search, search_tokens, search_patterns = parse_search_terms(
        query.get("search", [None])[0]
    )

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
        "search": search,
        "search_tokens": search_tokens,
        "search_patterns": search_patterns,
        "entity": parse_entity_filter(query),
    }


def parse_genome_search(query):
    return normalize_like_search_text(
        query.get("search", [None])[0],
        "Genome search",
    )


def parse_genome_sort(query):
    sort = query.get("sort", ["genome_id"])[0]
    direction = query.get("direction", ["asc"])[0].lower()
    sort_columns = {
        "genome_id": "gi.genome_id COLLATE NOCASE",
        "organism_name": "gi.organism_name COLLATE NOCASE",
        "operon_count": "operon_count",
        "gene_count": "gene_count",
    }
    if sort not in sort_columns:
        sort = "genome_id"
    if direction not in {"asc", "desc"}:
        direction = "asc"
    return sort, sort_columns[sort], direction.upper()


def parse_occurrence_filters(query):
    search, search_tokens, search_patterns = parse_search_terms(
        query.get("search", [None])[0]
    )
    return {
        "product": normalize_like_search_text(
            query.get("product", [None])[0],
            "Product filter",
        ),
        "search": search,
        "search_tokens": search_tokens,
        "search_patterns": search_patterns,
        "entity": parse_entity_filter(query),
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


async def fetch_occurrence_pathways(db, occurrence_id):
    rows = await run_all(
        db,
        """
        SELECT
          og.gene_key,
          e.ec_number,
          e.ec_description,
          pr.pathway_id,
          pr.pathway_name,
          pc.pathway_class
        FROM occurrence_genes AS og
        JOIN gene_pathways AS gp
          ON gp.gene_key = og.gene_key
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
        key = int(row["gene_key"])
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
          og.gene_key,
          sr.role_id,
          sr.role_name,
          sref.subsystem_id,
          sref.subsystem_name,
          sc.subsystem_superclass,
          sc.subsystem_class,
          sc.subsystem_subclass
        FROM occurrence_genes AS og
        JOIN gene_subsystems AS gs
          ON gs.gene_key = og.gene_key
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
        key = int(row["gene_key"])
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


def looks_like_pgfam_query(value):
    return str(value).lower().startswith("pgf")


def search_entity_source_sql(pgfam_only=False, include_pgfam=False):
    return """
        SELECT
          entity_type,
          entity_key,
          identifier,
          label,
          context,
          search_text
        FROM search_entities
    """


def matched_entities_cte(search):
    if looks_like_pgfam_query(search["q"]):
        match = PGFAM_PATTERN.fullmatch(search["q"])
        if match is None:
            return (
                """
                matched_entities AS (
                  SELECT
                    'pgfam' AS entity_type,
                    0 AS entity_key,
                    '' AS identifier,
                    '' AS label,
                    'PGFam' AS context
                  WHERE 0
                )
                """,
                [],
            )
        pgfam_num = int(match.group(1))
        return (
            """
            pgfam_candidate(entity_key) AS (
              VALUES (?)
            ),
            matched_entities AS (
              SELECT
                'pgfam' AS entity_type,
                entity_key,
                PRINTF('PGF_%08d', entity_key) AS identifier,
                PRINTF('PGF_%08d', entity_key) AS label,
                'PGFam' AS context
              FROM pgfam_candidate
              WHERE EXISTS (
                SELECT 1
                FROM operon_pgfams opg
                WHERE opg.pgfam_num = pgfam_candidate.entity_key
              )
            )
            """,
            [pgfam_num],
        )

    if not search["patterns"]:
        return (
            """
            matched_entities AS (
              SELECT entity_type, entity_key, identifier, label, context
              FROM search_entities
              WHERE 0
            )
            """,
            [],
        )

    conditions = " AND ".join(
        "search_text LIKE ? ESCAPE '\\'" for _ in search["patterns"]
    )
    return (
        f"""
        search_source AS (
          {search_entity_source_sql()}
        ),
        matched_entities AS (
          SELECT
            entity_type,
            entity_key,
            identifier,
            label,
            context
          FROM search_source
          WHERE {conditions}
        )
        """,
        list(search["patterns"]),
    )


def entity_type_order_sql(column="entity_type"):
    clauses = " ".join(
        f"WHEN '{entity_type}' THEN {index}"
        for index, entity_type in enumerate(SEARCH_ENTITY_TYPES)
    )
    return f"CASE {column} {clauses} ELSE {len(SEARCH_ENTITY_TYPES)} END"


def entity_match_rank_sql():
    return """
    CASE
      WHEN identifier = ? COLLATE NOCASE
        OR label = ? COLLATE NOCASE
        THEN 0
      WHEN INSTR(LOWER(identifier), LOWER(?)) = 1
        OR INSTR(LOWER(label), LOWER(?)) = 1
        THEN 1
      ELSE 2
    END
    """


def serialize_search_entity(row):
    return {
        "type": row["entity_type"],
        "key": int(row["entity_key"]),
        "identifier": row["identifier"],
        "label": row["label"],
        "context": row.get("context"),
    }


async def fetch_search_entity(db, entity_type, entity_key):
    row = await run_first(
        db,
        f"""
        SELECT
          entity_type,
          entity_key,
          identifier,
          label,
          context
        FROM (
          {search_entity_source_sql(include_pgfam=True)}
        )
        WHERE entity_type = ?
          AND entity_key = ?
        LIMIT 1
        """,
        (entity_type, entity_key),
    )
    if row is not None:
        return serialize_search_entity(row)

    identifier = (
        format_pgfam(entity_key)
        if entity_type == "pgfam"
        else str(entity_key)
    )
    return {
        "type": entity_type,
        "key": entity_key,
        "identifier": identifier,
        "label": identifier,
        "context": None,
    }


async def fetch_direct_search_hits(db, query_text):
    hits = []

    stable_match = STABLE_OPERON_PATTERN.fullmatch(query_text)
    if stable_match is not None:
        operon_id = int(stable_match.group(1))
        if await run_scalar(
            db,
            "SELECT COUNT(*) AS count FROM operons WHERE operon_id = ?",
            (operon_id,),
        ):
            display_id = format_stable_operon_id(operon_id)
            hits.append({
                "kind": "operon",
                "type": "operon",
                "key": operon_id,
                "identifier": display_id,
                "label": f"Operon family {display_id}",
                "context": "Operon family",
                "operonId": operon_id,
            })

    occurrence_match = OCCURRENCE_PATTERN.fullmatch(query_text)
    if occurrence_match is not None:
        occurrence_id = int(occurrence_match.group(1))
        if await run_scalar(
            db,
            "SELECT COUNT(*) AS count FROM occurrences WHERE occurrence_id = ?",
            (occurrence_id,),
        ):
            display_id = format_occurrence_id(occurrence_id)
            hits.append({
                "kind": "occurrence",
                "type": "occurrence",
                "key": occurrence_id,
                "identifier": display_id,
                "label": f"Operon occurrence {display_id}",
                "context": "Operon occurrence",
                "occurrenceId": occurrence_id,
            })

    gene_match = GENE_PATTERN.fullmatch(query_text)
    if gene_match is not None:
        genome_id = gene_match.group(1)
        peg_num = int(gene_match.group(2))
        gene_rows = await run_all(
            db,
            """
            SELECT
              og.occurrence_id,
              occ.operon_id,
              g.genome_key,
              g.genome_id,
              g.organism_name
            FROM genomes g
            JOIN occurrence_genes og
              ON og.genome_key = g.genome_key
            JOIN occurrences occ
              ON occ.occurrence_id = og.occurrence_id
            WHERE g.genome_id = ?
              AND og.peg_num = ?
            ORDER BY og.occurrence_id
            """,
            (genome_id, peg_num),
        )
        canonical_gene_id = f"{genome_id}.peg.{peg_num}"
        for row in gene_rows:
            hits.append({
                "kind": "gene",
                "type": "gene",
                "key": canonical_gene_id,
                "identifier": canonical_gene_id,
                "label": canonical_gene_id,
                "context": row.get("organism_name"),
                "geneId": canonical_gene_id,
                "occurrenceId": int(row["occurrence_id"]),
                "operonId": int(row["operon_id"]),
                "genomeKey": int(row["genome_key"]),
            })

    feature_match = PATRIC_FEATURE_PATTERN.fullmatch(query_text)
    if feature_match is not None:
        genome_id = feature_match.group(1)
        contig_name = feature_match.group(2)
        gene_start = int(feature_match.group(3))
        gene_end = int(feature_match.group(4))
        strand = 1 if feature_match.group(5).lower() == "fwd" else -1
        feature_rows = await run_all(
            db,
            """
            SELECT
              og.occurrence_id,
              occ.operon_id,
              og.peg_num,
              g.genome_key,
              g.genome_id,
              g.organism_name
            FROM genomes g
            JOIN contigs c
              ON c.genome_id = g.genome_id
            JOIN occurrence_genes og
              ON og.genome_key = g.genome_key
             AND og.contig_id = c.contig_id
             AND og.start = ?
            JOIN occurrences occ
              ON occ.occurrence_id = og.occurrence_id
            WHERE g.genome_id = ?
              AND c.contig_name = ?
              AND og.end = ?
              AND og.strand = ?
            ORDER BY og.occurrence_id
            """,
            (gene_start, genome_id, contig_name, gene_end, strand),
        )
        for row in feature_rows:
            canonical_gene_id = (
                f"{row['genome_id']}.peg.{int(row['peg_num'])}"
            )
            hits.append({
                "kind": "gene",
                "type": "gene",
                "key": canonical_gene_id,
                "identifier": query_text,
                "label": canonical_gene_id,
                "context": row.get("organism_name"),
                "geneId": canonical_gene_id,
                "occurrenceId": int(row["occurrence_id"]),
                "operonId": int(row["operon_id"]),
                "genomeKey": int(row["genome_key"]),
            })

    pgfam_match = PGFAM_PATTERN.fullmatch(query_text)
    if pgfam_match is not None:
        pgfam_num = int(pgfam_match.group(1))
        if await run_scalar(
            db,
            "SELECT COUNT(*) AS count FROM operon_pgfams WHERE pgfam_num = ?",
            (pgfam_num,),
        ):
            display_id = format_pgfam(pgfam_num)
            hits.append({
                "kind": "entity",
                "type": "pgfam",
                "key": pgfam_num,
                "identifier": display_id,
                "label": display_id,
                "context": "PGFam",
            })

    if query_text.isdigit():
        taxon_id = int(query_text)
        taxon_rows = await run_all(
            db,
            """
            SELECT entity_type, entity_key, identifier, label, context
            FROM search_entities
            WHERE entity_type IN ('species', 'genus', 'phylum')
              AND entity_key = ?
            ORDER BY CASE entity_type
              WHEN 'species' THEN 0
              WHEN 'genus' THEN 1
              ELSE 2
            END
            """,
            (taxon_id,),
        )
        for row in taxon_rows:
            entity = serialize_search_entity(row)
            entity["kind"] = "entity"
            hits.append(entity)

    exact_entities = await run_all(
        db,
        f"""
        SELECT
          entity_type,
          entity_key,
          identifier,
          label,
          context
        FROM (
          {search_entity_source_sql(include_pgfam=True)}
        )
        WHERE identifier = ? COLLATE NOCASE
        ORDER BY {entity_type_order_sql()}, entity_key
        LIMIT 20
        """,
        (query_text,),
    )
    seen_entities = set()
    for row in exact_entities:
        key = (row["entity_type"], int(row["entity_key"]))
        if key in seen_entities:
            continue
        seen_entities.add(key)
        entity = serialize_search_entity(row)
        entity["kind"] = "genome" if entity["type"] == "genome" else "entity"
        if entity["type"] == "genome":
            entity["genomeKey"] = entity["key"]
        hits.append(entity)

    return hits


async def search(db, page, request):
    direct_hits = await fetch_direct_search_hits(db, request["q"])
    cte_sql, cte_params = matched_entities_cte(request)
    rank_sql = entity_match_rank_sql()
    rank_params = [request["q"]] * 4

    if request["type"] is not None:
        entity_type = request["type"]
        total = await run_scalar(
            db,
            f"""
            WITH {cte_sql}
            SELECT COUNT(*) AS total
            FROM matched_entities
            WHERE entity_type = ?
            """,
            (*cte_params, entity_type),
        )
        offset = (page - 1) * PAGE_SIZE
        rows = await run_all(
            db,
            f"""
            WITH {cte_sql}
            SELECT
              entity_type,
              entity_key,
              identifier,
              label,
              context,
              {rank_sql} AS match_rank
            FROM matched_entities
            WHERE entity_type = ?
            ORDER BY
              match_rank,
              label COLLATE NOCASE,
              identifier COLLATE NOCASE,
              entity_key
            LIMIT ? OFFSET ?
            """,
            (
                *cte_params,
                *rank_params,
                entity_type,
                PAGE_SIZE,
                offset,
            ),
        )
        return {
            "q": request["q"],
            "mode": "entities",
            "type": entity_type,
            "typeLabel": SEARCH_ENTITY_TYPE_LABELS[entity_type],
            "page": page,
            "pageSize": PAGE_SIZE,
            "total": total,
            "directHits": direct_hits,
            "items": [serialize_search_entity(row) for row in rows],
        }

    rows = await run_all(
        db,
        f"""
        WITH {cte_sql},
        ranked_matches AS (
          SELECT
            entity_type,
            entity_key,
            identifier,
            label,
            context,
            {rank_sql} AS match_rank,
            COUNT(*) OVER (PARTITION BY entity_type) AS entity_total
          FROM matched_entities
        ),
        numbered_matches AS (
          SELECT
            *,
            ROW_NUMBER() OVER (
              PARTITION BY entity_type
              ORDER BY
                match_rank,
                label COLLATE NOCASE,
                identifier COLLATE NOCASE,
                entity_key
            ) AS entity_row
          FROM ranked_matches
        )
        SELECT
          entity_type,
          entity_key,
          identifier,
          label,
          context,
          entity_total,
          entity_row
        FROM numbered_matches
        WHERE entity_row <= {SEARCH_PREVIEW_SIZE}
        ORDER BY {entity_type_order_sql()}, entity_row
        """,
        (*cte_params, *rank_params),
    )

    groups_by_type = {}
    for row in rows:
        entity_type = row["entity_type"]
        group = groups_by_type.setdefault(entity_type, {
            "type": entity_type,
            "typeLabel": SEARCH_ENTITY_TYPE_LABELS[entity_type],
            "total": int(row["entity_total"]),
            "items": [],
        })
        group["items"].append(serialize_search_entity(row))

    return {
        "q": request["q"],
        "mode": "preview",
        "directHits": direct_hits,
        "groups": [
            groups_by_type[entity_type]
            for entity_type in SEARCH_ENTITY_TYPES
            if entity_type in groups_by_type
        ],
    }


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


def entity_operon_filter_sql(entity_type):
    statements = {
        "product": """
          SELECT operon_id
          FROM operon_products
          WHERE product_id = ?
        """,
        "pgfam": """
          SELECT operon_id
          FROM operon_pgfams
          WHERE pgfam_num = ?
        """,
        "ec": """
          SELECT operon_id
          FROM operon_ec_support
          WHERE ec_key = ?
        """,
        "pathway": """
          SELECT operon_id
          FROM operon_pathway_support
          WHERE pathway_key = ?
        """,
        "pathway_class": """
          SELECT operon_id
          FROM operon_pathway_class_support
          WHERE pathway_class_key = ?
        """,
        "subsystem": """
          SELECT operon_id
          FROM operon_subsystem_support
          WHERE subsystem_key = ?
        """,
        "subsystem_class": """
          SELECT operon_id
          FROM operon_subsystem_class_support
          WHERE subsystem_class_key = ?
        """,
        "role": """
          SELECT operon_id
          FROM operon_role_support
          WHERE role_key = ?
        """,
        "genome": """
          SELECT DISTINCT operon_id
          FROM occurrences
          WHERE genome_key = ?
        """,
        "species": """
          SELECT DISTINCT occ.operon_id
          FROM genome_taxonomy gt
          JOIN occurrences occ
            ON occ.genome_key = gt.genome_key
          WHERE gt.species_taxon_id = ?
        """,
        "genus": """
          SELECT DISTINCT occ.operon_id
          FROM genome_taxonomy gt
          JOIN occurrences occ
            ON occ.genome_key = gt.genome_key
          WHERE gt.genus_taxon_id = ?
        """,
        "phylum": """
          SELECT DISTINCT occ.operon_id
          FROM genome_taxonomy gt
          JOIN occurrences occ
            ON occ.genome_key = gt.genome_key
          WHERE gt.phylum_taxon_id = ?
        """,
    }
    return statements[entity_type]


def matched_operons_from_entities_sql():
    return """
      SELECT operon_id FROM (
      SELECT op.operon_id
      FROM matched_entities me
      JOIN operon_products op
        ON me.entity_type = 'product'
       AND op.product_id = me.entity_key

      UNION

      SELECT opg.operon_id
      FROM matched_entities me
      JOIN operon_pgfams opg
        ON me.entity_type = 'pgfam'
       AND opg.pgfam_num = me.entity_key

      UNION

      SELECT oes.operon_id
      FROM matched_entities me
      JOIN operon_ec_support oes
        ON me.entity_type = 'ec'
       AND oes.ec_key = me.entity_key

      UNION

      SELECT ops.operon_id
      FROM matched_entities me
      JOIN operon_pathway_support ops
        ON me.entity_type = 'pathway'
       AND ops.pathway_key = me.entity_key

      ) AS functional_matches_one

      UNION

      SELECT operon_id FROM (

      SELECT opcs.operon_id
      FROM matched_entities me
      JOIN operon_pathway_class_support opcs
        ON me.entity_type = 'pathway_class'
       AND opcs.pathway_class_key = me.entity_key

      UNION

      SELECT oss.operon_id
      FROM matched_entities me
      JOIN operon_subsystem_support oss
        ON me.entity_type = 'subsystem'
       AND oss.subsystem_key = me.entity_key

      UNION

      SELECT oscs.operon_id
      FROM matched_entities me
      JOIN operon_subsystem_class_support oscs
        ON me.entity_type = 'subsystem_class'
       AND oscs.subsystem_class_key = me.entity_key

      UNION

      SELECT ors.operon_id
      FROM matched_entities me
      JOIN operon_role_support ors
        ON me.entity_type = 'role'
       AND ors.role_key = me.entity_key

      ) AS functional_matches_two

      UNION

      SELECT operon_id FROM (

      SELECT occ.operon_id
      FROM matched_entities me
      JOIN occurrences occ
        ON me.entity_type = 'genome'
       AND occ.genome_key = me.entity_key

      UNION

      SELECT occ.operon_id
      FROM matched_entities me
      JOIN genome_taxonomy gt
        ON me.entity_type = 'species'
       AND gt.species_taxon_id = me.entity_key
      JOIN occurrences occ
        ON occ.genome_key = gt.genome_key

      UNION

      SELECT occ.operon_id
      FROM matched_entities me
      JOIN genome_taxonomy gt
        ON me.entity_type = 'genus'
       AND gt.genus_taxon_id = me.entity_key
      JOIN occurrences occ
        ON occ.genome_key = gt.genome_key

      UNION

      SELECT occ.operon_id
      FROM matched_entities me
      JOIN genome_taxonomy gt
        ON me.entity_type = 'phylum'
       AND gt.phylum_taxon_id = me.entity_key
      JOIN occurrences occ
        ON occ.genome_key = gt.genome_key
      ) AS genome_taxonomy_matches
    """


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
    if filters["search"] is not None:
        search_request = {
            "q": filters["search"],
            "tokens": filters["search_tokens"],
            "patterns": filters["search_patterns"],
        }
        search_ctes, search_params = matched_entities_cte(search_request)
        ctes.append(search_ctes)
        ctes.append(
            f"""
            matching_search AS (
              {matched_operons_from_entities_sql()}
            )
            """
        )
        joins.append(
            "JOIN matching_search ms ON ms.operon_id = o.operon_id"
        )
        params.extend(search_params)
    if filters["entity"] is not None:
        ctes.append(
            f"""
            matching_entity AS (
              {entity_operon_filter_sql(filters['entity']['type'])}
            )
            """
        )
        joins.append(
            "JOIN matching_entity me_filter ON me_filter.operon_id = o.operon_id"
        )
        params.append(filters["entity"]["key"])

    if filters["min_gene_count"] > MIN_GENE_COUNT:
        where_clauses.append("o.gene_count >= ?")
        params.append(filters["min_gene_count"])
    if filters["max_gene_count"] < MAX_GENE_COUNT:
        where_clauses.append("o.gene_count <= ?")
        params.append(filters["max_gene_count"])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    with_sql = f"WITH {', '.join(ctes)}" if ctes else ""
    from_sql = """
    FROM operons o
    LEFT JOIN operon_taxonomy_counts otc
      ON otc.operon_id = o.operon_id
    """
    if joins:
        from_sql = f"{from_sql}\n" + "\n".join(joins)
    return with_sql, from_sql, where_sql, params


def family_reason_union_sql():
    mappings = [
        ("product", "operon_products", "product_id"),
        ("pgfam", "operon_pgfams", "pgfam_num"),
        ("ec", "operon_ec_support", "ec_key"),
        ("pathway", "operon_pathway_support", "pathway_key"),
        ("pathway_class", "operon_pathway_class_support", "pathway_class_key"),
        ("subsystem", "operon_subsystem_support", "subsystem_key"),
        (
            "subsystem_class",
            "operon_subsystem_class_support",
            "subsystem_class_key",
        ),
        ("role", "operon_role_support", "role_key"),
    ]
    branches = []
    for entity_type, table, key_column in mappings:
        branches.append(f"""
          SELECT
            po.operon_id,
            me.entity_type,
            me.entity_key,
            me.identifier,
            me.label
          FROM page_operons po
          JOIN {table} mapping
            ON mapping.operon_id = po.operon_id
          JOIN matched_entities me
            ON me.entity_type = '{entity_type}'
           AND me.entity_key = mapping.{key_column}
        """)

    branches.extend([
        """
          SELECT
            po.operon_id,
            me.entity_type,
            me.entity_key,
            me.identifier,
            me.label
          FROM page_operons po
          JOIN occurrences occ
            ON occ.operon_id = po.operon_id
          JOIN matched_entities me
            ON me.entity_type = 'genome'
           AND me.entity_key = occ.genome_key
        """,
        """
          SELECT
            po.operon_id,
            me.entity_type,
            me.entity_key,
            me.identifier,
            me.label
          FROM page_operons po
          JOIN occurrences occ
            ON occ.operon_id = po.operon_id
          JOIN genome_taxonomy gt
            ON gt.genome_key = occ.genome_key
          JOIN matched_entities me
            ON me.entity_type = 'species'
           AND me.entity_key = gt.species_taxon_id
        """,
        """
          SELECT
            po.operon_id,
            me.entity_type,
            me.entity_key,
            me.identifier,
            me.label
          FROM page_operons po
          JOIN occurrences occ
            ON occ.operon_id = po.operon_id
          JOIN genome_taxonomy gt
            ON gt.genome_key = occ.genome_key
          JOIN matched_entities me
            ON me.entity_type = 'genus'
           AND me.entity_key = gt.genus_taxon_id
        """,
        """
          SELECT
            po.operon_id,
            me.entity_type,
            me.entity_key,
            me.identifier,
            me.label
          FROM page_operons po
          JOIN occurrences occ
            ON occ.operon_id = po.operon_id
          JOIN genome_taxonomy gt
            ON gt.genome_key = occ.genome_key
          JOIN matched_entities me
            ON me.entity_type = 'phylum'
           AND me.entity_key = gt.phylum_taxon_id
        """,
    ])
    # D1 constrains the number of terms in one compound SELECT. Keep each
    # nested compound below that limit, then deduplicate across the two groups.
    groups = [branches[index:index + 4] for index in range(0, len(branches), 4)]
    return "\nUNION\n".join(
        "SELECT * FROM ("
        + "\nUNION\n".join(group)
        + f") AS reason_group_{index}"
        for index, group in enumerate(groups)
    )


async def fetch_family_match_reasons(db, operon_ids, filters):
    if not operon_ids or filters["search"] is None:
        return {}

    search_request = {
        "q": filters["search"],
        "tokens": filters["search_tokens"],
        "patterns": filters["search_patterns"],
    }
    search_ctes, search_params = matched_entities_cte(search_request)
    values_sql = ", ".join("(?)" for _ in operon_ids)
    rows = await run_all(
        db,
        f"""
        WITH
        {search_ctes},
        page_operons(operon_id) AS (
          VALUES {values_sql}
        ),
        family_reasons AS (
          {family_reason_union_sql()}
        ),
        ranked_reasons AS (
          SELECT
            *,
            ROW_NUMBER() OVER (
              PARTITION BY operon_id
              ORDER BY
                {entity_type_order_sql()},
                label COLLATE NOCASE,
                identifier COLLATE NOCASE,
                entity_key
            ) AS reason_row
          FROM family_reasons
        )
        SELECT
          operon_id,
          entity_type,
          entity_key,
          identifier,
          label
        FROM ranked_reasons
        WHERE reason_row <= 5
        ORDER BY operon_id, reason_row
        """,
        (*search_params, *operon_ids),
    )

    reasons_by_operon = {}
    for row in rows:
        reasons_by_operon.setdefault(int(row["operon_id"]), []).append({
            "type": row["entity_type"],
            "key": int(row["entity_key"]),
            "identifier": row["identifier"],
            "label": row["label"],
        })
    return reasons_by_operon


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
          o.occurrence_count,
          COALESCE(otc.genome_count, 0) AS taxonomy_genome_count,
          COALESCE(otc.species_count, 0) AS taxonomy_species_count,
          COALESCE(otc.genus_count, 0) AS taxonomy_genus_count,
          COALESCE(otc.phylum_count, 0) AS taxonomy_phylum_count
        {from_sql}
        {where_sql}
        ORDER BY {sort_column} {sort_direction}, o.operon_id ASC
        LIMIT ? OFFSET ?
        """,
        (*filter_params, PAGE_SIZE, offset),
    )
    reasons_by_operon = await fetch_family_match_reasons(
        db,
        [int(item["operon_id"]) for item in items],
        filters,
    )
    for item in items:
        item["display_id"] = format_stable_operon_id(item["operon_id"])
        item["pgfams"] = format_pgfam_signature(item["pgfam_signature"])
        item.pop("pgfam_signature", None)
        item["taxonomyCounts"] = {
            "genomes": int(item.pop("taxonomy_genome_count")),
            "species": int(item.pop("taxonomy_species_count")),
            "genera": int(item.pop("taxonomy_genus_count")),
            "phyla": int(item.pop("taxonomy_phylum_count")),
        }
        item["matchReasons"] = reasons_by_operon.get(
            int(item["operon_id"]),
            [],
        )
    entity_filter = None
    if filters["entity"] is not None:
        entity_filter = await fetch_search_entity(
            db,
            filters["entity"]["type"],
            filters["entity"]["key"],
        )
    return {
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "sort": sort_key,
        "direction": sort_direction.lower(),
        "search": filters["search"] or "",
        "entityFilter": entity_filter,
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


def occurrence_entity_predicate(entity_type):
    predicates = {
        "product": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND og_entity.product_id = ?
          )
        """,
        "pgfam": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND og_entity.pgfam_num = ?
          )
        """,
        "ec": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            JOIN gene_pathways gp_entity
              ON gp_entity.gene_key = og_entity.gene_key
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND gp_entity.ec_key = ?
          )
        """,
        "pathway": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            JOIN gene_pathways gp_entity
              ON gp_entity.gene_key = og_entity.gene_key
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND gp_entity.pathway_key = ?
          )
        """,
        "pathway_class": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            JOIN gene_pathways gp_entity
              ON gp_entity.gene_key = og_entity.gene_key
            JOIN pathway_reference pr_entity
              ON pr_entity.pathway_key = gp_entity.pathway_key
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND pr_entity.pathway_class_key = ?
          )
        """,
        "subsystem": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            JOIN gene_subsystems gs_entity
              ON gs_entity.gene_key = og_entity.gene_key
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND gs_entity.subsystem_key = ?
          )
        """,
        "subsystem_class": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            JOIN gene_subsystems gs_entity
              ON gs_entity.gene_key = og_entity.gene_key
            JOIN subsystem_reference sr_entity
              ON sr_entity.subsystem_key = gs_entity.subsystem_key
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND sr_entity.subsystem_class_key = ?
          )
        """,
        "role": """
          EXISTS (
            SELECT 1
            FROM occurrence_genes og_entity
            JOIN gene_subsystems gs_entity
              ON gs_entity.gene_key = og_entity.gene_key
            WHERE og_entity.occurrence_id = occ.occurrence_id
              AND gs_entity.role_key = ?
          )
        """,
        "genome": "occ.genome_key = ?",
        "species": """
          EXISTS (
            SELECT 1
            FROM genome_taxonomy gt_entity
            WHERE gt_entity.genome_key = occ.genome_key
              AND gt_entity.species_taxon_id = ?
          )
        """,
        "genus": """
          EXISTS (
            SELECT 1
            FROM genome_taxonomy gt_entity
            WHERE gt_entity.genome_key = occ.genome_key
              AND gt_entity.genus_taxon_id = ?
          )
        """,
        "phylum": """
          EXISTS (
            SELECT 1
            FROM genome_taxonomy gt_entity
            WHERE gt_entity.genome_key = occ.genome_key
              AND gt_entity.phylum_taxon_id = ?
          )
        """,
    }
    return predicates[entity_type]


def occurrence_search_predicate():
    return """
    (
      EXISTS (
        SELECT 1
        FROM occurrence_genes og_search
        JOIN matched_entities me_search
          ON (
               me_search.entity_type = 'product'
               AND me_search.entity_key = og_search.product_id
             )
          OR (
               me_search.entity_type = 'pgfam'
               AND me_search.entity_key = og_search.pgfam_num
             )
        WHERE og_search.occurrence_id = occ.occurrence_id
      )
      OR EXISTS (
        SELECT 1
        FROM occurrence_genes og_search
        JOIN gene_pathways gp_search
          ON gp_search.gene_key = og_search.gene_key
        JOIN pathway_reference pr_search
          ON pr_search.pathway_key = gp_search.pathway_key
        JOIN matched_entities me_search
          ON (
               me_search.entity_type = 'ec'
               AND me_search.entity_key = gp_search.ec_key
             )
          OR (
               me_search.entity_type = 'pathway'
               AND me_search.entity_key = gp_search.pathway_key
             )
          OR (
               me_search.entity_type = 'pathway_class'
               AND me_search.entity_key = pr_search.pathway_class_key
             )
        WHERE og_search.occurrence_id = occ.occurrence_id
      )
      OR EXISTS (
        SELECT 1
        FROM occurrence_genes og_search
        JOIN gene_subsystems gs_search
          ON gs_search.gene_key = og_search.gene_key
        JOIN subsystem_reference sr_search
          ON sr_search.subsystem_key = gs_search.subsystem_key
        JOIN matched_entities me_search
          ON (
               me_search.entity_type = 'subsystem'
               AND me_search.entity_key = gs_search.subsystem_key
             )
          OR (
               me_search.entity_type = 'subsystem_class'
               AND me_search.entity_key = sr_search.subsystem_class_key
             )
          OR (
               me_search.entity_type = 'role'
               AND me_search.entity_key = gs_search.role_key
             )
        WHERE og_search.occurrence_id = occ.occurrence_id
      )
      OR EXISTS (
        SELECT 1
        FROM matched_entities me_search
        LEFT JOIN genome_taxonomy gt_search
          ON gt_search.genome_key = occ.genome_key
        WHERE (
                me_search.entity_type = 'genome'
                AND me_search.entity_key = occ.genome_key
              )
           OR (
                me_search.entity_type = 'species'
                AND me_search.entity_key = gt_search.species_taxon_id
              )
           OR (
                me_search.entity_type = 'genus'
                AND me_search.entity_key = gt_search.genus_taxon_id
              )
           OR (
                me_search.entity_type = 'phylum'
                AND me_search.entity_key = gt_search.phylum_taxon_id
              )
      )
    )
    """


def occurrence_query_parts(operon_id, filters):
    ctes = []
    cte_params = []
    where_clauses = ["occ.operon_id = ?"]
    where_params = [operon_id]

    if filters["search"] is not None:
        search_request = {
            "q": filters["search"],
            "tokens": filters["search_tokens"],
            "patterns": filters["search_patterns"],
        }
        search_ctes, search_params = matched_entities_cte(search_request)
        ctes.append(search_ctes)
        cte_params.extend(search_params)
        where_clauses.append(occurrence_search_predicate())
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
        where_params.append(like_contains_param(filters["product"]))
    if filters["entity"] is not None:
        where_clauses.append(
            occurrence_entity_predicate(filters["entity"]["type"])
        )
        where_params.append(filters["entity"]["key"])

    with_sql = f"WITH {', '.join(ctes)}" if ctes else ""
    where_sql = f"WHERE {' AND '.join(where_clauses)}"
    return with_sql, where_sql, [*cte_params, *where_params]


async def get_operon(db, operon_id, page, filters):
    operon = await run_first(
        db,
        """
        SELECT
          o.operon_id,
          o.pgfam_signature,
          o.gene_count,
          o.occurrence_count,
          COALESCE(otc.genome_count, 0) AS taxonomy_genome_count,
          COALESCE(otc.species_count, 0) AS taxonomy_species_count,
          COALESCE(otc.genus_count, 0) AS taxonomy_genus_count,
          COALESCE(otc.phylum_count, 0) AS taxonomy_phylum_count
        FROM operons o
        LEFT JOIN operon_taxonomy_counts otc
          ON otc.operon_id = o.operon_id
        WHERE o.operon_id = ?
        """,
        (operon_id,),
    )
    if operon is None:
        return None

    with_sql, where_sql, query_params = occurrence_query_parts(
        operon_id,
        filters,
    )
    total = await run_scalar(
        db,
        f"""
        {with_sql}
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
        {with_sql}
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
    operon["taxonomyCounts"] = {
        "genomes": int(operon.pop("taxonomy_genome_count")),
        "species": int(operon.pop("taxonomy_species_count")),
        "genera": int(operon.pop("taxonomy_genus_count")),
        "phyla": int(operon.pop("taxonomy_phylum_count")),
    }
    operon["page"] = page
    operon["pageSize"] = PAGE_SIZE
    operon["total"] = total
    operon["product"] = filters["product"] or ""
    operon["search"] = filters["search"] or ""
    operon["entityFilter"] = None
    if filters["entity"] is not None:
        operon["entityFilter"] = await fetch_search_entity(
            db,
            filters["entity"]["type"],
            filters["entity"]["key"],
        )
    for occurrence in occurrences:
        occurrence["display_id"] = format_occurrence_id(occurrence["occurrence_id"])
    operon["occurrences"] = occurrences
    operon["functional_summary"] = await fetch_operon_functional_summary(db, operon_id)
    return operon


async def get_operon_taxonomy(db, operon_id, genera_page):
    summary = await run_first(
        db,
        """
        SELECT
          o.operon_id,
          COALESCE(otc.genome_count, 0) AS genome_count,
          COALESCE(otc.species_count, 0) AS species_count,
          COALESCE(otc.genus_count, 0) AS genus_count,
          COALESCE(otc.phylum_count, 0) AS phylum_count,
          COALESCE(otc.species_unclassified_genome_count, 0)
            AS species_unclassified_genome_count,
          COALESCE(otc.genus_unclassified_genome_count, 0)
            AS genus_unclassified_genome_count,
          COALESCE(otc.phylum_unclassified_genome_count, 0)
            AS phylum_unclassified_genome_count
        FROM operons o
        LEFT JOIN operon_taxonomy_counts otc
          ON otc.operon_id = o.operon_id
        WHERE o.operon_id = ?
        """,
        (operon_id,),
    )
    if summary is None:
        return None

    phyla = await run_all(
        db,
        """
        WITH family_genomes AS (
          SELECT DISTINCT genome_key
          FROM occurrences
          WHERE operon_id = ?
        )
        SELECT
          gt.phylum_taxon_id AS taxon_id,
          MIN(gt.phylum_name) AS name,
          COUNT(*) AS genome_count,
          COUNT(DISTINCT CASE
            WHEN typeof(gt.species_taxon_id) = 'integer'
              AND gt.species_taxon_id > 0
            THEN gt.species_taxon_id
          END) AS species_count
        FROM family_genomes fg
        JOIN genome_taxonomy gt
          ON gt.genome_key = fg.genome_key
        WHERE typeof(gt.phylum_taxon_id) = 'integer'
          AND gt.phylum_taxon_id > 0
        GROUP BY gt.phylum_taxon_id
        ORDER BY
          genome_count DESC,
          name COLLATE NOCASE,
          taxon_id
        """,
        (operon_id,),
    )

    genera_offset = (genera_page - 1) * TAXONOMY_PAGE_SIZE
    genera_rows = await run_all(
        db,
        """
        WITH family_genomes AS (
          SELECT DISTINCT genome_key
          FROM occurrences
          WHERE operon_id = ?
        )
        SELECT
          gt.genus_taxon_id AS taxon_id,
          MIN(gt.genus_name) AS name,
          COUNT(*) AS genome_count,
          COUNT(DISTINCT CASE
            WHEN typeof(gt.species_taxon_id) = 'integer'
              AND gt.species_taxon_id > 0
            THEN gt.species_taxon_id
          END) AS species_count
        FROM family_genomes fg
        JOIN genome_taxonomy gt
          ON gt.genome_key = fg.genome_key
        WHERE typeof(gt.genus_taxon_id) = 'integer'
          AND gt.genus_taxon_id > 0
        GROUP BY gt.genus_taxon_id
        ORDER BY
          genome_count DESC,
          name COLLATE NOCASE,
          taxon_id
        LIMIT ? OFFSET ?
        """,
        (operon_id, TAXONOMY_PAGE_SIZE, genera_offset),
    )

    def serialize_taxon_breakdown(row):
        return {
            "taxonId": int(row["taxon_id"]),
            "name": row["name"],
            "genomeCount": int(row["genome_count"]),
            "speciesCount": int(row["species_count"]),
        }

    return {
        "operonId": int(summary["operon_id"]),
        "displayId": format_stable_operon_id(summary["operon_id"]),
        "counts": {
            "genomes": int(summary["genome_count"]),
            "species": int(summary["species_count"]),
            "genera": int(summary["genus_count"]),
            "phyla": int(summary["phylum_count"]),
        },
        "unclassified": {
            "speciesGenomes": int(
                summary["species_unclassified_genome_count"]
            ),
            "generaGenomes": int(
                summary["genus_unclassified_genome_count"]
            ),
            "phylaGenomes": int(
                summary["phylum_unclassified_genome_count"]
            ),
        },
        "phyla": [serialize_taxon_breakdown(row) for row in phyla],
        "genera": {
            "page": genera_page,
            "pageSize": TAXONOMY_PAGE_SIZE,
            "total": int(summary["genus_count"]),
            "items": [
                serialize_taxon_breakdown(row)
                for row in genera_rows
            ],
        },
    }


async def get_occurrence(db, occurrence_id, highlight_gene_id=None):
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
          og.gene_key,
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
    matched_highlight = None
    for row in rows:
        row["gene_id"] = f"{occurrence['genome_id']}.peg.{row['peg_num']}"
        row["pgfam_display"] = format_pgfam(row["pgfam_num"])
        key = int(row["gene_key"])
        row["pathways"] = pathways_by_gene.get(key, [])
        row["subsystems"] = subsystems_by_gene.get(key, [])
        row.pop("gene_key", None)
        row["highlighted"] = row["gene_id"] == highlight_gene_id
        if row["highlighted"]:
            matched_highlight = row["gene_id"]
        genes.append(row)

    occurrence["stable_display_id"] = format_stable_operon_id(occurrence["operon_id"])
    occurrence["occurrence_display_id"] = format_occurrence_id(occurrence["occurrence_id"])
    occurrence["highlightGeneId"] = matched_highlight
    occurrence["genes"] = genes
    return occurrence


async def browse_genomes(db, page, search, sort):
    offset = (page - 1) * PAGE_SIZE
    sort_key, sort_column, sort_direction = sort
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
          gi.operon_count,
          gi.gene_count
        FROM genomes gi
        {where_sql}
        ORDER BY {sort_column} {sort_direction}, gi.genome_key ASC
        LIMIT ? OFFSET ?
        """,
        (*params, PAGE_SIZE, offset),
    )
    return {
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "search": search or "",
        "sort": sort_key,
        "direction": sort_direction.lower(),
        "items": items,
    }


async def get_genome(db, genome_key):
    genome = await run_first(
        db,
        """
        SELECT
          genome_key,
          genome_id,
          organism_name,
          operon_count,
          gene_count
        FROM genomes
        WHERE genome_key = ?
        """,
        (genome_key,),
    )
    if genome is None:
        return None

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
