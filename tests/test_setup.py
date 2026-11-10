"""Ghidul de pornire: detectare, validare, salvare prin Supervisor, căutarea serverelor AI."""
import asyncio

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from app import setup as su
from app.web import build_app
from test_home_brain import setup  # noqa: F401  (fixture)


class FakeSupervisor:
    def __init__(self, options):
        self.opts = options
        self.saved = None
        self.restarted = False
        self.available = True

    async def options(self):
        return self.opts

    async def set_options(self, options):
        self.saved = options

    async def restart(self):
        self.restarted = True

    async def host_ips(self):
        return []


def test_clean_rejects_garbage_and_merge_keeps_the_rest():
    patch = su.clean({"language": "xx", "notify_services": ["notify.mobile_app_a", "light.x", 3],
                      "persons": ["person.a", "sensor.b"], "site_context": "  Casă  ",
                      "assistant": {"backend": "openai", "openai_url": " http://h:1234/v1 ", "num_ctx": "999999",
                                    "evil": "x"}})
    assert patch == {"notify_services": ["notify.mobile_app_a"], "persons": ["person.a"], "site_context": "Casă",
                     "assistant": {"backend": "openai", "openai_url": "http://h:1234/v1", "num_ctx": 131072}}
    current = {"language": "auto", "guard": {"battery_threshold": 20}, "learning": {"enabled": True, "persons": []},
               "assistant": {"backend": "ollama", "ollama_url": "http://o:11434", "api_key": "secret", "model": "m"}}
    merged = su.merge(current, patch)
    assert merged["guard"] == {"battery_threshold": 20} and merged["learning"]["enabled"] is True
    assert merged["learning"]["persons"] == ["person.a"]
    assert merged["assistant"]["ollama_url"] == "http://o:11434"  # neatins
    assert merged["assistant"]["api_key"] == "secret"  # cheia rămâne dacă nu trimiți alta
    assert merged["assistant"]["backend"] == "openai"
    assert current["learning"]["persons"] == []  # nu modifică originalul


def test_needs_setup():
    assert su.needs_setup({})
    assert not su.needs_setup({"notify_services": ["notify.x"]})
    assert not su.needs_setup({"learning": {"persons": ["person.a"]}})


async def test_discover_finds_local_ollama(monkeypatch):
    app = web.Application()
    async def tags(_req):
        return web.json_response({"models": [{"name": "qwen3.5:9b"}]})

    app.router.add_get("/api/tags", tags)
    server = TestServer(app, host="127.0.0.1")
    await server.start_server()
    monkeypatch.setattr(su, "AI_PORTS", {server.port: "ollama"})
    try:
        found = await su.discover_ai([], extra_hosts=["127.0.0.1"], scan_subnet=False)
        assert found == [{"backend": "ollama", "url": f"http://127.0.0.1:{server.port}", "models": ["qwen3.5:9b"]}]
    finally:
        await server.close()


async def test_setup_endpoints(setup):  # noqa: F811
    fake, brain = setup
    brain.supervisor = FakeSupervisor({**brain.opts, "assistant": {**brain.opts["assistant"], "api_key": "k"}})
    client = TestClient(TestServer(build_app(brain, allowed_ips=None)))
    await client.start_server()
    try:
        r = await (await client.get("/api/status")).json()
        assert r["needs_setup"] is False  # are deja notify_services
        r = await (await client.get("/api/setup")).json()
        assert r["can_save"]
        assert "api_key" not in r["options"]["assistant"] and r["options"]["assistant"]["has_key"]
        assert [n["service"] for n in r["detected"]["notify"]] == [
            "notify.mobile_app_hajni", "notify.mobile_app_razvan", "notify.persistent_notification"]
        assert {p["entity_id"] for p in r["detected"]["persons"]} == {"person.razvan", "person.hajni"}

        r = await (await client.post("/api/setup/test-ai", json={
            "backend": "ollama", "url": brain.llm.url})).json()
        assert r["ok"] is False or isinstance(r["models"], list)  # serverul fals n-are /api/tags
        r = await (await client.post("/api/setup/test-ai", json={"backend": "ollama", "url": ""})).json()
        assert r["ok"] is False

        r = await (await client.post("/api/setup/test-notify", json={"service": "notify.mobile_app_hajni"})).json()
        assert r["ok"]
        assert any(c["domain"] == "notify" and c["service"] == "mobile_app_hajni" for c in fake.calls)

        r = await (await client.post("/api/setup/save", json={"options": {
            "notify_services": ["notify.mobile_app_hajni"], "persons": ["person.hajni"],
            "assistant": {"backend": "openai", "openai_url": "http://lm:1234/v1", "model": "qwen"}}})).json()
        assert r["ok"] and r["restarting"]
        saved = brain.supervisor.saved
        assert saved["notify_services"] == ["notify.mobile_app_hajni"]
        assert saved["learning"]["persons"] == ["person.hajni"]
        assert saved["assistant"]["backend"] == "openai" and saved["assistant"]["api_key"] == "k"
        assert saved["guard"] == brain.opts["guard"]
        await asyncio.sleep(1.2)
        assert brain.supervisor.restarted
    finally:
        await client.close()


async def test_save_without_supervisor(setup):  # noqa: F811
    _, brain = setup
    brain.supervisor = FakeSupervisor({})
    brain.supervisor.available = False
    client = TestClient(TestServer(build_app(brain, allowed_ips=None)))
    await client.start_server()
    try:
        r = await (await client.post("/api/setup/save", json={"options": {"persons": ["person.a"]}})).json()
        assert r["ok"] is False
    finally:
        await client.close()
