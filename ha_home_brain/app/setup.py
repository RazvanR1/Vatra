"""Ghidul de pornire din panou: găsește singur ce poate (telefoane, persoane, server AI),
te lasă să bifezi, apoi salvează opțiunile add-on-ului prin Supervisor și repornește Vatra.

Fără YAML pentru utilizatorii noi. Tab-ul Configuration din HA rămâne pentru opțiunile avansate.
"""
from __future__ import annotations

import asyncio
import copy
import ipaddress
import logging
import os

import aiohttp

from .llm import BACKENDS, list_models

log = logging.getLogger("home_brain.setup")

# Porturile implicite ale serverelor AI locale cele mai folosite.
AI_PORTS = {11434: "ollama", 1234: "openai", 8080: "openai"}
EDITABLE = ("language", "notify_services", "site_context")
EDITABLE_LEARNING = ("persons",)
EDITABLE_AI = ("backend", "ollama_url", "openai_url", "api_key", "model", "num_ctx")


class Supervisor:
    """Clientul minim pentru API-ul Supervisor (rolul `default` ajunge pentru /addons/self/*)."""

    def __init__(self, url: str = "http://supervisor", token: str | None = None) -> None:
        self.url = url.rstrip("/")
        self.token = token if token is not None else os.environ.get("SUPERVISOR_TOKEN", "")

    @property
    def available(self) -> bool:
        return bool(self.token)

    async def _call(self, method: str, path: str, body: dict | None = None, timeout: float = 15):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.request(method, self.url + path, json=body,
                                 headers={"Authorization": f"Bearer {self.token}"}) as r:
                data = await r.json(content_type=None)
                if r.status >= 400 or (data or {}).get("result") == "error":
                    raise RuntimeError((data or {}).get("message") or f"HTTP {r.status}")
                return (data or {}).get("data") or {}

    async def options(self) -> dict:
        return (await self._call("GET", "/addons/self/info")).get("options") or {}

    async def set_options(self, options: dict) -> None:
        await self._call("POST", "/addons/self/options", {"options": options})

    async def restart(self) -> None:
        await self._call("POST", "/addons/self/restart", timeout=5)

    async def host_ips(self) -> list[str]:
        """IPv4-urile mașinii HA în rețeaua locală (ex. 192.168.1.20/24)."""
        info = await self._call("GET", "/network/info")
        out = []
        for iface in info.get("interfaces", []):
            for addr in ((iface.get("ipv4") or {}).get("address") or []):
                out.append(addr)
        return out


def merge(current: dict, patch: dict) -> dict:
    """Pune peste opțiunile curente doar câmpurile pe care le editează ghidul."""
    opts = copy.deepcopy(current)
    for k in EDITABLE:
        if k in patch:
            opts[k] = patch[k]
    if "persons" in patch:
        opts.setdefault("learning", {})["persons"] = patch["persons"]
    ai = patch.get("assistant") or {}
    if ai:
        a = opts.setdefault("assistant", {})
        for k in EDITABLE_AI:
            if k in ai:
                a[k] = ai[k]
    return opts


def clean(patch: dict) -> dict:
    """Validează ce vine din panou, ca Supervisor-ul să nu refuze opțiunile."""
    out: dict = {}
    if patch.get("language") in ("auto", "en", "ro"):
        out["language"] = patch["language"]
    if isinstance(patch.get("notify_services"), list):
        out["notify_services"] = [s.strip() for s in patch["notify_services"]
                                  if isinstance(s, str) and s.strip().startswith("notify.")]
    if isinstance(patch.get("persons"), list):
        out["persons"] = [p.strip() for p in patch["persons"]
                          if isinstance(p, str) and p.strip().startswith("person.")]
    if isinstance(patch.get("site_context"), str):
        out["site_context"] = patch["site_context"].strip()[:2000]
    ai = patch.get("assistant")
    if isinstance(ai, dict):
        a: dict = {}
        if ai.get("backend") in BACKENDS:
            a["backend"] = ai["backend"]
        for k in ("ollama_url", "openai_url", "api_key", "model"):
            if isinstance(ai.get(k), str):
                a[k] = ai[k].strip()
        try:
            if ai.get("num_ctx") not in (None, ""):
                a["num_ctx"] = max(2048, min(131072, int(ai["num_ctx"])))
        except (TypeError, ValueError):
            pass
        if a:
            out["assistant"] = a
    return out


def needs_setup(opts: dict) -> bool:
    return not opts.get("notify_services") and not (opts.get("learning") or {}).get("persons")


async def _probe(host: str, port: int, timeout: float) -> dict | None:
    backend = AI_PORTS[port]
    url = f"http://{host}:{port}"
    try:
        models = await list_models(backend, url, timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    return {"backend": backend, "url": url if backend == "ollama" else url + "/v1", "models": models}


async def discover_ai(host_cidrs: list[str], extra_hosts: list[str] | None = None,
                      scan_subnet: bool = True, timeout: float = 0.8) -> list[dict]:
    """Caută servere AI: întâi pe mașina HA și gazdele știute, apoi (Ollama) în tot /24-ul local."""
    hosts: list[str] = list(extra_hosts or [])
    nets = []
    for cidr in host_cidrs:
        try:
            iface = ipaddress.ip_interface(cidr)
        except ValueError:
            continue
        if iface.version != 4 or iface.ip.is_loopback:
            continue
        hosts.append(str(iface.ip))
        net = iface.network if iface.network.prefixlen >= 24 else ipaddress.ip_network(f"{iface.ip}/24", strict=False)
        nets.append(net)
    seen, jobs = set(), []
    for h in hosts:
        for port in AI_PORTS:
            if (h, port) not in seen:
                seen.add((h, port))
                jobs.append(_probe(h, port, timeout))
    if scan_subnet:
        for net in nets:
            for ip in net.hosts():
                if (str(ip), 11434) not in seen:
                    seen.add((str(ip), 11434))
                    jobs.append(_probe(str(ip), 11434, timeout))
    sem = asyncio.Semaphore(64)

    async def limited(job):
        async with sem:
            return await job

    found = [r for r in await asyncio.gather(*(limited(j) for j in jobs)) if r]
    # Ollama întâi, apoi după numărul de modele.
    found.sort(key=lambda r: (r["backend"] != "ollama", -len(r["models"])))
    return found


async def detect(ha) -> dict:
    """Ce găsim în HA: servicii de notificare mobile și persoane."""
    notify: list[dict] = []
    try:
        services = await ha.ws({"type": "get_services"})
        for name in sorted((services or {}).get("notify", {})):
            if name.startswith("mobile_app_") or name in ("persistent_notification",):
                notify.append({"service": f"notify.{name}",
                               "name": name.removeprefix("mobile_app_").replace("_", " ")})
    except Exception as err:  # noqa: BLE001
        log.debug("Could not list notify services: %s", err)
    persons = [{"entity_id": e, "name": s.get("attributes", {}).get("friendly_name", e)}
               for e, s in sorted(ha.states.items()) if e.startswith("person.")]
    return {"notify": notify, "persons": persons}
