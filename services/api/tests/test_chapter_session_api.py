"""Chapter sessions over the session API (M1-7): the teaching loop end to end, the student's node map,
the teacher's report and transcript. Always on the in-memory database, with templates only."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, service
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from test_teaching_loop import CHAPTER, correct_text

MINH = {"X-Demo-Student": "minh"}
TEACHER = {"X-Demo-Teacher": "1"}
FRAC = "KC-DEC-FRAC"


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


@pytest.fixture
def client(memory):
    return TestClient(app)


def start(client) -> dict:
    created = client.post("/v1/sessions", json={"student_display_name": "Minh"}, headers=MINH)
    assert created.status_code == 201, created.text
    view = created.json()
    assert (
        view["lifecycle_state"] == "READY"
        and view["lesson"]["lesson_id"] == chapter_service.DEFAULT_CHAPTER_ID
    )
    statuses = {n["node_id"]: n["status"] for n in view["teaching"]["nodes"]}
    assert statuses[FRAC] == "AVAILABLE" and list(statuses.values()).count("LOCKED") == 6
    joined = client.post(f"/v1/sessions/{view['session_id']}/join", headers=MINH)
    assert joined.status_code == 200, joined.text
    return joined.json()


def reply_text(state: dict, weak_retell: bool = False) -> str:
    teaching = state["teaching"]
    if teaching["awaiting"] == "THEORY_REPLY":
        return "Con nghĩ là được ạ."
    if teaching["awaiting"] == "RETELL":
        if weak_retell:
            return "Con không nhớ ạ."
        ideas = CHAPTER.node(teaching["current_node_id"]).explain.key_ideas
        return ". ".join(phrasings[0] for phrasings in ideas)
    item = state["item"]
    if item["expecting"] == "EXPLANATION":
        return CHAPTER.item(item["item_id"]).explanation or "Vì con làm theo quy tắc."
    return correct_text(item["item_id"])


def send(client, state: dict, text: str, key: str):
    body = {
        "item_attempt_id": state["teaching"]["input_id"],
        "kind": "ANSWER",
        "content": {"text": text},
        "expected_state_version": state["state_version"],
    }
    return client.post(
        f"/v1/sessions/{state['session_id']}/responses", json=body, headers={**MINH, "Idempotency-Key": key}
    )


def advance(client, state: dict, key: str, text: str | None = None) -> dict:
    sent = send(client, state, reply_text(state) if text is None else text, key)
    assert sent.status_code == 200, sent.text
    return client.get(f"/v1/sessions/{state['session_id']}/state", headers=MINH).json()


def test_the_teaching_loop_runs_through_the_session_api(client):
    state = start(client)
    teaching = state["teaching"]
    assert (teaching["awaiting"], teaching["current_node_id"], teaching["step"]) == ("THEORY_REPLY", FRAC, 2)
    assert state["item"] is None and state["allowed_commands"] == ["ANSWER"]
    assert [t["kind"] for t in state["transcript"]] == ["NODE", "THEORY"]
    assert teaching["prompt"] == CHAPTER.node(FRAC).theory[0].ask

    state = advance(client, state, "k0")
    assert state["teaching"]["awaiting"] == "ANSWER" and state["teaching"]["step"] == 3
    assert (
        state["item"]["item_id"] == "TP-CC-01"
        and state["teaching"]["input_id"] == state["item"]["item_attempt_id"]
    )
    assert "HINT_REQUEST" in state["allowed_commands"]

    for n in range(1, 200):
        if state["lifecycle_state"] == "COMPLETED":
            break
        state = advance(client, state, f"k{n}")
    assert state["lifecycle_state"] == "COMPLETED" and state["teaching"]["awaiting"] == "NOTHING"
    assert {node["status"] for node in state["teaching"]["nodes"]} == {"PASSED"}
    assert state["progress"] == {"items_done": 7, "items_total": 7}
    assert state["transcript"][-1]["kind"] == "SUMMARY"


def test_commands_must_fit_what_the_tutor_waits_for(client):
    state = start(client)
    sid = state["session_id"]
    hint = client.post(
        f"/v1/sessions/{sid}/hint-requests",
        json={
            "item_attempt_id": state["teaching"]["input_id"],
            "expected_state_version": state["state_version"],
        },
        headers={**MINH, "Idempotency-Key": "h1"},
    )
    assert hint.status_code == 409 and hint.json()["error"]["code"] == "COMMAND_NOT_ALLOWED_IN_ACTIVITY"
    stale = send(client, {**state, "teaching": {**state["teaching"], "input_id": "old"}}, "hi", "s1")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_ITEM"

    first = send(client, state, "Con nghĩ là được ạ.", "same")
    again = send(client, state, "Con nghĩ là được ạ.", "same")  # the same command sent twice
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    after = client.get(f"/v1/sessions/{sid}/state", headers=MINH).json()
    assert sum(t["actor"] == "student" for t in after["transcript"]) == 1


def test_the_teacher_report_explains_scores_and_decisions(client):
    state = start(client)
    for n in range(4):  # theory reply, check item (+ "vì sao" if sampled), retell...
        state = advance(client, state, f"k{n}")
    sid = state["session_id"]
    assert client.get(f"/v1/sessions/{sid}/report").status_code == 401  # teacher only
    report = client.get(f"/v1/sessions/{sid}/report", headers=TEACHER).json()
    assert report["versions"] == {
        "mastery": "node-mastery/0.1.0",
        "policy": "node-policy/0.1.0",
        "templates": "teaching-templates/0.1.0",
    }
    frac = next(n for n in report["nodes"] if n["node_id"] == FRAC)
    assert frac["status"] == "CURRENT" and frac["mastery"] is not None
    assert set(frac["dimensions"]) == {"C", "R", "A", "T", "I", "S", "D"}
    assert frac["pass_rule"]["min_mastery"] == 75.0 and "APPLICATION" in frac["missing"]
    assert {e["reason"] for e in report["evidence"]} >= {"ANSWER", "INDEPENDENCE"}
    rules = [d["rule_ids"][0] for d in report["decisions"]]
    assert rules[:3] == ["N-NEXT", "N-TEACH", "N-CHECK"]
    assert report["trace"] and all(t["node_id"] == FRAC for t in report["trace"])

    lesson = client.post("/v1/sessions", json={"lesson_id": service.DEFAULT_LESSON_ID}, headers=MINH).json()
    assert client.get(f"/v1/sessions/{lesson['session_id']}/report", headers=TEACHER).status_code == 404


def test_the_teacher_transcript_shows_the_rules_and_the_retell_verdict(client):
    state = start(client)
    n = 0
    while state["teaching"]["awaiting"] != "RETELL":
        state = advance(client, state, f"k{n}")
        n += 1
    state = advance(client, state, "weak", text=reply_text(state, weak_retell=True))
    sid = state["session_id"]
    transcript = client.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER).json()
    turns = [t for segment in transcript["segments"] for t in segment["turns"]]
    teach = [t["teach"] for t in turns if t.get("teach")]
    assert teach[0]["kind"] == "NODE" and teach[0]["rule_ids"] == ["N-NEXT"]
    assert any(t["kind"] == "THEORY" and t["rule_ids"] == ["N-RETEACH"] for t in teach)
    retell = next(t for t in turns if t["student"] and t["student"].get("retell"))
    assert retell["student"]["retell"] == {"score": 0.0, "ideas_found": 0, "ideas_total": 3}
    assert transcript["session"]["progress"] == {"items_done": 0, "items_total": 7}
