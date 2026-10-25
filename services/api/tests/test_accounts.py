"""The three fixed accounts and their login (ACC-1). In-memory database only."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.identity import accounts
from cavat.modules.identity import api as identity_api
from cavat.modules.identity.accounts import (
    Identity,
    LoginGuard,
    hash_pin,
    issue_token,
    read_token,
    verify_pin,
)
from cavat.modules.identity.repository import User, UserRepository
from cavat.modules.session import api as session_api
from cavat.modules.session.api import get_database
from cavat.modules.session.service import DEMO_SCHOOL_ID
from fastapi.testclient import TestClient

PINS = {"hocsinh": "2468", "phuhuynh": "1357", "giaovien": "9753"}


@pytest.fixture(autouse=True)
def templates_only(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)


@pytest.fixture
async def memory(accounts_mode):
    database = InMemoryDatabase()
    await ensure_indexes(database)
    repo = UserRepository(database, DEMO_SCHOOL_ID)
    student = await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="STUDENT",
            login_name="hocsinh",
            display_name="Minh",
            grade=5,
            pin_hash=hash_pin(PINS["hocsinh"]),
        )
    )
    await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="PARENT",
            login_name="phuhuynh",
            display_name="Mẹ Minh",
            pin_hash=hash_pin(PINS["phuhuynh"]),
            child_id=student.id,
        )
    )
    await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="TEACHER",
            login_name="giaovien",
            display_name="Cô Lan",
            pin_hash=hash_pin(PINS["giaovien"]),
        )
    )
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)


@pytest.fixture
def client(memory):
    return TestClient(app)


def login(client, name: str) -> dict:
    response = client.post("/v1/auth/login", json={"login_name": name, "pin": PINS[name]})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_pins_are_hashed_and_tokens_are_signed():
    stored = hash_pin("2468")
    assert "2468" not in stored and verify_pin("2468", stored) and not verify_pin("2469", stored)
    with pytest.raises(ValueError):
        hash_pin("12")  # too short
    who = Identity("u1", "STUDENT", "Minh")
    token = issue_token(who, b"key", now=1000.0)
    assert read_token(token, b"key", now=1001.0) == who
    assert read_token(token, b"other key", now=1001.0) is None  # another signing key
    body, signature = token.split(".")
    assert read_token(f"{body}x.{signature}", b"key", now=1001.0) is None  # tampered claims
    assert read_token(token, b"key", now=1000.0 + accounts.TOKEN_TTL_S + 1) is None  # expired


def test_wrong_pins_pause_the_account():
    guard = LoginGuard()
    for _ in range(accounts.MAX_FAILURES):
        guard.failed("hocsinh", now=100.0)
    assert guard.locked_for("hocsinh", now=101.0) > 0
    assert guard.locked_for("hocsinh", now=100.0 + accounts.LOCK_S + 1) == 0


def test_the_web_lists_the_three_accounts_and_only_a_right_pin_logs_in(client):
    config = client.get("/v1/auth/config").json()
    assert config["mode"] == "accounts"
    assert config["student_signup"] is True  # students come in by name, not by a fixed card
    assert [(a["kind"], a["display_name"]) for a in config["accounts"]] == [
        ("PARENT", "Mẹ Minh"),
        ("TEACHER", "Cô Lan"),
    ]
    assert client.post("/v1/auth/login", json={"login_name": "hocsinh", "pin": "0000"}).status_code == 401
    me = client.get("/v1/auth/me", headers=login(client, "hocsinh")).json()
    assert (me["kind"], me["display_name"]) == ("STUDENT", "Minh")


def test_each_account_sees_its_own_part_only(client):
    student, parent, teacher = (login(client, n) for n in ("hocsinh", "phuhuynh", "giaovien"))
    # The headers of the demo mode are not an identity any more.
    assert client.get("/v1/sessions/mine", headers={"X-Demo-Student": "minh"}).status_code == 401

    # The session takes the account's name, not a name typed in the web.
    created = client.post("/v1/sessions", json={"student_display_name": "Ai đó"}, headers=student)
    assert created.status_code == 201, created.text
    assert created.json()["student_display_name"] == "Minh"
    assert [s["student_display_name"] for s in client.get("/v1/sessions/mine", headers=student).json()] == [
        "Minh"
    ]

    assert client.get("/v1/teachers/class", headers=student).status_code == 403
    assert client.get("/v1/sessions/mine", headers=teacher).status_code == 403
    assert client.get("/v1/parents/me/child", headers=teacher).status_code == 403

    child = client.get("/v1/parents/me/child", headers=parent)
    assert child.status_code == 200, child.text
    assert child.json()["student_display_name"] == "Minh" and child.json()["sessions"]["total"] == 1

    students = client.get("/v1/teachers/class", headers=teacher).json()["students"]
    assert [s["display_name"] for s in students] == ["Minh"]
    # A session of the trials before the accounts (a random demo id) stays out of the teacher's views.
    assert client.get("/v1/teachers/students/old-random-id", headers=teacher).status_code == 404


def test_five_wrong_pins_pause_the_login(client):
    for _ in range(accounts.MAX_FAILURES):
        client.post("/v1/auth/login", json={"login_name": "giaovien", "pin": "1111"})
    locked = client.post("/v1/auth/login", json={"login_name": "giaovien", "pin": PINS["giaovien"]})
    assert locked.status_code == 429


def student_by_name(client, name: str):
    return client.post("/v1/auth/student", json={"name": name})


def test_a_student_comes_in_by_name_and_finds_the_same_history_again(client):
    first = student_by_name(client, "  Nguyễn  Bảo An ")
    assert first.status_code == 200, first.text
    user = first.json()["user"]
    assert (user["kind"], user["display_name"]) == ("STUDENT", "An")  # the given name only (rule 8)
    headers = {"Authorization": f"Bearer {first.json()['token']}"}
    created = client.post("/v1/sessions", json={"student_display_name": "x"}, headers=headers)
    assert created.status_code == 201, created.text

    # Back after a crash, from another device, with other capitals and accents: the same student.
    again = student_by_name(client, "nguyen bao an").json()
    assert again["user"]["user_id"] == user["user_id"]
    other = {"Authorization": f"Bearer {again['token']}"}
    assert [s["session_id"] for s in client.get("/v1/sessions/mine", headers=other).json()] == [
        created.json()["session_id"]
    ]

    # Another child is another student with an empty history; the teacher sees both.
    second = student_by_name(client, "Trần Bảo Anh").json()
    assert second["user"]["user_id"] != user["user_id"]
    mine = {"Authorization": f"Bearer {second['token']}"}
    assert client.get("/v1/sessions/mine", headers=mine).json() == []
    identity_api._guard.succeeded("giaovien")  # the pause test above leaves this login locked
    teacher = login(client, "giaovien")
    names = {s["display_name"] for s in client.get("/v1/teachers/class", headers=teacher).json()["students"]}
    assert "An" in names


def test_a_name_never_opens_another_role_and_the_fixed_student_keeps_the_history(client):
    # The fixed student of `make accounts` is found by its name, with its own account.
    fixed = student_by_name(client, "minh").json()
    fixed_me = client.get("/v1/auth/me", headers=login(client, "hocsinh")).json()
    assert fixed["user"]["user_id"] == fixed_me["user_id"]
    # Names of the other roles make students, never the parent or the teacher.
    for name in ("giaovien", "Mẹ Minh", "phuhuynh"):
        body = student_by_name(client, name).json()
        assert body["user"]["kind"] == "STUDENT"
        assert body["user"]["user_id"] != fixed_me["user_id"]
    assert (
        client.get("/v1/teachers/class", headers={"Authorization": f"Bearer {body['token']}"}).status_code
        == 403
    )


@pytest.mark.parametrize("name", ["", "   ", "!!!", "a" * 41])
def test_an_empty_or_odd_name_is_refused(client, name):
    assert student_by_name(client, name).status_code in (422, 400)
