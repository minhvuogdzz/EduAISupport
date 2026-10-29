"""Recovery uses saved input without another student turn, with bounded retries and replay safety."""

import pytest
from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.session import api
from cavat.modules.teaching.grounded import GroundedSpeaker, Spoken
from cavat.modules.teaching.loop import TeachingLoop
from test_chapter_session_api import MINH, client, memory, send, start, templates_only  # noqa: F401
from test_goal_driven_teaching import ENTRY_OK, opening_output
from test_grounded import CHAPTER


def state(http, session_id):
    return http.get(f"/v1/sessions/{session_id}/state", headers=MINH).json()


def recover(http, before, key="auto-retry"):
    return http.post(
        f"/v1/sessions/{before['session_id']}/recover",
        headers={**MINH, "Idempotency-Key": key},
        json={"expected_state_version": before["state_version"]},
    )


def test_failed_opening_recovers_without_student_input_and_retains_orientation(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(api, "tutor_router", lambda: AIRouter(chat_provider=None, model_only_speech=True))
    before = start(client)
    assert before["transcript"][0]["text"].startswith("Cô chào Minh!")
    assert CHAPTER.nodes[0].name in before["transcript"][0]["text"]
    assert before["tutor_recovery"]["status"] == "retrying"
    assert not before["teaching"]["prompt"]
    question = "Con viết 7/10 thành số thập phân nào?"
    provider = FakeChatModel([opening_output("Ba phần mười viết là 0,3. " + question), ENTRY_OK])
    live = AIRouter(chat_provider=provider, model_only_speech=True)
    monkeypatch.setattr(api, "tutor_router", lambda: live)
    response = recover(client, before)
    assert response.status_code == 200, response.text
    after = state(client, before["session_id"])
    assert after["tutor_recovery"] is None
    assert after["teaching"]["prompt"] == question
    assert after["progress"] == before["progress"]
    assert not any(t["actor"] == "student" for t in after["transcript"])
    assert len(provider.calls) == 2
    duplicate = recover(client, before)
    assert duplicate.json() == response.json()
    assert state(client, before["session_id"])["state_version"] == after["state_version"]
    assert len(provider.calls) == 2


def test_failed_student_turn_reuses_exact_words_and_does_not_display_a_duplicate(client, monkeypatch):  # noqa: F811
    before = start(client)
    live = AIRouter(chat_provider=FakeChatModel([{"label": "REPAIR"}] * 40), model_only_speech=True)
    monkeypatch.setattr(api, "tutor_router", lambda: live)
    heard = []

    def reply(self, text, **kwargs):
        heard.append(text)
        assert not any(MODEL_WAIT_MESSAGE in said for _, said in kwargs.get("recent", []))
        if len(heard) == 1:
            return Spoken("", "TEMPLATE", rejected=(("QUESTION_COUNT",),))
        return Spoken("Mình xem một phần mười trước nhé. Con viết 2/10 thành số thập phân nào?", "LLM")

    monkeypatch.setattr(GroundedSpeaker, "conversation_reply", reply)
    response = send(client, before, "con chưa hiểu", "first-input")
    assert response.status_code == 200, response.text
    held = state(client, before["session_id"])
    assert held["tutor_recovery"]["reason"] == "validation"
    assert recover(client, held).status_code == 200
    after = state(client, before["session_id"])
    assert heard == ["con chưa hiểu", "con chưa hiểu"]
    assert after["tutor_recovery"] is None
    assert [t["text"] for t in after["transcript"] if t["actor"] == "student"] == ["con chưa hiểu"]
    assert after["progress"] == before["progress"]
    assert after["teaching"]["prompt"].endswith("2/10 thành số thập phân nào?")


def test_retries_stop_with_a_clear_message_and_rejoining_can_restart_them(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(api, "tutor_router", lambda: AIRouter(chat_provider=None, model_only_speech=True))
    held = start(client)
    original = held["teaching"]
    for attempt in range(1, 4):
        response = recover(client, held, f"retry-{attempt}")
        assert response.status_code == 200, response.text
        held = state(client, held["session_id"])
        assert held["tutor_recovery"]["attempts"] == attempt
        assert held["teaching"] == original
    assert held["tutor_recovery"]["status"] == "stopped"
    assert held["transcript"][-1]["text"] == api.RECOVERY_STOP_MESSAGE
    assert recover(client, held, "after-stop").json()["state_version"] == held["state_version"]
    joined = client.post(f"/v1/sessions/{held['session_id']}/join", headers=MINH).json()
    assert joined["tutor_recovery"]["status"] == "retrying"
    assert joined["tutor_recovery"]["attempts"] == 0
    assert "quay trở lại" in joined["transcript"][-1]["text"]
    assert joined["teaching"] == original


def test_recovery_refuses_stale_versions_and_other_students(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(api, "tutor_router", lambda: AIRouter(chat_provider=None, model_only_speech=True))
    before = start(client)
    assert recover(client, before, "first").status_code == 200
    assert recover(client, before, "stale").status_code == 409
    response = client.post(
        f"/v1/sessions/{before['session_id']}/recover",
        headers={"X-Demo-Student": "someone-else", "Idempotency-Key": "other"},
        json={"expected_state_version": before["state_version"]},
    )
    assert response.status_code == 403


def test_courtesy_is_not_mistaken_for_a_failed_model_explanation(client, monkeypatch):  # noqa: F811
    before = start(client)
    live = AIRouter(chat_provider=FakeChatModel([]), model_only_speech=True)
    monkeypatch.setattr(api, "tutor_router", lambda: live)
    response = send(client, before, "con chào cô", "courtesy")
    assert response.status_code == 200, response.text
    after = state(client, before["session_id"])
    assert after["tutor_recovery"] is None
    assert after["transcript"][-1]["text"].endswith("Mình tiếp tục câu cô đang hỏi nhé?")
    for field in ("prompt", "step", "current_node_id", "awaiting", "nodes"):
        assert after["teaching"][field] == before["teaching"][field]
    assert after["progress"] == before["progress"]


@pytest.mark.asyncio
async def test_recovered_opening_survives_event_replay(client, memory, monkeypatch):  # noqa: F811
    from cavat.modules.session.repository import LearningSession

    monkeypatch.setattr(api, "tutor_router", lambda: AIRouter(chat_provider=None, model_only_speech=True))
    before = start(client)
    question = "Con viết 7/10 thành số thập phân nào?"
    provider = FakeChatModel([opening_output("Hai phần mười viết là 0,2. " + question), ENTRY_OK])
    monkeypatch.setattr(api, "tutor_router", lambda: AIRouter(chat_provider=provider, model_only_speech=True))
    assert recover(client, before).status_code == 200
    row = await memory["learning_sessions"].find_one(
        {"_id": before["session_id"], "school_id": "demo-school"}
    )
    saved = LearningSession.model_validate(row)
    loop = TeachingLoop.resume(CHAPTER, saved.id, [], saved.events)
    assert loop._prompt == question
    assert saved.state.activity["llm_calls"] == 2
    assert "tutor_recovery" not in saved.state.activity
    assert MODEL_WAIT_MESSAGE in [t["text"] for t in state(client, saved.id)["transcript"]]


@pytest.mark.asyncio
async def test_old_waiting_session_recovers_the_stored_student_words_on_entry(client, memory, monkeypatch):  # noqa: F811
    from cavat.core.events import EventType
    from cavat.modules.session.repository import NewEvent

    before = start(client)
    monkeypatch.setattr(api, "tutor_router", lambda: AIRouter(chat_provider=None, model_only_speech=True))
    assert send(client, before, "con chưa hiểu mẫu số", "old-input").status_code == 200
    repo = api._repo(memory)
    saved = await repo.get(before["session_id"])
    legacy = saved.state.model_copy(deep=True)
    legacy.activity.pop("tutor_recovery")
    await repo.commit(
        saved,
        state=legacy,
        events=[
            NewEvent(
                event_type=EventType.TEACH_MESSAGE_SENT,
                payload={
                    "kind": "FEEDBACK",
                    "ref": "MODEL_WAIT",
                    "text": "Con chờ cô một chút nhé.",
                    "source": "TEMPLATE",
                },
                actor=api.chapter_service.actor_for(EventType.TEACH_MESSAGE_SENT, saved.student_id),
            )
        ],
    )
    joined = client.post(f"/v1/sessions/{saved.id}/join", headers=MINH).json()
    assert joined["tutor_recovery"]["status"] == "retrying"
    recovered = await repo.get(saved.id)
    assert recovered.state.activity["tutor_recovery"]["kwargs"]["text"] == "con chưa hiểu mẫu số"
    # The API exposes status only; replayable input and command details remain server-side.
    assert "kwargs" not in joined["tutor_recovery"]
