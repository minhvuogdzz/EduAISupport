"""Live mathematical speech must be model-authored; rejected turns hold all learner state."""

from types import SimpleNamespace

import pytest
from cavat.config import Settings
from cavat.core.events import EventType
from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter, RecordingRouter, build_router
from cavat.modules.session.api import _hold_for_unavailable_models
from cavat.modules.session.repository import LifecycleState, NewEvent, SessionState
from cavat.modules.session.service import Step
from cavat.modules.teaching.grounded import GroundedSpeaker, Spoken
from test_chapter_session_api import MINH, client, memory, send, start, templates_only  # noqa: F401


def recording():
    return RecordingRouter(AIRouter(chat_provider=FakeChatModel([]), model_only_speech=True))


def test_live_factory_always_requires_model_speech():
    assert build_router(
        Settings(_env_file=None, groq_api_key="", gemini_api_key="", tts="off")
    ).model_only_speech


@pytest.mark.parametrize("source", ["TEMPLATE", "EXTRACT", "WEB"])
def test_mixed_turn_cannot_hide_a_static_explanation_behind_a_successful_llm(source):
    before = SessionState(
        lifecycle=LifecycleState.ACTIVE,
        activity={"node_id": "n", "prompt": "old", "llm_calls": 4},
        item={"item_attempt_id": "old"},
    )
    session = SimpleNamespace(state=before, state_version=2, student_id="s", events=[])
    after = before.model_copy(deep=True)
    after.activity["prompt"] = "new"
    after.item = None
    step = Step(
        after,
        [
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT, payload={"text": "Một lời LLM", "source": "LLM"}
            ),
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT,
                payload={"text": "3/10 bằng 0,3", "source": source, "rejected": [["QUESTION_COUNT"]]},
            ),
            NewEvent(event_type=EventType.ITEM_RESOLVED, payload={}),
        ],
        {"ended_at": "should not commit"},
    )
    held = _hold_for_unavailable_models(session, step, recording(), "ok", "VOICE")
    assert held.state == before and held.fields == {}
    assert [e.event_type for e in held.events] == [EventType.STUDENT_MESSAGE, EventType.TEACH_MESSAGE_SENT]
    assert held.events[0].payload["modality"] == "VOICE"
    assert held.events[-1].payload["text"] == MODEL_WAIT_MESSAGE
    assert ["QUESTION_COUNT"] in held.events[-1].payload["rejected"]


def test_greeting_and_valid_model_speech_can_commit():
    before = SessionState(lifecycle=LifecycleState.ACTIVE, activity={"node_id": "n"})
    session = SimpleNamespace(state=before, state_version=0, student_id="s", events=[])
    step = Step(
        before,
        [
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT,
                payload={"source": "TEMPLATE", "ref": "GREETING_ONLY", "text": "Cô chào con!"},
            ),
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT,
                payload={"source": "LLM", "text": "Con thử suy nghĩ nhé?"},
            ),
        ],
        {},
    )
    assert _hold_for_unavailable_models(session, step, recording()) is step


def test_new_question_is_announced_in_the_conversation_after_theory_feedback():
    before = SessionState(lifecycle=LifecycleState.ACTIVE, activity={"node_id": "n"})
    session = SimpleNamespace(state=before, state_version=0, student_id="s", events=[])
    step = Step(
        before,
        [
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT,
                payload={"source": "LLM", "text": "Con trả lời đúng, 5/10 = 0,5."},
            ),
            NewEvent(
                event_type=EventType.TUTOR_MESSAGE_SENT,
                payload={"source": "TEMPLATE", "move": "PRESENT", "text": "Viết 7/10 thành số thập phân."},
            ),
        ],
        {},
    )
    assert _hold_for_unavailable_models(session, step, recording()) is step
    assert len(step.events) == 2 and "7/10" in step.events[-1].payload["text"]


def test_rejected_live_dialogue_never_repeats_the_old_math_question(client, monkeypatch):  # noqa: F811
    from cavat.modules.session import api

    state = start(client)  # Existing fixture is a deterministic offline policy scaffold.
    live = AIRouter(chat_provider=FakeChatModel([{"label": "CONTINUE"}] * 100), model_only_speech=True)
    monkeypatch.setattr(api, "tutor_router", lambda: live)
    monkeypatch.setattr(
        GroundedSpeaker,
        "conversation_reply",
        lambda *a, **kw: Spoken(
            "Ừ, mình thử nhé. Viết 5/10 thành số thập phân?", "TEMPLATE", rejected=(("QUESTION_COUNT",),)
        ),
    )
    result = send(client, state, "ok", "no-template-dialogue")
    assert result.status_code == 200, result.text
    after = client.get(f"/v1/sessions/{state['session_id']}/state", headers=MINH).json()
    new = after["transcript"][len(state["transcript"]) :]
    assert [t["text"] for t in new if t["actor"] == "tutor"] == [MODEL_WAIT_MESSAGE]
    assert after["progress"] == state["progress"]
    for field in ("prompt", "step", "current_node_id", "awaiting", "input_id", "nodes"):
        assert after["teaching"][field] == state["teaching"][field]


def test_live_bridge_never_appends_a_static_mathematical_explanation():
    speaker = object.__new__(GroundedSpeaker)
    speaker.router = recording()
    speaker.t, speaker.s, speaker.name = "cô", "con", "An"
    speaker._lesson_say = lambda pack, **kwargs: Spoken("Lời do model viết và kiểm.", "LLM")
    result = speaker.bridge(
        "ok", asked="Câu cũ?", explanation="CÂU TOÁN TĨNH", judged="chưa rõ", lead="mẫu", teaching=False
    )
    assert result.source == "LLM" and result.text == "Lời do model viết và kiểm."
    assert "CÂU TOÁN TĨNH" not in result.text


def test_transition_and_worked_example_are_authored_from_approved_facts():
    from test_teaching_loop import CHAPTER

    speaker = object.__new__(GroundedSpeaker)
    speaker.t, speaker.s, speaker.name = "cô", "con", "An"
    packs = []

    def draft(pack, **kwargs):
        packs.append(pack)
        return Spoken("Lời model mới.", "LLM")

    speaker._lesson_say = draft
    node = next(n for n in CHAPTER.package.nodes if n.worked_examples)
    speaker.learning_transition("EXAMPLE", node, example=node.worked_examples[0])
    assert packs[0].lesson == node.name
    assert node.worked_examples[0].problem in packs[0].grounds
    assert "Không hỏi bài mới" in packs[0].task


def test_wait_keeps_model_cost_without_applying_the_failed_math_step():
    from cavat.modules.ai_gateway.base import ModelClass
    from test_ai_gateway import _request

    router = AIRouter(chat_provider=FakeChatModel([{"utterance": "rejected"}]), model_only_speech=True)
    recorder = RecordingRouter(router)
    recorder.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    state = SessionState(lifecycle=LifecycleState.ACTIVE, activity={"node_id": "n", "llm_calls": 3})
    session = SimpleNamespace(state=state, state_version=2, student_id="s", events=[])
    step = Step(
        state.model_copy(deep=True),
        [
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT,
                payload={"source": "TEMPLATE", "text": "Phần mười là…"},
            )
        ],
        {},
    )
    held = _hold_for_unavailable_models(session, step, recorder, "ok")
    assert held.state.activity["llm_calls"] == 4
    assert state.activity["llm_calls"] == 3
    assert held.events[-1].payload["text"] == MODEL_WAIT_MESSAGE
