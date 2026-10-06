"""The teacher's class and student views (PART 27.1, khung Toán §23-§28, §43-§46, §56, §57), in memory."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session import api as session_api
from cavat.modules.session import teacher_view
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from test_chapter_session_api import FRAC, TEACHER, reply_text
from test_progress_api import pass_first_node

LAN = {"X-Demo-Student": "lan"}
WRONG = {"TP-CP-01": "0,7", "TP-PR-01": "0,09"}  # both are FRAC-M01 in lesson.yaml


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


def lan_makes_the_placeholder_mistake(client) -> None:
    """Lan writes 7/100 as 0,7 once, then answers right until that item is over."""
    created = client.post("/v1/sessions", json={"student_display_name": "Lan"}, headers=LAN).json()
    state = client.post(f"/v1/sessions/{created['session_id']}/join", headers=LAN).json()
    wrong_item = None
    for n in range(60):
        item = state.get("item")
        if wrong_item and (item is None or item["item_id"] != wrong_item):
            return
        if wrong_item is None and item and item["item_id"] in WRONG and item["expecting"] == "ANSWER":
            wrong_item, text = item["item_id"], WRONG[item["item_id"]]
        else:
            text = reply_text(state)
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": text},
            "expected_state_version": state["state_version"],
        }
        sent = client.post(
            f"/v1/sessions/{state['session_id']}/responses",
            json=body,
            headers={**LAN, "Idempotency-Key": f"lan-{n}"},
        )
        assert sent.status_code == 200, sent.text
        state = client.get(f"/v1/sessions/{state['session_id']}/state", headers=LAN).json()
    raise AssertionError("Lan never finished the item she got wrong")


def test_the_class_view_is_a_student_by_kc_heatmap_with_misconceptions_and_attention(client):
    pass_first_node(client)
    lan_makes_the_placeholder_mistake(client)
    assert client.get("/v1/teachers/class").status_code == 401  # teachers only

    view = client.get("/v1/teachers/class", headers=TEACHER).json()
    assert [s["display_name"] for s in view["students"]] == ["Lan", "Minh"]
    assert len(view["nodes"]) == 7 and all(len(s["cells"]) == 7 for s in view["students"])
    lan, minh = view["students"]

    frac = minh["cells"][0]
    assert frac["node_id"] == FRAC and frac["passed"] and frac["mastery"] >= view["nodes"][0]["min_mastery"]
    assert all(c["mastery"] is None for c in minh["cells"][1:])
    assert minh["overall"]["mastery"] == frac["mastery"] and minh["overall"]["coverage"] == 14.3

    # §45: the class on each KC, over the students with a score.
    first = view["by_node"][0]
    assert first["students"] == 2 and first["passed"] == 1
    assert first["mean_mastery"] == round((frac["mastery"] + lan["cells"][0]["mastery"]) / 2, 1)
    assert view["by_node"][1] == {
        "node_id": view["nodes"][1]["node_id"],
        "mean_mastery": None,
        "students": 0,
        "passed": 0,
    }

    # §28: the misconception, its share, its students, its last 14 days; Lan needs attention (CRITICAL).
    [mis] = view["misconceptions"]
    assert mis["id"] == "FRAC-M01" and mis["node_id"] == FRAC and mis["severity"] == "CRITICAL"
    assert mis["count"] == 1 and mis["share"] == 100.0 and mis["students"] == 1 and mis["recent"] == 1
    assert mis["active_students"] == 1
    assert {"kind": "MISCONCEPTION", "node_id": FRAC, "misconception_id": "FRAC-M01", "count": 1} in [
        {k: v for k, v in r.items() if v is not None} for r in lan["attention"]
    ]
    assert lan["cells"][0]["active_misconceptions"] == 1
    assert minh["attention"] == []
    assert view["kpis"] == {
        "students": 2,
        "active_this_week": 2,
        "sessions": 2,
        "minutes": view["kpis"]["minutes"],
        "passed": 1,
        "cells": 14,
        "mean_mastery": round((minh["overall"]["mastery"] + lan["overall"]["mastery"]) / 2, 1),
        "attention": 1,
    }


def test_the_student_view_has_the_overview_radar_timeline_activity_and_kc_detail(client):
    pass_first_node(client)
    assert client.get("/v1/teachers/students/minh").status_code == 401
    assert client.get("/v1/teachers/students/nobody", headers=TEACHER).status_code == 404

    view = client.get("/v1/teachers/students/minh", headers=TEACHER).json()
    assert view["display_name"] == "Minh" and len(view["session_list"]) == 1
    frac = view["nodes"][0]
    assert frac["node_id"] == FRAC and frac["group"] == "PASSED" and frac["passed"]
    assert frac["items"] >= 2 and frac["solved"] >= 2 and frac["attempts"] >= frac["items"]
    assert frac["trend"] and frac["trend"][-1]["mastery"] == frac["mastery"]
    assert frac["direction"] in ("UP", "FLAT", "DOWN")
    assert frac["recommendation"] == teacher_view.recommendation(frac["mastery"])
    assert set(frac["dimensions"]) == {"C", "R", "A", "T", "I", "S", "D"}
    assert all(n["group"] == "NOT_STARTED" and n["recommendation"] == "DIAGNOSE" for n in view["nodes"][1:])

    overall = view["overall"]
    assert overall["passed"] == 1 and overall["total"] == 7 and overall["mastery"] == frac["mastery"]
    assert overall["level"] == teacher_view.band(frac["mastery"])
    assert view["dimensions"]["C"]["value"] is not None
    assert view["dimensions"]["S"] == {"value": None, "n_eff": 0.0}  # no delayed probe yet (§19, §55)
    [day] = view["timeline"]
    assert day["mastery"] == overall["mastery"]
    assert view["velocity"] is None  # nothing before this week to compare with (§39)
    [activity] = view["activity"]
    assert activity["date"] == day["date"] and activity["passed"] == 1
    assert activity["independent"] + activity["supported"] + activity["worked"] >= 2


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], None),
        ([50.0], None),
        ([50.0, 52.0], "FLAT"),
        ([50.0, 60.0], "UP"),
        ([60.0, 50.0], "DOWN"),
        ([10.0, 50.0, 50.0, 50.0, 51.0], "FLAT"),
    ],
)
def test_the_trend_compares_with_three_changes_earlier(values, expected):
    assert teacher_view.direction(values) == expected


def test_the_recommendation_and_level_follow_the_bands():
    assert teacher_view.recommendation(None) == "DIAGNOSE"
    assert [teacher_view.recommendation(m) for m in (39.9, 40, 59.9, 60, 74.9, 75, 89.9, 90)] == [
        "EXPLAIN",
        "GUIDED",
        "GUIDED",
        "PRACTICE",
        "PRACTICE",
        "TRANSFER",
        "TRANSFER",
        "CHALLENGE",
    ]
    assert [teacher_view.band(m) for m in (0, 19.9, 20, 40, 60, 75, 90, 100)] == [0, 0, 1, 2, 3, 4, 5, 5]
