import os
import sys
import types
import json
import asyncio
from pathlib import Path

import pytest
import httpx

# Ensure project root is on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Stub bcrypt to avoid external dependency
bcrypt_stub = types.SimpleNamespace(
    hashpw=lambda password, salt: password,
    gensalt=lambda: b"salt",
    checkpw=lambda password, hashed: password == hashed,
)
sys.modules["bcrypt"] = bcrypt_stub

os.environ["MODEL_DEFAULT"] = "command-r"

import app_ask
from fastapi import HTTPException


class SimpleResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return json.loads(self._body.decode())


class SimpleClient:
    def __init__(self, app):
        self.app = app

    def _request(self, method, path, json_body=None, headers=None):
        headers = headers or {}
        body_bytes = b""
        header_list = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode()
            header_list.append((b"content-type", b"application/json"))
            header_list.append((b"content-length", str(len(body_bytes)).encode()))
        else:
            header_list.append((b"content-length", b"0"))

        scope = {
            "type": "http",
            "asgi": {"spec_version": "2.1", "version": "3.0"},
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": header_list,
            "client": ("test", 123),
            "server": ("testserver", 80),
            "scheme": "http",
        }

        messages = []

        async def receive():
            nonlocal body_bytes
            if body_bytes:
                b = body_bytes
                body_bytes = b""
                return {"type": "http.request", "body": b, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        try:
            asyncio.run(self.app(scope, receive, send))
        except HTTPException as exc:
            return SimpleResponse(exc.status_code, json.dumps({"detail": exc.detail}).encode())

        status_code = 500
        body = b""
        for message in messages:
            if message["type"] == "http.response.start":
                status_code = message["status"]
            elif message["type"] == "http.response.body":
                body += message.get("body", b"")
        return SimpleResponse(status_code, body)

    def get(self, path, headers=None):
        return self._request("GET", path, headers=headers)

    def post(self, path, json=None, headers=None):
        return self._request("POST", path, json_body=json, headers=headers)


client = SimpleClient(app_ask.app)


def test_v1_chat_proxies_to_gateway(monkeypatch):
    async def ok_post(self, url, headers=None, json=None):
        return types.SimpleNamespace(status_code=200, json=lambda: {"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", ok_post, raising=False)
    resp = client.post("/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"


def test_ask_proxies_to_gateway(monkeypatch):
    async def ok_post(self, url, headers=None, json=None):
        return types.SimpleNamespace(status_code=200, json=lambda: {"choices": [{"message": {"content": "hi"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", ok_post, raising=False)
    resp = client.post("/ask", json={"message": "hello"})
    assert resp.status_code == 200
    assert resp.json()["response"] == "hi"


def test_v1_models_lists_models(monkeypatch):
    async def ok_get(self, url, headers=None):
        return types.SimpleNamespace(status_code=200, json=lambda: {"object": "list", "data": [{"id": "m", "object": "model"}]})

    monkeypatch.setattr(httpx.AsyncClient, "get", ok_get, raising=False)
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert data["data"][0]["id"] == "m"
    assert data["data"][0]["object"] == "model"

