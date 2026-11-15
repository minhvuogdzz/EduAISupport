"""ENG-7b (english-module-rules F1): the report API of Mathematics answers exactly as before English.

``golden/math-reports-before-eng7b.json`` was written on the commit before ENG-7b by
``golden/make_math_reports_golden.py``: the database scripted learners left, and the JSON of every report
endpoint of Mathematics on a fixed day. Here the same database is loaded and each response must be equal,
key for key and value for value (an added English field that leaks into a Mathematics view fails).
"""

import json
from datetime import date
from pathlib import Path

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.main import app
from cavat.modules.session import progress
from cavat.modules.session.api import get_database, local_today
from fastapi.testclient import TestClient
from golden.make_math_reports_golden import decode, requests

GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "math-reports-before-eng7b.json").read_text(encoding="utf-8")
)


@pytest.fixture
def client():
    database = InMemoryDatabase()
    for name, docs in decode(GOLDEN["database"]).items():
        database.get_collection(name)._docs.extend(docs)
    today = date.fromisoformat(GOLDEN["today"])
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[local_today] = lambda: today
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)
    app.dependency_overrides.pop(local_today, None)


CASES = requests(GOLDEN["chapters"], progress.parent_code("minh"))


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_mathematics_report_answers_as_before_english(client, name):
    path, headers = CASES[name]
    got = client.get(path, headers=headers)
    assert got.status_code == 200, got.text
    assert json.dumps(got.json(), ensure_ascii=False, sort_keys=True) == json.dumps(
        GOLDEN["responses"][name], ensure_ascii=False, sort_keys=True
    )


def test_the_golden_covers_every_mathematics_report():
    assert set(GOLDEN["responses"]) == set(CASES)
    assert {"class", "teacher_student_lan", "parent_child_minh", "taught_chapters"} <= set(CASES)
