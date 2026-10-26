"""CTX-1: the tutor reads an unclear message in context and answers it. The owner's live case first: after
the hint "mẫu số đặc biệt", the child asked "mẫu như nào" and got "Mình quay lại câu đang làm nhé". Offline:
the rule reader, a scripted router standing in for Qwen."""

from datetime import UTC, datetime

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, HintLevel, Move, Outcome
from cavat.modules.ai_gateway.base import ChatResult
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.session import chapter_service
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.item_loop import HINT_REQUEST_TEXT, ItemTutor
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.policy import ItemFacts, decide
from cavat.modules.tutor.reader import LiveReader, ModelReader, Reading, RecordedReader, rule_reading
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

NOW = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)
CHAPTER = chapter_service.chapters()["math-g5-decimals"]
ITEM = CHAPTER.item("TP-CC-01")  # "Phân số nào dưới đây là phân số thập phân: 3/7, 7/10 hay 10/3?"
HINT_H1 = "Phân số thập phân có mẫu số đặc biệt. Con nhìn mẫu số của từng phân số nhé?"
PASSAGE = "Phân số thập phân là phân số có mẫu số 10, 100, 1000... Mẫu số có bao nhiêu chữ số 0 thì..."


class ScriptedRouter:
    """Answers each request with the next scripted JSON object (None: the provider is down)."""

    def __init__(self, *answers: dict | None) -> None:
        self.answers = list(answers)
        self.requests: list = []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append((model_class, request))
        data = self.answers.pop(0) if self.answers else None
        if data is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        return ChatOutcome(ChatResult("qwen-test", str(data), data), None, 1)


def tutor(reader=None, renderer=None) -> ItemTutor:
    t = ItemTutor(
        ITEM,
        CHAPTER.lesson_of(ITEM.id),
        ActivityType.CONCEPT_CHECK,
        renderer or TemplateRenderer(),
        validate_message,
        reader=reader if reader is not None else LiveReader(None),
        explainer=lambda focus, last: [PASSAGE],
    )
    t.start()
    return t


# --- reading -------------------------------------------------------------------------------------------


def test_a_question_on_a_word_of_the_last_hint_asks_about_it():
    assert rule_reading("mẫu như nào", HINT_H1) == Reading("ASKS_ABOUT", focus="mẫu")
    assert rule_reading("mẫu số đặc biệt là sao ạ", HINT_H1).focus == "mẫu số đặc biệt"
    assert rule_reading("mẫu số đặc biệt", HINT_H1) is None  # not a question
    assert rule_reading("con mèo tên là gì", HINT_H1) is None  # a question about something else


def test_the_model_proposes_a_reading_and_its_answer_is_graded_by_the_checker():
    router = ScriptedRouter({"label": "ANSWER", "focus": "", "answer": "7/10"})
    t = tutor(LiveReader(ModelReader(router)))
    turn = t.on_student("con nghĩ là cái có mẫu mười ạ")
    read = next(e for e in turn.events if e.type == EventType.MESSAGE_READ)
    assert read.payload["label"] == "ANSWER" and read.payload["source"] == "LLM"
    submitted = next(e for e in turn.events if e.type == EventType.ANSWER_SUBMITTED)
    assert submitted.payload["outcome"] == Outcome.CORRECT  # rule 2: the checker decides, on "7/10"
    assert router.requests[0][0].value == "lightweight"


def test_an_unusable_model_reading_falls_back_to_the_rule():
    for answers in [({"label": "MAYBE", "focus": "", "answer": ""},), (None,)]:
        t = tutor(LiveReader(ModelReader(ScriptedRouter(*answers))))
        t.on_student(HINT_REQUEST_TEXT)
        assert t.on_student("mẫu như nào").move == Move.EXPLAIN


# --- the owner's case ----------------------------------------------------------------------------------


def test_asking_about_the_hint_gets_an_explanation_not_a_redirect():
    t = tutor()
    assert t.on_student(HINT_REQUEST_TEXT).text.endswith(HINT_H1)
    turn = t.on_student("mẫu như nào")
    assert turn.move == Move.EXPLAIN
    assert turn.text.startswith("Cô nói rõ hơn nhé:") and "10, 100 hay 1000" in turn.text
    assert turn.text.endswith("?") and "7/10 là" not in turn.text  # a question, never the answer
    read = next(e for e in turn.events if e.type == EventType.MESSAGE_READ)
    assert (read.payload["label"], read.payload["focus"], read.payload["source"]) == (
        "ASKS_ABOUT",
        "mẫu",
        "RULE",
    )
    assert t.state.max_hint_level == HintLevel.H2  # it is help: the next rung, so no hint repeats it


def test_qwen_says_the_explanation_in_context_and_the_checks_hold():
    said = "Mẫu số đặc biệt là 10, 100 hay 1000 đó con. Trong ba phân số, phân số nào có mẫu số như vậy?"
    router = ScriptedRouter(None, {"message": said, "safety_flag": False, "policy_feedback": ""})
    renderer = LLMRenderer(router, TemplateRenderer(), validate_message)
    t = tutor(renderer=renderer)
    t.on_student(HINT_REQUEST_TEXT)  # the H1 hint: the model is down, the template says it
    turn = t.on_student("mẫu như nào")
    assert turn.move == Move.EXPLAIN and turn.text == said
    user = router.requests[-1][1].messages[1].content
    assert "điều con hỏi (mẫu)" in user and "[CĂN CỨ ĐÃ DUYỆT]" in user and PASSAGE[:40] in user


@pytest.mark.parametrize(
    "leak",
    [
        "Mẫu số đặc biệt là 10, nên đáp án là 7/10 nhé con. Con thấy chưa?",
        "Con chọn 7/10 là đúng rồi đó. Con thử giải thích xem?",
    ],
)
def test_a_model_explanation_that_singles_out_the_right_option_is_refused(leak):
    """Before CTX-1 a choice item without leak_patterns let such a model message through (T03)."""
    answer = {"message": leak, "safety_flag": False, "policy_feedback": ""}
    router = ScriptedRouter(None, answer, answer)  # the hint falls back; the explanation leaks twice
    renderer = LLMRenderer(router, TemplateRenderer(), validate_message)
    t = tutor(renderer=renderer)
    t.on_student(HINT_REQUEST_TEXT)
    turn = t.on_student("mẫu như nào")
    assert turn.move == Move.EXPLAIN and turn.text.startswith("Cô nói rõ hơn nhé:")  # the template
    assert all("ANSWER_LEAK" in codes for codes in renderer.last_trace.rejected)


def test_in_an_end_of_lesson_test_the_question_is_only_said_again():
    t = ItemTutor(
        ITEM,
        CHAPTER.lesson_of(ITEM.id),
        ActivityType.EXIT_ASSESSMENT,
        TemplateRenderer(),
        validate_message,
        reader=LiveReader(None),
    )
    t.start()
    t.on_student(HINT_REQUEST_TEXT)
    assert t.on_student("mẫu như nào").move == Move.REDIRECT


def test_asked_again_and_again_the_child_gets_the_next_hint():
    from cavat.modules.assessment.math_checker import CheckResult
    from cavat.modules.tutor.contracts import ItemState, PolicyInput

    state = ItemState(item_id=ITEM.id, activity=ActivityType.CONCEPT_CHECK, explanations=2)
    d = decide(
        PolicyInput(ITEM, state, CheckResult(Outcome.ASKS_ABOUT), "ANSWER"), ItemFacts(top_hint_level=5)
    )
    assert d.move == Move.HINT and "R-EXPLAIN" in d.rule_ids


# --- replay and the teaching loop ----------------------------------------------------------------------


def test_a_replay_reads_the_record_and_never_calls_the_model():
    router = ScriptedRouter({"label": "ASKS_ABOUT", "focus": "mẫu số đặc biệt", "answer": ""})
    loop = TeachingLoop(CHAPTER, "s1", item_reader=LiveReader(ModelReader(router)))
    turn = loop.start(NOW)
    while turn.awaiting != Awaiting.ANSWER:
        turn = loop.on_student("Con nghĩ là 4/100 ạ.", NOW)
    loop.on_student(HINT_REQUEST_TEXT, NOW)
    turn = loop.on_student("cái mẫu đó là gì ạ", NOW)
    assert any(e.event_type == EventType.MESSAGE_READ for e in turn.events) and len(router.requests) == 1
    again = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)
    assert again.tutor.state.explanations == loop.tutor.state.explanations == 1
    assert again.tutor.phase == loop.tutor.phase and len(router.requests) == 1
    assert again.tutor.last_tutor == loop.events[-1].payload["text"]  # what the child saw last


def test_recorded_readings_are_found_by_turn():
    reader = RecordedReader({2: Reading("ASKS_ABOUT", "mẫu", "", "LLM")})
    assert reader.read(stem="", last_tutor="", said="x", turn=2).focus == "mẫu"
    assert reader.read(stem="", last_tutor="", said="x", turn=3) is None


@pytest.mark.parametrize(
    ("node", "said", "starts"),
    [
        ("KC-DEC-FRAC", "ko", "Không sao đâu"),  # "phân số nào?": "ko" is "con không biết"
        ("KC-DEC-EQ", "ko", "Đúng rồi!"),  # "... có dài hơn không?": "ko" is the answer
    ],
)
def test_a_bare_ko_is_read_with_the_question_it_answers(node, said, starts):
    loop = TeachingLoop(CHAPTER, "s1")
    turn = loop.start(NOW)
    while not (turn.awaiting == Awaiting.THEORY_REPLY and turn.node_id == node):
        turn = loop.on_student(
            _theory_answer(turn) if turn.awaiting == Awaiting.THEORY_REPLY else _right(loop, turn), NOW
        )
    assert loop.on_student(said, NOW).messages[0].text.startswith(starts)


def _theory_answer(turn) -> str:
    variant = next(t for t in CHAPTER.node(turn.node_id).theory if t.ask == turn.prompt)
    return variant.accept[0] if variant.accept else "Con nghĩ là được ạ."


def _right(loop: TeachingLoop, turn) -> str:
    """A right answer for whatever the loop waits for (items and retells), to reach a node quickly."""
    if turn.awaiting == Awaiting.RETELL:
        return ". ".join(p[0] for p in CHAPTER.node(turn.node_id).explain.key_ideas)
    item = loop.tutor.item
    if loop.tutor.phase is not None and loop.tutor.phase.value in (
        "VERIFYING",
        "TEACH_BACK",
        "AWAITING_REASON",
    ):
        return item.explanation or "Vì con làm theo quy tắc."
    ans = item.answer
    if ans.type == "compare":
        from cavat.modules.assessment.vi_numbers import parse_literal

        a, b = parse_literal(ans.left).value, parse_literal(ans.right).value
        return f"{ans.left} {'>' if a > b else '<' if a < b else '='} {ans.right}"
    if ans.type == "order":
        return "; ".join(ans.numbers if ans.direction == "asc" else ans.numbers)
    if ans.type == "choice":
        return next(o.id for o in ans.options if o.correct)
    if ans.type == "boolean":
        return "đúng" if ans.value else "sai"
    return getattr(ans, "value", "")


# --- through the API ------------------------------------------------------------------------------------


@pytest.fixture
async def client(monkeypatch):
    from cavat.core.memory_db import InMemoryDatabase
    from cavat.db import ensure_indexes
    from cavat.main import app
    from cavat.modules.rag.service import RagService
    from cavat.modules.session import api as session_api
    from cavat.modules.session import service
    from cavat.modules.session.api import get_database
    from fastapi.testclient import TestClient

    monkeypatch.setattr(session_api, "tutor_router", lambda: None)  # no model: the rule reads
    monkeypatch.setattr(
        session_api,
        "_rag_service",
        RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: None),
    )
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)


def test_the_owner_case_through_the_api_and_the_teacher_sees_the_reading(client):
    an = {"X-Demo-Student": "an"}

    def send(state, path, body, key):
        sent = client.post(
            f"/v1/sessions/{state['session_id']}/{path}", json=body, headers={**an, "Idempotency-Key": key}
        )
        assert sent.status_code == 200, sent.text
        return client.get(f"/v1/sessions/{state['session_id']}/state", headers=an).json()

    def answer(state, text, key):
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": text},
            "expected_state_version": state["state_version"],
        }
        return send(state, "responses", body, key)

    created = client.post("/v1/sessions", json={"student_display_name": "An"}, headers=an).json()
    state = client.post(f"/v1/sessions/{created['session_id']}/join", headers=an).json()
    state = answer(state, "Con nghĩ là 4/100 ạ.", "k0")  # the theory question: now TP-CC-01
    assert state["item"]["item_id"] == "TP-CC-01"
    hint = {
        "item_attempt_id": state["item"]["item_attempt_id"],
        "expected_state_version": state["state_version"],
    }
    state = send(state, "hint-requests", hint, "k1")
    state = answer(state, "mẫu như nào", "k2")
    said = state["transcript"][-1]["text"]
    assert said.startswith("Cô nói rõ hơn nhé:") and "10, 100 hay 1000" in said

    from test_chapter_session_api import TEACHER

    transcript = client.get(f"/v1/sessions/{created['session_id']}/transcript", headers=TEACHER).json()
    turns = [t for s in transcript["segments"] for t in s["turns"]]
    asked = next(t for t in turns if t["text"] == "mẫu như nào")
    assert asked["student"]["read"] == {"label": "ASKS_ABOUT", "focus": "mẫu", "source": "RULE"}
    assert any(t["tutor"] and t["tutor"]["move"] == "EXPLAIN" for t in turns)
