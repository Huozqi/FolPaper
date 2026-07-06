"""PaperDownload — FastAPI application entry point.

Batch-download open-access PDFs from DOI, arXiv, bioRxiv, medRxiv, ChemRxiv.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import DOWNLOAD_DIR, STATIC_DIR, HOST, PORT, CORS_ORIGINS, MAX_CONCURRENT, TASK_TIMEOUT
from downloader import process_one
from models import DownloadRequest, PaperResult
from utils import close_client, get_client, split_inputs

# Ensure directories exist
STATIC_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up the HTTP client on startup; close it (and the browser) on shutdown."""
    await get_client()
    yield
    await close_client()
    # Only close the browser if browser_fetcher was imported (lazy, on demand).
    try:
        from browser_fetcher import close_browser
        await close_browser()
    except Exception:
        pass


app = FastAPI(title="PaperDownload", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes — download
# ---------------------------------------------------------------------------

@app.post("/api/download", response_model=list[PaperResult])
async def download_papers(payload: DownloadRequest) -> list[PaperResult]:
    """Batch download (non-streaming). All results returned at once."""
    items = split_inputs(payload.inputs)
    if not items:
        raise HTTPException(status_code=400, detail="请输入 DOI、arXiv 编号或 URL")

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def guarded(item: str) -> PaperResult:
        async with sem:
            return await process_one(
                item,
                translate=payload.translate,
                api_key=payload.api_key,
            )

    return await asyncio.gather(*(guarded(item) for item in items))


@app.post("/api/download/stream")
async def download_papers_stream(payload: DownloadRequest, request: Request):
    """Stream download results via Server-Sent Events.

    Each paper result is emitted as it completes, with progress counters.
    Closing the connection cancels remaining work.
    """
    items = split_inputs(payload.inputs)
    if not items:
        raise HTTPException(status_code=400, detail="请输入 DOI、arXiv 编号或 URL")

    cancel = asyncio.Event()
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    total = len(items)
    completed = 0
    stages: dict[str, str] = {item: "queued" for item in items}
    status_q: asyncio.Queue[dict[str, str]] = asyncio.Queue()

    def _emit(event_type: str, **kwargs) -> str:
        return f"data: {json.dumps({'type': event_type, **kwargs}, ensure_ascii=False)}\n\n"

    async def event_generator():
        nonlocal completed

        # --- phase 1: announce all items ---
        yield _emit("start", queries=items, total=total)

        async def guarded(item: str) -> PaperResult:
            nonlocal completed
            if cancel.is_set():
                return PaperResult(query=item, status="cancelled", error="下载已取消")
            async with sem:
                stages[item] = "processing"
                await status_q.put({"query": item, "stage": "processing"})
                try:
                    result = await asyncio.wait_for(
                        process_one(
                            item,
                            translate=payload.translate,
                            api_key=payload.api_key,
                        ),
                        timeout=TASK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    result = PaperResult(
                        query=item,
                        status="failed",
                        error=f"处理超时（{int(TASK_TIMEOUT)}s）",
                    )
                except Exception as exc:
                    result = PaperResult(query=item, status="failed", error=str(exc))
            completed += 1
            stages[item] = result.status
            return result

        coros = [guarded(item) for item in items]
        tasks = [asyncio.create_task(c) for c in coros]
        pending = set(tasks)

        try:
            while pending:
                # Drain status queue first
                while not status_q.empty():
                    status = await status_q.get()
                    yield _emit("status", stages={status["query"]: status["stage"]})

                # Wait for next task completion (with brief timeout to check disconnect)
                done, pending = await asyncio.wait(
                    pending, timeout=0.5, return_when=asyncio.FIRST_COMPLETED
                )
                for t in done:
                    try:
                        result = await t
                    except Exception as exc:
                        result = PaperResult(query="?", status="failed", error=str(exc))
                    yield _emit(
                        "result",
                        data=result.model_dump(),
                        progress={"done": completed, "total": total},
                        stages=dict(stages),
                    )

                if await request.is_disconnected():
                    cancel.set()
                    break
        finally:
            cancel.set()
            for t in pending:
                if not t.done():
                    t.cancel()
            yield _emit("done")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Routes — file listing
# ---------------------------------------------------------------------------

@app.get("/api/files")
async def list_files() -> list[dict[str, Any]]:
    """List downloaded PDFs, newest first."""
    files: list[dict[str, Any]] = []
    for path in sorted(
        DOWNLOAD_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "url": f"/downloads/{quote(path.name)}",
            }
        )
    return files


# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

app.mount("/downloads", StaticFiles(directory=DOWNLOAD_DIR), name="downloads")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
