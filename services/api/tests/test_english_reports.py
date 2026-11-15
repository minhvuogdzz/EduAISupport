"""ENG-7b (ADR-067): the report views of an English unit and the teacher's replay of a spoken turn.

Every field added for English is checked against its source in the event log (ADR-060 §9, DI-113, DI-114,
DI-144-DI-146); the Mathematics responses are the golden of ``test_math_reports_golden.py``. The sessions are
the real teaching loop on Unit 11 with synthetic spoken turns (``english_report_data``: ENG-5b not merged).
"""

import json
import time
from datetime import timedelta
from types import SimpleNamespace

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.identity.accounts import Identity, issue_token
from cavat.modules.reports import english as report
from cavat.modules.session import progress
from cavat.modules.session.api import get_database, local_today
from cavat.modules.session.chapter_service import STEP_OF
from cavat.modules.voice import api as voice_api
from english_report_data import AUDIO, T0, TODAY, UNIT, UNIT_ID, Learner, converse, store, voiced
from fastapi.testclient import TestClient

TEACHER = {"X-Demo-Teacher": "1"}
PARENT = {"X-Demo-Parent": "1"}
MAI, TUAN = {"X-Demo-Student": "mai"}, {"X-Demo-Student": "tuan"}
# Tuấn picks "đi thuyền quanh đảo" for "walked on the beach" once: ENG5-U11-M06 (lesson-1-did-you).
TUAN_WRONG = {"U11-VO-PR-01": "B"}
MAI_Q = [0.93, 0.88, 0.71, 0.97, None, 0.9]  # clear, clear, so-so, clear, no q, clear
TUAN_Q = [0.31, 0.45, 0.82, 0.52, 0.9, 0.2, 0.67]  # 4 of 7 below 0,6


@pytest.fixture
async def memory(tmp_path, monkeypatch):
    database = InMemoryDatabase()
    await ensure_indexes(database)
    monkeypatch.setattr(voice_api, "_storage", lambda: tmp_path)
    mai = voiced(converse(Learner(), T0, 40), "mai", MAI_Q, tmp_path)
    tuan = voiced(converse(Learner(dict(TUAN_WRONG)), T0 + timedelta(hours=2), 60), "tuan", TUAN_Q, tmp_path)
    await store(database, "mai", "Mai", mai)
    await store(database, "tuan", "Tuấn", tuan)
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[local_today] = lambda: TODAY
    yield database, tmp_path
    app.dependency_overrides.pop(get_database, None)
    app.dependency_overrides.pop(local_today, None)


@pytest.fixture
def client(memory):
    return TestClient(app)


def unit(path: str) -> str:
    return f"{path}{'&' if '?' in path else '?'}chapter={UNIT_ID}"


async def folded(database, student):
    from cavat.modules.session.repository import LearningSessionRepository
    from cavat.modules.session.service import DEMO_SCHOOL_ID

    sessions = await LearningSessionRepository(database, DEMO_SCHOOL_ID).list_for_student(student)
    return progress.fold(UNIT, sessions)


# --- the teacher's student view (ADR-060 §9.1) --------------------------------------------------------


async def test_the_teacher_sees_every_spoken_turn_verbatim_with_q_language_and_recording(client, memory):
    database, _ = memory
    view = client.get(unit("/v1/teachers/students/tuan"), headers=TEACHER).json()
    assert view["chapter"] == {"chapter_id": UNIT_ID, "title": "Unit 11: Family time", "subject": "english"}
    f = await folded(database, "tuan")
    recorded = [e for e in f.events if e.event_type == "VOICE_TURN_RECORDED"]
    turns = view["voice_turns"]
    assert len(turns) == len(recorded) == len(TUAN_Q)
    assert [t["asr_confidence"] for t in turns] == list(reversed(TUAN_Q))  # newest first
    for turn, event in zip(turns, reversed(recorded), strict=True):
        p = event.payload
        assert turn["turn_id"] == p["voice_turn_id"] and turn["audio_ref"] == p["audio_ref"]
        assert turn["transcript"] == p["heard"]  # what the listener wrote, never corrected
        assert turn["language"] == p["language"] and turn["session_id"] == event.session_id
        assert turn["item_id"] == p["message_ref"] and turn["prompt"] == UNIT.item(p["message_ref"]).stem
        assert turn["node_id"] in UNIT.item(p["message_ref"]).kc_ids
        assert turn["teacher_override"] is False
    # the graded outcome of the turn: the wrong choice is WRONG, the others CORRECT
    wrong = [t for t in turns if t["item_id"] in TUAN_WRONG and t["transcript"] == "B"]
    assert wrong and all(t["outcome"] == "WRONG" for t in wrong)
    assert {t["outcome"] for t in turns if t not in wrong} == {"CORRECT"}
    assert {t["language"] for t in turns} <= {"en", "vi"}


def test_activity_counts_the_spoken_turns_and_the_four_outcome_groups(client):
    view = client.get(unit("/v1/teachers/students/tuan"), headers=TEACHER).json()
    days = view["activity"]
    assert sum(d["voice_turns"] for d in days) == len(TUAN_Q)
    assert sum(d["asr_low"] for d in days) == sum(1 for q in TUAN_Q if q is not None and q < 0.6) == 4
    # DI-114 item 1: the four groups stay apart, from ITEM_RESOLVED.resolution (shared with Mathematics)
    assert all({"independent", "supported", "worked", "unresolved"} <= set(d) for d in days)


async def test_the_journey_says_how_each_item_was_answered(client, memory):
    database, _ = memory
    view = client.get(unit("/v1/teachers/students/mai"), headers=TEACHER).json()
    f = await folded(database, "mai")
    resolved = [e.payload for e in f.events if e.event_type == "ITEM_RESOLVED"]
    assert [j["modality"] for j in view["journey"]] == [p["modality"] for p in resolved]
    assert "VOICE" in {j["modality"] for j in view["journey"]} and "TEXT" in {
        j["modality"] for j in view["journey"]
    }


def test_asr_low_needs_the_teacher_only_for_the_child_heard_unclearly(client):
    tuan = client.get(unit("/v1/teachers/students/tuan"), headers=TEACHER).json()
    mai = client.get(unit("/v1/teachers/students/mai"), headers=TEACHER).json()
    [low] = [a for a in tuan["attention"] if a["kind"] == "ASR_LOW"]
    assert low["voice_turns"] == 7 and low["share"] == round(4 / 7, 2) and low["count"] == 4
    assert not any(a["kind"] == "ASR_LOW" for a in mai["attention"])
    # the misconception of the wrong answer is in the node detail, named in English (ADR-060 §9.1)
    seen = [m for n in tuan["nodes"] for m in n["misconceptions"]]
    assert seen and all(m["id"].startswith("ENG5-U11-M") and m["name"] != m["id"] for m in seen)


def test_asr_low_follows_di_114_at_its_boundaries():
    def low(qs, days_ago=0):
        events = voiced(converse(Learner(), T0 - timedelta(days=days_ago), 40), "x", qs)
        return report.asr_low(SimpleNamespace(events=events), TODAY)  # only the events are read

    assert low([0.1, 0.2, 0.3, 0.4]) is None  # four turns: not enough
    assert low([0.1, 0.2, 0.9, 0.9, 0.9]) == {"kind": "ASR_LOW", "voice_turns": 5, "share": 0.4, "count": 2}
    assert low([0.1, 0.9, 0.9, 0.9, 0.9]) is None  # 20 %
    assert low([None, None, None, None, 0.1]) is None  # a turn without q is not "low"
    assert low([0.6, 0.6, 0.6, 0.1, 0.1])["count"] == 2  # 0,6 itself is heard: only q < 0,6 is low
    assert low([0.1] * 6, days_ago=7) is None  # older than the last seven days
    assert low([0.1] * 6, days_ago=6)["voice_turns"] == 6


# --- the class (ADR-060 §9.2) -------------------------------------------------------------------------


async def test_the_class_shows_the_voice_share_and_asr_low(client, memory):
    database, _ = memory
    view = client.get(unit("/v1/teachers/class"), headers=TEACHER).json()
    assert view["chapter"]["subject"] == "english"
    assert [s["display_name"] for s in view["students"]] == ["Mai", "Tuấn"]
    mai, tuan = view["students"]
    assert any(a["kind"] == "ASR_LOW" for a in tuan["attention"])
    assert not any(a["kind"] == "ASR_LOW" for a in mai["attention"])
    total = voiced_n = 0
    for who in ("mai", "tuan"):
        f = await folded(database, who)
        said = [e for e in f.events if e.event_type == "STUDENT_MESSAGE"]
        total += len(said)
        voiced_n += sum(1 for e in said if e.payload["modality"] == "VOICE")
    assert voiced_n == len(MAI_Q) + len(TUAN_Q)
    assert view["kpis"]["voice_share"] == round(100 * voiced_n / total, 1)
    assert view["kpis"]["attention"] == sum(1 for s in view["students"] if s["attention"])
    assert {m["id"] for m in view["misconceptions"]} <= {
        m.id for lesson in UNIT.lessons.values() for m in lesson.misconceptions
    }


def test_the_teacher_lists_the_english_units_apart(client):
    english = client.get("/v1/teachers/taught-chapters?subject=english", headers=TEACHER).json()
    assert english == [{"chapter_id": UNIT_ID, "title": "Unit 11: Family time", "subject": "english"}]
    math = client.get("/v1/teachers/taught-chapters", headers=TEACHER).json()
    assert UNIT_ID not in {c["chapter_id"] for c in math} and all("subject" not in c for c in math)
    assert client.get("/v1/teachers/taught-chapters?subject=physics", headers=TEACHER).status_code == 422


# --- the student and the parent (ADR-060 §8, §9.3, DI-113) ----------------------------------------------


async def test_the_student_sees_the_patterns_the_units_and_the_step(client, memory):
    database, _ = memory
    view = client.get(unit("/v1/students/me/overview"), headers=MAI).json()
    assert view["chapter"]["subject"] == "english"
    assert view["chapters"] == [
        {"chapter_id": UNIT_ID, "title": "Unit 11: Family time", "subject": "english"}
    ]
    assert {n["node_id"]: n["pattern"] for n in view["nodes"]} == {n.id: n.pattern for n in UNIT.nodes}
    assert all(t["pattern"] for t in view["going_well"] + view["to_practise"])
    f = await folded(database, "mai")
    last = [e for e in f.unfinished[-1].events if e.event_type == "NODE_DECISION"][-1]
    assert view["current_step"] == STEP_OF[last.payload["action"]] and 1 <= view["current_step"] <= 6
    # DI-113: the same qualitative states as Mathematics, no score
    assert all("mastery" not in n for n in view["nodes"])
    assert {n["quality"] for n in view["nodes"]} <= {
        "NOT_STARTED",
        "INSUFFICIENT_DATA",
        "FAMILIAR",
        "WITH_SUPPORT",
        "INDEPENDENT",
        "SOLID",
    }


def test_the_parent_gets_words_and_a_sentence_to_say_at_home_never_turns_or_scores(client):
    code = progress.parent_code("tuan")
    view = client.get(unit(f"/v1/parents/children/{code}"), headers=PARENT).json()
    assert view["chapter"]["subject"] == "english" and view["home_tips"]
    for tip in view["home_tips"]:
        assert tip["example"] and f"'{tip['example']}'" in tip["tip"]
    text = json.dumps(view, ensure_ascii=False)
    for secret in ("voice_turns", "transcript", "audio_ref", "asr_confidence", '"mastery"', "share"):
        assert secret not in text  # rule F4, PART 27.4


def test_every_home_tip_of_the_unit_gives_its_english_sentence():
    examples = {n.id: report.home_example(n.home_tip) for n in UNIT.nodes}
    assert examples == {
        "ENG5-U11-VOCAB": "We took photos.",
        "ENG5-U11-PAST": "I walked to school.",  # 'hôm nay con làm gì?' is Vietnamese: skipped
        "ENG5-U11-DIDYOU": "Did you take photos?",
        "ENG5-U11-WHATDID": "What did our family do there?",
        "ENG5-U11-STRESS": "When did you go to London?",
        "ENG5-U11-TRIP": "We swam in the sea.",
    }
    assert report.home_example("Cùng con đọc 'xin chào' nhé.") is None
    assert report.home_example("") is None


# --- the recording, for the teacher only (rules F4, F5, V3) -------------------------------------------


def a_turn(client) -> dict:
    return client.get(unit("/v1/teachers/students/tuan"), headers=TEACHER).json()["voice_turns"][0]


def test_the_teacher_hears_a_turn_again(client):
    turn = a_turn(client)
    got = client.get(f"/v1/teachers/voice/{turn['audio_ref']}", headers=TEACHER)
    assert got.status_code == 200 and got.content == AUDIO
    assert got.headers["content-type"] == "audio/webm"
    assert got.headers["cache-control"] == "private, no-store"


def test_a_student_or_a_parent_never_gets_a_recording(client):
    ref = a_turn(client)["audio_ref"]
    assert client.get(f"/v1/teachers/voice/{ref}", headers={"X-Demo-Student": "tuan"}).status_code == 401
    assert client.get(f"/v1/teachers/voice/{ref}", headers=PARENT).status_code == 401
    assert client.get(f"/v1/teachers/voice/{ref}").status_code == 401


def test_the_recording_endpoint_refuses_tokens_of_other_roles(memory, accounts_mode):
    client = TestClient(app)
    ref = "in/2026-11-12/0123456789abcdef/" + "a" * 32 + ".webm"
    key = b"test-signing-key"
    for kind in ("STUDENT", "PARENT"):
        token = issue_token(Identity("tuan", kind, "Tuấn"), key, now=time.time())
        got = client.get(f"/v1/teachers/voice/{ref}", headers={"Authorization": f"Bearer {token}"})
        assert got.status_code == 403, (kind, got.text)
    token = issue_token(Identity("t1", "TEACHER", "Cô"), key, now=time.time())
    got = client.get(f"/v1/teachers/voice/{ref}", headers={"Authorization": f"Bearer {token}"})
    assert got.status_code == 404  # a teacher, but no turn of the school has it


@pytest.mark.parametrize(
    "ref",
    [
        "../../../../etc/passwd",
        "in/../../secret.webm",
        "in/2026-11-12/0123456789abcdef/../../../x.webm",
        "/etc/passwd",
        "tts/abc.wav",
        "in/2026-11-12/0123456789abcdef/" + "a" * 32 + ".json",  # the turn record beside it
        "in/2026-11-12/0123456789ABCDEF/" + "a" * 32 + ".webm",
    ],
)
def test_no_path_outside_the_recordings_is_served(client, ref):
    got = client.get(f"/v1/teachers/voice/{ref}", headers=TEACHER)
    assert got.status_code == 404
    assert b"root:" not in got.content


def test_a_file_no_turn_of_the_school_names_is_never_served(client, memory):
    _, folder = memory
    stray = "in/2026-11-12/0123456789abcdef/" + "b" * 32 + ".webm"
    (folder / stray).parent.mkdir(parents=True, exist_ok=True)
    (folder / stray).write_bytes(b"someone else")
    assert client.get(f"/v1/teachers/voice/{stray}", headers=TEACHER).status_code == 404


async def test_a_turn_of_another_school_is_never_served(client, memory):
    database, folder = memory
    other = voiced(converse(Learner(), T0, 20), "khoa", [0.9], folder)
    session = await store(database, "khoa", "Khoa", other, school="another-school")
    [ref] = [e.payload["audio_ref"] for e in session.events if e.event_type == "VOICE_TURN_RECORDED"]
    assert (folder / ref).is_file()
    assert client.get(f"/v1/teachers/voice/{ref}", headers=TEACHER).status_code == 404


def test_a_link_out_of_the_recordings_is_never_followed(client, memory, tmp_path_factory):
    _, folder = memory
    outside = tmp_path_factory.mktemp("outside") / "secret.webm"
    outside.write_bytes(b"secret")
    turn = a_turn(client)
    target = folder / turn["audio_ref"]
    target.unlink()
    target.symlink_to(outside)
    assert client.get(f"/v1/teachers/voice/{turn['audio_ref']}", headers=TEACHER).status_code == 404


# --- Mathematics is not touched ---------------------------------------------------------------------------


def test_a_math_view_has_none_of_the_english_fields(client):
    from test_teacher_view_api import lan_makes_the_placeholder_mistake

    lan_makes_the_placeholder_mistake(client)
    view = client.get("/v1/teachers/students/lan", headers=TEACHER).json()
    text = json.dumps(view)
    for added in ("voice_turns", "asr_low", "modality", '"subject"', "voice_share"):
        assert added not in text
    overview = client.get("/v1/students/me/overview", headers={"X-Demo-Student": "lan"}).json()
    assert all("pattern" not in n for n in overview["nodes"]) and "current_step" not in overview
    assert UNIT_ID not in {c["chapter_id"] for c in overview["chapters"]}
