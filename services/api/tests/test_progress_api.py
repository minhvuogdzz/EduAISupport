"""Student and parent views of the chapter across sessions (PART 27.1, DI-14). In-memory database only."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session import api as session_api
from cavat.modules.session import progress
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from test_chapter_session_api import FRAC, MINH, advance, start

PARENT = {"X-Demo-Parent": "1"}


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


def pass_first_node(client) -> dict:
    state = start(client)
    n = 0
    while state["teaching"]["passed"] == 0:
        state = advance(client, state, f"p{n}")
        n += 1
    return state


def test_the_student_sees_the_chapter_in_words_across_sessions(client):
    state = pass_first_node(client)
    view = client.get("/v1/students/me/overview", headers=MINH).json()
    assert view["passed"] == 1 and view["total"] == 7
    frac = next(n for n in view["nodes"] if n["node_id"] == FRAC)
    assert frac["passed"] and frac["quality"] in ("INDEPENDENT", "SOLID")
    assert all(n["quality"] == "NOT_STARTED" for n in view["nodes"] if n["status"] == "LOCKED")
    assert "mastery" not in frac  # the student never sees the score itself
    assert view["going_well"][0]["node_id"] == FRAC
    assert view["streak"] == 1 and len(view["study_days"]) == 1 and view["this_week"]["passed"] == 1
    assert view["sessions"] == {
        "total": 1,
        "completed": 0,
        "unfinished": 1,
        "minutes": view["sessions"]["minutes"],
    }
    assert view["current_session_id"] == state["session_id"]
    assert view["parent_code"] == progress.parent_code("minh")


def test_the_parent_follows_the_child_with_the_code(client):
    pass_first_node(client)
    lan = {"X-Demo-Student": "lan"}
    assert client.post("/v1/sessions", json={"student_display_name": "Lan"}, headers=lan).status_code == 201
    code = client.get("/v1/students/me/overview", headers=MINH).json()["parent_code"]
    assert client.get(f"/v1/parents/children/{code}").status_code == 401  # parents only
    assert client.get("/v1/parents/children/ZZZZZZ", headers=PARENT).status_code == 404
    view = client.get(f"/v1/parents/children/{code.lower()}", headers=PARENT).json()
    assert view["student_display_name"] == "Minh" and view["passed"] == 1
    assert len(view["trend"]) == 28 and view["trend"][-1]["passed"] == 1 and view["trend"][-1]["studied"]
    assert view["home_tips"] and view["home_tips"][0]["tip"]
    assert view["session_list"][0]["passed_names"] == ["Phân số thập phân"]
    assert view["sessions"]["total"] == 1  # Lan's session is not Minh's
    assert "transcript" not in view  # no drill-down into the conversation for parents (PART 27.4)


def test_quality_follows_di_14():
    class State:
        def __init__(self, mastery, level, insufficient=False, passed_at=None):
            self.mastery, self.level, self.insufficient_data, self.passed_at = (
                mastery,
                level,
                insufficient,
                passed_at,
            )

    assert progress.quality(State(None, 0)) == "NOT_STARTED"
    assert progress.quality(State(40.0, 2, insufficient=True)) == "INSUFFICIENT_DATA"
    assert progress.quality(State(80.0, 4, insufficient=True, passed_at=3)) == "INDEPENDENT"
    assert [progress.quality(State(50.0, lv)) for lv in range(6)] == [
        "FAMILIAR",
        "FAMILIAR",
        "WITH_SUPPORT",
        "INDEPENDENT",
        "INDEPENDENT",
        "SOLID",
    ]
