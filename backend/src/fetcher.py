"""Template Fetcher - discovers and downloads NZISM templates from GitHub."""

import time
from dataclasses import dataclass

import requests


class TemplateFetchError(Exception):
    """Raised when template fetching from GitHub fails."""


@dataclass
class TemplateFile:
    name: str          # e.g. "Operational-Best-Practices-for-NZISM-Extension.yaml"
    download_url: str  # Raw content URL
    content: str       # Raw YAML content


# Module-level cache shared across Lambda invocations (warm starts)
_cache: dict = {"templates": None, "timestamp": 0.0}
CACHE_TTL_SECONDS = 600  # 10 minutes


class TemplateFetcher:
    REPO_OWNER = "awslabs"
    REPO_NAME = "aws-config-rules"
    DIRECTORY = "aws-config-conformance-packs"
    NZISM_PATTERN = "Operational-Best-Practices-for-NZISM-"
    CONTENTS_API = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    def __init__(self) -> None:
        self._headers: dict[str, str] = {}

    def list_nzism_templates(self) -> list[TemplateFile]:
        """Discover all NZISM template files from GitHub and download their content.

        Results are cached in-memory for CACHE_TTL_SECONDS to avoid GitHub rate limits: Unauthenticated 60 requests/hour per IP
        """
        now = time.time()
        if _cache["templates"] is not None and (now - _cache["timestamp"]) < CACHE_TTL_SECONDS:
            return _cache["templates"]

        url = self.CONTENTS_API.format(
            owner=self.REPO_OWNER,
            repo=self.REPO_NAME,
            path=self.DIRECTORY,
        )

        try:
            response = requests.get(url, headers=self._headers, timeout=15)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise TemplateFetchError("Unable to reach GitHub") from exc

        if response.status_code == 403:
            raise TemplateFetchError("GitHub API rate limit exceeded")
        if response.status_code == 404:
            raise TemplateFetchError("Template repository not found")
        if not response.ok:
            raise TemplateFetchError(
                f"GitHub API returned unexpected status {response.status_code}"
            )

        files = response.json()
        templates: list[TemplateFile] = []

        for entry in files:
            name = entry.get("name", "")
            if self._is_nzism_template(name):
                download_url = entry.get("download_url", "")
                content = self._fetch_content(download_url)
                templates.append(
                    TemplateFile(name=name, download_url=download_url, content=content)
                )

        _cache["templates"] = templates
        _cache["timestamp"] = time.time()
        return templates

    def _fetch_content(self, url: str) -> str:
        """Download raw YAML content from a URL."""
        try:
            response = requests.get(url, headers=self._headers, timeout=15)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise TemplateFetchError("Unable to reach GitHub") from exc

        if response.status_code == 403:
            raise TemplateFetchError("GitHub API rate limit exceeded")
        if response.status_code == 404:
            raise TemplateFetchError("Template repository not found")
        if not response.ok:
            raise TemplateFetchError(
                f"GitHub API returned unexpected status {response.status_code}"
            )

        return response.text

    def fetch_template_content(self, template: TemplateFile) -> str:
        """Download raw YAML content for a template (public API kept for compatibility)."""
        return self._fetch_content(template.download_url)

    @staticmethod
    def _is_nzism_template(filename: str) -> bool:
        """Check if a filename matches the NZISM template pattern."""
        return (
            filename.startswith(TemplateFetcher.NZISM_PATTERN)
            and filename.endswith(".yaml")
        )
