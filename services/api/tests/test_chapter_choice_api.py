"""A student or a parent may look at any chapter the tutor teaches (REFORM 4.4), not only the first one.

The chapter is named in the URL (``?chapter=``) like the teacher's views are; without it the default chapter
stays. Always on the in-memory database, with templates only."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, progress
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from test_chapter_session_api import MINH, TEACHER, advance, start
from test_progress_api import PARENT

FIRST = chapter_service.DEFAULT_CHAPTER_ID
SECOND = "math-g5-area-triangle-trapezoid"
SECOND_TITLE = "Diện tích hình tam giác, hình thang"


@pytest.fixture(autouse=True)
def templates_only(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)


@pytest.fixture(autouse=True)
def two_chapters(monkeypatch):
    """The second chapter is a plan the teacher published from the documents; here it is a copy of the first
    one under another id, in a registry the test gives back."""
    monkeypatch.setattr(chapter_service, "_published", {})
    monkeypatch.setattr(chapter_service, "_current", {})
    first = chapter_service.chapters()[FIRST]
    package = first.package.model_dump(mode="json") | {"chapter_id": SECOND, "title": SECOND_TITLE}
    lessons = {key: lesson.model_dump(mode="json") for key, lesson in first.lessons.items()}
    chapter_service.register_published(SECOND, "0.1.0", package, lessons, current=True)


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


def start_on(client, chapter: str) -> dict:
    created = client.post("/v1/sessions", json={"lesson_id": chapter}, headers=MINH)
    assert created.status_code == 201, created.text
    joined = client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=MINH)
    assert joined.status_code == 200, joined.text
    return joined.json()


def test_without_a_chapter_the_student_sees_the_first_one_and_the_list_to_pick_from(client):
    view = client.get("/v1/students/me/overview", headers=MINH).json()
    assert view["chapter"]["chapter_id"] == FIRST
    # the default chapter first, whatever the order of the ids
    assert view["chapters"] == [
        {"chapter_id": FIRST, "title": view["chapter"]["title"]},
        {"chapter_id": SECOND, "title": SECOND_TITLE},
    ]


def test_the_student_sees_each_chapter_on_its_own_sessions(client):
    first = start(client)
    second = start_on(client, SECOND)
    assert second["lesson"]["lesson_id"] == SECOND and second["session_id"] != first["session_id"]

    one = client.get("/v1/students/me/overview", headers=MINH).json()
    two = client.get(f"/v1/students/me/overview?chapter={SECOND}", headers=MINH).json()
    assert one["chapter"]["chapter_id"] == FIRST and one["current_session_id"] == first["session_id"]
    assert two["chapter"] == {"chapter_id": SECOND, "title": SECOND_TITLE}
    assert two["current_session_id"] == second["session_id"]
    assert one["sessions"]["total"] == two["sessions"]["total"] == 1  # each chapter counts its own sessions
    assert one["chapters"] == two["chapters"]  # the list to pick from does not depend on the pick

    mine = client.get("/v1/sessions/mine", headers=MINH).json()
    assert {s["session_id"] for s in mine} == {first["session_id"], second["session_id"]}


def test_a_chapter_without_a_session_is_empty_not_missing(client):
    start(client)
    view = client.get(f"/v1/students/me/overview?chapter={SECOND}", headers=MINH).json()
    assert view["sessions"]["total"] == 0 and view["current_session_id"] is None and view["passed"] == 0
    assert view["total"] == len(view["nodes"]) > 0


def test_a_chapter_that_does_not_exist_is_not_found(client):
    assert client.get("/v1/students/me/overview?chapter=nope", headers=MINH).status_code == 404
    assert client.get("/v1/parents/children/ZZZZZZ?chapter=nope", headers=PARENT).status_code == 404


def test_the_parent_follows_the_child_on_the_chapter_they_pick(client):
    start(client)
    second = start_on(client, SECOND)
    code = progress.parent_code("minh")
    assert client.get(f"/v1/parents/children/{code}?chapter=nope", headers=PARENT).status_code == 404

    default = client.get(f"/v1/parents/children/{code}", headers=PARENT).json()
    named = client.get(f"/v1/parents/children/{code}?chapter={SECOND}", headers=PARENT).json()
    assert default["chapter"]["chapter_id"] == FIRST
    assert named["chapter"]["chapter_id"] == SECOND and named["current_session_id"] == second["session_id"]
    assert [s["session_id"] for s in named["session_list"]] == [second["session_id"]]
    assert named["home_tips"] and len(named["trend"]) == 28
    assert [c["chapter_id"] for c in named["chapters"]] == [FIRST, SECOND]


def test_the_parent_account_names_the_chapter_of_the_linked_child(client):
    start(client)
    second = start_on(client, SECOND)
    app.dependency_overrides[session_api.linked_child] = lambda: "minh"  # the guardian link of ACC-1
    try:
        default = client.get("/v1/parents/me/child").json()
        named = client.get(f"/v1/parents/me/child?chapter={SECOND}").json()
        assert client.get("/v1/parents/me/child?chapter=nope").status_code == 404
    finally:
        app.dependency_overrides.pop(session_api.linked_child, None)
    assert default["chapter"]["chapter_id"] == FIRST
    assert named["chapter"]["chapter_id"] == SECOND and named["current_session_id"] == second["session_id"]


def test_a_student_is_not_shown_another_students_sessions_on_the_chapter(client):
    start_on(client, SECOND)
    lan = {"X-Demo-Student": "lan"}
    view = client.get(f"/v1/students/me/overview?chapter={SECOND}", headers=lan).json()
    assert view["sessions"]["total"] == 0 and view["current_session_id"] is None


def test_the_teacher_views_still_name_their_chapter(client):
    advance(client, start(client), "c0")
    assert client.get(f"/v1/teachers/class?chapter={SECOND}", headers=TEACHER).status_code == 200
    assert client.get("/v1/teachers/class?chapter=nope", headers=TEACHER).status_code == 404
