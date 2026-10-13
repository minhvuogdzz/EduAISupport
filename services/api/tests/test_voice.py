"""Voice live (ADR-030): the words the tutor's voice reads, and the voice endpoints, offline with fakes."""

import pytest
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.base import ModelUnavailable, Speech, Transcription
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.ai_gateway.vieneu import VieneuSpeech
from cavat.modules.session import api as session_api
from cavat.modules.session.api import get_database
from cavat.modules.voice import api as voice_api
from cavat.modules.voice.speech_text import read_integer, read_number, speech_text
from fastapi.testclient import TestClient

MINH = {"X-Demo-Student": "minh"}


@pytest.mark.parametrize(
    ("digits", "spoken"),
    [
        ("5", "năm"),
        ("15", "mười lăm"),
        ("21", "hai mươi mốt"),
        ("25", "hai mươi lăm"),
        ("105", "một trăm linh năm"),
        ("110", "một trăm mười"),
        ("1001", "một nghìn không trăm linh một"),
        ("2025", "hai nghìn không trăm hai mươi lăm"),
        ("1000000", "một triệu"),
        ("05", "không năm"),
        ("0", "không"),
    ],
)
def test_integers_are_read_as_a_vietnamese_teacher_reads_them(digits, spoken):
    assert read_integer(digits) == spoken


def test_a_decimal_is_read_with_its_comma():
    assert read_number("3,05") == "ba phẩy không năm"
    assert read_number("0,125") == "không phẩy một trăm hai mươi lăm"


@pytest.mark.parametrize(
    ("written", "spoken"),
    [
        ("3,05 < 3,5", "ba phẩy không năm bé hơn ba phẩy năm"),
        ("S = a × h : 2", "S bằng a nhân h chia hai"),
        ("(a + b) × h : 2", "(a cộng b) nhân h chia hai"),
        ("Diện tích là 12 cm² nhé!", "Diện tích là mười hai xăng-ti-mét vuông nhé!"),
        ("phân số 3/10", "phân số ba phần mười"),
        ("có 1 015 bạn, 1.500 kg", "có một nghìn không trăm mười lăm bạn, một nghìn năm trăm ki-lô-gam"),
        ("7 - 2,5", "bảy trừ hai phẩy năm"),
        ("Bước 1: viết 7,5\nBước 2: so sánh 😁", "Bước một: viết bảy phẩy năm. Bước hai: so sánh"),
        ("Con điền dấu «>», «<» hay «=»?", "Con điền dấu lớn hơn, bé hơn hay bằng?"),
    ],
)
def test_a_tutor_message_is_written_out_for_the_voice(written, spoken):
    assert speech_text(written) == spoken


class FakeSTT:
    def __init__(self, fail=False):
        self.fail, self.heard = fail, []

    def transcribe(self, audio, *, model, language="vi", filename="audio.webm"):
        if self.fail:
            raise ModelUnavailable("quota", model=model)
        self.heard.append((audio, language, filename))
        return Transcription(model=model, text="ba phẩy năm", language=language)


class FakeTTS:
    name = "fake-tts"

    def __init__(self):
        self.said = []

    def speak(self, text):
        self.said.append(text)
        return Speech(model=self.name, audio=b"RIFF....WAVE")


@pytest.fixture
def voice(monkeypatch, tmp_path):
    stt, tts = FakeSTT(), FakeTTS()
    gateway = AIRouter(stt_provider=stt, tts_provider=tts)
    monkeypatch.setattr(session_api, "_shared_router", lambda: gateway)
    monkeypatch.setattr(voice_api, "_storage", lambda: tmp_path)
    return stt, tts, tmp_path


@pytest.fixture
def client():
    database = InMemoryDatabase()
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)


def test_the_status_says_what_the_server_can_do(client, voice):
    got = client.get("/v1/voice/status", headers=MINH)
    assert got.status_code == 200 and got.json() == {
        "listen": True,
        "speak": True,
        "speech_model": "fake-tts",
    }


def test_without_a_provider_the_browser_listens_and_reads(client, monkeypatch):
    monkeypatch.setattr(session_api, "_shared_router", lambda: AIRouter())
    assert client.get("/v1/voice/status", headers=MINH).json() == {
        "listen": False,
        "speak": False,
        "speech_model": None,
    }
    said = client.post("/v1/voice/speech", json={"text": "Chào con"}, headers=MINH)
    assert said.status_code == 503 and said.json()["error"]["code"] == "MODEL_UNAVAILABLE"


def test_a_recording_is_kept_and_turned_into_words(client, voice):
    stt, _, storage = voice
    files = {"audio": ("rec.webm", b"\x1aE\xdf\xa3 fake opus", "audio/webm;codecs=opus")}
    got = client.post("/v1/voice/transcribe", files=files, headers=MINH)
    assert got.status_code == 200, got.text
    assert got.json() == {"text": "ba phẩy năm", "model": "whisper-large-v3"}
    assert stt.heard[0][1] == "vi"
    kept = list((storage / "in").rglob("*.webm"))
    assert len(kept) == 1 and kept[0].read_bytes() == b"\x1aE\xdf\xa3 fake opus"
    assert "minh" not in str(kept[0])  # the folder is a hash of the student, not the id


def test_a_bad_recording_is_refused(client, voice):
    empty = client.post("/v1/voice/transcribe", files={"audio": ("a.webm", b"", "audio/webm")}, headers=MINH)
    assert empty.status_code == 422
    text = client.post("/v1/voice/transcribe", files={"audio": ("a.txt", b"hi", "text/plain")}, headers=MINH)
    assert text.status_code == 415
    big = b"0" * (voice_api.MAX_AUDIO_BYTES + 1)
    too_long = client.post(
        "/v1/voice/transcribe", files={"audio": ("a.webm", big, "audio/webm")}, headers=MINH
    )
    assert too_long.status_code == 413


def test_speech_to_text_out_of_quota_lets_the_browser_listen(client, voice, monkeypatch):
    monkeypatch.setattr(session_api, "_shared_router", lambda: AIRouter(stt_provider=FakeSTT(fail=True)))
    got = client.post("/v1/voice/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}, headers=MINH)
    assert got.status_code == 503 and got.json()["error"]["code"] == "MODEL_UNAVAILABLE"


def test_the_tutor_is_read_from_its_written_out_words_and_cached(client, voice):
    _, tts, _ = voice
    first = client.post("/v1/voice/speech", json={"text": "So sánh 3,05 và 3,5 nhé."}, headers=MINH)
    again = client.post("/v1/voice/speech", json={"text": "So sánh 3,05 và 3,5 nhé."}, headers=MINH)
    assert first.status_code == again.status_code == 200
    assert first.headers["content-type"] == "audio/wav" and first.content == again.content == b"RIFF....WAVE"
    assert tts.said == ["So sánh ba phẩy không năm và ba phẩy năm nhé."]  # once: the second from the cache


def test_the_voice_is_for_students_only(client, voice):
    assert client.post("/v1/voice/speech", json={"text": "Chào"}).status_code == 401
    assert client.get("/v1/voice/status").status_code == 401


def test_vieneu_not_running_is_a_model_unavailable():
    class Down:
        def post(self, *a, **k):
            raise ConnectionError("refused")

    with pytest.raises(ModelUnavailable):
        VieneuSpeech("http://127.0.0.1:8010", client=Down()).speak("Chào con")


async def test_a_spoken_answer_is_recorded_as_voice(voice):
    from test_chapter_session_api import send, start

    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    try:
        client = TestClient(app)
        state = start(client)
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": "con nghĩ là được ạ"},
            "modality": "VOICE",
            "expected_state_version": state["state_version"],
        }
        sent = client.post(
            f"/v1/sessions/{state['session_id']}/responses",
            json=body,
            headers={**MINH, "Idempotency-Key": "v1"},
        )
        assert sent.status_code == 200, sent.text
        doc = await database["learning_sessions"].find_one({"_id": state["session_id"]})
        said = [e for e in doc["events"] if e["event_type"] == "STUDENT_MESSAGE"]
        assert said[-1]["payload"]["modality"] == "VOICE"
    finally:
        app.dependency_overrides.pop(get_database, None)
    assert send  # the text path stays the same helper
