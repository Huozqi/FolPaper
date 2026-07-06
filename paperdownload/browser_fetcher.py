"""Headless-free browser fallback for PDFs hidden behind Cloudflare bot protection.

bioRxiv / medRxiv serve their ``.full.pdf`` files behind a Cloudflare Managed
Challenge. Plain ``httpx`` requests (and even Playwright's bundled Chromium)
are blocked with HTTP 403 + a "Just a moment…" interstitial. Only a *real*
system Chrome driven via Playwright (``channel="chrome"``) can pass the
challenge.

How passing actually works on this site (verified empirically, 2026-06):
  * Passing is **probabilistic / time-varying**, not a stable cookie grant.
    The same paper can pass on one attempt and fail the next; a fresh context
    per attempt is at least as good as a reused one.
  * Cross-paper cookie reuse does **NOT** work: fetching paper B's PDF with
    paper A's still-warm cookies still returns 403. Each paper needs its own
    passed challenge.
  * Therefore the reliable strategy is **retry**: for each paper, navigate the
    landing page, wait for the interstitial to clear, then ``fetch()`` the PDF
    from inside the page; if blocked, re-navigate and try again (up to
    ``MAX_ATTEMPTS`` times, with exponential backoff).

Per-paper flow inside one attempt:
  1. New context + page (clean state, anti-detection init script).
  2. ``goto(landing_url)``; poll the title until it's no longer the Cloudflare
     interstitial.
  3. In-page ``fetch(pdf_url)`` (carries the page's challenge cookies + real
     fingerprint) returns the raw bytes, streamed back via chunked base64.

The browser process is a process-wide singleton (lazy start, kept warm across
papers) so we only pay the ~3s Chrome cold start once per run.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Optional

from patchright.async_api import (
    Browser,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from models import PaperInfo, PdfDownloadError

# System Chrome path used by Playwright ``channel="chrome"``. Keep it real so
# Cloudflare sees a genuine browser fingerprint.
CHROME_CHANNEL = "chrome"

# Per-paper retry budget. Passing is probabilistic, so a few attempts cover the
# common transient failures. Tuned from probing (papers usually pass within 1-2).
MAX_ATTEMPTS = 4
# Per-navigation timeout for ``goto``.
NAV_TIMEOUT = 45  # seconds
# How long to wait for the "Just a moment…" interstitial to clear per attempt.
CHALLENGE_TIMEOUT = 40  # seconds
# How long the in-page fetch may take to return the PDF bytes.
PDF_FETCH_TIMEOUT = 60  # seconds
# Backoff base (seconds) between attempts: 2, 4, 8, ...
BACKOFF_BASE = 2.0

_challenge_titles = ("just a moment", "请稍候", "un momento", "até que", "juste un")

_state: dict = {"playwright": None, "browser": None}
_lock = asyncio.Lock()


async def _get_browser() -> Browser:
    """Return the shared browser, starting it (and Playwright) on first use."""
    if _state["browser"] is not None:
        return _state["browser"]
    async with _lock:
        if _state["browser"] is not None:
            return _state["browser"]
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.launch(
                channel=CHROME_CHANNEL,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except PlaywrightError as exc:
            await pw.stop()
            raise PdfDownloadError(
                "无法启动系统 Chrome（browser 自动化模式）。"
                "请确认已安装 Google Chrome，或稍后重试。"
                f"\n底层错误: {exc}",
            ) from exc
        _state["playwright"] = pw
        _state["browser"] = browser
        return browser


async def _wait_past_cloudflare(page) -> bool:
    """Block until the page title is no longer a Cloudflare interstitial."""
    for _ in range(CHALLENGE_TIMEOUT * 2):
        title = (await page.title()) or ""
        low = title.lower()
        if title.strip() and not any(m in low for m in _challenge_titles):
            return True
        await page.wait_for_timeout(500)
    return False


async def fetch_pdf_via_browser(info: PaperInfo) -> bytes:
    """Download ``info.pdf_url`` using Patchright (patchright) to bypass Cloudflare.

    Strategy: navigate to the landing page (DOI page) to pass Cloudflare, then
    directly ``goto`` the PDF URL and capture the response body. This works for
    bioRxiv, medRxiv, ChemRxiv, and any other CF-protected PDF host.
    """
    if not info.pdf_url:
        raise PdfDownloadError("未发现 PDF 链接，无法启动浏览器下载。", info)

    pdf_url = info.pdf_url
    # ChemRxiv: PDF URL 本身就是可访问页面，直接用它过 CF
    if "chemrxiv.org" in (pdf_url or ""):
        landing_url = pdf_url
    elif pdf_url.endswith(".full.pdf"):
        landing_url = pdf_url[: -len(".full.pdf")]
    elif info.landing_url:
        landing_url = info.landing_url
    else:
        landing_url = f"https://doi.org/{info.identifier}" if info.identifier.startswith("10.") else pdf_url

    browser = await _get_browser()
    last_error: str | None = None

    async with _lock:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(
                f"[browser] attempt {attempt}/{MAX_ATTEMPTS} via landing -> {landing_url}",
                file=sys.stderr,
            )
            context = await browser.new_context()
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()
            try:
                # Step 1: navigate to landing page to pass Cloudflare challenge
                try:
                    await page.goto(landing_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT * 1000)
                except (PlaywrightTimeout, Exception):
                    pass
                if not await _wait_past_cloudflare(page):
                    raise PdfDownloadError(f"Cloudflare 挑战未在 {CHALLENGE_TIMEOUT}s 内通过")

                # Step 2: on the landing page, JS-fetch the PDF via CF-approved session
                result = await page.evaluate("""
                    async (url) => {
                        const r = await fetch(url, {credentials: 'include'});
                        if (!r.ok) return 'HTTP ' + r.status;
                        const buf = await r.arrayBuffer();
                        const bytes = new Uint8Array(buf);
                        const n = bytes.length;
                        // Verify PDF header
                        if (bytes[0] !== 0x25 || bytes[1] !== 0x50) return 'NOT_PDF';
                        // Store in window for chunked retrieval
                        window.__pdf = bytes;
                        return '' + n;
                    }
                """, pdf_url)
                if result.startswith("HTTP"):
                    raise PdfDownloadError(f"JS fetch 返回 {result}")
                if result == "NOT_PDF":
                    raise PdfDownloadError("返回内容不是 PDF")

                # Retrieve bytes in 2MB chunks to avoid base64-encoding the whole thing at once
                total = int(result)
                chunks = []
                offset = 0
                CHUNK = 2 * 1024 * 1024
                while offset < total:
                    end = min(offset + CHUNK, total)
                    b64 = await page.evaluate(
                        """([off, end]) => {
                            const bytes = window.__pdf;
                            let bin = '';
                            for (let i = off; i < end; i++) bin += String.fromCharCode(bytes[i]);
                            return btoa(bin);
                        }""",
                        [offset, end],
                    )
                    import base64
                    chunks.append(base64.b64decode(b64))
                    offset = end
                await page.evaluate("() => { delete window.__pdf; }")
                data = b"".join(chunks)
                if not data.startswith(b"%PDF"):
                    raise PdfDownloadError("PDF 校验失败")
            except asyncio.TimeoutError:
                last_error = f"PDF 下载超时"
                print(f"[browser] attempt {attempt}: {last_error}", file=sys.stderr)
            except PdfDownloadError as exc:
                last_error = str(exc)
                print(f"[browser] attempt {attempt}: {last_error}", file=sys.stderr)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                print(f"[browser] attempt {attempt}: {last_error}", file=sys.stderr)
            else:
                print(f"[browser] attempt {attempt}: SUCCESS ({len(data)} bytes)", file=sys.stderr)
                return data
            finally:
                await context.close()

            if attempt < MAX_ATTEMPTS:
                delay = BACKOFF_BASE ** (attempt - 1)
                print(f"[browser] backing off {delay:.0f}s", file=sys.stderr)
                await asyncio.sleep(delay)

    raise PdfDownloadError(
        f"经过 {MAX_ATTEMPTS} 次重试仍无法下载 PDF（最后错误：{last_error}）。"
        "可能是 Cloudflare 或站点限制，请稍后重试或在浏览器中手动打开链接。",
        info,
    )


async def close_browser() -> None:
    """Tear down the shared browser and Playwright driver (call on shutdown)."""
    global _state
    browser: Optional[Browser] = _state.get("browser")
    pw = _state.get("playwright")
    if browser is not None:
        try:
            await browser.close()
        except Exception:
            pass
    if pw is not None:
        try:
            await pw.stop()
        except Exception:
            pass
    _state = {"playwright": None, "browser": None}
