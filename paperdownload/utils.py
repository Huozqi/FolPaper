"""HTTP client management, regex constants, and string helpers."""

from __future__ import annotations

import asyncio
import re
import unicodedata
from urllib.parse import quote

import httpx

from config import USER_AGENT, TIMEOUT, CONNECT_TIMEOUT, RETRY_MAX, RETRY_BACKOFF

# --- Regex constants ---

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.I)
ARXIV_RE = re.compile(
    r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?(?P<id>(?:\d{4}\.\d{4,5})(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.I,
)
CHEMRXIV_RE = re.compile(r"\b10\.26434/chemrxiv[-.0-9A-Za-z]+\b", re.I)

# --- Shared HTTP client ---

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    """Return a reusable global httpx.AsyncClient singleton."""
    global _client
    if _client is None or _client.is_closed:
        async with _client_lock:
            if _client is None or _client.is_closed:
                _client = httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=httpx.Timeout(TIMEOUT, connect=CONNECT_TIMEOUT),
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/pdf,application/json,*/*",
                    },
                )
    return _client


async def close_client() -> None:
    """Close the global HTTP client."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


async def fetch_with_retry(
    url: str,
    *,
    c: httpx.AsyncClient | None = None,
    **kwargs,
) -> httpx.Response:
    """GET *url* with automatic retry on transient errors.

    Uses exponential backoff: 2s, 4s, 8s by default.
    """
    if c is None:
        c = await get_client()
    last_exc: Exception | None = None
    for attempt in range(RETRY_MAX):
        try:
            resp = await c.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_exc = e
            if attempt < RETRY_MAX - 1:
                await asyncio.sleep(RETRY_BACKOFF ** attempt)
    raise last_exc  # type: ignore[misc]


# --- Input parsing ---

def split_inputs(text: str) -> list[str]:
    """Split user input into individual identifiers, stripping punctuation."""
    items: list[str] = []
    for line in re.split(r"[\n\r]+", text):
        line = line.strip().strip(",;，；")
        if line:
            items.append(line)
    return items


# --- Identifier cleaning ---

def clean_doi(value: str) -> str | None:
    """Extract and normalize a DOI from *value*. Returns ``None`` if not found."""
    match = DOI_RE.search(value)
    if not match:
        return None
    doi = match.group(0).rstrip(".。),]")
    return doi.lower()


def clean_arxiv(value: str) -> str | None:
    """Extract an arXiv identifier from *value*. Returns ``None`` if not found."""
    # arXiv DOI pattern: 10.48550/arxiv.XXXX.XXXXX
    arxiv_doi = re.search(r"10\.48550/arxiv\.(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)", value, re.I)
    if arxiv_doi:
        return arxiv_doi.group("id")
    # Avoid false-positive DOI matches
    if re.search(r"10\.\d{4,9}/", value, re.I):
        return None
    match = ARXIV_RE.search(value)
    if not match:
        return None
    arxiv_id = match.group("id").removesuffix(".pdf")
    # Reject too-short matches
    if "." not in arxiv_id and "/" not in arxiv_id:
        return None
    return arxiv_id


# --- Filename sanitization ---

def safe_filename(name: str, suffix: str = ".pdf") -> str:
    """Sanitize *name* into a safe filename, truncating at 140 chars."""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    if not name:
        name = "未命名文献"
    if len(name) > 140:
        name = name[:140].rstrip()
    return f"{name}{suffix}"
