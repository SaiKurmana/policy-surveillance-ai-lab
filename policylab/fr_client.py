"""Minimal, polite client for the Federal Register API and GovInfo full text.

* Metadata: https://www.federalregister.gov/api/v1/ (no key required).
* Full text: the GPO GovInfo HTML edition of the same document. FederalRegister.gov
  asks automated clients to use its API rather than its full-text pages, so this
  client never requests those pages.
"""

from __future__ import annotations

import time
from typing import Any

import requests

FR_API = "https://www.federalregister.gov/api/v1"
GOVINFO_HTML = "https://www.govinfo.gov/content/pkg/FR-{date}/html/{number}.htm"
USER_AGENT = (
    "policy-surveillance-ai-lab/0.1 (+https://github.com/saikurmana/policy-surveillance-ai-lab)"
)

DOC_FIELDS = [
    "document_number",
    "title",
    "type",
    "subtype",
    "action",
    "abstract",
    "agencies",
    "publication_date",
    "effective_on",
    "comments_close_on",
    "dates",
    "html_url",
    "pdf_url",
    "citation",
    "page_length",
    "start_page",
    "end_page",
    "topics",
    "cfr_references",
    "docket_ids",
    "regulation_id_numbers",
    "significant",
]


class FederalRegisterClient:
    def __init__(
        self, delay: float = 0.6, timeout: int = 60, session: requests.Session | None = None
    ):
        self.delay = delay
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last = 0.0

    def _get(self, url: str, params: Any = None) -> requests.Response:
        for attempt in range(4):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError(f"unreachable: {url}")

    # ---- metadata -------------------------------------------------------
    def search(self, term: str, types: list[str] | None = None, per_page: int = 1000) -> dict:
        """Run a discovery query; returns count and the matching document numbers."""
        params: dict[str, Any] = {
            "conditions[term]": term,
            "per_page": per_page,
            "order": "relevance",
            "fields[]": ["document_number"],
        }
        if types:
            params["conditions[type][]"] = types
        data = self._get(f"{FR_API}/documents.json", params=params).json()
        numbers = [d["document_number"] for d in data.get("results", [])]
        return {"count": int(data.get("count", 0)), "document_numbers": numbers}

    def document(self, number: str) -> dict:
        params = {"fields[]": DOC_FIELDS}
        return self._get(f"{FR_API}/documents/{number}.json", params=params).json()

    # ---- full text --------------------------------------------------------
    @staticmethod
    def govinfo_url(meta: dict) -> str:
        return GOVINFO_HTML.format(date=meta["publication_date"], number=meta["document_number"])

    def full_text_html(self, meta: dict) -> str:
        resp = self._get(self.govinfo_url(meta))
        resp.encoding = resp.encoding or "utf-8"
        return resp.text
