"""Panoul web (ingress) din sidebar-ul Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from pathlib import Path

from aiohttp import web
from . import i18n
from . import setup as setup_mod
from .i18n import t

log = logging.getLogger("home_brain.web")
STATIC = Path(__file__).parent / "static"
INGRESS_IPS = {"172.30.32.2", "127.0.0.1", "::1"}


def build_app(brain, allowed_ips: set[str] | None = INGRESS_IPS) -> web.Application:
    @web.middleware
    async def only_ingress(req: web.Request, handler):
        # Panoul poate comanda dispozitive, deci acceptăm doar cereri venite prin ingress-ul HA.
        if allowed_ips is not None and req.remote not in allowed_ips:
            raise web.HTTPForbidden(text="Acces doar prin Home Assistant")
        return await handler(req)

    app = web.Application(middlewares=[only_ingress])
    chat_history: list[dict] = []
    J = web.json_response

    async def index(_req):
        return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    async def status(_req):
        ha = brain.ha
        store = getattr(brain, "store", None)
        span = store.data_span() if store else (None, None)
        return J({
            "connected": ha.connected.is_set(),
            "entities": len(ha.states),
            "active_alerts": [asdict(a) for a in brain.notifier.active.values()],
            "history": [asdict(a) for a in list(brain.notifier.history)[:50]],
            "automations": brain.automations.status(),
            "assistant": {"enabled": brain.assistant.enabled, "model": brain.assistant.model},
            "memory": {
                "transitions": store.count_transitions() if store else 0,
                "days": round((span[1] - span[0]) / 86400, 1) if span and span[0] else 0,
                "import": getattr(getattr(brain, "recorder", None), "import_status", "—"),
                "last_learning": getattr(brain, "last_learning", None),
            },
            "pending": len(brain.approvals.pending()) if hasattr(brain, "approvals") else 0,
            "findings": list(getattr(brain, "findings", {}).values()),
            "language": i18n.lang(),
            "explained": getattr(getattr(brain, "guard", None), "explained", {}),
            "notifications": {
                "mode": brain.notifier.mode, "quiet_hours": brain.notifier.quiet,
                "queued": len(brain.notifier.queue), "deferred": len(brain.notifier.deferred),
                "sent_today": brain.notifier.store.get(
                    f"push_count:{brain.notifier._today()}", 0) if brain.notifier.store else 0,
                "max_per_day": brain.notifier.max_per_day,
            },
            "agents": getattr(getattr(brain, "agents", None), "status", {}),
            "safety": brain.approvals.summary() if hasattr(brain, "approvals") else {},
            "llm": {"calls": brain.llm.calls, "last_seconds": round(brain.llm.last_seconds, 1),
                    "backend": brain.llm.backend}
            if hasattr(brain, "llm") else {},
            "needs_setup": setup_mod.needs_setup(getattr(brain, "opts", {}) or {})
            and not (store.get("setup_dismissed") if store else False),
        })

    # ---------- ghid de pornire ----------
    def supervisor():
        sup = getattr(brain, "supervisor", None)
        return sup if sup is not None else setup_mod.Supervisor()

    async def current_options() -> dict:
        sup = supervisor()
        if sup.available:
            try:
                return await sup.options()
            except Exception as err:  # noqa: BLE001
                log.warning("Could not read add-on options: %s", err)
        return getattr(brain, "opts", {}) or {}

    async def setup_get(_req):
        opts = await current_options()
        ai = dict(opts.get("assistant") or {})
        has_key = bool(ai.pop("api_key", ""))
        return J({
            "can_save": supervisor().available,
            "options": {"language": opts.get("language", "auto"),
                        "notify_services": opts.get("notify_services", []),
                        "persons": (opts.get("learning") or {}).get("persons", []),
                        "site_context": opts.get("site_context", ""),
                        "assistant": {**ai, "has_key": has_key}},
            "detected": await setup_mod.detect(brain.ha),
        })

    async def setup_test_ai(req):
        b = await req.json()
        try:
            models = await setup_mod.list_models(str(b.get("backend") or "ollama"), str(b.get("url") or ""),
                                                 str(b.get("api_key") or ""), timeout=8)
        except Exception as err:  # noqa: BLE001
            return J({"ok": False, "error": str(err) or type(err).__name__})
        return J({"ok": True, "models": models})

    async def setup_discover(_req):
        cidrs: list[str] = []
        sup = supervisor()
        if sup.available:
            try:
                cidrs = await sup.host_ips()
            except Exception as err:  # noqa: BLE001
                log.debug("Could not read host network: %s", err)
        found = await setup_mod.discover_ai(cidrs, extra_hosts=["homeassistant.local", "host.docker.internal"])
        return J({"found": found, "scanned": cidrs})

    async def setup_test_notify(req):
        b = await req.json()
        svc = str(b.get("service") or "")
        if not svc.startswith("notify."):
            raise web.HTTPBadRequest()
        try:
            await brain.ha.call_service("notify", svc.split(".", 1)[1],
                                        {"title": "Vatra", "message": t("web.test")})
        except Exception as err:  # noqa: BLE001
            return J({"ok": False, "message": t("error.generic", err=err)})
        return J({"ok": True, "message": t("setup.test_sent", svc=svc)})

    async def setup_save(req):
        b = await req.json()
        patch = setup_mod.clean(b.get("options") or {})
        sup = supervisor()
        if not sup.available:
            return J({"ok": False, "message": t("setup.no_supervisor")})
        try:
            merged = setup_mod.merge(await sup.options(), patch)
            await sup.set_options(merged)
        except Exception as err:  # noqa: BLE001
            log.warning("Saving options failed: %s", err)
            return J({"ok": False, "message": t("error.generic", err=err)})
        if getattr(brain, "store", None):
            brain.store.set("setup_dismissed", True)
            brain.store.log("memorie", t("setup.saved_log"))
        if b.get("restart", True):
            asyncio.get_running_loop().call_later(1.0, lambda: asyncio.ensure_future(_restart(sup)))
        return J({"ok": True, "restarting": bool(b.get("restart", True)), "message": t("setup.saved")})

    async def _restart(sup):
        try:
            await sup.restart()
        except Exception as err:  # noqa: BLE001
            log.debug("Restart call ended: %s", err)  # conexiunea se poate închide chiar la repornire

    async def setup_dismiss(_req):
        if getattr(brain, "store", None):
            brain.store.set("setup_dismissed", True)
        return J({"ok": True})

    async def chat(req):
        body = await req.json()
        question = str(body.get("message", "")).strip()
        if not question:
            return J({"reply": t("web.ask"), "actions": []})
        result = await brain.assistant.ask(question, chat_history)
        chat_history.extend([{"role": "user", "content": question},
                             {"role": "assistant", "content": result.get("reply", "")}])
        del chat_history[:-12]
        return J(result)

    async def test_notify(_req):
        await brain.notifier.send("Vatra", t("web.test"), "info")
        return J({"ok": True})

    # ---------- obiceiuri ----------
    async def habits(_req):
        return J(brain.store.items("habit", limit=200))

    async def habit_action(req):
        hid, act = req.match_info["id"], req.match_info["action"]
        if act == "propose":
            await brain.propose(hid, notify=True)
            return J({"message": t("web.proposed")})
        if act == "create":
            return J({"message": await brain.create_automation(hid)})
        if act == "reject":
            return J({"message": await brain.reject_habit(hid)})
        if act == "restore":
            brain.store.set_status("habit", hid, "new")
            return J({"message": t("web.restored")})
        raise web.HTTPBadRequest()

    async def relearn(_req):
        hs = await brain.learn()
        return J({"message": t("web.relearned", n=len(hs))})

    # ---------- aprobări, acțiuni ----------
    async def approvals(_req):
        return J(brain.approvals.pending())

    async def decide(req):
        msg = await brain.approvals.decide(req.match_info["id"], req.match_info["decision"])
        return J({"message": msg})

    async def done(_req):
        return J(brain.approvals.recent_done())

    async def undo(req):
        return J({"message": await brain.approvals.undo(req.match_info["id"])})

    # ---------- agenți, jurnal ----------
    async def insights(_req):
        return J(brain.agents.insights())

    async def run_agent(req):
        key = req.match_info["key"]
        agent = next((a for a in brain.agents.agents if a.key == key), None)
        if not agent:
            raise web.HTTPNotFound()
        out = await brain.agents.run_agent(agent, force=True)
        return J({"message": t("web.agent_ran", name=agent.name, n=len(out)), "insights": out})

    async def activity(_req):
        return J(brain.store.activity(150))

    async def health(_req):
        return J({"ok": brain.ha.connected.is_set(), "ts": time.time()})

    r = app.router
    r.add_get("/", index)
    r.add_get("/api/health", health)
    r.add_get("/api/status", status)
    r.add_post("/api/chat", chat)
    r.add_post("/api/test-notify", test_notify)
    r.add_get("/api/setup", setup_get)
    r.add_post("/api/setup/test-ai", setup_test_ai)
    r.add_post("/api/setup/discover", setup_discover)
    r.add_post("/api/setup/test-notify", setup_test_notify)
    r.add_post("/api/setup/save", setup_save)
    r.add_post("/api/setup/dismiss", setup_dismiss)
    if hasattr(brain, "store"):
        r.add_get("/api/habits", habits)
        r.add_post("/api/habits/{id}/{action}", habit_action)
        r.add_post("/api/learn", relearn)
        r.add_get("/api/approvals", approvals)
        r.add_post("/api/approvals/{id}/{decision}", decide)
        r.add_get("/api/done", done)
        r.add_post("/api/undo/{id}", undo)
        r.add_get("/api/insights", insights)
        r.add_post("/api/agents/{key}/run", run_agent)
        r.add_get("/api/activity", activity)
    return app
