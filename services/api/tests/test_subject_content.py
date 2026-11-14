"""ENG-3b (ADR-062): content loaded by subject, the English schema, and Unit 11 "Family time".

A Mathematics session, view or list never gets an English unit, and the other way round; a package without
a subject is refused; the English answer types and the provenance of every English item are checked by the
package validator; the teacher's review page lists Unit 11 when English is picked. Offline, in memory.
"""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest
import yaml
from cavat.config import REPO_ROOT
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.content.chapter_package import load_chapter, validate_chapter
from cavat.modules.content.lesson_package import (
    LessonPackage,
    PhraseAnswer,
    load_lesson_package,
    validate_package,
)
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, service
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from pydantic import ValidationError

MATH = "math-g5-decimals"
FAMILY = "eng-g5-u11-family-time"
UNIT = REPO_ROOT / "docs/pedagogy/english-g5/unit-11-family-time"
MATH_LESSONS = {"math-g5-dec-concept", "math-g5-dec-compare"}
ENGLISH_LESSONS = {"eng-g5-u11-l1", "eng-g5-u11-l2", "eng-g5-u11-l3"}
TEACHER = {"X-Demo-Teacher": "1"}
STUDENT = {"X-Demo-Student": "minh"}
# Fields ENG-3b added; a Mathematics package sets none of them.
NEW_ITEM_FIELDS = (
    "source",
    "answer_source",
    "origin",
    "answer_status",
    "review",
    "response_language",
    "kind",
)


# ---------------------------------------------------------------- the loader keeps the subjects apart


def test_every_caller_that_names_no_subject_gets_mathematics_only():
    """DI-124: Mathematics by default; the chapters and lessons it had before English, and nothing else."""
    assert set(chapter_service.chapter_sources()) == {MATH}
    assert set(chapter_service.chapters()) == {MATH}
    assert set(service.lesson_packages()) == MATH_LESSONS
    assert all(c.package.subject == "math" for c in chapter_service.chapters().values())
    assert chapter_service.chapter_for(FAMILY, None) is None
    assert chapter_service.chapter_for(FAMILY, "0.1.0") is None


def test_english_gets_its_unit_and_never_a_mathematics_chapter():
    assert set(chapter_service.chapter_sources("english")) == {FAMILY}
    assert set(chapter_service.chapters("english")) == {FAMILY}
    assert set(service.lesson_packages("english")) == ENGLISH_LESSONS
    assert chapter_service.chapter_for(MATH, None, "english") is None
    unit = chapter_service.chapter_for(FAMILY, None, "english")
    assert unit is not None and unit.package.subject == "english"
    assert {lesson.subject for lesson in unit.lessons.values()} == {"english"}


def test_the_rag_sees_both_subjects_and_builds_each_index_from_its_own():
    assert set(chapter_service.all_chapters()) == {MATH, FAMILY}
    rag = session_api._rag_service
    assert set(rag.chapters("math")) == {MATH} and set(rag.chapters("english")) == {FAMILY}


def test_an_unknown_subject_is_an_error_not_mathematics():
    with pytest.raises(ValueError):
        chapter_service.chapters("history")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        service.lesson_packages("")  # type: ignore[arg-type]


def test_a_published_plan_stays_in_its_subject(monkeypatch):
    monkeypatch.setattr(chapter_service, "_published", {})
    monkeypatch.setattr(chapter_service, "_current", {})
    first = chapter_service.chapters()[MATH]
    package = first.package.model_dump(mode="json") | {"chapter_id": "eng-copy", "subject": "english"}
    lessons = {k: v.model_dump(mode="json") | {"subject": "english"} for k, v in first.lessons.items()}
    chapter_service.register_published("eng-copy", "0.1.0", package, lessons, current=True)
    assert "eng-copy" not in chapter_service.chapters()
    assert "eng-copy" in chapter_service.chapters("english")
    assert chapter_service.chapter_for("eng-copy", "0.1.0") is None
    assert chapter_service.chapter_for("eng-copy", "0.1.0", "english") is not None


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _tree(root: Path, *, english_id: str = "eng-x") -> None:
    """A docs/pedagogy with one Mathematics chapter and one English unit (copies of the real files)."""
    math = yaml.safe_load((REPO_ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml").read_text())
    for rel in math["lessons"]:
        src = REPO_ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan" / rel
        _write(
            root / "docs/pedagogy/m/lessons" / src.parent.name / "lesson.yaml",
            yaml.safe_load(src.read_text()),
        )
    math["lessons"] = [f"../lessons/{Path(rel).parent.name}/lesson.yaml" for rel in math["lessons"]]
    _write(root / "docs/pedagogy/m/chapter/chapter.yaml", math)
    unit = yaml.safe_load((UNIT / "chapter.yaml").read_text()) | {"chapter_id": english_id}
    for rel in unit["lessons"]:
        _write(root / "docs/pedagogy/e" / rel, yaml.safe_load((UNIT / rel).read_text()))
    _write(root / "docs/pedagogy/e/chapter.yaml", unit)


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    monkeypatch.setattr(chapter_service, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(service, "REPO_ROOT", tmp_path)
    chapter_service.all_chapter_sources.cache_clear()
    service.all_lesson_packages.cache_clear()
    yield tmp_path
    chapter_service.all_chapter_sources.cache_clear()
    service.all_lesson_packages.cache_clear()


def test_discovery_filters_by_the_subject_written_in_the_file(fake_root):
    _tree(fake_root)
    assert set(chapter_service.chapter_sources()) == {MATH}
    assert set(chapter_service.chapter_sources("english")) == {"eng-x"}
    assert set(service.lesson_packages()) == MATH_LESSONS
    assert set(service.lesson_packages("english")) == ENGLISH_LESSONS


def test_two_chapters_with_one_id_are_an_error_not_one_hiding_the_other(fake_root):
    _tree(fake_root, english_id=MATH)
    with pytest.raises(ValueError, match="math-g5-decimals"):
        chapter_service.all_chapter_sources()


def test_a_new_package_without_a_subject_is_refused(tmp_path):
    unit = yaml.safe_load((UNIT / "chapter.yaml").read_text())
    unit.pop("subject")
    for rel in unit["lessons"]:
        _write(tmp_path / rel, yaml.safe_load((UNIT / rel).read_text()))
    _write(tmp_path / "chapter.yaml", unit)
    with pytest.raises(ValidationError, match="subject"):
        load_chapter(tmp_path / "chapter.yaml")
    lesson = yaml.safe_load((UNIT / "lesson-1-did-you/lesson.yaml").read_text())
    lesson.pop("subject")
    with pytest.raises(ValidationError, match="subject"):
        LessonPackage.model_validate(lesson)


def test_a_chapter_never_mixes_subjects(tmp_path):
    unit = yaml.safe_load((UNIT / "chapter.yaml").read_text())
    for rel in unit["lessons"]:
        lesson = yaml.safe_load((UNIT / rel).read_text())
        _write(tmp_path / rel, lesson | {"subject": "math"} if rel.startswith("lesson-2") else lesson)
    _write(tmp_path / "chapter.yaml", unit)
    with pytest.raises(ValueError, match="eng-g5-u11-l2 is math"):
        load_chapter(tmp_path / "chapter.yaml")


def test_the_mathematics_packages_set_none_of_the_new_fields():
    """The Mathematics content is read exactly as before: no item sets a field of ENG-3b and no answer is of
    an English type (the dump without unset fields is the dump of before, see the PR)."""
    chapter = chapter_service.chapters()[MATH]
    lessons = [*chapter.lessons.values(), *service.lesson_packages().values()]
    for lesson in lessons:
        assert validate_package(lesson) == []
        for item in lesson.items:
            assert all(getattr(item, name) is None for name in NEW_ITEM_FIELDS), item.id
            assert item.answer.type not in ("phrase", "word_order")
        assert all(m.error_class is None for m in lesson.misconceptions)
    assert validate_chapter(chapter) == []


# ---------------------------------------------------------------- API: Mathematics never serves Unit 11


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)


def test_a_session_or_a_view_cannot_open_the_english_unit_through_mathematics(client):
    """Until the English session (ENG-5) the unit is not reachable from a student or parent route at all."""
    created = client.post("/v1/sessions", json={"lesson_id": FAMILY}, headers=STUDENT)
    assert created.status_code == 404
    for lesson_id in ENGLISH_LESSONS:
        assert client.post("/v1/sessions", json={"lesson_id": lesson_id}, headers=STUDENT).status_code == 404
    assert client.get(f"/v1/students/me/overview?chapter={FAMILY}", headers=STUDENT).status_code == 404
    taught = client.get("/v1/teachers/taught-chapters", headers=TEACHER).json()
    assert [c["chapter_id"] for c in taught] == [MATH]
    overview = client.get("/v1/students/me/overview", headers=STUDENT).json()
    assert [c["chapter_id"] for c in overview["chapters"]] == [MATH]


def test_the_teacher_review_page_lists_unit_11_when_english_is_picked(client):
    default = client.get("/v1/teachers/chapters", headers=TEACHER).json()
    assert [(c["chapter_id"], c["subject"]) for c in default] == [(MATH, "math")]
    english = client.get("/v1/teachers/chapters?subject=english", headers=TEACHER).json()
    assert [(c["chapter_id"], c["subject"], c["nodes"]) for c in english] == [(FAMILY, "english", 6)]
    assert english[0]["items"] == 47
    assert client.get("/v1/teachers/chapters?subject=history", headers=TEACHER).status_code == 422

    content = client.get(f"/v1/teachers/chapters/{FAMILY}", headers=TEACHER).json()
    assert content["subject"] == "english"
    assert content["source"].endswith("unit-11-family-time/chapter.yaml")
    items = {i["item_id"]: i for n in content["nodes"] for i in n["items"]}
    said = items["U11-VO-PR-02"]
    assert (said["answer_type"], said["answer"]) == ("phrase", "We ate seafood.")
    assert said["source"] == {"doc": "SGK", "page": "8", "ref": "L2 Ex2b, tả tranh bằng lời"}
    assert said["answer_source"]["page"] == "184" and said["answer_status"] == "VERIFIED_SGV"
    assert items["U11-VO-CP-01"]["kind"] == "say_after_me"
    assert items["U11-VO-CC-01"]["review"] == {
        "status": "APPROVED",
        "reviewed_by": "chủ dự án",
        "reviewed_on": "2026-11-13",
    }
    assert {m["id"]: m["error_class"] for m in content["misconceptions"]}["ENG5-U11-M03"] == "EN_SHORT_ANSWER"

    math = client.get(f"/v1/teachers/chapters/{MATH}", headers=TEACHER).json()
    math_item = next(i for n in math["nodes"] for i in n["items"] if i["item_id"] == "TP-PR-01")
    assert not set(math_item) & {*NEW_ITEM_FIELDS}
    assert all("error_class" not in m for m in math["misconceptions"])


# ---------------------------------------------------------------- the English schema and its validator


def _lesson(**changes) -> LessonPackage:
    data = yaml.safe_load((UNIT / "lesson-1-did-you/lesson.yaml").read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    for item_id, patch in changes.items():
        item = next(it for it in data["items"] if it["id"] == item_id.replace("_", "-"))
        for key, value in patch.items():
            if value is None:
                item.pop(key, None)
            else:
                item[key] = value
    return LessonPackage.model_validate(data)


def _problems(**changes) -> list[str]:
    return validate_package(_lesson(**changes))


def test_a_phrase_answer_needs_something_to_compare_with():
    empty = {"type": "phrase"}
    assert "U11-VO-PR-02: a phrase answer needs at least one accept or required group" in _problems(
        U11_VO_PR_02={"answer": empty}
    )
    blank = {"type": "phrase", "required": [["ate seafood"], []]}
    assert any("empty required group" in p for p in _problems(U11_VO_PR_02={"answer": blank}))
    unknown = {"type": "phrase", "accept": ["We ate seafood."], "wrong_answers": {"we eat seafood": "NOPE"}}
    assert "U11-VO-PR-02: unknown misconception NOPE" in _problems(U11_VO_PR_02={"answer": unknown})
    with pytest.raises(ValidationError):
        _lesson(U11_VO_PR_02={"answer": {"type": "phrase", "accept": ["x"], "normalize": "en/2"}})


def test_a_word_order_answer_uses_exactly_its_tokens():
    good = {"type": "word_order", "tokens": ["we", "ate", "seafood"], "accept": [["we", "ate", "seafood"]]}
    assert not any("word_order" in p or "order must" in p for p in _problems(U11_VO_PR_02={"answer": good}))
    bad = good | {"accept": [["we", "eat", "seafood"]]}
    assert "U11-VO-PR-02: every accepted order must use exactly the given tokens" in _problems(
        U11_VO_PR_02={"answer": bad}
    )
    assert any(
        "at least one accepted order" in p for p in _problems(U11_VO_PR_02={"answer": good | {"accept": []}})
    )


def test_an_authored_item_is_taught_only_once_the_owner_approved_it():
    assert "U11-VO-CC-01: an authored item is taught only after the owner approved it" in _problems(
        U11_VO_CC_01={"review": None}
    )
    assert any("approved it" in p for p in _problems(U11_VO_CC_01={"review": {"status": "PENDING"}}))
    assert "U11-VO-CC-01: an approval names who approved it and when" in _problems(
        U11_VO_CC_01={"review": {"status": "APPROVED"}}
    )


def test_every_answer_traces_back_to_its_page():
    assert "U11-PA-PR-01: a VERIFIED_SGV answer needs its answer_source page" in _problems(
        U11_PA_PR_01={"answer_source": None}
    )
    assert "U11-PA-PR-01: a book item needs its source page" in _problems(U11_PA_PR_01={"source": None})
    assert any("cannot be taught" in p for p in _problems(U11_PA_PR_01={"answer_status": "NO_ANSWER"}))
    assert any(
        "answer_status AUTHORED needs origin AUTHORED" in p
        for p in _problems(U11_PA_PR_01={"answer_status": "AUTHORED"})
    )


def test_an_english_item_says_where_it_comes_from_and_in_which_language_it_is_answered():
    problems = _problems(U11_VO_PR_02={"response_language": None, "origin": None})
    assert "U11-VO-PR-02: an English item needs response_language" in problems
    assert "U11-VO-PR-02: an English item needs origin" in problems
    assert any("answered in English" in p for p in _problems(U11_VO_CP_01={"response_language": "vi"}))


def test_an_english_misconception_has_an_error_class():
    data = yaml.safe_load((UNIT / "lesson-1-did-you/lesson.yaml").read_text(encoding="utf-8"))
    data["misconceptions"][0].pop("error_class")
    assert "ENG5-U11-M01: an English misconception needs an error_class" in validate_package(
        LessonPackage.model_validate(data)
    )
    data["misconceptions"][0]["error_class"] = "CONCEPTUAL"  # the general class is not a DI-107 code
    with pytest.raises(ValidationError):
        LessonPackage.model_validate(data)


def test_repeating_after_the_tutor_is_never_a_success_of_the_node(tmp_path):
    """DI-108: a say_after_me item sits in the node's completion, never in its checks or practice."""
    unit = yaml.safe_load((UNIT / "chapter.yaml").read_text())
    for rel in unit["lessons"]:
        _write(tmp_path / rel, yaml.safe_load((UNIT / rel).read_text()))
    vocab = unit["nodes"][0]
    vocab["practice"].append(vocab["completion"].pop())
    _write(tmp_path / "chapter.yaml", unit)
    problems = validate_chapter(load_chapter(tmp_path / "chapter.yaml"))
    assert "ENG5-U11-VOCAB: say_after_me item U11-VO-CP-01 belongs in completion, not practice" in problems


# ---------------------------------------------------------------- Unit 11 "Family time"


def test_unit_11_loads_and_is_clean():
    unit = chapter_service.chapters("english")[FAMILY]
    for lesson in unit.lessons.values():
        assert validate_package(lesson) == [], lesson.lesson_id
    assert validate_chapter(unit) == []
    assert unit.topological_order() == [
        "ENG5-U11-VOCAB",
        "ENG5-U11-PAST",
        "ENG5-U11-DIDYOU",
        "ENG5-U11-WHATDID",
        "ENG5-U11-STRESS",
        "ENG5-U11-TRIP",
    ]
    items = [it for lesson in unit.lessons.values() for it in lesson.items]
    assert len(items) == 47
    used = {i for n in unit.nodes for i in (*n.checks, *n.completion, *n.practice, *n.transfer)}
    assert used == {it.id for it in items}
    assert sum(isinstance(it.answer, PhraseAnswer) for it in items) == 23
    # Level C items answered in Vietnamese stay open (README §3); every other open answer became a phrase.
    assert all(it.response_language == "vi" for it in items if it.answer.type == "open")


def test_the_20_authored_items_carry_the_owners_approval_of_13_november():
    items = [
        it for lesson in chapter_service.chapters("english")[FAMILY].lessons.values() for it in lesson.items
    ]
    authored = [it for it in items if it.answer_status == "AUTHORED"]
    assert len(authored) == 20
    assert {(it.origin, it.review.status, it.review.reviewed_on) for it in authored} == {
        ("AUTHORED", "APPROVED", date(2026, 11, 13))
    }
    statuses = sorted(it.answer_status for it in items)
    assert statuses.count("VERIFIED_SGV") == 24 and statuses.count("FROM_TEXT") == 3


def test_sources_yaml_agrees_with_the_lesson_files():
    sources = yaml.safe_load((UNIT / "sources.yaml").read_text(encoding="utf-8"))
    lessons = [
        load_lesson_package(UNIT / rel)
        for rel in yaml.safe_load((UNIT / "chapter.yaml").read_text())["lessons"]
    ]
    items = {it.id: it for lesson in lessons for it in lesson.items}
    listed = {row["id"]: row for row in sources["items"]}
    assert set(listed) == set(items)
    for item_id, row in listed.items():
        item = items[item_id]
        assert row["status"] == item.answer_status, item_id
        assert ("AUTHORED" if str(row["origin"]).startswith("AUTHORED") else "BOOK") == item.origin, item_id
    for exercise in sources["exercises"]:
        assert set(exercise["used_in"]) <= set(items), exercise["ref"]
