"""Module repositories: org, identity, content, scheduling, assessment, learner."""

from pathlib import Path

import pytest
from cavat.core.repository import AlreadyExists, ImmutableRecord, NotFound
from cavat.db import repository_classes
from cavat.modules.assessment.repository import Evidence, EvidenceRepository
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.content.repository import LessonRepository, LessonVersion, package_hash
from cavat.modules.identity.repository import User, UserRepository
from cavat.modules.ingest.repository import ItemBank, ItemBankRepository, TeachingPlan, TeachingPlanRepository
from cavat.modules.learner.repository import StudentKCStateRepository
from cavat.modules.library.repository import DocumentRepository, TeacherDocument
from cavat.modules.org.repository import (
    ClassRepository,
    Enrollment,
    EnrollmentRepository,
    School,
    SchoolClass,
    SchoolRepository,
)
from cavat.modules.scheduling.repository import ScheduleRepository, ScheduleRule
from cavat.modules.session.repository import (
    EventRepository,
    LearningSession,
    LearningSessionRepository,
    NewEvent,
)
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[3]
LESSON = REPO / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"


@pytest.fixture(scope="module")
def package():
    return load_lesson_package(LESSON)


# --- org ----------------------------------------------------------------------------------------


async def test_schools(db):
    repo = SchoolRepository(db)
    school = await repo.create(School(id="sch-A", name="Trường Tiểu học A"))
    assert await repo.get("sch-A") == school
    assert await repo.get("missing") is None
    with pytest.raises(AlreadyExists):
        await repo.create(School(id="sch-A", name="again"))


async def test_classes(db):
    repo = ClassRepository(db, "sch-A")
    c1 = await repo.create(SchoolClass(school_id="sch-A", name="5B", grade=5, school_year="2026-2027"))
    c2 = await repo.create(SchoolClass(school_id="sch-A", name="5A", grade=5, school_year="2026-2027"))
    await repo.create(SchoolClass(school_id="sch-A", name="5C", grade=5, school_year="2025-2026"))
    assert await repo.get(c1.id) == c1
    assert [c.id for c in await repo.list_for_year("2026-2027")] == [c2.id, c1.id]
    assert await ClassRepository(db, "sch-B").get(c1.id) is None


async def test_enrollments(db):
    repo = EnrollmentRepository(db, "sch-A")
    await repo.enroll(Enrollment(school_id="sch-A", class_id="cls-1", student_id="stu-2"))
    await repo.enroll(Enrollment(school_id="sch-A", class_id="cls-1", student_id="stu-1"))
    await repo.enroll(Enrollment(school_id="sch-A", class_id="cls-2", student_id="stu-1", status="WITHDRAWN"))
    with pytest.raises(AlreadyExists):
        await repo.enroll(Enrollment(school_id="sch-A", class_id="cls-1", student_id="stu-1"))
    assert [e.student_id for e in await repo.students_of("cls-1")] == ["stu-1", "stu-2"]
    assert [e.class_id for e in await repo.classes_of("stu-1")] == ["cls-1"]
    assert [e.class_id for e in await repo.classes_of("stu-1", active_only=False)] == ["cls-1", "cls-2"]
    assert await EnrollmentRepository(db, "sch-B").students_of("cls-1") == []


# --- identity -----------------------------------------------------------------------------------


async def test_users(db):
    repo = UserRepository(db, "sch-A")
    student = await repo.create(
        User(school_id="sch-A", kind="STUDENT", login_name="an.nguyen", display_name="An", grade=5)
    )
    await repo.create(User(school_id="sch-A", kind="TEACHER", login_name="co.lan", display_name="cô Lan"))
    assert await repo.get(student.id) == student
    assert (await repo.get_by_login("an.nguyen")).id == student.id
    assert [u.login_name for u in await repo.list_by_kind("STUDENT")] == ["an.nguyen"]
    with pytest.raises(AlreadyExists):
        await repo.create(
            User(school_id="sch-A", kind="STUDENT", login_name="an.nguyen", display_name="An 2")
        )

    other = UserRepository(db, "sch-B")
    await other.create(User(school_id="sch-B", kind="STUDENT", login_name="an.nguyen", display_name="An"))
    assert await other.get(student.id) is None
    assert (await other.get_by_login("an.nguyen")).id != student.id


def test_user_requires_school_and_login():
    with pytest.raises(ValidationError):
        User(kind="STUDENT", login_name="x", display_name="X")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        User(school_id="sch-A", kind="STUDENT", login_name="", display_name="X")


# --- content ------------------------------------------------------------------------------------


async def test_lesson_round_trip(db, package):
    repo = LessonRepository(db, "sch-A")
    saved = await repo.save(package)
    loaded = await repo.get(package.lesson_id, package.version)
    assert loaded == saved
    assert loaded.to_package() == package
    assert loaded.content_hash == package_hash(package) and len(loaded.content_hash) == 64
    assert (loaded.subject, loaded.grade, loaded.status) == ("math", 5, package.status)
    assert await LessonRepository(db, "sch-B").get(package.lesson_id, package.version) is None


async def test_lesson_draft_can_change_until_published(db, package):
    repo = LessonRepository(db, "sch-A")
    first = await repo.save(package)
    edited = package.model_copy(update={"title": package.title + " (sửa)"})
    second = await repo.save(edited)
    assert second.id == first.id
    assert second.title.endswith("(sửa)")
    assert second.content_hash != first.content_hash
    assert len(await repo.list_versions(package.lesson_id)) == 1
    assert await repo.latest_published(package.lesson_id) is None

    published = await repo.publish(package.lesson_id, package.version)
    assert published.status == "PUBLISHED" and published.published_at is not None
    assert (await repo.latest_published(package.lesson_id)).id == first.id

    with pytest.raises(ImmutableRecord):
        await repo.save(package)
    with pytest.raises(ImmutableRecord):
        await repo.publish(package.lesson_id, package.version)
    with pytest.raises(NotFound):
        await repo.publish(package.lesson_id, "9.9.9")
    assert (await repo.get(package.lesson_id, package.version)).content_hash == second.content_hash


async def test_latest_published_picks_newest(db, package):
    repo = LessonRepository(db, "sch-A")
    for version in ("0.1.0", "0.2.0"):
        await repo.save(package.model_copy(update={"version": version}))
        await repo.publish(package.lesson_id, version)
    await repo.save(package.model_copy(update={"version": "0.3.0"}))  # draft, not published
    assert (await repo.latest_published(package.lesson_id)).version == "0.2.0"


def test_package_field_names_must_be_storable(package):
    numeric = next(it for it in package.items if it.answer.type == "numeric")
    broken = numeric.model_copy(
        update={"answer": numeric.answer.model_copy(update={"wrong_answers": {"0.5": "X"}})}
    )
    with pytest.raises(ValueError, match="cannot be stored"):
        LessonVersion.from_package("sch-A", package.model_copy(update={"items": [broken]}))


# --- scheduling ---------------------------------------------------------------------------------


async def test_schedules(db):
    repo = ScheduleRepository(db, "sch-A")
    rule = ScheduleRule(
        school_id="sch-A",
        class_id="cls-1",
        subject="math",
        weekdays=[1, 3],
        start_time="08:15",
        duration_min=30,
        valid_from="2026-10-05",
        lesson_id="math-g5-dec-compare",
    )
    await repo.create(rule)
    assert await repo.get(rule.id) == rule
    assert [r.id for r in await repo.list_for_class("cls-1")] == [rule.id]
    assert await ScheduleRepository(db, "sch-B").list_for_class("cls-1") == []


@pytest.mark.parametrize(
    "bad", [{"weekdays": [0]}, {"weekdays": []}, {"start_time": "25:00"}, {"valid_from": "5/10/2026"}]
)
def test_schedule_rule_validation(bad):
    fields = dict(
        school_id="sch-A",
        class_id="c",
        subject="math",
        weekdays=[1],
        start_time="08:00",
        duration_min=30,
        valid_from="2026-10-05",
    )
    with pytest.raises(ValidationError):
        ScheduleRule(**{**fields, **bad})


# --- assessment ---------------------------------------------------------------------------------


def _evidence(**kw) -> Evidence:
    fields = dict(
        school_id="sch-A",
        student_id="stu-1",
        session_id="ses-1",
        source_event_ids=["evt-1"],
        kc_id="KC-DEC-CMP",
        dimension="C",
        score=1.0,
        weight=0.85,
        support_level="SUPPORTED",
        policy_version="mastery-v1",
    )
    return Evidence(**{**fields, **kw})


async def test_evidence_is_append_only(db):
    repo = EvidenceRepository(db, "sch-A")
    first = await repo.append(_evidence())
    fix = await repo.append(_evidence(score=0.0, supersedes_id=first.id))
    await repo.append(_evidence(kc_id="KC-DEC-ORD"))
    assert [e.id for e in await repo.list_for_student("stu-1", "KC-DEC-CMP")] == [first.id, fix.id]
    assert len(await repo.list_for_student("stu-1")) == 3
    assert len(await repo.list_for_session("ses-1")) == 3
    assert await EvidenceRepository(db, "sch-B").list_for_student("stu-1") == []
    with pytest.raises(AlreadyExists):
        await repo.append(first)
    with pytest.raises(ValueError):
        await repo.append(_evidence(kc_id=None))
    public = {n for n in dir(EvidenceRepository) if not n.startswith("_")}
    assert not {n for n in public if n.startswith(("update", "delete", "remove", "replace"))}


def test_evidence_validation():
    with pytest.raises(ValidationError):
        _evidence(score=1.5)
    with pytest.raises(ValidationError):
        _evidence(source_event_ids=[])
    with pytest.raises(ValidationError):
        _evidence(dimension="Z")


# --- learner ------------------------------------------------------------------------------------


async def test_student_kc_state_upsert(db):
    repo = StudentKCStateRepository(db, "sch-A")
    first = await repo.put("stu-1", "KC-DEC-CMP", "mastery-v1", {"mastery": 0.4}, 3)
    second = await repo.put("stu-1", "KC-DEC-CMP", "mastery-v1", {"mastery": 0.6}, 5)
    assert second.id == first.id and second.created_at == first.created_at
    assert second.state == {"mastery": 0.6} and second.source_evidence_count == 5
    await repo.put(
        "stu-1", "KC-DEC-CMP", "mastery-v2", {"mastery": 0.5}, 5
    )  # other policy: separate projection
    await repo.put("stu-1", "KC-DEC-ORD", "mastery-v1", {"mastery": 0.1}, 1)
    assert (await repo.get("stu-1", "KC-DEC-CMP", "mastery-v1")).state == {"mastery": 0.6}
    assert [s.kc_id for s in await repo.list_for_student("stu-1", "mastery-v1")] == [
        "KC-DEC-CMP",
        "KC-DEC-ORD",
    ]
    assert await StudentKCStateRepository(db, "sch-B").get("stu-1", "KC-DEC-CMP", "mastery-v1") is None


# --- tenancy sweep ------------------------------------------------------------------------------


async def test_every_stored_learner_document_has_school_id(db, package):
    await SchoolRepository(db).create(School(id="sch-A", name="A"))
    await UserRepository(db, "sch-A").create(
        User(school_id="sch-A", kind="STUDENT", login_name="a", display_name="A")
    )
    await ClassRepository(db, "sch-A").create(
        SchoolClass(school_id="sch-A", name="5A", grade=5, school_year="y")
    )
    await EnrollmentRepository(db, "sch-A").enroll(
        Enrollment(school_id="sch-A", class_id="c", student_id="s")
    )
    await LessonRepository(db, "sch-A").save(package)
    await ScheduleRepository(db, "sch-A").create(
        ScheduleRule(
            school_id="sch-A",
            class_id="c",
            subject="math",
            weekdays=[2],
            start_time="09:00",
            duration_min=30,
            valid_from="2026-10-01",
        )
    )
    sessions = LearningSessionRepository(db, "sch-A")
    session = await sessions.create(
        LearningSession(school_id="sch-A", student_id="s", lesson_id="l", lesson_version="1"),
        [NewEvent(event_type="SESSION_SCHEDULED")],
    )
    await sessions.copy_events_to_ledger(session.id, EventRepository(db, "sch-A"))
    await EvidenceRepository(db, "sch-A").append(_evidence())
    await StudentKCStateRepository(db, "sch-A").put("s", "KC", "v1", {}, 0)
    await DocumentRepository(db, "sch-A").create(
        TeacherDocument(
            school_id="sch-A",
            title="SGK",
            filename="sgk.pdf",
            content_type="application/pdf",
            size=1,
            sha256="0",
            stored_path="documents/x/sgk.pdf",
            uploaded_by="t",
        )
    )

    await ItemBankRepository(db, "sch-A").save(ItemBank(school_id="sch-A", chapter_id="c", version="v"))
    await TeachingPlanRepository(db, "sch-A").save(
        TeachingPlan(school_id="sch-A", chapter_id="c", version="v")
    )

    for repo in repository_classes():
        docs = await db[repo.collection_name].find({}).to_list()
        assert docs, repo.collection_name
        if repo.tenant_scoped:
            assert all(d.get("school_id") == "sch-A" for d in docs), repo.collection_name
