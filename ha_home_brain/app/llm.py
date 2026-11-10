"""Un singur client LLM pentru tot add-on-ul: apeluri serializate, același model și context.

Două backend-uri:
- `ollama`: API-ul nativ Ollama (`/api/chat`), cu `num_ctx` și `keep_alive`.
- `openai`: orice server compatibil OpenAI (`/v1/chat/completions`) – LM Studio, llama.cpp,
  vLLM, LocalAI, Jan, text-generation-webui... sau un serviciu online, dacă vrei.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from urllib.parse import urlparse

import aiohttp
from .i18n import t

log = logging.getLogger("home_brain.llm")

BACKENDS = ("ollama", "openai")
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def openai_base(url: str) -> str:
    """`http://host:1234` → `http://host:1234/v1`; o cale dată explicit (ex. `/api/v1`) rămâne."""
    url = (url or "").strip().rstrip("/")
    if url and urlparse(url).path in ("", "/"):
        url += "/v1"
    return url


def parse_json(text: str) -> dict | None:
    """JSON din răspunsul modelului, tolerant la <think>, ```json ... ``` și text în jur."""
    text = _FENCE.sub("", _THINK.sub("", text or "").strip()).strip()
    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            data = json.loads(c)
        except (json.JSONDecodeError, ValueError):
            continue
        return data if isinstance(data, dict) else {"value": data}
    return None


class LLM:
    def __init__(self, cfg: dict) -> None:
        self.backend = (cfg.get("backend") or "ollama").lower()
        if self.backend not in BACKENDS:
            self.backend = "ollama"
        if self.backend == "openai":
            self.url = openai_base(cfg.get("openai_url") or cfg.get("ollama_url") or "")
        else:
            self.url = (cfg.get("ollama_url") or "").strip().rstrip("/")
        self.api_key = (cfg.get("api_key") or "").strip()
        self.model = cfg.get("model") or "llama3.1:8b"
        # Același num_ctx ca integrarea Ollama din HA: altfel Ollama reîncarcă modelul.
        self.num_ctx = int(cfg.get("num_ctx", 8192))
        self.lock = asyncio.Lock()
        self.calls = 0
        self.last_seconds = 0.0
        self._json_mode = True  # unele servere OpenAI nu acceptă response_format=json_object

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    @property
    def label(self) -> str:
        return "Ollama" if self.backend == "ollama" else "OpenAI-compatible"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    async def chat_json(self, messages: list[dict], timeout: float = 180) -> tuple[dict | None, str]:
        """Întoarce (json, text brut). json e None dacă modelul n-a respectat formatul."""
        if not self.enabled:
            return None, t("llm.not_configured")
        async with self.lock:
            t0 = time.monotonic()
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
                    if self.backend == "openai":
                        content = await self._openai(s, messages)
                    else:
                        content = await self._ollama(s, messages)
            finally:
                self.calls += 1
                self.last_seconds = time.monotonic() - t0
        return parse_json(content), content

    async def _ollama(self, s: aiohttp.ClientSession, messages: list[dict]) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False, "format": "json",
                   "think": False, "keep_alive": -1, "options": {"num_ctx": self.num_ctx}}
        async with s.post(f"{self.url}/api/chat", json=payload, headers=self._headers()) as r:
            r.raise_for_status()
            body = await r.json()
        return body.get("message", {}).get("content", "")

    async def _openai(self, s: aiohttp.ClientSession, messages: list[dict]) -> str:
        payload: dict = {"model": self.model, "messages": messages, "stream": False, "temperature": 0.2}
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with s.post(f"{self.url}/chat/completions", json=payload, headers=self._headers()) as r:
            if r.status in (400, 422) and self._json_mode:
                # Server fără JSON mode (ex. unele versiuni LM Studio): reîncercăm fără, ținem minte.
                log.info("Server rejected response_format=json_object (%s); retrying without it", r.status)
                self._json_mode = False
                payload.pop("response_format", None)
            else:
                r.raise_for_status()
                body = await r.json()
                return _openai_content(body)
        async with s.post(f"{self.url}/chat/completions", json=payload, headers=self._headers()) as r:
            r.raise_for_status()
            return _openai_content(await r.json())

    async def models(self, timeout: float = 8) -> list[str]:
        """Modelele de pe server (pentru ghidul de pornire). Aruncă excepție dacă serverul nu răspunde."""
        return await list_models(self.backend, self.url, self.api_key, timeout)

    def budget_chars(self, share: float = 0.6) -> int:
        return int(self.num_ctx * share * 3.5)


def _openai_content(body: dict) -> str:
    choices = body.get("choices") or [{}]
    return ((choices[0] or {}).get("message") or {}).get("content") or ""


async def list_models(backend: str, url: str, api_key: str = "", timeout: float = 8) -> list[str]:
    backend = backend if backend in BACKENDS else "ollama"
    url = openai_base(url) if backend == "openai" else (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("empty url")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    path = "/models" if backend == "openai" else "/api/tags"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
        async with s.get(url + path, headers=headers) as r:
            r.raise_for_status()
            body = await r.json(content_type=None)
    if backend == "openai":
        return sorted(str(m.get("id")) for m in body.get("data", []) if m.get("id"))
    return sorted(str(m.get("name") or m.get("model")) for m in body.get("models", [])
                  if m.get("name") or m.get("model"))
