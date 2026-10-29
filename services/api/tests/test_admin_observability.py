"""Admin credentials, tenant isolation and actual source/model traces; entirely offline."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from cavat.config import get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.main import create_app
from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ChatResult, ModelClass, Usage
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.identity.accounts import Identity, issue_token
from cavat.modules.identity.api import signing_secret
from cavat.modules.observability import api as admin
from cavat.modules.observability.store import OperationalLog, TraceContext, context, new_row
from cavat.modules.observability.trace import traced
from cavat.modules.rag.retrieve import RagIndex
from cavat.modules.session.api import get_database
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.teaching.web import WikipediaVi
from fastapi.concurrency import run_in_threadpool
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("ADMIN_PASSWORD", "1234")
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "1")
    get_settings.cache_clear()
    log = OperationalLog(tmp_path / "logs.jsonl")
    monkeypatch.setattr(admin, "journal", lambda: log)
    monkeypatch.setattr(admin, "_guard", admin.LoginGuard())
    database = InMemoryDatabase()
    app = create_app(web_dist=tmp_path / "no-web")
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as browser:
        yield browser, database, log, app
    get_settings.cache_clear()


def headers(client):
    response = client.post("/v1/admin/login", json={"password": "1234"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def test_admin_is_independent_and_protected_even_in_demo_mode(client):
    browser, _, _, _ = client
    assert browser.get("/v1/admin/overview").status_code == 401
    assert browser.post("/v1/admin/login", json={"password": "0000"}).status_code == 401
    teacher = issue_token(Identity("teacher", "TEACHER", "Teacher"), signing_secret())
    assert (
        browser.get("/v1/admin/overview", headers={"Authorization": "Bearer " + teacher}).status_code == 401
    )
    assert browser.get("/v1/admin/overview", headers=headers(browser)).status_code == 200
    assert browser.get("/v1/admin/overview", headers={"Authorization": "Bearer malformed"}).status_code == 401


def test_expired_foreign_and_changed_password_tokens_are_rejected(client, monkeypatch):
    browser, _, _, _ = client
    valid = headers(browser)
    foreign = {"Authorization": "Bearer " + admin.issue_admin_token("other-school")}
    assert browser.get("/v1/admin/overview", headers=foreign).status_code == 401
    with monkeypatch.context() as patch:
        patch.setattr(admin.time, "time", lambda: 99_999_999_999)
        assert browser.get("/v1/admin/overview", headers=valid).status_code == 401
    monkeypatch.setenv("ADMIN_PASSWORD", "4321")
    get_settings.cache_clear()
    assert browser.get("/v1/admin/overview", headers=valid).status_code == 401


def test_wrong_passwords_are_rate_limited(client):
    browser, _, _, _ = client
    for _ in range(5):
        assert browser.post("/v1/admin/login", json={"password": "9999"}).status_code == 401
    assert browser.post("/v1/admin/login", json={"password": "1234"}).status_code == 429


@pytest.mark.asyncio
async def test_history_and_runtime_are_school_scoped_and_payloads_do_not_leak(client):
    browser, database, log, _ = client
    now = datetime.now(UTC)
    event = {
        "event_id": "call-1",
        "event_type": "MODEL_CALLED",
        "occurred_at": now,
        "payload": {
            "model": "offline-test",
            "purpose": "tutor_turn",
            "prompt_tokens": 12,
            "completion_tokens": 4,
            "attempts": [{"model": "offline-test", "sent": True, "detail": "private-provider-message"}],
            "messages": "private-student-words",
        },
    }
    for school, session in [(DEMO_SCHOOL_ID, "own-session"), ("other-school", "foreign-session")]:
        await database["learning_sessions"].insert_one(
            {"_id": session, "school_id": school, "updated_at": now, "events": [event]}
        )
        row = new_row(TraceContext(log, school, "request", session, "/v1/test"), "rag", "retrieve")
        row["status"] = "success"
        log.write(row)
    response = browser.get("/v1/admin/overview", headers=headers(browser))
    assert response.status_code == 200
    body = response.json()
    assert body["history"]["totals"]["prompt_tokens"] == 12
    assert len(body["runtime"]["logs"]) == 1
    assert [s["id"] for s in body["history"]["sessions"]] == ["own-session"]
    assert "foreign-session" not in response.text
    assert "private-provider-message" not in response.text
    assert "private-student-words" not in response.text
    filtered = browser.get("/v1/admin/overview?session_id=foreign-session", headers=headers(browser)).json()
    assert filtered["history"]["logs"] == [] and filtered["runtime"]["logs"] == []


def test_gateway_and_empty_rag_are_observed_in_threadpool_without_logging_prompts(client):
    browser, _, log, app = client

    class Provider:
        def chat(self, request, model):
            return ChatResult(model, "private-answer", usage=Usage(14, 5, 19))

    gateway = AIRouter(chat_provider=Provider())

    @app.post("/v1/sessions/synthetic/observability-check")
    async def command():
        def work():
            RagIndex([], None, {}).retrieve("private-student-question")
            return gateway.chat(
                model_class=ModelClass.LIGHTWEIGHT,
                request=ChatRequest((ChatMessage("user", "private-student-words"),)),
                calls_used=0,
            )

        await run_in_threadpool(work)
        return {"ok": True}

    assert browser.post("/v1/sessions/synthetic/observability-check").status_code == 200
    rows = log.snapshot(DEMO_SCHOOL_ID)
    assert {r["kind"] for r in rows} == {"model", "rag", "command"}
    assert len({r["request_id"] for r in rows}) == 1
    assert all(r["session_id"] == "synthetic" for r in rows)
    call = next(r for r in rows if r["kind"] == "model")
    assert (call["prompt_tokens"], call["completion_tokens"], call["calls_sent"]) == (14, 5, 1)
    assert next(r for r in rows if r["kind"] == "rag")["status"] == "miss"
    assert "private-student" not in json.dumps(rows)
    assert "private-answer" not in json.dumps(rows)


def test_missed_web_lookup_is_recorded_and_metadata_failure_does_not_change_work(client):
    _, _, log, _ = client
    ctx = TraceContext(log, DEMO_SCHOOL_ID, "request", "session", "/v1/test")
    token = context.set(ctx)
    try:
        # A hit in this adapter's cache avoids any network request.
        source = WikipediaVi()
        source._fetch = lambda query: None
        assert source.lookup("a-concept") is None

        @traced("rag")
        def unusual_result():
            return 42

        assert unusual_result() == 42
    finally:
        context.reset(token)
    rows = log.snapshot(DEMO_SCHOOL_ID)
    assert rows[0]["status"] == "success" and rows[1]["status"] == "miss"


def test_journal_is_bounded_durable_and_tolerates_corrupt_tail(tmp_path):
    path = tmp_path / "operations.jsonl"
    log = OperationalLog(path, capacity=2)
    for i in range(3):
        row = new_row(TraceContext(log, "school", "request", str(i), "/test"), "model", "chat")
        log.write(row)
    assert len(log.snapshot("school")) == 2
    with path.open("a") as stream:
        stream.write("broken json\n")
    restored = OperationalLog(path, capacity=2).snapshot("school")
    assert len(restored) == 2 and all(row["status"] == "interrupted" for row in restored)


@pytest.mark.asyncio
async def test_kind_filter_runs_before_limit_so_old_retrievals_remain_visible(client):
    browser, database, _, _ = client
    now = datetime.now(UTC)
    await database["learning_sessions"].insert_one(
        {
            "_id": "old-rag",
            "school_id": DEMO_SCHOOL_ID,
            "updated_at": now,
            "events": [
                {
                    "event_id": "rag",
                    "event_type": "RAG_RETRIEVED",
                    "occurred_at": "2026-01-01",
                    "payload": {"grounded": False},
                },
                {
                    "event_id": "model",
                    "event_type": "MODEL_CALLED",
                    "occurred_at": "2026-10-29",
                    "payload": {"model": "fake"},
                },
            ],
        }
    )
    result = browser.get("/v1/admin/overview?limit=1&kind=rag", headers=headers(browser)).json()
    assert [r["id"] for r in result["history"]["logs"]] == ["rag"]
    assert result["history"]["filtered_total"] == 1
    assert result["history"]["totals"]["model_operations"] == 1


def test_command_without_ai_says_zero_calls_and_reading_admin_does_not_add_calls(client):
    browser, _, log, app = client

    @app.post("/v1/sessions/offline/no-model")
    async def deterministic():
        return {"ok": True}

    assert browser.post("/v1/sessions/offline/no-model").status_code == 200
    [row] = log.snapshot(DEMO_SCHOOL_ID)
    assert row["kind"] == "command" and row["status"] == "success"
    assert row["details"] == {
        "http_status": 200,
        "model_calls": 0,
        "rag_calls": 0,
        "web_calls": 0,
        "network_calls": 0,
        "cache_calls": 0,
    }
    browser.get("/v1/admin/overview", headers=headers(browser))
    assert len(log.snapshot(DEMO_SCHOOL_ID)) == 1


def test_source_http_counts_failures_without_leaking_search_or_credentials(client):
    import httpx
    from cavat.modules.teaching.search_web import SearchEducation

    _, _, log, _ = client
    token = context.set(TraceContext(log, DEMO_SCHOOL_ID, "http-proof", "s1", "/test"))
    try:
        transport = httpx.MockTransport(lambda request: httpx.Response(403))
        with httpx.Client(transport=transport) as http:
            assert SearchEducation()._read(http, "https://www.bing.com/search?q=PRIVATE_CHILD_TEXT") is None
        rows = log.snapshot(DEMO_SCHOOL_ID)
        network = [r for r in rows if r["kind"] == "network"]
        assert len(network) == 1
        assert network[0]["status"] == "error"
        assert network[0]["details"]["http_status"] == 403
        assert network[0]["details"]["url"] == "https://www.bing.com/search"
        assert "PRIVATE_CHILD_TEXT" not in json.dumps(rows)
        assert admin.totals(rows)["network_errors"] == 1
    finally:
        context.reset(token)


def test_cache_hit_is_not_an_internet_connection(client, tmp_path):
    import hashlib

    _, _, log, _ = client
    query = "số thập phân"
    key = hashlib.sha256(query.encode()).hexdigest()[:24]
    (tmp_path / f"{key}.json").write_text("null")
    token = context.set(TraceContext(log, DEMO_SCHOOL_ID, "cache-proof", "s1", "/test"))
    try:
        assert WikipediaVi(cache_dir=tmp_path).lookup(query) is None
        counts = admin.totals(log.snapshot(DEMO_SCHOOL_ID))
        assert counts["web"] == 1
        assert counts["cache"] == 1
        assert counts["network"] == 0
    finally:
        context.reset(token)


def test_source_timeout_is_visible_and_original_error_is_preserved(client):
    import httpx
    from cavat.modules.observability.trace import network_request

    _, _, log, _ = client
    token = context.set(TraceContext(log, DEMO_SCHOOL_ID, "timeout-proof", None, "/test"))
    try:
        with pytest.raises(httpx.ReadTimeout), network_request("https://example.org/lesson"):
            raise httpx.ReadTimeout("private error payload")
        row = log.snapshot(DEMO_SCHOOL_ID)[0]
        assert row["status"] == "error"
        assert row["details"]["error"] == "ReadTimeout"
        assert "private error payload" not in json.dumps(row)
    finally:
        context.reset(token)


def test_pagination_and_historical_http_coverage(client):
    browser, _, log, _ = client
    ctx = TraceContext(log, DEMO_SCHOOL_ID, "paging", None, "/test")
    for i in range(30):
        row = new_row(ctx, "rag" if i % 2 else "network", str(i))
        row["status"] = "success"
        log.write(row)
    data = browser.get("/v1/admin/overview?kind=rag&limit=5&offset=10", headers=headers(browser)).json()
    assert data["runtime"]["filtered_total"] == 15
    assert len(data["runtime"]["logs"]) == 5
    assert [r["operation"] for r in data["runtime"]["logs"]] == ["9", "7", "5", "3", "1"]
    assert data["history"]["coverage"]["network_tracked"] is False
    assert data["runtime"]["coverage"]["network_tracked"] is True
