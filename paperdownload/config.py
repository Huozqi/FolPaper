"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = Path(os.getenv("PAPER_DOWNLOAD_DIR", str(APP_DIR / "downloads")))
STATIC_DIR = APP_DIR / "static"

HOST = os.getenv("PAPER_HOST", "127.0.0.1")
PORT = int(os.getenv("PAPER_PORT", "7862"))

USER_AGENT = os.getenv(
    "PAPER_USER_AGENT",
    "paperdownload/0.2 (+local scholarly downloader; mailto:example@example.com)",
)
UNPAYWALL_EMAIL = os.getenv("PAPER_EMAIL", "example@example.com")

TIMEOUT = float(os.getenv("PAPER_TIMEOUT", "30"))
CONNECT_TIMEOUT = float(os.getenv("PAPER_CONNECT_TIMEOUT", "10"))
MAX_CONCURRENT = int(os.getenv("PAPER_MAX_CONCURRENT", "4"))
RETRY_MAX = int(os.getenv("PAPER_RETRY_MAX", "3"))
RETRY_BACKOFF = float(os.getenv("PAPER_RETRY_BACKOFF", "2.0"))
# Per-paper wall-clock budget. bioRxiv downloads go through a real browser
# (Cloudflare challenge ~10-15s, serialized), so this must comfortably exceed
# the slowest single download or batch downloads will be misreported as timed out.
TASK_TIMEOUT = float(os.getenv("PAPER_TASK_TIMEOUT", "240"))

CORS_ORIGINS = [
    f"http://{HOST}:{PORT}",
    f"http://localhost:{PORT}",
    f"http://127.0.0.1:{PORT}",
]

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
