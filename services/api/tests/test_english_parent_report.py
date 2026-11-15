"""ENG-7c (DI-153): the English report says the child's typical mistakes as concretely as Mathematics, and a
parent finds both subjects.

The first real run on Unit 11 showed "cần luyện" with only "Cần luyện thêm để tự làm được" and the parent
view open on Mathematics unless ``?chapter=`` named the unit. The sessions here are the real teaching loop
on Unit 11 (``english_report_data``), offline; the Mathematics responses stay the golden of
``test_math_reports_golden.py``.
"""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.reports import english as report
from cavat.modules.session import progress
from cavat.modules.session.api import get_database, local_today
from english_report_data import T0, TODAY, UNIT, UNIT_ID, Learner, converse, store
from fastapi.testclient import TestClient

TEACHER = {"X-Demo-Teacher": "1"}
PARENT = {"X-Demo-Parent": "1"}
VOCAB = "ENG5-U11-VOCAB"
# Linh says the present for the past once, mishears "walked on the beach" once, misspells "boat" once, and
# the session stops while VOCAB is still to practise.
LINH_WRONG = {
    "U11-VO-PR-02": "We eat seafood.",
    "U11-VO-PR-01": "B",
    "U11-VO-CP-01": "We took a bot trip around the bay.",
}
LINH_TURNS = 15


@pytest.fixture
async def database():
    db = InMemoryDatabase()
    await ensure_indexes(db)
    await store(db, "linh", "Linh", converse(Learner(dict(LINH_WRONG)), T0, LINH_TURNS))
    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[local_today] = lambda: TODAY
    yield db
    app.dependency_overrides.pop(get_database, None)
    app.dependency_overrides.pop(local_today, None)


@pytest.fixture
def client(database):
    return TestClient(app)


def linh_parent(client) -> dict:
    code = progress.parent_code("linh")
    got = client.get(f"/v1/parents/children/{code}?chapter={UNIT_ID}", headers=PARENT)
    assert got.status_code == 200, got.text
    return got.json()


# --- "cần luyện" names the mistakes -----------------------------------------------------------------------


def test_to_practise_names_the_typical_mistakes_with_a_short_example(client):
    view = linh_parent(client)
    [vocab] = [t for t in view["to_practise"] if t["node_id"] == VOCAB]
    assert vocab["reason"] == "Có lúc nhầm: kể chuyện đã qua bằng động từ nguyên mẫu, ví dụ eat → ate"
    labels = {m["label"]: m for m in vocab["mistakes"]}
    # the lesson's approved misconception names (lesson-1-did-you: M04, M06), then a DI-153 word
    assert labels["Kể chuyện đã qua bằng động từ nguyên mẫu"]["examples"] == ["eat → ate"]
    assert labels["Nhầm nghĩa giữa các cụm hoạt động"]["examples"] == [
        "chọn “đi thuyền quanh đảo” thay vì “đi dạo trên bãi biển”"
    ]
    assert labels[report.MISTAKE_LABEL["EN_SLIP"]]["examples"] == ["bot → boat"]
    assert all(m["count"] == 1 for m in vocab["mistakes"])


def test_the_parent_never_gets_the_childs_whole_sentence(client):
    text = json.dumps(linh_parent(client), ensure_ascii=False)
    for said in LINH_WRONG.values():
        if len(said) > 1:
            assert said not in text and said.lower().rstrip(".") not in text  # rule F4: no transcript


async def test_the_student_sees_the_same_mistakes(client):
    view = client.get(
        f"/v1/students/me/overview?chapter={UNIT_ID}", headers={"X-Demo-Student": "linh"}
    ).json()
    parent = linh_parent(client)
    assert view["to_practise"] == parent["to_practise"]


def test_the_teacher_sees_the_mistakes_of_every_node(client):
    view = client.get(f"/v1/teachers/students/linh?chapter={UNIT_ID}", headers=TEACHER).json()
    nodes = {n["node_id"]: n for n in view["nodes"]}
    assert len(nodes[VOCAB]["mistakes"]) == 3
    assert all("mistakes" not in n for k, n in nodes.items() if k != VOCAB)  # no mistake: no field


def test_a_node_without_a_mistake_keeps_the_shared_reason():
    f = SimpleNamespace(events=converse(Learner(), T0, LINH_TURNS))
    assert report.mistakes(UNIT, f, VOCAB) == []
    assert report.mistake_reason([]) is None


def test_a_mistake_seen_twice_is_said_often():
    found = [{"label": "Viết sai chính tả", "count": 2, "examples": ["seafod → seafood"]}]
    assert report.mistake_reason(found) == "Còn hay nhầm: viết sai chính tả, ví dụ seafod → seafood"
    assert (
        report.mistake_reason([{**found[0], "count": 1, "examples": []}]) == "Có lúc nhầm: viết sai chính tả"
    )


@pytest.mark.parametrize(
    ("said", "right", "pair"),
    [
        ("We eat seafood.", "We ate seafood.", "eat → ate"),
        ("We took a bot trip around the bay.", "We took a boat trip around the bay.", "bot → boat"),
        ("We took a boat trip.", "We took a boat trip around the bay.", "thiếu “around the bay”"),
        ("Did you swam?", "Did you swim?", "swam → swim"),
        ("We took a boat trip.", "We took a boat trip.", None),
    ],
)
def test_the_example_is_the_words_that_differ(said, right, pair):
    assert report._pair(said, right) == pair


def test_a_spelling_slip_is_one_close_word():
    assert report._slip("seafod → seafood") and report._slip("bot → boat")
    assert not report._slip("eat → ate") and not report._slip("thiếu “around the bay”")


# --- a parent finds both subjects -------------------------------------------------------------------------


async def test_the_parent_sees_every_subject_the_child_studied_the_latest_first(client, database):
    from test_teacher_view_api import lan_makes_the_placeholder_mistake

    lan_makes_the_placeholder_mistake(client)  # a Mathematics session of Lan
    await store(database, "lan", "Lan", converse(Learner(), T0 + timedelta(days=1), 10))
    code = progress.parent_code("lan")
    got = client.get(f"/v1/parents/children/{code}/subjects", headers=PARENT)
    assert got.status_code == 200, got.text
    rows = got.json()
    assert {r["subject"] for r in rows} == {"math", "english"}
    assert [r["last_session_at"] for r in rows] == sorted((r["last_session_at"] for r in rows), reverse=True)
    [english] = [r for r in rows if r["subject"] == "english"]
    assert english == {**english, "chapter_id": UNIT_ID, "title": "Unit 11: Family time", "sessions": 1}
    # the view without ?chapter= stays the Mathematics one, as before English (rule F1)
    view = client.get(f"/v1/parents/children/{code}", headers=PARENT).json()
    assert view["chapter"]["chapter_id"] != UNIT_ID and "subject" not in view["chapter"]
    assert all("mistakes" not in t for t in view["to_practise"])


def test_an_unknown_code_has_no_subjects(client):
    assert client.get("/v1/parents/children/ZZZZZZ/subjects", headers=PARENT).status_code == 404


def test_only_english_subjects_for_a_child_who_studied_only_english(client):
    code = progress.parent_code("linh")
    rows = client.get(f"/v1/parents/children/{code}/subjects", headers=PARENT).json()
    assert [(r["subject"], r["chapter_id"]) for r in rows] == [("english", UNIT_ID)]
