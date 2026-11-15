"""Write the Mathematics report API golden (ENG-7b, english-module-rules F1): run once BEFORE a change.

Scripted learners study the decimals chapter through the real API, offline, with templates only (no
model, in-memory database): Minh passes the first node, Lan writes 7/100 as 0,7 once (an active CRITICAL
misconception), Hoa opens a session of every other Mathematics chapter. The database they leave and the JSON
of every report endpoint of Mathematics (student overview, parent by code, the teacher's chapters, class
and student views) on a fixed ``today`` are written to ``math-reports-before-eng7b.json``.
``test_math_reports_golden.py`` loads the same database and compares each response byte for byte.

Run from services/api: ``.venv/bin/python tests/golden/make_math_reports_golden.py``. It was run on the
commit before ENG-7b (b0310d0); running it again after a change would hide a regression, not find one.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # the tests' scripted learners
# As tests/conftest.py: demo identities, no model, no web, no voice server, no journal.
os.environ.update(
    AUTH_MODE="demo", OBSERVABILITY_ENABLED="0", GROQ_API_KEY="", GEMINI_API_KEY="", WEB_LOOKUP="off", TTS="off"
)
os.environ["WEB_DIST"] = str(HERE.parent / "no-web-build")
os.environ["API_DOCS"] = "0"

OUT = HERE / "math-reports-before-eng7b.json"
TEACHER = {"X-Demo-Teacher": "1"}
PARENT = {"X-Demo-Parent": "1"}


def encode(value: Any) -> Any:
    """A database document as JSON: dates and ObjectIds tagged so ``decode`` gives them back."""
    from bson import ObjectId

    if isinstance(value, datetime):
        return {"$date": value.isoformat()}
    if isinstance(value, ObjectId):
        return {"$oid": str(value)}
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [encode(v) for v in value]
    return value


def decode(value: Any) -> Any:
    from bson import ObjectId

    if isinstance(value, dict):
        if set(value) == {"$date"}:
            return datetime.fromisoformat(value["$date"])
        if set(value) == {"$oid"}:
            return ObjectId(value["$oid"])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def requests(chapters: list[str], code: str) -> dict[str, tuple[str, dict[str, str]]]:
    """Every Mathematics report request of the golden: name -> (path, headers)."""
    minh, lan = {"X-Demo-Student": "minh"}, {"X-Demo-Student": "lan"}
    out: dict[str, tuple[str, dict[str, str]]] = {
        "student_overview_minh": ("/v1/students/me/overview", minh),
        "student_overview_lan": ("/v1/students/me/overview", lan),
        "parent_child_minh": (f"/v1/parents/children/{code}", PARENT),
        "taught_chapters": ("/v1/teachers/taught-chapters", TEACHER),
        "class": ("/v1/teachers/class", TEACHER),
        "teacher_student_minh": ("/v1/teachers/students/minh", TEACHER),
        "teacher_student_lan": ("/v1/teachers/students/lan", TEACHER),
    }
    for cid in chapters:
        out[f"class_{cid}"] = (f"/v1/teachers/class?chapter={cid}", TEACHER)
        out[f"student_overview_minh_{cid}"] = (f"/v1/students/me/overview?chapter={cid}", minh)
        out[f"parent_child_minh_{cid}"] = (f"/v1/parents/children/{code}?chapter={cid}", PARENT)
    return out


def main() -> None:
    from cavat.core.memory_db import InMemoryDatabase
    from cavat.db import ensure_indexes
    from cavat.main import app
    from cavat.modules.session import api as session_api
    from cavat.modules.session import chapter_service, progress
    from cavat.modules.session.api import get_database, local_today
    from fastapi.testclient import TestClient
    from test_progress_api import pass_first_node
    from test_teacher_view_api import lan_makes_the_placeholder_mistake

    session_api.tutor_router = lambda: None  # templates only, as the tests
    database = InMemoryDatabase()
    asyncio.run(ensure_indexes(database))
    app.dependency_overrides[get_database] = lambda: database
    client = TestClient(app)
    pass_first_node(client)
    lan_makes_the_placeholder_mistake(client)
    others = sorted(c for c in chapter_service.chapters() if c != chapter_service.DEFAULT_CHAPTER_ID)
    hoa = {"X-Demo-Student": "hoa"}
    for cid in others:
        created = client.post("/v1/sessions", json={"lesson_id": cid}, headers=hoa)
        assert created.status_code in (200, 201), created.text
        joined = client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=hoa)
        assert joined.status_code == 200, joined.text

    today = local_today()
    app.dependency_overrides[local_today] = lambda: today
    responses = {}
    for name, (path, headers) in requests(others, progress.parent_code("minh")).items():
        got = client.get(path, headers=headers)
        assert got.status_code == 200, (name, got.text)
        responses[name] = got.json()
    app.dependency_overrides.clear()

    dump = {name: encode(col._docs) for name, col in database._collections.items()}
    OUT.write_text(
        json.dumps(
            {
                "today": today.isoformat(),
                "chapters": others,
                "database": dump,
                "responses": responses,
            },
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.name}: {len(responses)} responses, chapters {others}")


if __name__ == "__main__":
    main()
