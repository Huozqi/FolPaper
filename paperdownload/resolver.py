"""Paper resolution: detect query type and fetch metadata from arXiv, bioRxiv, Crossref, Unpaywall."""

from __future__ import annotations

import asyncio
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from config import UNPAYWALL_EMAIL
from models import PaperInfo
from utils import clean_doi, clean_arxiv, fetch_with_retry, get_client


# ---------------------------------------------------------------------------
# Query detection
# ---------------------------------------------------------------------------

def detect_query(query: str) -> PaperInfo:
    """Classify *query* as arXiv, bioRxiv/medRxiv, or generic DOI."""
    arxiv_id = clean_arxiv(query)
    if arxiv_id:
        return PaperInfo(query=query, kind="arxiv", identifier=arxiv_id, source="arXiv")

    doi = clean_doi(query)
    if doi:
        if doi.startswith("10.1101/"):
            return PaperInfo(query=query, kind="biorxiv", identifier=doi, source="bioRxiv/medRxiv")
        if doi.startswith("10.26434/chemrxiv"):
            return PaperInfo(query=query, kind="doi", identifier=doi, source="ChemRxiv/DOI")
        return PaperInfo(query=query, kind="doi", identifier=doi, source="DOI/OA")

    raise ValueError("未识别 DOI、arXiv 编号或文献 URL")


# ---------------------------------------------------------------------------
# arXiv
# ---------------------------------------------------------------------------

async def fetch_arxiv(info: PaperInfo) -> PaperInfo:
    """Resolve an arXiv paper: set PDF URL and fetch title from the API."""
    info.pdf_url = f"https://arxiv.org/pdf/{info.identifier}.pdf"
    info.landing_url = f"https://arxiv.org/abs/{info.identifier}"
    info.source = "arXiv"

    # arXiv API 经常很慢，给 8s 超时；拿不到标题也不影响下载
    try:
        c = await get_client()
        resp = await c.get(
            f"https://export.arxiv.org/api/query?id_list={quote(info.identifier)}",
            timeout=8,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        title_el = root.find("atom:entry/atom:title", ns)
        if title_el is not None and title_el.text:
            info.title = " ".join(title_el.text.split())
    except Exception:
        pass  # 拿不到标题也无所谓，PDF URL 已就绪
    return info


# ---------------------------------------------------------------------------
# bioRxiv / medRxiv
# ---------------------------------------------------------------------------

async def fetch_biorxiv(info: PaperInfo) -> PaperInfo:
    """Try bioRxiv and medRxiv metadata APIs, falling back to DOI resolution.

    The details API returns the latest version of the manuscript; we read the
    ``version`` field (e.g. ``"2"``) instead of hard-coding ``v1`` so that the
    constructed PDF/landing URLs point at the correct version.
    """
    # bioRxiv's details API only accepts the bare DOI (no ``vN`` suffix); strip
    # any version the user may have pasted so the query still matches.
    bare_doi = re.sub(r"v\d+$", "", info.identifier)
    last_error: str | None = None
    for server in ("biorxiv", "medrxiv"):
        url = f"https://api.biorxiv.org/details/{server}/{bare_doi}"
        try:
            response = await fetch_with_retry(url)
            data = response.json()
        except httpx.HTTPStatusError as exc:
            last_error = f"{server} API HTTP {exc.response.status_code}"
            print(f"[biorxiv] {last_error} for {info.identifier}", file=sys.stderr)
            continue
        except Exception as exc:  # network / JSON parse errors
            last_error = f"{server} API error: {type(exc).__name__}: {exc}"
            print(f"[biorxiv] {last_error}", file=sys.stderr)
            continue

        collection = data.get("collection") or []
        if not collection:
            print(f"[biorxiv] {server}: empty collection for {info.identifier}", file=sys.stderr)
            continue

        item = collection[0]
        # Prefer the original-case DOI returned by the API; fall back to the
        # lowercased identifier so URL construction is robust either way.
        doi = item.get("doi") or info.identifier
        version = item.get("version") or "1"
        info.title = item.get("title") or info.title
        info.source = server
        info.landing_url = f"https://www.{server}.org/content/{doi}v{version}"
        info.pdf_url = f"https://www.{server}.org/content/{doi}v{version}.full.pdf"
        return info

    print(
        f"[biorxiv] all servers failed for {info.identifier} ({last_error}); "
        "falling back to generic DOI resolution",
        file=sys.stderr,
    )
    # Fallback: generic DOI/OA discovery
    return await fetch_doi(info)


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

async def _fetch_crossref(c: httpx.AsyncClient, doi: str) -> tuple[str | None, str | None]:
    """Query Crossref API for title and PDF link."""
    try:
        response = await fetch_with_retry(
            f"https://api.crossref.org/works/{quote(doi, safe='')}",
            c=c,
        )
        data = response.json().get("message") or {}
        titles: list[str] = data.get("title") or []
        title = titles[0] if titles else None

        pdf_url: str | None = None
        for link in data.get("link") or []:
            url = link.get("URL")
            content_type = (link.get("content-type") or "").lower()
            # Only match real PDF links — skip similarity-checking (iThenticate)
            if url and ("pdf" in url.lower() or "pdf" in content_type):
                pdf_url = url
                break
        return title, pdf_url
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Unpaywall
# ---------------------------------------------------------------------------

async def _fetch_unpaywall(c: httpx.AsyncClient, doi: str) -> tuple[str | None, str | None]:
    """Query Unpaywall API for OA title and PDF link."""
    try:
        url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={UNPAYWALL_EMAIL}"
        response = await fetch_with_retry(url, c=c)
        data = response.json()
        title: str | None = data.get("title")

        best = data.get("best_oa_location") or {}
        pdf_url: str | None = best.get("url_for_pdf") or best.get("url")
        if not pdf_url:
            for loc in data.get("oa_locations") or []:
                pdf_url = loc.get("url_for_pdf") or loc.get("url")
                if pdf_url:
                    break
        return title, pdf_url
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Landing-page PDF discovery
# ---------------------------------------------------------------------------

def _pdf_links_from_html(html: str, base_url: str) -> list[str]:
    """Extract PDF candidate URLs from an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []

    # Meta tags: citation_pdf_url, bepress_citation_pdf_url
    for meta_name in ("citation_pdf_url", "bepress_citation_pdf_url"):
        for tag in soup.find_all("meta", attrs={"name": meta_name}):
            content = tag.get("content")
            if content:
                urls.append(urljoin(base_url, content))

    # Anchor / link tags with PDF indicators
    for tag in soup.find_all(["a", "link"]):
        href = tag.get("href")
        if not href:
            continue
        text = tag.get_text(" ", strip=True).lower()
        rel = " ".join(tag.get("rel") or []).lower()
        href_l = href.lower()
        if ".pdf" in href_l or "pdf" in text or "pdf" in rel:
            urls.append(urljoin(base_url, href))

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


async def _discover_pdf_from_landing(
    c: httpx.AsyncClient, landing_url: str
) -> tuple[str | None, str | None]:
    """Scrape a landing page for PDF links and title metadata."""
    try:
        resp = await c.get(landing_url, headers={"Accept": "text/html,application/pdf,*/*"})
        if resp.status_code >= 400:
            return None, None
        content_type = resp.headers.get("content-type", "").lower()
        if "application/pdf" in content_type:
            return str(resp.url), None

        soup = BeautifulSoup(resp.text, "html.parser")
        title: str | None = None
        meta_title = soup.find("meta", attrs={"name": "citation_title"})
        if meta_title and meta_title.get("content"):
            title = meta_title["content"]
        elif soup.title:
            title = soup.title.get_text(" ", strip=True)

        for pdf_url in _pdf_links_from_html(resp.text, str(resp.url)):
            return pdf_url, title
    except Exception:
        return None, None
    return None, None


# ---------------------------------------------------------------------------
# Generic DOI
# ---------------------------------------------------------------------------

async def fetch_doi(info: PaperInfo) -> PaperInfo:
    """Resolve a generic DOI via Crossref + Unpaywall + landing-page scraping."""
    c = await get_client()
    crossref_task = _fetch_crossref(c, info.identifier)
    unpaywall_task = _fetch_unpaywall(c, info.identifier)
    (title, crossref_pdf), (oa_title, oa_pdf) = await asyncio.gather(
        crossref_task, unpaywall_task
    )

    info.title = oa_title or title
    if crossref_pdf or oa_pdf:
        info.pdf_url = crossref_pdf or oa_pdf

    doi_landing = f"https://doi.org/{info.identifier}"
    info.landing_url = doi_landing

    # 已知 OA 期刊：直接构建 PDF URL，避免被 Cloudflare 挡住 scraping
    if not info.pdf_url and not crossref_pdf and not oa_pdf:
        _KNOWN_OA_PATTERNS = [
            # Nature 系列: https://www.nature.com/articles/s41467-xxx-xxxx-x.pdf
            (r'^10\.1038/', lambda d: f'https://www.nature.com/articles/{d.split("/", 1)[1]}.pdf'),
            # Science: https://www.science.org/doi/pdf/10.1126/xxx
            (r'^10\.1126/', lambda d: f'https://www.science.org/doi/pdf/{d}'),
            # PLOS: https://journals.plos.org/plosone/article/file?id=10.1371/xxx&type=printable
            (r'^10\.1371/', lambda d: f'https://journals.plos.org/plosone/article/file?id={d}&type=printable'),
            # eLife: https://elifesciences.org/articles/xxxxx.pdf
            (r'^10\.7554/', lambda d: f'https://elifesciences.org/articles/{d.split("/", 1)[1].split(".")[0]}.pdf'),
        ]
        for pattern, builder in _KNOWN_OA_PATTERNS:
            if __import__('re').match(pattern, info.identifier):
                info.pdf_url = builder(info.identifier)
                break

    if not info.pdf_url:
        found_pdf, found_title = await _discover_pdf_from_landing(c, doi_landing)
        info.pdf_url = found_pdf
        info.title = info.title or found_title
    return info


# ---------------------------------------------------------------------------
# Top-level dispatcher
# ---------------------------------------------------------------------------

async def resolve_paper(query: str) -> PaperInfo:
    """Detect query type and fetch full metadata + PDF URL."""
    info = detect_query(query)
    if info.kind == "arxiv":
        return await fetch_arxiv(info)
    if info.kind == "biorxiv":
        return await fetch_biorxiv(info)
    return await fetch_doi(info)
