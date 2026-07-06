"""PDF download and top-level processing logic."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

from config import DOWNLOAD_DIR
from models import PaperInfo, PaperResult, PdfDownloadError
from pd_translator import translate_title_deepseek
from utils import get_client, safe_filename

FILE_WRITE_LOCK = asyncio.Lock()

DOWNLOAD_DIR.mkdir(exist_ok=True)


async def _looks_like_cloudflare_block(resp: httpx.Response) -> bool:
    """Heuristic: did the server return a Cloudflare challenge instead of a PDF?"""
    if resp.status_code != 403:
        return False
    body = resp.content[:512].lower()
    return b"just a moment" in body or b"cf_chl" in body or b"challenges.cloudflare" in body


async def _fetch_pdf_bytes(info: PaperInfo) -> bytes:
    """Fetch the PDF bytes, falling back to a real browser for Cloudflare-protected hosts.

    bioRxiv / medRxiv sit behind Cloudflare's bot challenge, which httpx cannot
    pass (intermittent 403 + "Just a moment…" interstitial). For those sources
    we retry via the browser fallback defined in :mod:`browser_fetcher`. Every
    other source keeps the fast in-process path.
    """
    c = await get_client()
    resp = await c.get(info.pdf_url, headers={"Accept": "application/pdf,*/*"})

    if resp.status_code == 403:
        # bioRxiv / medRxiv / ChemRxiv are behind Cloudflare; try browser fallback
        cf_hosts = ('biorxiv.org', 'medrxiv.org', 'chemrxiv.org', 'nature.com')
        if info.kind == "biorxiv" or _looks_like_cloudflare_block(resp) or \
           any(h in (info.pdf_url or '') for h in cf_hosts):
            print(
                f"[download] {info.pdf_url} blocked by Cloudflare; retrying via browser",
                file=sys.stderr,
            )
            from browser_fetcher import fetch_pdf_via_browser
            return await fetch_pdf_via_browser(info)
        raise PdfDownloadError(
            "PDF 链接存在，但站点拒绝后端直接下载（HTTP 403）。"
            "请用浏览器打开链接下载，或稍后使用浏览器自动化模式。",
            info,
        )
    if resp.status_code >= 400:
        raise PdfDownloadError(f"PDF 下载失败：HTTP {resp.status_code}", info)

    content_type = resp.headers.get("content-type", "").lower()
    content = resp.content
    if "pdf" not in content_type and not content.startswith(b"%PDF"):
        raise RuntimeError("目标链接未返回 PDF 文件")
    return content


async def download_pdf(info: PaperInfo, filename: str) -> Path:
    """Download a PDF from *info.pdf_url* and save it to the downloads directory.

    Returns the path to the saved file.
    """
    if not info.pdf_url:
        raise RuntimeError("未找到开放 PDF 链接。可能是闭源期刊或需要登录。")

    content = await _fetch_pdf_bytes(info)

    async with FILE_WRITE_LOCK:
        target = DOWNLOAD_DIR / filename
        base = target.stem
        suffix = target.suffix
        counter = 2
        while target.exists():
            target = DOWNLOAD_DIR / f"{base}_{counter}{suffix}"
            counter += 1
        target.write_bytes(content)
    return target


async def process_one(
    query: str,
    *,
    translate: bool = False,
    api_key: str | None = None,
) -> PaperResult:
    """Resolve and download a single paper identified by *query*.

    If *translate* is ``True`` and *api_key* is provided, the title is
    translated to Chinese via DeepSeek before being used as the filename.
    """
    from resolver import resolve_paper

    try:
        info = await resolve_paper(query)
        if not info.pdf_url:
            raise RuntimeError("未发现可下载 PDF。仅支持预印本或开放获取 PDF。")

        title = info.title
        chinese_title: str | None = None
        translate_error: str | None = None

        if translate and api_key and title:
            chinese_title, translate_error = await translate_title_deepseek(title, api_key)

        filename = safe_filename(chinese_title or title or info.identifier.replace("/", "_"))
        path = await download_pdf(info, filename)
        return PaperResult(
            query=query,
            status="success",
            source=info.source,
            title=chinese_title or title,
            pdf_url=info.pdf_url,
            file=path.name,
            translate_error=translate_error,
        )
    except PdfDownloadError as exc:
        pinfo = exc.info
        return PaperResult(
            query=query,
            status="blocked",
            source=pinfo.source if pinfo else None,
            title=pinfo.title if pinfo else None,
            pdf_url=pinfo.pdf_url if pinfo else None,
            error=str(exc),
        )
    except Exception as exc:
        return PaperResult(query=query, status="failed", error=str(exc))
