"""Data models for PaperDownload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class DownloadRequest(BaseModel):
    inputs: str = Field(
        ...,
        description="One DOI, arXiv id, URL, or multiple items separated by newlines",
    )
    translate: bool = Field(
        False,
        description="Translate title to Chinese via DeepSeek API (requires api_key)",
    )
    api_key: str | None = Field(
        None,
        description="DeepSeek API key (sk-...). Sent from frontend localStorage.",
    )


class PaperResult(BaseModel):
    query: str
    status: str  # "success" | "blocked" | "failed" | "cancelled"
    source: str | None = None
    title: str | None = None
    pdf_url: str | None = None
    file: str | None = None
    error: str | None = None
    translate_error: str | None = None


class PdfDownloadError(RuntimeError):
    """Raised when a PDF is found but cannot be downloaded (e.g. HTTP 403)."""

    def __init__(self, message: str, info: PaperInfo | None = None):
        super().__init__(message)
        self.info = info


@dataclass
class PaperInfo:
    query: str
    kind: str  # "arxiv" | "biorxiv" | "doi"
    identifier: str
    title: str | None = None
    pdf_url: str | None = None
    landing_url: str | None = None
    source: str | None = None
