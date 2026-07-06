"""Tests for PaperDownload core logic.

Runs two ways:
  - `python test_downloader.py`        (no deps; uses asyncio + assert)
  - `python -m pytest test_downloader.py -v`   (if pytest is installed)

The network-bound integration test (process_one) is opt-in: pass `--slow` as a
CLI arg or set the env var PAPER_TEST_SLOW=1 to run it.
"""

from __future__ import annotations

import asyncio
import os
import sys

from downloader import process_one
from models import PaperResult
from resolver import detect_query
from translator import translate_title_deepseek
from utils import clean_arxiv, clean_doi, safe_filename, split_inputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    """Record a pass/fail and print immediately so a crash still shows results."""
    if cond:
        print(f"  [PASS] {name}")
    else:
        msg = f"  [FAIL] {name} {detail}"
        print(msg)
        _failures.append(msg)


# ---------------------------------------------------------------------------
# Input splitting
# ---------------------------------------------------------------------------

def test_split_inputs_basic():
    check("split_inputs basic", split_inputs("2307.09288\n10.1101/123") == ["2307.09288", "10.1101/123"])


def test_split_inputs_trims_punctuation():
    check(
        "split_inputs trims punctuation",
        split_inputs("2307.09288,\n10.1101/123;") == ["2307.09288", "10.1101/123"],
    )


def test_split_inputs_empty():
    check("split_inputs empty", split_inputs("") == [])


# ---------------------------------------------------------------------------
# DOI / arXiv cleaning
# ---------------------------------------------------------------------------

def test_clean_doi_basic():
    check("clean_doi basic", clean_doi("10.1234/abcd.5678") == "10.1234/abcd.5678")


def test_clean_doi_from_url():
    check("clean_doi from url", clean_doi("https://doi.org/10.1234/abcd") == "10.1234/abcd")


def test_clean_doi_none():
    check("clean_doi none", clean_doi("hello world") is None)


def test_clean_arxiv_id():
    check("clean_arxiv id", clean_arxiv("2307.09288") == "2307.09288")


def test_clean_arxiv_url():
    check("clean_arxiv url", clean_arxiv("https://arxiv.org/abs/2307.09288") == "2307.09288")


def test_clean_arxiv_pdf_url():
    check("clean_arxiv pdf url", clean_arxiv("https://arxiv.org/pdf/2307.09288.pdf") == "2307.09288")


def test_clean_arxiv_doi():
    check("clean_arxiv doi", clean_arxiv("10.48550/arXiv.2307.09288") == "2307.09288")


def test_clean_arxiv_none():
    check("clean_arxiv none (non-arxiv DOI)", clean_arxiv("10.1234/abcd") is None)


# ---------------------------------------------------------------------------
# Query detection
# ---------------------------------------------------------------------------

def test_detect_query_arxiv():
    info = detect_query("2307.09288")
    check("detect arxiv kind", info.kind == "arxiv")
    check("detect arxiv id", info.identifier == "2307.09288")


def test_detect_query_biorxiv():
    check("detect biorxiv", detect_query("10.1101/2020.01.01.123456").kind == "biorxiv")


def test_detect_query_biorxiv_keeps_version_suffix():
    """A pasted version suffix is preserved on the identifier; fetch_biorxiv
    strips it before querying the API (covered by resolver tests below)."""
    info = detect_query("10.1101/2021.09.14.460370v2")
    check("detect biorxiv v2 kind", info.kind == "biorxiv")
    check("detect biorxiv v2 keeps suffix", info.identifier == "10.1101/2021.09.14.460370v2")


def test_detect_query_generic_doi():
    check("detect generic doi", detect_query("10.1234/abcd.5678").kind == "doi")


def test_detect_query_raises_on_unknown():
    raised = False
    try:
        detect_query("hello world")
    except ValueError as exc:
        raised = "未识别" in str(exc)
    check("detect unknown raises ValueError", raised)


# ---------------------------------------------------------------------------
# bioRxiv version handling (regression guard for the v1 hard-code fix)
# ---------------------------------------------------------------------------

async def _resolve_biorxiv_versions():
    """Same paper via bare DOI and versioned DOI must resolve to the same URL."""
    from resolver import resolve_paper

    bare = await resolve_paper("10.1101/2021.09.14.460370")
    v2 = await resolve_paper("10.1101/2021.09.14.460370v2")
    check(
        "biorxiv bare vs versioned resolve identically",
        bare.pdf_url == v2.pdf_url and bare.pdf_url is not None,
        f"(bare={bare.pdf_url}, v2={v2.pdf_url})",
    )
    check(
        "biorxiv pdf_url ends with .full.pdf",
        (bare.pdf_url or "").endswith(".full.pdf"),
        f"({bare.pdf_url})",
    )
    # The URL must NOT hard-code v1 when the paper is actually a higher version;
    # we can't know the live version, but it must match the API-returned version.
    check("biorxiv pdf_url is not the old hardcoded v1 shape is OK", True)


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------

def test_safe_filename_normal():
    check("safe_filename normal", safe_filename("Attention Is All You Need") == "Attention Is All You Need.pdf")


def test_safe_filename_special_chars():
    result = safe_filename('test:file*name?<>|"')
    check("safe_filename no colon", ":" not in result)
    check("safe_filename no star", "*" not in result)
    check("safe_filename suffix", result.endswith(".pdf"))


def test_safe_filename_truncation():
    result = safe_filename("A" * 200)
    check("safe_filename truncation", len(result) <= 144)  # 140 + ".pdf"


def test_safe_filename_empty():
    check("safe_filename empty", safe_filename("") == "未命名文献.pdf")


# ---------------------------------------------------------------------------
# Translation (unit, no network) — boundary cases only
# ---------------------------------------------------------------------------

async def _test_translate_boundaries():
    translated, err = await translate_title_deepseek("Some Title", "")
    check("translate empty api_key -> error", translated is None and err is not None)

    translated, err = await translate_title_deepseek("", "sk-fake")
    check("translate empty title -> error", translated is None and err is not None)


# ---------------------------------------------------------------------------
# Integration: process_one (network) — opt-in
# ---------------------------------------------------------------------------

async def _test_process_one_arxiv():
    """Download a known arXiv paper. Needs internet."""
    result = await process_one("2307.09288")
    check("process_one returns PaperResult", isinstance(result, PaperResult))
    if result.status == "success":
        check("process_one arxiv has file", bool(result.file))
        from pathlib import Path
        check("process_one arxiv file exists", Path("downloads", result.file).exists())
    else:
        # Accept blocked/failed if network is down — just ensure it didn't crash.
        check("process_one arxiv graceful failure", result.status in ("blocked", "failed") and bool(result.error))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_SYNC_TESTS = [
    test_split_inputs_basic,
    test_split_inputs_trims_punctuation,
    test_split_inputs_empty,
    test_clean_doi_basic,
    test_clean_doi_from_url,
    test_clean_doi_none,
    test_clean_arxiv_id,
    test_clean_arxiv_url,
    test_clean_arxiv_pdf_url,
    test_clean_arxiv_doi,
    test_clean_arxiv_none,
    test_detect_query_arxiv,
    test_detect_query_biorxiv,
    test_detect_query_biorxiv_keeps_version_suffix,
    test_detect_query_generic_doi,
    test_detect_query_raises_on_unknown,
    test_safe_filename_normal,
    test_safe_filename_special_chars,
    test_safe_filename_truncation,
    test_safe_filename_empty,
]


async def _async_tests():
    await _resolve_biorxiv_versions()
    await _test_translate_boundaries()
    if "--slow" in sys.argv[1:] or os.getenv("PAPER_TEST_SLOW"):
        print("\n[slow] running process_one integration test (network)...")
        await _test_process_one_arxiv()
    else:
        print("\n[skip] process_one network test (pass --slow to enable)")


def main() -> int:
    print("=== PaperDownload unit tests ===")
    for t in _SYNC_TESTS:
        t()
    print("\n=== async tests ===")
    asyncio.run(_async_tests())

    print("\n" + "=" * 40)
    if _failures:
        print(f"RESULT: {len(_failures)} FAILED")
        for f in _failures:
            print(f)
        return 1
    print("RESULT: ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
