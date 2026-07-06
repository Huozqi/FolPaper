"""Sync wrapper for paperdownload — usable from Flask routes."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure paperdownload is on sys.path for imports
_pkg = Path(__file__).resolve().parent
if str(_pkg) not in sys.path:
    sys.path.insert(0, str(_pkg))

from downloader import process_one
from config import DOWNLOAD_DIR


def download_by_doi(doi: str) -> Path | None:
    """Sync wrapper: resolve and download a paper by DOI. Returns the saved file path or None."""
    result = asyncio.run(process_one(doi))
    if result.status == "success" and result.file:
        return DOWNLOAD_DIR / result.file
    return None


def download_by_query(query: str) -> Path | None:
    """Sync wrapper: resolve and download by any query (DOI, arXiv ID, URL)."""
    result = asyncio.run(process_one(query))
    if result.status == "success" and result.file:
        return DOWNLOAD_DIR / result.file
    return None
