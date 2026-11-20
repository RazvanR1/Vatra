"""Panoul web (ingress) din sidebar-ul Home Assistant."""
from __future__ import annotations

import asyncio
import logging
import secrets
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


def plain_speech(text: str) -> str:
    """Text bun de citit cu voce tare: fără Markdown (ID-urile le evită promptul)."""
    import re
    text = re.sub(r"`([^`]*)`", r"\1", text or "")
    text = re.sub(r"\*\*|__|(?<!\w)[*_](?!\s)|(?<!\s)[*_](?!\w)|^#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    return re.sub(r"\s+\n", "\n", text).strip()


def alert_entity(key: str, states: dict) -> str:
    """Entitatea din cheia unei alerte (`battery:sensor.x`, `unavailable:light.y`), dacă există în HA."""
    eid = key.partition(":")[2]
    return eid if eid in states else ""


def build_app(brain, allowed_ips: set[str] | None = INGRESS_IPS) -> web.Application:
    @web.middleware
    async def only_ingress(req: web.Request, handler):
        # Panoul poate comanda dispozitive, deci acceptăm doar cereri venite prin ingress-ul HA.
        # Excepție: integrarea Vatra pentru Assist, care vine din HA cu codul secret.
        if req.path == "/api/conversation" and assist_token() and \
                secrets.compare_digest(req.headers.get("X-Vatra-Token", "").encode(), assist_token().encode()):
            return await handler(req)
        if allowed_ips is not None and req.remote not in allowed_ips:
            raise web.HTTPForbidden(text="Acces doar prin Home Assistant")
        return await handler(req)

    def assist_token() -> str:
        a = getattr(brain, "assist", None)
        return a.token() if a is not None else ""

    app = web.Application(middlewares=[only_ingress])
    chat_history: list[dict] = []
    J = web.json_response

    def alert_dict(a) -> dict:
        d = asdict(a)
        eid = alert_entity(a.key, brain.ha.states)
        d["entity_id"] = eid
        d["entity_name"] = brain.ha.attr(eid, "friendly_name", eid) if eid else ""
        ctx = getattr(brain, "context", None)
        if eid and ctx is not None and hasattr(ctx, "group_of"):
            d["group"], d["group_name"] = ctx.group_of(eid)
        else:
            d["group"], d["group_name"] = (f"entity:{eid}" if eid else a.key), d["entity_name"]
        return d

    async def index(_req):
        return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    async def i18n_panel(req):
        return J(i18n.panel(req.match_info["code"]))

    async def status(_req):
        ha = brain.ha
        store = getattr(brain, "store", None)
        span = store.data_span() if store else (None, None)
        return J({
            "connected": ha.connected.is_set(),
            "entities": len(ha.states),
            "active_alerts": [alert_dict(a) for a in brain.notifier.active.values()],
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
            "languages": i18n.languages(),
            "habits": {"mode": getattr(brain, "habit_mode", "notify"),
                       "machine": [ha.name(e) for e in getattr(getattr(brain, "miner", None), "machine_skipped", [])][:20],
                       "ignored": len(brain.store.get("habit_ignore", [])) if store else 0},
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
            "vacation": {"active": brain.vacation.is_active(), "mode": brain.vacation.manual,
                         "days_week": round(brain.vacation.days_in_last(7), 1)}
            if hasattr(brain, "vacation") else {},
            "mqtt": {"connected": brain.mqtt.connected, "error": brain.mqtt.error}
            if hasattr(brain, "mqtt") else {},
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
                        "habits": brain.habit_mode,
                        "site_context": opts.get("site_context", ""),
                        "assistant": {**ai, "has_key": has_key}},
            "detected": await setup_mod.detect(brain.ha),
            "assist": {"token": assist_token(), "port": 8099,
                       "host": getattr(getattr(brain, "assist", None), "hostname", "") or ""},
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

    async def weekly_get(_req):
        saved = brain.store.get("weekly_report")
        return J({"last": saved, "preview": brain.weekly.build()})

    async def weekly_send(_req):
        r = await brain.weekly.send()
        return J({"ok": True, "message": t("week.sent"), "report": r})

    async def vacation_set(req):
        mode = str((await req.json()).get("mode", "auto"))
        try:
            brain.vacation.set_manual(mode)
        except ValueError:
            raise web.HTTPBadRequest()
        return J({"ok": True, "active": brain.vacation.is_active(), "message": t(f"vac.mode_{mode}")})

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

    conversations: dict[str, list[dict]] = {}

    async def conversation(req):
        """Assist (voce sau text din HA) -> Jarvis. Răspunsul e scurt, bun de citit cu voce tare."""
        body = await req.json()
        text = str(body.get("text", "")).strip()
        cid = str(body.get("conversation_id") or "") or f"c{int(time.time() * 1000)}"
        if not text:
            return J({"speech": t("web.ask"), "conversation_id": cid})
        hist = conversations.setdefault(cid, [])
        result = await brain.assistant.ask(text, hist, voice=True)
        speech = plain_speech(result.get("reply", "")) or t("web.ask")
        hist.extend([{"role": "user", "content": text}, {"role": "assistant", "content": speech}])
        del hist[:-12]
        if len(conversations) > 50:
            for k in list(conversations)[:-50]:
                conversations.pop(k, None)
        return J({"speech": speech, "conversation_id": cid, "actions": result.get("actions", [])})

    async def test_notify(_req):
        await brain.notifier.send("Vatra", t("web.test"), "info")
        return J({"ok": True})

    # ---------- obiceiuri ----------
    async def habits(_req):
        return J(brain.store.items("habit", limit=200))

    async def habits_ignored(_req):
        return J([{"entity_id": e, "name": brain.ha.name(e)} for e in brain.store.get("habit_ignore", [])])

    async def habits_unignore(req):
        eid = req.match_info["entity_id"]
        left = [e for e in brain.store.get("habit_ignore", []) if e != eid]
        brain.store.set("habit_ignore", left)
        brain.miner.ignore_entities = set(left)
        return J({"message": t("web.restored")})

    async def habit_action(req):
        hid, act = req.match_info["id"], req.match_info["action"]
        if act == "propose":
            await brain.propose(hid, notify=True)
            return J({"message": t("web.proposed")})
        if act == "create":
            return J({"message": await brain.create_automation(hid)})
        if act == "reject":
            return J({"message": await brain.reject_habit(hid)})
        if act == "never":
            return J({"message": await brain.never_for_entity(hid)})
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
    r.add_get("/api/i18n/{code}", i18n_panel)
    r.add_post("/api/chat", chat)
    r.add_post("/api/test-notify", test_notify)
    r.add_get("/api/setup", setup_get)
    r.add_post("/api/setup/test-ai", setup_test_ai)
    r.add_post("/api/setup/discover", setup_discover)
    r.add_post("/api/setup/test-notify", setup_test_notify)
    r.add_post("/api/setup/save", setup_save)
    r.add_post("/api/setup/dismiss", setup_dismiss)
    r.add_post("/api/vacation", vacation_set)
    r.add_post("/api/conversation", conversation)
    r.add_get("/api/weekly", weekly_get)
    r.add_post("/api/weekly/send", weekly_send)
    if hasattr(brain, "store"):
        r.add_get("/api/habits", habits)
        r.add_get("/api/habits/ignored", habits_ignored)
        r.add_post("/api/habits/ignored/{entity_id}/remove", habits_unignore)
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
