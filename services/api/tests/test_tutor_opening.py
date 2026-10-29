"""Observed regressions: join bypassing the speaker and a teaching script shown to children."""

from dataclasses import replace

import pytest
from cavat.core.events import EventType
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.session import api as session_api
from cavat.modules.session.api import get_database
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import TeachingLoop
from cavat.modules.tutor import brain
from cavat.modules.tutor.reader import LiveReader
from fastapi.testclient import TestClient
from test_brain2 import small_index
from test_brain4 import OK
from test_goal_driven_teaching import ENTRY_OK, opening_output
from test_grounded import CHAPTER, NOW

SCRIPT = "Tô 30 ô trên lưới: bao nhiêu phần mười? Giới thiệu 3/10 = 0,3."
INTRO = "Hôm nay mình học phân số thập phân. Cô giải thích cách viết phần mười của một đơn vị nhé."


def scripted_chapter():
    node = CHAPTER.package.nodes[0]
    first = node.theory[0].model_copy(update={"text": SCRIPT})
    node = node.model_copy(update={"theory": [first, *node.theory[1:]]})
    return replace(
        CHAPTER, package=CHAPTER.package.model_copy(update={"nodes": [node, *CHAPTER.package.nodes[1:]]})
    )


def test_no_model_fallback_never_reads_teacher_activity_script():
    chapter = scripted_chapter()
    turn = TeachingLoop(chapter, "synthetic").start(NOW)
    opening = " ".join(m.text for m in turn.messages)
    assert "Hôm nay" in opening and chapter.package.nodes[0].name in opening
    assert "Tô 30 ô" not in opening and "Giới thiệu" not in opening
    assert chapter.package.nodes[0].method.rule in opening
    assert turn.prompt == chapter.package.nodes[0].theory[0].ask


def test_teacher_instruction_is_rejected_even_if_it_contains_correct_math():
    assert brain.teacher_voice(SCRIPT)
    assert not brain.teacher_voice("Ba phần mười viết là 0,3.")


@pytest.mark.parametrize("said", ["mấy là mấy", "chưa hiểu", "con vẫn chưa hiểu"])
def test_clarifying_a_word_or_not_understanding_does_not_repeat_the_question(said):
    chapter = scripted_chapter()
    provider = FakeChatModel(
        [
            {
                "message": (
                    "Với mẫu số 100, con đếm được hai chữ số 0. Phần thập phân sẽ có hai chữ số. "
                    "Con thử viết 7/100 thành số thập phân nào?"
                ),
                "safety_flag": False,
                "policy_feedback": "",
            },
            OK,
        ]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop = TeachingLoop(chapter, "synthetic")
    first = loop.start(NOW)
    # Use the exact word contract of the observed question without changing progression.
    loop._prompt = "Mẫu số có mấy chữ số 0 thì phần thập phân có mấy chữ số?"
    loop.go_live(reader=LiveReader(None, semantic=True), speaker=speaker)
    turn = loop.on_student(said, NOW)
    assert turn.messages[-1].text.count("?") == 1
    assert turn.messages[-1].source == "LLM"
    assert turn.awaiting == first.awaiting and loop._node == first.node_id
    assert not any(
        e.event_type in {EventType.RETELL_JUDGED, EventType.ANSWER_SUBMITTED, EventType.NODE_DECISION}
        for e in turn.events
    )
    if said == "mấy là mấy":
        assert "«mấy»" in provider.calls[0][1].messages[1].content


@pytest.mark.asyncio
async def test_api_join_calls_speaker_records_usage_and_does_not_regenerate_on_rejoin(monkeypatch):
    database = InMemoryDatabase()
    await ensure_indexes(database)
    actual_question = "Con viết phần tô màu của bốn ô trong một trăm ô thành phân số nào?"
    provider = FakeChatModel([opening_output(INTRO + " " + actual_question), ENTRY_OK])
    monkeypatch.setattr(session_api, "tutor_router", lambda: AIRouter(chat_provider=provider))
    app.dependency_overrides[get_database] = lambda: database
    try:
        with TestClient(app) as client:
            headers = {"X-Demo-Student": "synthetic-opening"}
            created = client.post("/v1/sessions", headers=headers, json={}).json()
            url = f"/v1/sessions/{created['session_id']}/join"
            joined = client.post(url, headers=headers)
            assert joined.status_code == 200, joined.text
            assert INTRO in joined.text and len(provider.calls) == 2
            again = client.post(url, headers=headers)
            assert again.status_code == 200 and len(provider.calls) == 2
            row = await database["learning_sessions"].find_one(
                {"_id": created["session_id"], "school_id": "demo-school"}
            )
            assert row["state"]["activity"]["llm_calls"] == 2
            assert row["state"]["activity"]["prompt"] == actual_question
            from cavat.modules.session.repository import LearningSession

            saved = LearningSession.model_validate(row)
            restored = TeachingLoop.resume(CHAPTER, saved.id, [], saved.events)
            assert restored._prompt == actual_question
            assert sum(e["event_type"] == "MODEL_CALLED" for e in row["events"]) == 2
    finally:
        app.dependency_overrides.pop(get_database, None)


def test_a_fraction_itself_cannot_be_called_its_denominator():
    pack = brain.BrainPack(task="Giải thích", question="Mẫu số là gì?")
    assert "WRONG_MATH" in brain.speech_codes("Mẫu số 1/1000 có ba chữ số 0.", pack)
    assert "WRONG_MATH" not in brain.speech_codes("Phân số 1/1000 có mẫu số 1000.", pack)


def test_lecture_does_not_put_the_teacher_in_the_student_role():
    from cavat.modules.teaching.grounded import lecture_request

    _, guard = lecture_request(
        "Phân số thập phân có mẫu 10, 100, 1000.", ask="Mẫu số là gì?", node_name="Phân số thập phân"
    )
    assert "WRONG_ADDRESS" in guard("Cô sẽ học cách viết phân số thập phân.")
