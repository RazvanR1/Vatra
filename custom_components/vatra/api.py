"""Clientul care vorbește cu add-on-ul Vatra (pe rețeaua internă a Home Assistant)."""
from __future__ import annotations

from typing import Any

import aiohttp

from .const import TIMEOUT


class VatraError(Exception):
    """Vatra nu răspunde sau a refuzat cererea."""


class VatraAuthError(VatraError):
    """Codul secret nu e bun."""


async def ask(session: aiohttp.ClientSession, host: str, port: int, token: str, text: str,
              conversation_id: str | None = None, language: str | None = None,
              timeout: float = TIMEOUT) -> dict[str, Any]:
    url = f"http://{host}:{port}/api/conversation"
    try:
        async with session.post(url, json={"text": text, "conversation_id": conversation_id, "language": language},
                                headers={"X-Vatra-Token": token},
                                timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
            if resp.status == 403:
                raise VatraAuthError("invalid token")
            resp.raise_for_status()
            return await resp.json()
    except VatraAuthError:
        raise
    except (aiohttp.ClientError, TimeoutError) as err:
        raise VatraError(str(err)) from err
