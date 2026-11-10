"""Backend-uri LLM: Ollama nativ și servere compatibile OpenAI (LM Studio, llama.cpp, vLLM...)."""
import json

from aiohttp import web
from aiohttp.test_utils import TestServer

from app.llm import LLM, list_models, openai_base, parse_json


async def _server(routes) -> TestServer:
    app = web.Application()
    for method, path, handler in routes:
        app.router.add_route(method, path, handler)
    server = TestServer(app)
    await server.start_server()
    return server


def test_openai_base():
    assert openai_base("http://h:1234") == "http://h:1234/v1"
    assert openai_base("http://h:1234/") == "http://h:1234/v1"
    assert openai_base("http://h:1234/v1/") == "http://h:1234/v1"
    assert openai_base("https://api.example.com/openai/v1") == "https://api.example.com/openai/v1"
    assert openai_base("") == ""


def test_parse_json_tolerant():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('<think>hmm</think>\n```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json('Sure! Here it is: {"a": 3} hope it helps') == {"a": 3}
    assert parse_json("not json") is None


async def test_openai_backend_chat_and_models():
    seen = {}

    async def chat(req):
        body = await req.json()
        seen["body"], seen["auth"] = body, req.headers.get("Authorization")
        return web.json_response({"choices": [{"message": {"content": json.dumps({"reply": "salut"})}}]})

    async def models(req):
        return web.json_response({"data": [{"id": "qwen2.5-7b"}, {"id": "llama-3.1-8b"}]})

    server = await _server([("POST", "/v1/chat/completions", chat), ("GET", "/v1/models", models)])
    try:
        base = str(server.make_url("")).rstrip("/")
        llm = LLM({"backend": "openai", "openai_url": base, "api_key": "sk-test", "model": "qwen2.5-7b"})
        assert llm.enabled and llm.url == base + "/v1"
        data, _raw = await llm.chat_json([{"role": "user", "content": "hi"}])
        assert data == {"reply": "salut"}
        assert seen["auth"] == "Bearer sk-test"
        assert seen["body"]["model"] == "qwen2.5-7b"
        assert seen["body"]["response_format"] == {"type": "json_object"}
        assert await llm.models() == ["llama-3.1-8b", "qwen2.5-7b"]
    finally:
        await server.close()


async def test_openai_backend_without_json_mode_falls_back():
    calls = []

    async def chat(req):
        body = await req.json()
        calls.append(body)
        if "response_format" in body:
            return web.json_response({"error": "response_format must be json_schema or text"}, status=400)
        return web.json_response({"choices": [{"message": {"content": '```json\n{"ok": true}\n```'}}]})

    server = await _server([("POST", "/v1/chat/completions", chat)])
    try:
        llm = LLM({"backend": "openai", "openai_url": str(server.make_url("/v1")), "model": "m"})
        data, _ = await llm.chat_json([{"role": "user", "content": "x"}])
        assert data == {"ok": True}
        data, _ = await llm.chat_json([{"role": "user", "content": "y"}])
        assert data == {"ok": True}
        # după primul refuz nu mai trimite response_format
        assert ["response_format" in c for c in calls] == [True, False, False]
    finally:
        await server.close()


async def test_ollama_backend_still_default_and_lists_models():
    async def chat(req):
        body = await req.json()
        assert body["format"] == "json" and body["options"]["num_ctx"] == 4096
        return web.json_response({"message": {"content": '{"x": 1}'}})

    async def tags(req):
        return web.json_response({"models": [{"name": "qwen3.5:9b"}, {"name": "llama3.1:8b"}]})

    server = await _server([("POST", "/api/chat", chat), ("GET", "/api/tags", tags)])
    try:
        base = str(server.make_url("")).rstrip("/")
        llm = LLM({"ollama_url": base, "num_ctx": 4096})
        assert llm.backend == "ollama"
        assert (await llm.chat_json([{"role": "user", "content": "x"}]))[0] == {"x": 1}
        assert await list_models("ollama", base) == ["llama3.1:8b", "qwen3.5:9b"]
    finally:
        await server.close()


def test_disabled_without_url():
    assert not LLM({"backend": "openai"}).enabled
    assert not LLM({}).enabled
