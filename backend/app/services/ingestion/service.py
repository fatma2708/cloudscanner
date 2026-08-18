"""Source ingestion: read Terraform/OpenTofu sources from a zip archive or a
public GitHub repository (via the GitHub API).

Both paths return a ``{relative_path: content}`` mapping that the analysis
orchestrator feeds to the HCL parser.
"""

from __future__ import annotations

import io
import re
import zipfile
from urllib.parse import urlparse

import httpx

TF_EXTENSIONS = (".tf", ".tofu")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 200


class IngestionError(Exception):
    """Raised when a source cannot be ingested."""


def read_zip(data: bytes) -> dict[str, str]:
    """Extract Terraform files from an uploaded zip archive."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise IngestionError("The uploaded file is not a valid zip archive.") from exc

    files: dict[str, str] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        if not info.filename.endswith(TF_EXTENSIONS):
            continue
        if info.file_size > MAX_FILE_BYTES:
            continue
        content = archive.read(info.filename)
        files[info.filename] = content.decode("utf-8", errors="replace")
        if len(files) >= MAX_FILES:
            break
    if not files:
        raise IngestionError("No Terraform (.tf / .tofu) files found in the archive.")
    return files


_GITHUB_RE = re.compile(
    r"^(?:https?://(?:www\.)?github\.com/|git@github\.com:)?([^/\s]+)/([^/\s]+?)(?:\.git)?/?$"
)


def _normalize_github_url(url: str) -> tuple[str, str]:
    if not url:
        raise IngestionError("A GitHub repository URL is required.")
    # Support tree/subdir paths: owner/repo/tree/<branch>/<path>
    parsed = urlparse(url if "://" in url else f"https://{url}")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise IngestionError("Could not parse the GitHub repository URL.")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    return owner, repo


def fetch_github(url: str) -> dict[str, str]:
    """Fetch Terraform files from a public GitHub repository using the git trees API."""
    owner, repo = _normalize_github_url(url)
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        try:
            meta = client.get(api_base).raise_for_status().json()
        except httpx.HTTPStatusError as exc:
            raise IngestionError(
                f"GitHub repository not found or not accessible ({exc.response.status_code})."
            ) from exc
        default_branch = meta.get("default_branch", "main")
        tree_url = f"{api_base}/git/trees/{default_branch}?recursive=1"
        tree = client.get(tree_url).raise_for_status().json()

    files: dict[str, str] = {}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for entry in tree.get("tree", []):
            if entry.get("type") != "blob":
                continue
            path = entry["path"]
            if not path.endswith(TF_EXTENSIONS):
                continue
            if entry.get("size", 0) > MAX_FILE_BYTES:
                continue
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/{path}"
            content = client.get(raw_url).text
            files[path] = content
            if len(files) >= MAX_FILES:
                break

    if not files:
        raise IngestionError("No Terraform (.tf / .tofu) files found in that repository.")
    return files
