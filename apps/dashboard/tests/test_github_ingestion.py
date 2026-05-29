import io
import json
import sqlite3

import importlib.util
import os

# Load serve module by path to avoid package import issues during tests
serve_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'serve.py'))
spec = importlib.util.spec_from_file_location('serve', serve_path)
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class DummyResp:
    def __init__(self, status=200, data=b"{}"):
        self.status = status
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummyHandler:
    def __init__(self, body: dict):
        raw = json.dumps(body).encode("utf-8")
        self.rfile = io.BytesIO(raw)
        self.headers = {"Content-Length": str(len(raw))}


def test_github_test_connection_success(monkeypatch):
    # Simulate a successful github API call (status 200)
    monkeypatch.setattr(serve.urllib.request, "urlopen", lambda req, timeout=8.0: DummyResp(status=200))

    handler = DummyHandler({"github_token": "fake-token"})
    resp = serve.handle_github_test_connection(handler)

    assert resp["success"] is True
    assert "verified" in resp.get("message", "").lower() or "success" in resp.get("message", "").lower()


def test_github_test_connection_unauthorized(monkeypatch):
    # Simulate GitHub returning a 401 HTTPError
    def raise_401(req, timeout=8.0):
        raise serve.urllib.error.HTTPError(req.full_url if hasattr(req, 'full_url') else req.get_full_url(), 401, "Unauthorized", hdrs=None, fp=None)

    monkeypatch.setattr(serve.urllib.request, "urlopen", raise_401)

    handler = DummyHandler({"github_token": "bad-token"})
    resp = serve.handle_github_test_connection(handler)

    assert resp["success"] is False
    assert "invalid" in resp.get("error", "").lower() or "unauthorized" in resp.get("error", "").lower()


def test_handle_ingest_github_spawns_job(monkeypatch, tmp_path):
    # Prepare an in-memory sqlite DB and a single project row
    def fake_get_db_connection():
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE wiki_projects (id TEXT PRIMARY KEY, name TEXT, repo_path TEXT)")
        cursor.execute("INSERT INTO wiki_projects (id, name, repo_path) VALUES (?, ?, ?)", ("proj-1", "Test Project", "/tmp/repo"))
        conn.commit()
        conn.row_factory = sqlite3.Row
        return conn

    spawned = {}

    def fake_spawn_background_job(job_id, cmd, project_id=None, env=None):
        spawned["job_id"] = job_id
        spawned["cmd"] = cmd
        spawned["project_id"] = project_id
        spawned["env"] = env
        return True

    monkeypatch.setattr(serve, "get_db_connection", fake_get_db_connection)
    monkeypatch.setattr(serve, "spawn_background_job", fake_spawn_background_job)

    handler = DummyHandler({
        "project_id": "proj-1",
        "github_token": "ghp_test",
        "repository_url": "https://github.com/owner/repo"
    })

    resp = serve.handle_ingest_github(handler)
    assert resp["success"] is True
    assert "job_id" in resp["data"]
    assert spawned.get("project_id") == "proj-1"
    assert spawned.get("env") and spawned["env"].get("WIKIHUB_GITHUB_TOKEN") == "ghp_test"
