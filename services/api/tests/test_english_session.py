"""ENG-5b (ADR-066, DI-140–143): an English Unit 11 session runs end to end over the real session API.

Offline: templates only (no model), the in-memory database, a scripted speech-to-text for the spoken turns.
What is checked here:
- a student opens a session on the unit by its id; the backend takes the subject from the unit package
  (rule S1) and keeps it in the session document; the list of units carries the subject;
- a simulated student goes through the six-step cycle of Unit 11 by typing and speaking, passes nodes, and the
  spoken answers leave ``VOICE_TURN_RECORDED`` and ``ItemResolved.asr_confidence`` (ADR-064);
- grading is the English checker, the projection the English policy (ADR-063), the validator the English one;
- a Mathematics question in the English session is OFF_TOPIC: no attempt, no grade, no RAG passage, the
  same question asked again (DI-139, DI-141);
- Mathematics and English sessions of the same student, interleaved, do not mix events, mastery or prompts;
  the Mathematics events are those of the same Mathematics session run alone;
- live: the English session sends only English prompts (no Mathematics constitution, chooser or reader) and
  reads the English configuration (ENGLISH_WEB_LOOKUP, ENGLISH_MAX_LLM_CALLS_PER_UNIT), never the Math one.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from cavat.config import get_settings
from cavat.core.events import EventType, ItemResolved, VoiceTurnRecorded
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.base import ChatResult, Usage
from cavat.modules.ai_gateway.fake import FakeSpeechToText
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.assessment.projector import ENGLISH_POLICY, MASTERY_POLICY_VERSION, project_chapter
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service
from cavat.modules.session.api import get_database
from cavat.modules.tutor.english_validator import math_terms_in
from cavat.modules.tutor.prompt_builder import prompt_set, tutor_system_prompt
from cavat.modules.voice import api as voice_api
from fastapi.testclient import TestClient
from test_math_session_golden import normalize

UNIT = "eng-g5-u11-family-time"
AN = {"X-Demo-Student": "an"}
TEACHER = {"X-Demo-Teacher": "1"}


def unit():
    return chapter_service.chapters("english")[UNIT]


MATH = chapter_service.chapters()[chapter_service.DEFAULT_CHAPTER_ID]


@pytest.fixture(autouse=True)
def templates_only(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)


@pytest.fixture
async def memory():
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)


@pytest.fixture
def client(memory):
    return TestClient(app)


@pytest.fixture
def stt(monkeypatch, tmp_path):
    fake = FakeSpeechToText(script=[])
    monkeypatch.setattr(session_api, "_shared_router", lambda: AIRouter(stt_provider=fake))
    monkeypatch.setattr(voice_api, "_storage", lambda: tmp_path)
    return fake


async def stored(memory, session_id):
    return await session_api._repo(memory).get(session_id)


# --------------------------------------------------------------------------- a simulated student


def english_reply(state: dict) -> str:
    """What a student who learned the unit says: the approved answers of the unit's own data."""
    ch, teaching = unit(), state["teaching"]
    if teaching["awaiting"] == "THEORY_REPLY":
        node = ch.node(teaching["current_node_id"])
        variant = next((t for t in node.theory if t.ask == teaching["prompt"]), None)
        accepts = variant.accept if variant and variant.accept else [a for t in node.theory for a in t.accept]
        return accepts[0] if accepts else "Con hiểu rồi ạ."
    if teaching["awaiting"] == "RETELL":
        return ". ".join(p[0] for p in ch.node(teaching["current_node_id"]).explain.key_ideas)
    item = ch.item(state["item"]["item_id"])
    if state["item"]["expecting"] == "EXPLANATION":
        return item.explanation or "Vì con nhớ mẫu câu của bài."
    accept = getattr(item.answer, "accept", None)
    if accept:
        return accept[0]
    return getattr(item.answer, "sample", None) or item.explanation or "Con không biết ạ."


def open_unit(client, who=AN) -> dict:
    created = client.post("/v1/sessions", json={"lesson_id": UNIT}, headers=who)
    assert created.status_code == 201, created.text
    joined = client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=who)
    assert joined.status_code == 200, joined.text
    return joined.json()


def state_of(client, sid, who=AN) -> dict:
    return client.get(f"/v1/sessions/{sid}/state", headers=who).json()


def send(client, state, text, key, who=AN, *, modality="TEXT", voice_turn_id=None):
    body = {
        "item_attempt_id": state["teaching"]["input_id"],
        "kind": "ANSWER",
        "content": {"text": text},
        "modality": modality,
        "expected_state_version": state["state_version"],
        **({"voice_turn_id": voice_turn_id} if voice_turn_id else {}),
    }
    sent = client.post(
        f"/v1/sessions/{state['session_id']}/responses", json=body, headers={**who, "Idempotency-Key": key}
    )
    assert sent.status_code == 200, sent.text
    return state_of(client, state["session_id"], who)


def speak(client, stt, state, text, key, q=0.9):
    """A spoken turn: the web records, the backend hears it in the language it chose, the web sends it."""
    language = state["voice"]["language"]
    stt.script.append((text, q))
    files = {"audio": ("rec.webm", b"\x1aE\xdf\xa3 opus", "audio/webm")}
    heard = client.post(
        "/v1/voice/transcribe",
        files=files,
        data={"session_id": state["session_id"], "language": language},
        headers=AN,
    )
    assert heard.status_code == 200, heard.text
    got = heard.json()
    return send(client, state, got["text"], key, modality="VOICE", voice_turn_id=got.get("voice_turn_id"))


# --------------------------------------------------------------------------- opening a unit


def test_the_unit_list_carries_the_subject_and_mathematics_comes_first(client):
    listed = client.get("/v1/sessions/chapters", headers=AN)
    assert listed.status_code == 200
    rows = listed.json()
    assert rows[0] == {
        "chapter_id": chapter_service.DEFAULT_CHAPTER_ID,
        "title": MATH.package.title,
        "subject": "math",
    }
    assert {"chapter_id": UNIT, "title": unit().package.title, "subject": "english"} in rows
    assert {r["subject"] for r in rows} == {"math", "english"}


async def test_a_unit_session_is_english_from_its_package_and_the_client_cannot_choose(client, memory):
    refused = client.post("/v1/sessions", json={"lesson_id": UNIT, "subject": "math"}, headers=AN)
    assert refused.status_code == 422  # a subject is never part of the request (rule S1)
    refused = client.post("/v1/sessions", json={"subject": "english"}, headers=AN)
    assert refused.status_code == 422

    state = open_unit(client)
    assert state["subject"] == "english" and state["lesson"]["lesson_id"] == UNIT
    assert state["teaching"]["awaiting"] == "THEORY_REPLY" and state["teaching"]["step"] == 1
    session = await stored(memory, state["session_id"])
    assert session.state.activity["subject"] == "english"
    assert chapter_service.subject_of(session) == "english"

    math = client.post("/v1/sessions", json={}, headers=AN).json()
    assert math["subject"] == "math" and math["lesson"]["lesson_id"] == chapter_service.DEFAULT_CHAPTER_ID
    math_doc = await stored(memory, math["session_id"])
    assert "subject" not in math_doc.state.activity  # a Mathematics document is written as before (S4)
    assert chapter_service.subject_of(math_doc) == "math"

    mine = {s["session_id"]: s for s in client.get("/v1/sessions/mine", headers=AN).json()}
    assert mine[state["session_id"]]["subject"] == "english" and mine[math["session_id"]]["subject"] == "math"


def test_a_session_with_a_subject_that_is_not_one_is_an_error_not_mathematics():
    from cavat.modules.session.repository import LearningSession, SessionState

    broken = LearningSession(
        school_id="s",
        student_id="a",
        lesson_id=UNIT,
        lesson_version="x",
        state=SessionState(activity={"mode": "CHAPTER", "chapter_id": UNIT, "subject": "physics"}),
    )
    with pytest.raises(ValueError):
        chapter_service.subject_of(broken)


# --------------------------------------------------------------------------- the six steps, typed and spoken


async def test_a_student_goes_through_unit_11_typing_and_speaking(client, memory, stt):
    state = open_unit(client)
    sid = state["session_id"]
    steps, spoken = {state["teaching"]["step"]}, 0
    for n in range(400):
        if state["lifecycle_state"] == "COMPLETED":
            break
        reply = english_reply(state)
        item = state["item"]
        english_answer = state["voice"]["language"] == "en"
        if spoken < 4 and item and english_answer:
            spoken += 1
            state = speak(client, stt, state, reply, f"k{n}")
        elif spoken >= 1 and spoken < 6 and item and item["expecting"] == "EXPLANATION":
            spoken += 1
            state = speak(client, stt, state, reply, f"k{n}")  # "vì sao" heard in Vietnamese
        else:
            state = send(client, state, reply, f"k{n}")
        if state["teaching"]["step"] is not None:
            steps.add(state["teaching"]["step"])
    assert state["lifecycle_state"] == "COMPLETED"
    assert steps >= {1, 2, 3, 4, 5, 6}  # the whole six-step cycle (ADR-059)
    passed = [n for n in state["teaching"]["nodes"] if n["status"] == "PASSED"]
    assert len(passed) >= 1

    session = await stored(memory, sid)
    events = session.events
    kinds = [e.event_type for e in events]
    ch = unit()
    english_items = {i for lesson in ch.lessons.values() for i in (it.id for it in lesson.items)}
    resolved = [
        ItemResolved.model_validate(e.payload) for e in events if e.event_type == EventType.ITEM_RESOLVED
    ]
    assert resolved and {r.item_id for r in resolved} <= english_items
    # the English checker graded the phrase answers (ADR-063)
    answers = [e.payload for e in events if e.event_type == EventType.ANSWER_SUBMITTED]
    phrase = [a for a in answers if ch.item(a["item_id"]).answer.type == "phrase"]
    assert phrase and any(a["outcome"] == "CORRECT" for a in phrase)
    # the spoken turns (ADR-064): recorded once each, the item resolved by a spoken answer carries its q
    recorded = [
        VoiceTurnRecorded.model_validate(e.payload) for e in events if e.event_type == "VOICE_TURN_RECORDED"
    ]
    assert len(recorded) == spoken and {r.language for r in recorded} == {"en", "vi"}
    for at, kind in enumerate(kinds):
        if kind == EventType.VOICE_TURN_RECORDED:
            assert kinds[at - 1] == EventType.STUDENT_MESSAGE
    voiced = [r for r in resolved if r.modality == "VOICE"]
    assert voiced and all(r.asr_confidence == 0.9 for r in voiced)
    # L-3 (DI-150): the attempt of a spoken turn is a VOICE attempt, as its STUDENT_MESSAGE
    for at, e in enumerate(events):
        if e.event_type == EventType.ANSWER_SUBMITTED:
            said = next(m for m in reversed(events[:at]) if m.event_type == EventType.STUDENT_MESSAGE)
            assert e.payload["modality"] == said.payload["modality"], (e.payload, said.payload)
    assert any(a["modality"] == "VOICE" for a in answers)
    # the projection is the English policy's, every node an English one (no mastery on a Mathematics node)
    projection = project_chapter(events, ch)
    assert projection.policy_version == ENGLISH_POLICY.version != MASTERY_POLICY_VERSION
    assert set(projection.nodes) == {n.id for n in ch.package.nodes}
    # no tutor message was rejected by the English validator on the template path
    rejected = [e.payload for e in events if e.event_type == EventType.OUTPUT_REJECTED]
    assert not rejected, rejected
    # every passage the English session retrieved is an English one (ADR-061)
    math_nodes = {n.id for n in MATH.package.nodes}
    for e in events:
        if e.event_type == EventType.RAG_RETRIEVED:
            assert not any(c["chunk_id"].split(":")[0] in math_nodes for c in e.payload["chunks"])

    # the teacher's report and transcript of the English session work on the same events
    report = client.get(f"/v1/sessions/{sid}/report", headers=TEACHER)
    assert report.status_code == 200, report.text
    assert client.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER).status_code == 200


def test_say_after_me_items_are_completion_items_and_never_leak_checked(client):
    """DI-108: "con nói theo cô" is a completion item; the tutor says the model sentence (not a leak)."""
    ch = unit()
    said_after = [it for lesson in ch.lessons.values() for it in lesson.items if it.kind == "say_after_me"]
    assert said_after
    completion = {i for n in ch.package.nodes for i in n.completion}
    assert {it.id for it in said_after} <= completion


# --------------------------------------------------------------------------- a Mathematics question


async def test_a_mathematics_question_in_the_english_session_is_brought_back_to_the_lesson(client, memory):
    state = open_unit(client)
    sid, prompt = state["session_id"], state["teaching"]["prompt"]
    before = len((await stored(memory, sid)).events)
    state = send(client, state, "cô ơi 12,5 + 3,7 bằng bao nhiêu?", "m1")
    assert state["teaching"]["awaiting"] == "THEORY_REPLY" and state["teaching"]["prompt"] == prompt
    new = (await stored(memory, sid)).events[before:]
    kinds = [e.event_type for e in new]
    assert kinds[0] == EventType.STUDENT_MESSAGE and new[0].payload["item_id"].endswith(":OFF_TOPIC")
    back = [e.payload for e in new if e.event_type == EventType.TEACH_MESSAGE_SENT]
    assert len(back) == 1 and back[0]["ref"] == "OFF_SUBJECT" and prompt in back[0]["text"]
    assert not math_terms_in(back[0]["text"])  # nothing of the other subject is said
    assert not {EventType.RAG_RETRIEVED, EventType.WEB_LOOKED, EventType.ANSWER_SUBMITTED} & set(kinds)

    # at an item: no attempt, no grade, no hint; the same item still waits
    for n in range(20):
        if state["teaching"]["awaiting"] == "ANSWER" and state["item"]["expecting"] == "ANSWER":
            break
        state = send(client, state, english_reply(state), f"w{n}")
    attempt = state["teaching"]["input_id"]
    before = len((await stored(memory, sid)).events)
    state = send(client, state, "diện tích hình tam giác tính thế nào ạ?", "m2")
    assert state["teaching"]["input_id"] == attempt and state["item"]["expecting"] == "ANSWER"
    new = (await stored(memory, sid)).events[before:]
    kinds = [e.event_type for e in new]
    assert new[0].payload["item_id"].endswith(":OFF_TOPIC")
    back = [e.payload["text"] for e in new if e.event_type == EventType.TEACH_MESSAGE_SENT]
    assert back and unit().item(state["item"]["item_id"]).stem in back[-1]  # L-6: the whole question
    assert not {
        EventType.ANSWER_SUBMITTED,
        EventType.HINT_DELIVERED,
        EventType.POLICY_DECISION,
        EventType.ITEM_RESOLVED,
        EventType.MISCONCEPTION_DETECTED,
        EventType.RAG_RETRIEVED,
    } & set(kinds)
    # the right answer after it is graded as the first attempt
    state = send(client, state, english_reply(state), "after")
    first = [
        e.payload for e in (await stored(memory, sid)).events if e.event_type == EventType.ANSWER_SUBMITTED
    ]
    assert first[-1]["attempt_no"] == 1 and first[-1]["outcome"] == "CORRECT"


def test_a_mathematics_session_never_reads_off_topic_by_the_english_rule(client):
    """A Mathematics session keeps its own paths for a Mathematics question (no English gate is built)."""
    from test_chapter_session_api import MINH

    state = client.post("/v1/sessions", json={}, headers=MINH).json()
    joined = client.post(f"/v1/sessions/{state['session_id']}/join", headers=MINH).json()
    after = send(client, joined, "12,5 + 3,7 bằng bao nhiêu?", "x", who=MINH)
    assert all(t.get("ref") != "OFF_SUBJECT" for t in after["transcript"])


# --------------------------------------------------------------------------- interleaved subjects


def _math_script(state: dict) -> str:
    from test_chapter_session_api import reply_text

    return reply_text(state)


def _math_run(client, who, interleave_with: dict | None = None, turns: int = 30) -> str:
    state = client.post("/v1/sessions", json={}, headers=who).json()
    sid = state["session_id"]
    state = client.post(f"/v1/sessions/{sid}/join", headers=who).json()
    english = interleave_with
    for n in range(turns):
        if state["lifecycle_state"] == "COMPLETED":
            break
        state = send(client, state, _math_script(state), f"math{n}", who)
        if english is not None and english["lifecycle_state"] != "COMPLETED":
            english = send(client, english, english_reply(english), f"eng{n}", who)
    return sid


async def test_math_and_english_sessions_of_one_student_do_not_mix(client, memory):
    alone = _math_run(client, {"X-Demo-Student": "binh"})
    english = open_unit(client, {"X-Demo-Student": "an"})
    mixed = _math_run(client, {"X-Demo-Student": "an"}, interleave_with=english)

    def events(session):
        return [
            {"type": e.event_type, "payload": e.payload, "activity": e.activity_id}
            for e in session.events
            if e.event_type != EventType.SESSION_STARTED
        ]

    a, m = await stored(memory, alone), await stored(memory, mixed)
    # the Mathematics session interleaved with an English one is the Mathematics session run alone
    assert normalize(events(m), {}) == normalize(events(a), {})
    e = await stored(memory, english["session_id"])
    english_nodes = {n.id for n in unit().package.nodes}
    math_nodes = {n.id for n in MATH.package.nodes}
    assert {ev.activity_id for ev in e.events if ev.activity_id} <= english_nodes
    assert {ev.activity_id for ev in m.events if ev.activity_id} <= math_nodes
    # each subject's view projects with its own policy, from its own sessions only
    state = state_of(client, english["session_id"])
    assert {n["node_id"] for n in state["teaching"]["nodes"]} == english_nodes
    math_state = state_of(client, mixed)
    assert {n["node_id"] for n in math_state["teaching"]["nodes"]} == math_nodes
    assert math_state["subject"] == "math" and state["subject"] == "english"


# --------------------------------------------------------------------------- live: prompts by subject


class EnglishOnlyProvider:
    """A chat provider that answers each schema and records every request the session sends."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, Any]] = []

    def chat(self, request, model):
        self.requests.append((model, request))
        name = request.schema_name
        if name.startswith("dialogue_listen"):
            data = {"label": "PASS", "focus": "", "answer": ""}
        elif name.startswith("tutor_turn"):
            data = {
                "message": "Con nhìn lại tranh nhé: cả nhà đang làm gì ở bãi biển?",
                "safety_flag": False,
                "policy_feedback": "",
            }
        elif name.startswith("curriculum_check"):
            data = {
                "english_correct": True,
                "within_scope": True,
                "task_preserved": True,
                "addresses_student": True,
                "solution_leaked": False,
                "reason": "",
                "needs_pedagogy_support": False,
            }
        else:
            data = {}
        text = json.dumps(data, ensure_ascii=False)
        return ChatResult(model=model, text=text, data=data, usage=Usage(10, 10, 20))


def test_a_live_english_session_sends_only_english_prompts(client, monkeypatch):
    provider = EnglishOnlyProvider()
    monkeypatch.setattr(session_api, "tutor_router", lambda: AIRouter(chat_provider=provider))
    state = open_unit(client)
    for n in range(25):
        if state["lifecycle_state"] == "COMPLETED":
            break
        text = "con không biết" if n % 3 == 1 else english_reply(state)
        state = send(client, state, text, f"live{n}")
    assert provider.requests, "the live English session called no model"
    math_system = {tutor_system_prompt("math"), prompt_set("math").listener}
    names = {r.schema_name for _, r in provider.requests}
    assert names <= {"tutor_turn_en", "dialogue_listen_en_v1"}, names
    for _, request in provider.requests:
        system = request.messages[0].content
        assert system not in math_system and "Toán lớp 5" not in system
        for message in request.messages:
            assert not math_terms_in(message.content), message.content[:200]


def test_english_configuration_never_changes_mathematics(monkeypatch):
    monkeypatch.setenv("WEB_LOOKUP", "official")
    monkeypatch.setenv("ENGLISH_WEB_LOOKUP", "off")
    monkeypatch.setenv("MAX_LLM_CALLS_PER_CHAPTER", "160")
    monkeypatch.setenv("ENGLISH_MAX_LLM_CALLS_PER_UNIT", "7")
    get_settings.cache_clear()
    try:
        assert session_api._web_source("english") is None
        assert session_api._web_source("math") is not None  # WEB_LOOKUP still drives Mathematics
        monkeypatch.setenv("WEB_LOOKUP", "off")
        monkeypatch.setenv("ENGLISH_WEB_LOOKUP", "official")
        get_settings.cache_clear()
        assert session_api._web_source("math") is None
        assert session_api._web_source("english") is not None
        from cavat.modules.session.repository import LearningSession, SessionState

        def session(activity):
            return LearningSession(
                school_id="s",
                student_id="a",
                lesson_id="x",
                lesson_version="1",
                state=SessionState(activity=activity),
            )

        assert (
            session_api._chapter_cap(session({"mode": "CHAPTER", "chapter_id": UNIT, "subject": "english"}))
            == 7
        )
        assert session_api._chapter_cap(session({"mode": "CHAPTER", "chapter_id": "math-g5-decimals"})) == 160
    finally:
        get_settings.cache_clear()


def test_the_session_validator_trusts_approved_words_but_not_the_models():
    """DI-141: approved unit text passes (a name, the teacher's H4 hint); a model's words get every English
    check; a term of the other subject is refused in both."""
    from dataclasses import replace

    from cavat.core.pedagogy import ActivityType, Move
    from cavat.modules.tutor.contracts import PolicyDecision, RenderContext
    from cavat.modules.tutor.english_session import english_tools, session_validator
    from cavat.modules.tutor.item_loop import ItemTutor
    from cavat.modules.tutor.renderer import TemplateRenderer

    ch = unit()
    validate = session_validator(english_tools(ch).lexicon)
    item, lesson = ch.item("U11-VO-PR-01"), ch.lesson_of("U11-VO-PR-01")
    tutor = ItemTutor(item, lesson, ActivityType.GUIDED_PRACTICE, TemplateRenderer(), validate)
    ctx = RenderContext(decision=PolicyDecision(Move.PRESENT), item=item, package=lesson, state=tutor.state)
    approved = TemplateRenderer().render(ctx).text
    assert validate(approved, ctx).ok  # "Co To Island" is the book's, not out of the unit
    model = replace(ctx, free_numbers=True)
    assert "OUT_OF_UNIT_ENGLISH" in validate("Con nói thử nhé: We visited the museum yesterday?", model).codes
    assert "MATH_TERM" in validate("Con tính diện tích hình tam giác nhé?", ctx).codes
    assert "MATH_TERM" in validate("Con tính diện tích hình tam giác nhé?", model).codes


# --------------------------------------------------------------------------- ENG-5c: the deployed router


class QuotaProvider:
    """A provider whose every model is out of quota (the free tier at a busy minute)."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, request, model):
        from cavat.modules.ai_gateway.base import QuotaExceeded

        self.calls += 1
        raise QuotaExceeded("429", model=model)


def deployed_router(provider) -> AIRouter:
    """The router of a deployment (``build_router``): model-only speech for Mathematics, a real chain."""
    from cavat.modules.ai_gateway.base import ModelClass

    chain = ("model-a", "model-b")
    chains = {c: chain for c in (ModelClass.TUTOR_REASONING, ModelClass.INTENT_AGENT, ModelClass.LIGHTWEIGHT)}
    return AIRouter(chat_provider=provider, chains=chains, model_only_speech=True)


@pytest.mark.parametrize("provider_class", [EnglishOnlyProvider, QuotaProvider])
async def test_an_english_session_runs_with_the_deployed_router(client, memory, monkeypatch, provider_class):
    """L-0 (DI-148): with the deployed router (``model_only_speech=True``) an English session was held on
    "Con chờ cô một chút nhé…" from its first theory line, with no model call. It must go on: the model's
    words when a model answers, the unit's approved words when every model is busy (DI-140)."""
    from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE

    provider = provider_class()
    router = deployed_router(provider)
    monkeypatch.setattr(session_api, "tutor_router", lambda: router)
    state = open_unit(client)
    sid = state["session_id"]
    assert state["teaching"]["prompt"], "the opening waits on no question"
    steps = {state["teaching"]["step"]}
    for n in range(60):
        if state["lifecycle_state"] == "COMPLETED":
            break
        state = send(client, state, english_reply(state), f"dep{n}")
        steps.add(state["teaching"]["step"])
    events = (await stored(memory, sid)).events
    said = [e.payload for e in events if e.event_type == EventType.TEACH_MESSAGE_SENT]
    assert not [p for p in said if p.get("text") == MODEL_WAIT_MESSAGE or p.get("ref") == "MODEL_WAIT"]
    assert {1, 2} <= steps, steps  # past the opening theory line, into the items
    assert any(e.event_type == EventType.ANSWER_SUBMITTED for e in events)
    assert provider_class is QuotaProvider or provider.requests  # the model is used when it answers
    if provider_class is EnglishOnlyProvider:
        tutor = [e.payload for e in events if e.event_type == EventType.TUTOR_MESSAGE_SENT]
        assert any(p.get("source") == "LLM" for p in tutor)


def test_the_deployed_router_still_holds_a_mathematics_session_on_model_wait(client, monkeypatch):
    """The Mathematics rule is unchanged: with every model out of quota, the deployed router holds a
    Mathematics chapter session on MODEL_WAIT rather than speaking an unchecked template."""
    from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE
    from test_chapter_session_api import MINH

    monkeypatch.setattr(session_api, "tutor_router", lambda: deployed_router(QuotaProvider()))
    created = client.post(
        "/v1/sessions", json={"lesson_id": chapter_service.DEFAULT_CHAPTER_ID}, headers=MINH
    )
    assert created.status_code == 201, created.text
    joined = client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=MINH).json()
    assert joined["transcript"][-1]["text"] == MODEL_WAIT_MESSAGE


async def test_an_answer_in_vietnamese_is_asked_again_in_english_then_graded_l1(client, memory):
    """L-2 (DI-107/129/149): Vietnamese to an English phrase item is not "không đọc được". The first time
    is not graded and the tutor asks for English (R-L1); the next is graded WRONG with the class L1; an
    English answer after it is graded as usual."""
    state = open_unit(client)
    sid = state["session_id"]
    for n in range(80):
        item = state["item"]
        if (
            item
            and item["expecting"] == "ANSWER"
            and state["voice"]["language"] == "en"
            and unit().item(item["item_id"]).answer.type == "phrase"
            and unit().item(item["item_id"]).kind != "say_after_me"
        ):
            break
        state = send(client, state, english_reply(state), f"v{n}")
    else:
        pytest.fail("no English phrase item reached")
    item_id, reply = state["item"]["item_id"], english_reply(state)

    before = len((await stored(memory, sid)).events)
    state = send(client, state, "Nhà con đi ăn hải sản ạ.", "vi1")
    first = (await stored(memory, sid)).events[before:]
    decisions = [e.payload for e in first if e.event_type == EventType.POLICY_DECISION]
    assert decisions and decisions[-1]["rule_ids"] == ["R-L1"], decisions
    assert "UNREADABLE" not in decisions[-1]["reason_codes"]
    assert not [e for e in first if e.event_type == EventType.ANSWER_SUBMITTED]
    said = [e.payload["text"] for e in first if e.event_type == EventType.TUTOR_MESSAGE_SENT]
    assert said and "tiếng Anh" in said[-1]
    assert state["item"]["item_id"] == item_id

    before = len((await stored(memory, sid)).events)
    state = send(client, state, "Nhà con đi ăn hải sản ạ.", "vi2")
    second = (await stored(memory, sid)).events[before:]
    graded = [e.payload for e in second if e.event_type == EventType.ANSWER_SUBMITTED]
    assert len(graded) == 1 and graded[0]["outcome"] == "WRONG" and graded[0]["error_class"] == "L1"
    decision = next(e.payload for e in second if e.event_type == EventType.POLICY_DECISION)
    assert decision["move"] != "PROBE" and "R-L1" in decision["rule_ids"]

    if state["item"] and state["item"]["item_id"] == item_id and state["item"]["expecting"] == "ANSWER":
        before = len((await stored(memory, sid)).events)
        send(client, state, reply, "en1")
        after = (await stored(memory, sid)).events[before:]
        graded = [e.payload for e in after if e.event_type == EventType.ANSWER_SUBMITTED]
        assert graded and graded[0]["outcome"] == "CORRECT"


def _last_tutor_sentence(state: dict) -> str:
    import re

    tutor = [t["text"] for t in state["transcript"] if t["actor"] == "tutor" and t.get("text")]
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", tutor[-1]) if p.strip()]
    return parts[-1] if parts else tutor[-1]


async def test_a_student_who_only_repeats_the_tutor_ends_the_unit_without_passing(client, memory):
    """L-4 (DI-151): a child who only repeats the tutor's last sentence used to turn on to the turn cap.
    Each period now stops with its reason (STOP_NODE, N-ECHO) and the session ends; no node is passed."""
    state = open_unit(client)
    sid = state["session_id"]
    for n in range(200):
        if state["lifecycle_state"] == "COMPLETED":
            break
        state = send(client, state, _last_tutor_sentence(state), f"echo{n}")
    assert state["lifecycle_state"] == "COMPLETED", n
    assert not [x for x in state["teaching"]["nodes"] if x["status"] == "PASSED"]
    events = (await stored(memory, sid)).events
    echo_stops = [
        e.payload
        for e in events
        if e.event_type == EventType.NODE_DECISION and e.payload["rule_ids"] == ["N-ECHO"]
    ]
    assert echo_stops and all(p["action"] == "STOP_NODE" for p in echo_stops)
    # the session replays to the same state from its events (the rule reads only stored events)
    replayed = chapter_service.TeachingLoop.resume(
        unit(), sid, [], (await stored(memory, sid)).events, **chapter_service._loop_options(unit())
    )
    assert replayed.awaiting.value == "NOTHING"


def test_the_echo_rule_is_english_only():
    from cavat.modules.tutor.english_session import ECHO_STOP_EN, loop_options

    assert "echo_stop" not in chapter_service._loop_options(MATH)
    assert loop_options(unit())["echo_stop"] == ECHO_STOP_EN
