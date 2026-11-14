"""ENG-6 (ADR-064): voice for the English module, offline with fakes.

- q of DI-109 from Whisper segments (DI-132), and the Groq adapter returning it with the language.
- The language Whisper hears, chosen by the backend from the subject and the input the session waits for;
  a Mathematics session always hears "vi" and answers as before.
- VOICE_TURN_RECORDED, and ``asr_confidence`` on ITEM_RESOLVED when the deciding answer was spoken.
- The tutor's voice in English: never a bare English word (V2b), "ate" and the verb table to the browser's
  English voice (DI-133).
"""

import math
from dataclasses import replace

import httpx
import pytest
from cavat.core.events import PAYLOAD_MODELS, EventType, ItemResolved, StudentMessage, VoiceTurnRecorded
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.base import Speech, Transcription
from cavat.modules.ai_gateway.fake import FakeSpeechToText
from cavat.modules.ai_gateway.groq import GroqClient, asr_confidence
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.session import api as session_api
from cavat.modules.session.api import get_database
from cavat.modules.voice import api as voice_api
from cavat.modules.voice.english_speech import LEAD_IN, SpeechPart, bare_english, risky, speech_plan
from cavat.modules.voice.listening import choose_language, profile_for
from cavat.modules.voice.turns import load_turn
from fastapi.testclient import TestClient
from test_chapter_session_api import reply_text, send
from test_teaching_loop import CHAPTER, correct_text

MINH = {"X-Demo-Student": "minh"}
AN = {"X-Demo-Student": "an"}


# --- q (DI-109) -----------------------------------------------------------------------------------------


def seg(logprob, no_speech=0.1, start=0.0, end=1.0, text=" x"):
    return {"avg_logprob": logprob, "no_speech_prob": no_speech, "start": start, "end": end, "text": text}


def test_q_is_exp_of_the_mean_logprob_weighted_by_segment_length():
    segments = [seg(-0.1, start=0.0, end=3.0), seg(-0.7, start=3.0, end=4.0)]
    expected = math.exp((3 * -0.1 + 1 * -0.7) / 4)
    assert asr_confidence(segments) == round(expected, 4) == 0.7788


def test_q_is_zero_when_every_segment_is_silence():
    assert asr_confidence([seg(-0.2, no_speech=0.9), seg(-0.1, no_speech=0.61)]) == 0.0
    # one segment with speech is enough to read q from the log-probabilities
    assert asr_confidence([seg(-0.2, no_speech=0.9), seg(-0.2, no_speech=0.6)]) == round(math.exp(-0.2), 4)


def test_q_without_times_weighs_segments_the_same_and_stays_in_0_1():
    no_times = [{"avg_logprob": -0.2, "no_speech_prob": 0.0}, {"avg_logprob": -0.4, "no_speech_prob": 0.0}]
    assert asr_confidence(no_times) == round(math.exp(-0.3), 4)
    assert asr_confidence([seg(0.3)]) == 1.0  # a positive log-probability never makes q above 1


def test_q_is_none_without_segment_metadata():
    assert asr_confidence(None) is None
    assert asr_confidence([]) is None
    assert asr_confidence([{"text": "hi"}]) is None
    assert asr_confidence([{"avg_logprob": float("nan"), "text": "hi"}]) is None


def test_q_is_deterministic():
    segments = [seg(-0.123456, start=0, end=1.7), seg(-0.98765, start=1.7, end=2.2)]
    assert len({asr_confidence(segments) for _ in range(20)}) == 1


def test_the_groq_adapter_sends_the_language_and_returns_q():
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = request.content
        return httpx.Response(
            200,
            json={
                "text": " We ate seafood.",
                "segments": [seg(-0.05, start=0, end=1.2, text=" We ate seafood.")],
            },
        )

    client = GroqClient("k", transport=httpx.MockTransport(handler))
    heard = client.transcribe(b"opus", language="en")
    assert heard == Transcription(
        model="whisper-large-v3", text="We ate seafood.", language="en", confidence=round(math.exp(-0.05), 4)
    )
    assert b'name="language"\r\n\r\nen' in sent["body"]


def test_the_router_never_lets_whisper_guess_the_language():
    stt = FakeSpeechToText(script=["x", "y"])
    gateway = AIRouter(stt_provider=stt)
    for bad in ("", "auto", "ms", None):
        with pytest.raises(ValueError):
            gateway.transcribe(b"a", language=bad)
    gateway.transcribe(b"a", language="en")
    gateway.transcribe(b"a")  # Mathematics' default stays "vi"
    assert [language for _, language in stt.calls] == ["en", "vi"]


# --- the language by subject and step (DI-132) ----------------------------------------------------------


@pytest.mark.parametrize("response_language", ["en", "vi", "either", None])
@pytest.mark.parametrize("awaiting", ["ANSWER", "THEORY_REPLY", "RETELL", None])
def test_mathematics_always_hears_vietnamese(awaiting, response_language):
    got = choose_language("math", awaiting=awaiting, expecting="ANSWER", response_language=response_language)
    assert (got.language, got.allowed) == ("vi", ("vi",))


@pytest.mark.parametrize(
    ("awaiting", "expecting", "response_language", "language", "reason"),
    [
        ("ANSWER", "ANSWER", "en", "en", "ITEM_EN"),  # repeat after the tutor, English Q&A
        ("ANSWER", "ANSWER", "vi", "vi", "ITEM_VI"),  # a meaning question
        ("ANSWER", "ANSWER", "either", "vi", "ITEM_EITHER"),  # a mixed answer: "en" would translate
        ("ANSWER", "ANSWER", None, "vi", "ITEM_UNSPECIFIED"),
        ("ANSWER", "EXPLANATION", "en", "vi", "EXPLANATION"),  # "vì sao" is said in Vietnamese (DI-111)
        ("THEORY_REPLY", None, None, "vi", "NOT_ITEM"),
        ("RETELL", None, None, "vi", "NOT_ITEM"),
    ],
)
def test_english_hears_english_only_for_an_english_answer(
    awaiting, expecting, response_language, language, reason
):
    got = choose_language(
        "english", awaiting=awaiting, expecting=expecting, response_language=response_language
    )
    assert (got.language, got.allowed, got.reason) == (language, (language,), reason)
    assert got.admits(language) and got.admits(None)
    assert not got.admits("en" if language == "vi" else "vi") and not got.admits("auto")


def test_a_missing_subject_is_an_error_not_mathematics():
    for subject in ("", None, "physics"):
        with pytest.raises(ValueError):
            choose_language(subject, awaiting="ANSWER")
        with pytest.raises(ValueError):
            profile_for(subject)


def test_the_profiles_keep_mathematics_as_it_was():
    math_profile, english = profile_for("math"), profile_for("english", english_min_confidence=0.6)
    assert not math_profile.record_turns and math_profile.ask_again_below is None
    assert math_profile.speech == "tutor"
    assert english.record_turns and english.ask_again_below == 0.6 and english.speech == "mixed"


# --- the tutor's voice in English (V2b, DI-133) ---------------------------------------------------------


def test_a_bare_english_word_never_goes_alone_to_the_tutors_voice():
    assert speech_plan("Mother.") == [SpeechPart(f"{LEAD_IN} Mother.", "tutor")]
    assert speech_plan("Giỏi lắm! Grandmother.") == [SpeechPart(f"Giỏi lắm! {LEAD_IN} Grandmother.", "tutor")]
    assert speech_plan("Con nói theo cô: mother.") == [SpeechPart("Con nói theo cô: mother.", "tutor")]
    assert bare_english("Mother.") and bare_english("big family")
    assert not bare_english("Con nói theo cô: mother.") and not bare_english("This is my mother.")


def test_whole_english_sentences_go_to_the_tutors_voice_as_written():
    text = "Where did you go last summer? I went to Ha Long Bay."
    assert speech_plan(text) == [SpeechPart(text, "tutor")]
    assert speech_plan("There are 4 people in my family.") == [
        SpeechPart("There are four people in my family.", "tutor")
    ]


def test_ate_and_the_verb_table_are_read_by_the_browsers_english_voice():
    assert speech_plan("Con nói theo cô nhé: We ate seafood.") == [
        SpeechPart("Con nói theo cô nhé:", "tutor"),
        SpeechPart("We ate seafood.", "browser_en"),
    ]
    assert speech_plan("Con nhớ nhé: go, went. Eat, ate.") == [
        SpeechPart("Con nhớ nhé:", "tutor"),
        SpeechPart("go, went. Eat, ate.", "browser_en"),
    ]
    assert speech_plan("Từ ate là quá khứ của eat.") == [
        SpeechPart("Từ", "tutor"),
        SpeechPart("ate", "browser_en"),
        SpeechPart("là quá khứ của eat.", "tutor"),
    ]
    assert risky("buy - bought") and risky("We ATE fish.") and not risky("I went to the beach.")
    assert not risky("Con giỏi lắm, Late") and not risky("We took photos.")


def test_with_the_flag_vieneu_reads_everything_but_never_a_bare_word():
    plan = speech_plan("Con nhớ nhé: go, went. Eat, ate.", risky_voice="vieneu")
    assert plan == [SpeechPart(f"Con nhớ nhé: go, went. {LEAD_IN} Eat, ate.", "tutor")]


def test_no_tutor_part_of_an_english_plan_is_a_bare_english_word():
    lines = [
        "Mother.",
        "Đúng rồi! Father. Sister.",
        "Con nói theo cô nhé: We ate seafood.",
        "Brother. Con đọc lại nhé: She is my sister.",
        "Yes. No.",
    ]
    for line in lines:
        for part in speech_plan(line):
            for sentence in part.text.split(". "):
                assert part.voice == "browser_en" or not bare_english(sentence), (line, part)


# --- the API --------------------------------------------------------------------------------------------


class FakeTTS:
    name = "fake-tts"

    def __init__(self):
        self.said = []

    def speak(self, text):
        self.said.append(text)
        return Speech(model=self.name, audio=b"RIFF....WAVE")


@pytest.fixture(autouse=True)
def templates_only(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)


@pytest.fixture
async def client():
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)


@pytest.fixture
def voice(monkeypatch, tmp_path):
    stt, tts = FakeSpeechToText(script=[]), FakeTTS()
    monkeypatch.setattr(session_api, "_shared_router", lambda: AIRouter(stt_provider=stt, tts_provider=tts))
    monkeypatch.setattr(voice_api, "_storage", lambda: tmp_path)
    return stt, tts, tmp_path


def english_chapter():
    """The chapter of the tests as if it were an English unit whose items are answered in English. The
    English unit loader is ENG-3b; this only changes what the session's voice reads (subject, language)."""
    items = {
        item_id: (item.model_copy(update={"response_language": "en"}), lesson)
        for item_id, (item, lesson) in CHAPTER._items.items()
    }
    return replace(CHAPTER, package=CHAPTER.package.model_copy(update={"subject": "english"}), _items=items)


@pytest.fixture
def english(monkeypatch):
    chapter = english_chapter()
    monkeypatch.setattr(session_api, "_chapter", lambda chapter_id, version=None: chapter)
    return chapter


def start(client):
    created = client.post("/v1/sessions", json={"student_display_name": "Minh"}, headers=MINH)
    assert created.status_code == 201, created.text
    joined = client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=MINH)
    assert joined.status_code == 200, joined.text
    return joined.json()


def state_of(client, session_id):
    return client.get(f"/v1/sessions/{session_id}/state", headers=MINH).json()


def until_item_answer(client, state):
    """Answer the theory replies and retells until an item waits for its answer."""
    for n in range(40):
        teaching, item = state["teaching"], state["item"]
        if teaching["awaiting"] == "ANSWER" and item and item["expecting"] == "ANSWER":
            return state
        assert send(client, state, reply_text(state), f"warm-{n}").status_code == 200
        state = state_of(client, state["session_id"])
    raise AssertionError("no item came")


def record(client, session_id, language=None, who=MINH):
    data = {"session_id": session_id, **({"language": language} if language else {})}
    files = {"audio": ("rec.webm", b"\x1aE\xdf\xa3 opus", "audio/webm")}
    return client.post("/v1/voice/transcribe", files=files, data=data, headers=who)


def speak_answer(client, state, text, voice_turn_id, key):
    body = {
        "item_attempt_id": state["teaching"]["input_id"],
        "kind": "ANSWER",
        "content": {"text": text},
        "modality": "VOICE",
        "expected_state_version": state["state_version"],
        **({"voice_turn_id": voice_turn_id} if voice_turn_id else {}),
    }
    return client.post(
        f"/v1/sessions/{state['session_id']}/responses",
        json=body,
        headers={**MINH, "Idempotency-Key": key},
    )


async def stored(session_id):
    database = app.dependency_overrides[get_database]()
    return await session_api._repo(database).get(session_id)


def test_a_math_session_hears_vietnamese_and_answers_as_before(client, voice):
    stt, _, storage = voice
    stt.script.extend([("ba phẩy năm", 0.3)])
    state = start(client)
    assert state["voice"] == {"language": "vi", "allowed": ["vi"], "speech": "tutor"}
    got = record(client, state["session_id"], "vi")
    assert got.status_code == 200, got.text
    assert got.json() == {"text": "ba phẩy năm", "model": "whisper-large-v3"}  # no field added for Math
    assert stt.calls == [("whisper-large-v3", "vi")]
    assert [p.suffix for p in (storage / "in").rglob("*.*")] == [".webm"]  # no voice-turn record beside it
    refused = record(client, state["session_id"], "en")
    assert refused.status_code == 422 and len(stt.calls) == 1  # the client cannot make Math hear English


async def test_a_math_voice_answer_records_no_new_event(client, voice):
    stt, _, _ = voice
    state = until_item_answer(client, start(client))
    stt.script.append((correct_text(state["item"]["item_id"]), 0.2))
    heard = record(client, state["session_id"]).json()
    sent = speak_answer(client, state, heard["text"], "2026-11-13/" + "0" * 32, "math-voice")
    assert sent.status_code == 200, sent.text
    session = await stored(state["session_id"])
    assert not any(e.event_type == EventType.VOICE_TURN_RECORDED for e in session.events)
    resolved = [e.payload for e in session.events if e.event_type == EventType.ITEM_RESOLVED]
    assert all(p["asr_confidence"] is None and p["modality"] == "TEXT" for p in resolved)


async def test_an_english_session_hears_english_for_an_english_answer_and_keeps_q(client, voice, english):
    stt, _, storage = voice
    state = start(client)
    if state["teaching"]["awaiting"] != "ANSWER":
        assert state["voice"]["language"] == "vi"  # the theory reply is said in Vietnamese
    state = until_item_answer(client, state)
    assert state["voice"] == {"language": "en", "allowed": ["en"], "speech": "mixed"}
    assert record(client, state["session_id"], "vi").status_code == 422

    answer = correct_text(state["item"]["item_id"])
    stt.script.append((answer, 0.42))
    got = record(client, state["session_id"], "en")
    assert got.status_code == 200, got.text
    heard = got.json()
    assert heard["language"] == "en" and heard["confidence"] == 0.42 and heard["ask_again"] is True
    assert stt.calls[-1] == ("whisper-large-v3", "en")
    turn = load_turn(storage, heard["voice_turn_id"], student="minh", session_id=state["session_id"])
    assert turn is not None and turn.asr_confidence == 0.42 and turn.audio_ref.endswith(".webm")
    assert (storage / turn.audio_ref).read_bytes() == b"\x1aE\xdf\xa3 opus"
    # another student cannot use this turn, nor can it be used in another session
    assert load_turn(storage, heard["voice_turn_id"], student="an", session_id=state["session_id"]) is None
    assert load_turn(storage, heard["voice_turn_id"], student="minh", session_id="other") is None
    assert load_turn(storage, "../../etc/passwd", student="minh", session_id=state["session_id"]) is None

    assert speak_answer(client, state, answer, heard["voice_turn_id"], "en-1").status_code == 200
    session = await stored(state["session_id"])
    kinds = [e.event_type for e in session.events]
    at = kinds.index(EventType.VOICE_TURN_RECORDED)
    assert kinds[at - 1] == EventType.STUDENT_MESSAGE
    recorded = VoiceTurnRecorded.model_validate(session.events[at].payload)
    assert recorded == VoiceTurnRecorded(
        school_id=session.school_id,
        voice_turn_id=heard["voice_turn_id"],
        message_ref=StudentMessage.model_validate(session.events[at - 1].payload).item_id,
        audio_ref=turn.audio_ref,
        language="en",
        asr_confidence=0.42,
        model="whisper-large-v3",
        heard=answer,
    )
    assert session.events[at].actor.type == "system" and session.events[at].school_id == session.school_id

    # the item closes on a later turn ("vì sao", said in Vietnamese): its q is the one of the spoken answer
    for n in range(6):
        if any(e.event_type == EventType.ITEM_RESOLVED for e in session.events):
            break
        state = state_of(client, state["session_id"])
        assert state["voice"]["language"] == "vi"
        stt.script.append((reply_text(state), 0.9))
        why = record(client, state["session_id"], "vi").json()
        assert why["ask_again"] is False
        assert speak_answer(client, state, why["text"], why["voice_turn_id"], f"why-{n}").status_code == 200
        session = await stored(state["session_id"])
    resolved = [
        ItemResolved.model_validate(e.payload) for e in session.events if e.event_type == "ITEM_RESOLVED"
    ]
    assert resolved and resolved[0].modality == "VOICE" and resolved[0].asr_confidence == 0.42
    for e in session.events:  # every event still parses with its payload model
        model = PAYLOAD_MODELS.get(EventType(e.event_type))
        if model is not None:
            model.model_validate(e.payload)


async def test_a_typed_answer_or_an_edited_transcript_carries_no_q(client, voice, english):
    stt, _, _ = voice
    state = until_item_answer(client, start(client))
    answer = correct_text(state["item"]["item_id"])
    stt.script.append(("something else", 0.95))
    heard = record(client, state["session_id"], "en").json()
    assert speak_answer(client, state, answer, heard["voice_turn_id"], "edited").status_code == 200
    session = await stored(state["session_id"])
    recorded = [e.payload for e in session.events if e.event_type == EventType.VOICE_TURN_RECORDED]
    assert len(recorded) == 1 and recorded[0]["edited"] is True
    for n in range(6):
        if any(e.event_type == EventType.ITEM_RESOLVED for e in session.events):
            break
        state = state_of(client, state["session_id"])
        assert send(client, state, reply_text(state), f"typed-{n}").status_code == 200
        session = await stored(state["session_id"])
    resolved = [e.payload for e in session.events if e.event_type == EventType.ITEM_RESOLVED]
    assert resolved and resolved[0]["asr_confidence"] is None and resolved[0]["modality"] == "TEXT"


async def test_a_voice_turn_of_another_student_is_ignored(client, voice, english):
    stt, _, _ = voice
    state = until_item_answer(client, start(client))
    other = client.post("/v1/sessions", json={"student_display_name": "An"}, headers=AN).json()
    assert record(client, state["session_id"], "en", who=AN).status_code == 403  # not An's session
    stt.script.append(("x", 0.9))
    foreign = record(client, other["session_id"], who=AN).json()  # An's own (Math-like READY) session
    assert "voice_turn_id" not in foreign or foreign["voice_turn_id"]
    answer = correct_text(state["item"]["item_id"])
    sent = speak_answer(client, state, answer, foreign.get("voice_turn_id") or "bad-id", "foreign")
    assert sent.status_code == 200
    session = await stored(state["session_id"])
    assert not any(e.event_type == EventType.VOICE_TURN_RECORDED for e in session.events)


def test_nothing_heard_asks_again_in_english(client, voice, english):
    stt, _, storage = voice
    state = until_item_answer(client, start(client))
    stt.script.append(("", 0.0))
    heard = record(client, state["session_id"], "en").json()
    assert heard["ask_again"] is True and "voice_turn_id" not in heard
    assert not list((storage / "in").rglob("*.json"))


def test_the_english_speech_plan_and_speech(client, voice, english):
    _, tts, _ = voice
    state = start(client)
    plan = client.post(
        "/v1/voice/speech-plan",
        json={"text": "Con nói theo cô nhé: We ate seafood.", "session_id": state["session_id"]},
        headers=MINH,
    )
    assert plan.status_code == 200 and plan.json() == {
        "parts": [
            {"text": "Con nói theo cô nhé:", "voice": "tutor"},
            {"text": "We ate seafood.", "voice": "browser_en"},
        ]
    }
    said = client.post(
        "/v1/voice/speech", json={"text": "Mother.", "session_id": state["session_id"]}, headers=MINH
    )
    assert said.status_code == 200 and tts.said == [f"{LEAD_IN} Mother."]  # V2b on the server too
    client.post(
        "/v1/voice/speech",
        json={"text": "There are 4 people.", "session_id": state["session_id"]},
        headers=MINH,
    )
    assert tts.said[-1] == "There are 4 people."  # Math's "bốn" reading is not applied to English


def test_the_math_speech_plan_is_the_whole_message(client, voice):
    _, tts, _ = voice
    state = start(client)
    text = "3,05 < 3,5 nhé."
    plan = client.post(
        "/v1/voice/speech-plan", json={"text": text, "session_id": state["session_id"]}, headers=MINH
    )
    assert plan.json() == {"parts": [{"text": text, "voice": "tutor"}]}
    client.post("/v1/voice/speech", json={"text": text, "session_id": state["session_id"]}, headers=MINH)
    client.post("/v1/voice/speech", json={"text": "3,05 > 3", "session_id": None}, headers=MINH)
    assert tts.said == ["ba phẩy không năm bé hơn ba phẩy năm nhé.", "ba phẩy không năm lớn hơn ba"]


def test_an_old_event_log_without_voice_turns_still_parses():
    old = {"item_id": "X", "kind": "ANSWER", "text": "3,5", "modality": "VOICE", "seconds": 2}
    assert StudentMessage.model_validate(old).modality == "VOICE"
    stored_resolved = {
        "item_id": "X",
        "purpose": "PRACTICE",
        "kc_ids": ["K"],
        "cognitive_level": "B",
        "difficulty": 0.5,
        "resolution": "INDEPENDENT",
        "max_hint_level": 0,
        "attempts": 1,
        "hints_count": 0,
    }
    assert ItemResolved.model_validate(stored_resolved).asr_confidence is None
