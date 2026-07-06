"""Title translation via DeepSeek API."""

from __future__ import annotations

import httpx

from config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

TRANSLATE_SYSTEM_PROMPT = (
    "你是一个学术文献翻译助手。将以下英文论文标题翻译为简洁准确的中文。"
    "只返回翻译结果，不要解释，不要加引号。"
)


async def translate_title_deepseek(
    title: str,
    api_key: str,
    *,
    base_url: str = DEEPSEEK_BASE_URL,
    model: str = DEEPSEEK_MODEL,
) -> tuple[str | None, str | None]:
    """Translate an English paper title to Chinese via DeepSeek API.

    Returns ``(translated_title, error_message)``.  On success *error_message*
    is ``None``; on failure *translated_title* is ``None`` and *error_message*
    explains why (e.g.  "401 — invalid API key", "model not found").
    """
    if not api_key:
        return None, "未提供 API Key"
    if not title:
        return None, "标题为空"

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
            {"role": "user", "content": title},
        ],
        "max_tokens": 200,
        "temperature": 0.1,
        "thinking": {"type": "disabled"},
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                detail = ""
                try:
                    err = resp.json()
                    detail = err.get("error", {}).get("message", "")
                except Exception:
                    detail = resp.text[:120]
                return None, f"DeepSeek HTTP {resp.status_code} — {detail}"
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            translated = (message.get("content") or "").strip()
            if translated:
                return translated, None
            return None, "DeepSeek 返回空内容"
    except httpx.TimeoutException:
        return None, "DeepSeek 请求超时"
    except Exception as exc:
        return None, f"DeepSeek 请求失败: {exc}"
