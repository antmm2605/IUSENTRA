from __future__ import annotations

import base64
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from legal_ocr.models import PageArtifact

from .config import UnlimitedOcrSettings

JsonPoster = Callable[[str, dict[str, Any], int, str], dict[str, Any]]


class UnlimitedOcrClient:
    def __init__(self, settings: UnlimitedOcrSettings, *, post_json: JsonPoster | None = None) -> None:
        self.settings = settings
        self._post_json = post_json or post_json_request

    def generate_for_pages(self, pages: list[PageArtifact]) -> dict[str, Any]:
        payload = build_openai_payload(pages, settings=self.settings)
        last_error = ""
        started = time.perf_counter()
        for attempt in range(self.settings.max_retries):
            try:
                response = self._post_json(
                    self.settings.chat_completions_url,
                    payload,
                    self.settings.timeout_seconds,
                    self.settings.api_key,
                )
                text = extract_openai_text(response)
                return {
                    "ok": bool(text.strip()),
                    "text": text,
                    "raw": response,
                    "attempts": attempt + 1,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "error": "" if text.strip() else "Risposta senza testo.",
                }
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt < self.settings.max_retries - 1:
                    time.sleep(self.settings.retry_backoff_seconds * (attempt + 1))
        return {
            "ok": False,
            "text": "",
            "raw": {},
            "attempts": self.settings.max_retries,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": f"Endpoint non utilizzabile: {last_error}",
        }


def build_openai_payload(pages: list[PageArtifact], *, settings: UnlimitedOcrSettings) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": settings.prompt}]
    for page in pages:
        content.append(encode_page_image(page.image_path))
    payload: dict[str, Any] = {
        "model": settings.model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "skip_special_tokens": False,
        "stream": settings.stream,
        "images_config": {"image_mode": settings.image_mode},
        "custom_params": {"ngram_size": 35, "window_size": 1024},
    }
    return payload


def encode_page_image(image_path: str | Path) -> dict[str, Any]:
    path = Path(image_path)
    data = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def extract_openai_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [str(item.get("text") or "") for item in content if isinstance(item, dict)]
            if any(parts):
                return "\n".join(part for part in parts if part.strip())
        if isinstance(first.get("text"), str):
            return str(first.get("text") or "")
        delta = first.get("delta") if isinstance(first.get("delta"), dict) else {}
        if isinstance(delta.get("content"), str):
            return str(delta.get("content") or "")
    for key in ("text", "content", "output", "result"):
        if isinstance(response.get(key), str):
            return str(response.get(key) or "")
    return ""


def post_json_request(url: str, payload: dict[str, Any], timeout: int, api_key: str = "") -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - endpoint validato local-first da UnlimitedOcrSettings.readiness().
        raw = response.read()
    decoded = raw.decode("utf-8")
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        if payload.get("stream"):
            return _parse_openai_sse(decoded)
        raise


def _parse_openai_sse(raw: str) -> dict[str, Any]:
    parts: list[str] = []
    stream_events = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped.startswith("data:"):
            continue
        data = stripped.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        item = json.loads(data)
        stream_events += 1
        choices = item.get("choices") if isinstance(item, dict) else None
        if not isinstance(choices, list):
            continue
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            for value in (delta.get("content"), message.get("content"), choice.get("text")):
                if isinstance(value, str) and value:
                    parts.append(value)
    if not parts:
        raise ValueError("Stream Unlimited-OCR senza contenuto testuale.")
    return {"choices": [{"message": {"content": "".join(parts)}}], "stream_events": stream_events}
