import json
from urllib.parse import quote

from workers import Response


DOWNLOAD_RELEASE = "1.0.0"
DOWNLOAD_PREFIX = f"releases/{DOWNLOAD_RELEASE}/"
DOWNLOAD_MANIFEST_KEY = f"{DOWNLOAD_PREFIX}downloads_manifest.json"


class DownloadsError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.message = message
        self.status = status


async def get_download_manifest(bucket, download_base_url=""):
    manifest_object = await bucket.get(DOWNLOAD_MANIFEST_KEY)
    if manifest_object is None:
        raise DownloadsError("Download manifest not found", 404)

    manifest = await read_json(manifest_object)
    release = str(manifest.get("release") or DOWNLOAD_RELEASE)
    prefix = f"releases/{release}/"

    datasets = []
    for dataset in manifest.get("datasets") or []:
        filename = safe_filename(dataset.get("filename"))
        if not filename:
            continue
        item = dict(dataset)
        item["download_url"] = download_url(release, filename, download_base_url)
        item["object_key"] = f"{prefix}{filename}"
        datasets.append(item)

    documentation = manifest.get("documentation") or {}
    documentation_filename = safe_filename(documentation.get("filename"))
    normalized_documentation = dict(documentation)
    if documentation_filename:
        normalized_documentation["download_url"] = download_url(
            release,
            documentation_filename,
            download_base_url,
        )
        normalized_documentation["object_key"] = f"{prefix}{documentation_filename}"

    return {
        "release": release,
        "generated_at": manifest.get("generated_at"),
        "prefix": prefix,
        "datasets": datasets,
        "documentation": normalized_documentation,
    }


async def get_download_file_response(bucket, release, filename):
    normalized_release = safe_release(release)
    normalized_filename = safe_filename(filename)
    if not normalized_release or not normalized_filename:
        raise DownloadsError("Invalid download path", 400)

    key = f"releases/{normalized_release}/{normalized_filename}"
    download_object = await bucket.get(key)
    if download_object is None:
        raise DownloadsError("Download file not found", 404)

    headers = {
        "Cache-Control": "public, max-age=3600",
        "Content-Disposition": f'attachment; filename="{normalized_filename}"',
        "Content-Type": content_type(normalized_filename),
        "X-Content-Type-Options": "nosniff",
    }
    etag = getattr(download_object, "httpEtag", None)
    if etag:
        headers["ETag"] = etag

    body = download_object.body if hasattr(download_object, "body") else None
    return Response(body, status=200 if body is not None else 412, headers=headers)


async def read_json(r2_object):
    if hasattr(r2_object, "text"):
        return json.loads(await maybe_await(r2_object.text()))
    if hasattr(r2_object, "json"):
        parsed = await maybe_await(r2_object.json())
        if hasattr(parsed, "to_py"):
            return parsed.to_py()
        return parsed
    raise DownloadsError("Download manifest body is unavailable", 500)


async def maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value


def download_url(release, filename, download_base_url=""):
    base_url = normalize_base_url(download_base_url)
    encoded_release = quote(str(release), safe="")
    encoded_filename = quote(filename, safe="")
    if base_url:
        return f"{base_url}/releases/{encoded_release}/{encoded_filename}"
    return f"/api/downloads/releases/{encoded_release}/files/{encoded_filename}"


def normalize_base_url(value):
    text = str(value or "").strip().rstrip("/")
    if not text.startswith("https://"):
        return ""
    return text


def safe_release(value):
    text = str(value or "").strip()
    if not text or "/" in text or "\\" in text or ".." in text:
        return ""
    return text


def safe_filename(value):
    text = str(value or "").strip()
    if not text or "/" in text or "\\" in text or ".." in text:
        return ""
    return text


def content_type(filename):
    if filename.endswith(".tsv.gz"):
        return "application/gzip"
    if filename.endswith(".tsv"):
        return "text/tab-separated-values; charset=utf-8"
    if filename.endswith(".json"):
        return "application/json; charset=utf-8"
    return "application/octet-stream"
