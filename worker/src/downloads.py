import json
from urllib.parse import quote


DOWNLOAD_RELEASE = "1.1.0"
DOWNLOAD_PREFIX = f"releases/{DOWNLOAD_RELEASE}/"
DOWNLOAD_MANIFEST_KEY = f"{DOWNLOAD_PREFIX}downloads_manifest.json"


class DownloadsError(Exception):
    def __init__(self, message, status=500):
        super().__init__(message)
        self.message = message
        self.status = status


async def get_download_manifest(bucket, download_base_url=""):
    public_base_url = normalize_base_url(download_base_url)
    if not public_base_url:
        raise DownloadsError("Download base URL is not configured", 500)

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
        item["download_url"] = download_url(release, filename, public_base_url)
        item["object_key"] = f"{prefix}{filename}"
        datasets.append(item)

    documentation = manifest.get("documentation") or {}
    documentation_filename = safe_filename(documentation.get("filename"))
    normalized_documentation = dict(documentation)
    if documentation_filename:
        normalized_documentation["download_url"] = download_url(
            release,
            documentation_filename,
            public_base_url,
        )
        normalized_documentation["object_key"] = f"{prefix}{documentation_filename}"

    return {
        "release": release,
        "generated_at": manifest.get("generated_at"),
        "prefix": prefix,
        "datasets": datasets,
        "documentation": normalized_documentation,
    }


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


def download_url(release, filename, base_url):
    encoded_release = quote(str(release), safe="")
    encoded_filename = quote(filename, safe="")
    return f"{base_url}/releases/{encoded_release}/{encoded_filename}"


def normalize_base_url(value):
    text = str(value or "").strip().rstrip("/")
    if not text.startswith("https://"):
        return ""
    return text


def safe_filename(value):
    text = str(value or "").strip()
    if not text or "/" in text or "\\" in text or ".." in text:
        return ""
    return text
