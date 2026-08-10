import json
from urllib.parse import parse_qs, urlparse

from workers import Response

from db import (
    browse_genomes,
    browse_operons,
    get_genome,
    get_genome_viewer,
    get_occurrence,
    get_operon,
    genome_operons,
    organisms,
    parse_genome_search,
    parse_genome_sort,
    parse_occurrence_filters,
    parse_operon_filters,
    parse_operon_sort,
    parse_page,
    stats,
)
from downloads import (
    DownloadsError,
    get_download_manifest,
)


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


async def route_request(request, env):
    method = getattr(request, "method", "GET")
    if method == "OPTIONS":
        return Response(None, status=204, headers=CORS_HEADERS)
    if method != "GET":
        return json_response({"error": "Method not allowed"}, 405)

    parsed = urlparse(request.url)
    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    page = parse_page(query)

    if path_parts == ["api", "health"]:
        return json_response({"ok": True})

    rate_limit_response = await check_rate_limits(request, env, path_parts)
    if rate_limit_response is not None:
        return rate_limit_response

    if path_parts[:2] == ["api", "downloads"]:
        try:
            downloads = env.DOWNLOADS
        except Exception:
            return json_response({"error": "Downloads bucket binding is not configured"}, 500)

        try:
            return await route_downloads(path_parts, downloads, env)
        except DownloadsError as exc:
            return json_response({"error": exc.message}, exc.status)
        except Exception as exc:
            print(f"Downloads request failed: {exc}")
            return json_response({"error": "Downloads error"}, 500)

    try:
        db = env.DB
    except Exception:
        return json_response({"error": "Database binding is not configured"}, 500)

    try:
        return await route_api(path_parts, query, page, db)
    except Exception as exc:
        print(f"Database request failed: {exc}")
        return json_response({"error": "Database error"}, 500)


async def route_api(path_parts, query, page, db):
    if path_parts == ["api", "stats"]:
        return json_response(
            await stats(db),
            headers={"Cache-Control": "public, max-age=300"},
        )

    if path_parts == ["api", "organisms"]:
        return json_response(
            await organisms(db),
            headers={"Cache-Control": "public, max-age=900"},
        )

    if path_parts == ["api", "operons"]:
        return json_response(
            await browse_operons(
                db,
                page,
                parse_operon_filters(query),
                parse_operon_sort(query),
            )
        )

    if len(path_parts) == 3 and path_parts[:2] == ["api", "operons"]:
        operon_id = parse_int(path_parts[2])
        if operon_id is None:
            return json_response({"error": "Invalid operon_id"}, 400)
        payload = await get_operon(db, operon_id, page, parse_occurrence_filters(query))
        if payload is None:
            return json_response({"error": "Stable operon not found"}, 404)
        return json_response(payload)

    if len(path_parts) == 3 and path_parts[:2] == ["api", "occurrences"]:
        occurrence_id = parse_int(path_parts[2])
        if occurrence_id is None:
            return json_response({"error": "Invalid occurrence_id"}, 400)
        payload = await get_occurrence(db, occurrence_id)
        if payload is None:
            return json_response({"error": "Occurrence not found"}, 404)
        return json_response(payload)

    if path_parts == ["api", "genomes"]:
        return json_response(
            await browse_genomes(
                db,
                page,
                parse_genome_search(query),
                parse_genome_sort(query),
            )
        )

    if len(path_parts) == 3 and path_parts[:2] == ["api", "genomes"]:
        genome_key = parse_int(path_parts[2])
        if genome_key is None:
            return json_response({"error": "Invalid genome_key"}, 400)
        payload = await get_genome(db, genome_key)
        if payload is None:
            return json_response({"error": "Genome not found"}, 404)
        return json_response(payload)

    if (
        len(path_parts) == 4
        and path_parts[:2] == ["api", "genomes"]
        and path_parts[3] == "viewer"
    ):
        genome_key = parse_int(path_parts[2])
        if genome_key is None:
            return json_response({"error": "Invalid genome_key"}, 400)
        payload = await get_genome_viewer(db, genome_key, parse_operon_filters(query))
        if payload is None:
            return json_response({"error": "Genome not found"}, 404)
        return json_response(payload)

    if (
        len(path_parts) == 4
        and path_parts[:2] == ["api", "genomes"]
        and path_parts[3] == "operons"
    ):
        genome_key = parse_int(path_parts[2])
        if genome_key is None:
            return json_response({"error": "Invalid genome_key"}, 400)
        payload = await genome_operons(
            db,
            genome_key,
            page,
            parse_operon_sort(query),
            parse_operon_filters(query),
        )
        if payload is None:
            return json_response({"error": "Genome not found"}, 404)
        return json_response(payload)

    return json_response({"error": "Not found"}, 404)


async def route_downloads(path_parts, downloads, env):
    if path_parts == ["api", "downloads"]:
        return json_response(
            await get_download_manifest(downloads, get_download_base_url(env)),
            headers={"Cache-Control": "public, max-age=300"},
        )

    return json_response({"error": "Not found"}, 404)


async def check_rate_limits(request, env, path_parts):
    if not is_api_path(path_parts):
        return None

    client_key = rate_limit_client_key(request)
    if await is_rate_limited(env, "API_RATE_LIMITER", f"api:{client_key}"):
        return rate_limit_response("Too many API requests")

    if is_heavy_api_path(path_parts):
        route_key = heavy_route_key(path_parts)
        if await is_rate_limited(
            env,
            "HEAVY_API_RATE_LIMITER",
            f"heavy:{route_key}:{client_key}",
        ):
            return rate_limit_response("Too many requests for this endpoint")

    return None


def is_api_path(path_parts):
    return len(path_parts) >= 1 and path_parts[0] == "api"


def is_heavy_api_path(path_parts):
    if len(path_parts) >= 2 and path_parts[1] in ("operons", "occurrences"):
        return True
    if len(path_parts) >= 4 and path_parts[1] == "genomes":
        return path_parts[3] in ("viewer", "operons")
    return False


def heavy_route_key(path_parts):
    if len(path_parts) >= 2 and path_parts[1] in ("operons", "occurrences"):
        return path_parts[1]
    if len(path_parts) >= 4 and path_parts[1] == "genomes":
        return f"genomes:{path_parts[3]}"
    return "api"


def rate_limit_client_key(request):
    headers = getattr(request, "headers", None)
    if headers is not None:
        for header in ("cf-connecting-ip", "x-forwarded-for"):
            value = headers.get(header)
            if value:
                return value.split(",", 1)[0].strip()
    return "anonymous"


async def is_rate_limited(env, binding_name, key):
    try:
        limiter = getattr(env, binding_name)
    except Exception:
        return False

    try:
        result = await limiter.limit({"key": key})
    except Exception as exc:
        print(f"Rate limiter {binding_name} failed: {exc}")
        return False

    try:
        if isinstance(result, dict):
            return not bool(result.get("success"))
        return not bool(result.success)
    except Exception:
        return False


def rate_limit_response(message):
    return json_response(
        {"error": message},
        429,
        headers={"Retry-After": "60"},
    )


def get_download_base_url(env):
    try:
        return str(env.DOWNLOAD_BASE_URL or "")
    except Exception:
        return ""


def parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def json_response(payload, status=200, headers=None):
    response_headers = {
        "Content-Type": "application/json; charset=utf-8",
        **CORS_HEADERS,
    }
    if headers:
        response_headers.update(headers)

    return Response(
        json.dumps(payload, separators=(",", ":")),
        status=status,
        headers=response_headers,
    )
