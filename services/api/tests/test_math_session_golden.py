"""ENG-5b: a Mathematics session over the session API is the same after English sessions were wired in.

The golden ``tests/golden/math-session-before-eng5b.json`` was written from the clean ``main`` (b0310d0)
BEFORE any code of ENG-5b changed (``WRITE_GOLDEN=1``); it is never written again after code changes. One
scripted student runs the decimals chapter end to end (right answers, a wrong one, a hint, a question outside
the lesson, a spoken answer, a theory reply that is not understood), and every state view the web reads and
every stored event are compared, ids, clocks and timings replaced by stable placeholders.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session import api as session_api
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from test_chapter_session_api import MINH, reply_text

GOLDEN = Path(__file__).parent / "golden" / "math-session-before-eng5b.json"

_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
_CLOCK_KEYS = {
    "seconds",
    "latency_ms",
    "time_s",
    "occurred_at",
    "recorded_at",
    "created_at",
    "updated_at",
    "started_at",
    "ended_at",
}


def normalize(value: Any, ids: dict[str, str]) -> Any:
    """Ids become <id1>, <id2>… in order of appearance; clocks and timings become fixed placeholders."""
    if isinstance(value, dict):
        return {
            k: ("<clock>" if k in _CLOCK_KEYS and v is not None else normalize(v, ids))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [normalize(v, ids) for v in value]
    if isinstance(value, str):
        if _ID.match(value):
            return ids.setdefault(value, f"<id{len(ids) + 1}>")
        if _TIME.match(value):
            return "<clock>"
    return value


@pytest.fixture(autouse=True)
def templates_only(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)


@pytest.fixture
async def memory():
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)


def _script(state: dict, n: int) -> tuple[str, str]:
    """(command, text) of turn ``n``: mostly right answers, with the detours a real child takes."""
    teaching = state["teaching"]
    if n == 1:
        return "ANSWER", "con không hiểu"  # a theory reply not understood: taught again (REFORM-6)
    if n == 3 and teaching["awaiting"] == "ANSWER":
        return "ANSWER", "con nghĩ là 7"  # a wrong answer
    if n == 4 and "HINT_REQUEST" in state["allowed_commands"]:
        return "HINT_REQUEST", ""
    if n == 6:
        return "ANSWER", "cô ơi cô thích đá bóng không?"  # talk outside the lesson
    if n == 8:
        return "VOICE", reply_text(state)
    return "ANSWER", reply_text(state)


def _run(client: TestClient, database: InMemoryDatabase) -> dict[str, Any]:
    created = client.post("/v1/sessions", json={"student_display_name": "Minh"}, headers=MINH)
    assert created.status_code == 201, created.text
    sid = created.json()["session_id"]
    views = [created.json()]
    state = client.post(f"/v1/sessions/{sid}/join", headers=MINH).json()
    views.append(state)
    acks = []
    for n in range(1, 400):
        if state["lifecycle_state"] == "COMPLETED":
            break
        command, text = _script(state, n)
        headers = {**MINH, "Idempotency-Key": f"k{n}"}
        if command == "HINT_REQUEST":
            body = {
                "item_attempt_id": state["teaching"]["input_id"],
                "expected_state_version": state["state_version"],
            }
            sent = client.post(f"/v1/sessions/{sid}/hint-requests", json=body, headers=headers)
        else:
            body = {
                "item_attempt_id": state["teaching"]["input_id"],
                "kind": "ANSWER",
                "content": {"text": text},
                "modality": "VOICE" if command == "VOICE" else "TEXT",
                "expected_state_version": state["state_version"],
            }
            sent = client.post(f"/v1/sessions/{sid}/responses", json=body, headers=headers)
        assert sent.status_code == 200, sent.text
        acks.append(sent.json())
        state = client.get(f"/v1/sessions/{sid}/state", headers=MINH).json()
        views.append(state)
    assert state["lifecycle_state"] == "COMPLETED"
    stored = [d for d in database["learning_sessions"]._docs if d.get("_id") == sid or d.get("id") == sid]
    events = [e for d in database["events"]._docs for e in [d]]
    mine = client.get("/v1/sessions/mine", headers=MINH).json()
    overview = client.get("/v1/students/me/overview", headers=MINH).json()
    return {
        "views": views,
        "acks": acks,
        "stored": stored,
        "ledger": events,
        "mine": mine,
        "overview": overview,
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _record(client: TestClient, database: InMemoryDatabase) -> Any:
    ids: dict[str, str] = {}
    out = json.loads(json.dumps(normalize(_run(client, database), ids), ensure_ascii=False, default=str))
    # Every state view by its fields and their digest (the full views are 5 MB); the last one in full.
    out["view_digests"] = [{"keys": sorted(v), "sha": _digest(v)} for v in out["views"]]
    out["last_view"] = out["views"][-1]
    return out


def test_math_session_identical_to_before_eng5b(memory):
    got = _record(TestClient(app), memory)
    if os.environ.get("WRITE_GOLDEN") == "1" and not GOLDEN.exists():
        kept = {k: v for k, v in got.items() if k != "views"}
        GOLDEN.write_text(
            json.dumps(kept, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert set(want) <= set(got)
    for key in want:
        if key == "view_digests":
            # ENG-5b may add optional fields to a view (rule F1); every field of before is the same.
            assert len(got["views"]) == len(want[key])
            for i, (view, b) in enumerate(zip(got["views"], want[key], strict=True)):
                before = {k: view.get(k) for k in b["keys"]}
                assert _digest(before) == b["sha"], f"state view {i} differs"
        elif key in ("last_view", "mine"):
            wanted = want[key] if key == "last_view" else want[key][0]
            have = got[key] if key == "last_view" else got[key][0]
            assert {k: have.get(k) for k in wanted} == wanted, key
        else:
            assert got[key] == want[key], key
