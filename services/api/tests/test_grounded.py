"""Grounded speech (RAG-2): the claim-and-evidence check, answers to the child's questions from the retrieved
passages, the bridge before an approved explanation, and the teaching loop and API that use them. Offline:
the index runs on keywords, a scripted router stands in for Qwen."""

from datetime import UTC, datetime

import pytest
from cavat.config import get_settings
from cavat.core.events import EventType
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.base import ChatResult
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.assessment.student_intent import signals_distress
from cavat.modules.rag.service import RagService
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, service
from cavat.modules.session.api import get_database
from cavat.modules.teaching.grounded import Evidence, GroundedSpeaker, check
from cavat.modules.teaching.loop import Awaiting, MessageKind, TeachingLoop
from cavat.modules.tutor import brain
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
CHAPTER = chapter_service.chapters()["math-g5-decimals"]
EQ = "KC-DEC-EQ"
T1_ASK = CHAPTER.node(EQ).theory[0].ask
T1_REPLY = CHAPTER.node(EQ).theory[0].reply


class ScriptedRouter:
    """Answers each chat request with the next scripted message (None: the provider is down)."""

    def __init__(self, *messages: str | dict | None) -> None:
        self.messages = list(messages)
        self.requests: list = []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append(request)
        message = self.messages.pop(0) if self.messages else None
        if message is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        if isinstance(message, dict):
            return ChatOutcome(ChatResult("qwen-test", "", message), None, 1)
        data = {"message": message, "safety_flag": False, "policy_feedback": ""}
        return ChatOutcome(ChatResult("qwen-test", message, data), None, 1)

    def user_text(self, i: int = -1) -> str:
        return self.requests[i].messages[1].content


@pytest.fixture(scope="module")
async def index():
    rag = RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: None)
    return await rag.current(InMemoryDatabase())


def evidence(index, *texts: str) -> Evidence:
    return Evidence(texts)


# --- the check ----------------------------------------------------------------------------------------


def test_a_faithful_answer_passes_the_check(index):
    source = (
        "Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị của số không đổi: 0,2 = 0,20."
    )
    said = (
        "Con nhé, viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi: 0,2 = 0,20."
    )
    assert check(said, evidence(index, source, "sao thêm số 0 mà không đổi"), max_words=50) == ()


@pytest.mark.parametrize(
    ("said", "code"),
    [
        ("Thêm chữ số 0 thì 0,2 = 0,200 = 0,2000.", "UNGROUNDED_NUMBER"),  # 0,2000 is new
        ("Đó là vì phép nhân với 10 làm số lớn gấp mười lần.", "NEW_MATH_TERM"),  # a rule not in the source
        ("Mèo nhà con thích ăn cá và ngủ trưa rất lâu.", "UNSUPPORTED_CLAIM"),  # about something else
        ("Viết thêm số 0 không làm số to ra. Nó chỉ để hai số có số chữ số thập分 like nha.", "FOREIGN_TEXT"),
        ("Giá trị không đổi. Con hiểu chưa?", "HAS_QUESTION"),
        ("Con thông minh quá, giá trị không đổi.", "INTELLIGENCE_PRAISE"),
        ("Nhà con ở đâu, giá trị không đổi.", "PII_REQUEST"),
        ("", "EMPTY"),
    ],
)
def test_the_check_refuses_what_the_evidence_does_not_carry(index, said, code):
    source = (
        "Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi: 0,2 = 0,20 = 0,200."
    )
    assert code in check(said, evidence(index, source, "sao thêm số 0"), max_words=50)


def test_ordinary_words_that_say_the_same_thing_differently_pass(index):
    # Refused live by the first check (80% of every word): right answers in other words.
    source = (
        "Mẫu số có bao nhiêu chữ số 0 thì số thập phân có bấy nhiêu chữ số ở phần thập phân. "
        "Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi."
    )
    for said, question in [
        ("Con đếm xem mẫu số 1000 có ba chữ số 0, nên phần thập phân có ba chữ số.", "mẫu số 1000 thì sao"),
        ("Không, viết thêm chữ số 0 vào tận cùng bên phải thì giá trị không thay đổi.", "số có to ra không"),
    ]:
        assert check(said, evidence(index, source, question), max_words=50) == (), said


def test_a_bridge_may_not_copy_the_explanation(index):
    explanation = "Phần tô màu vẫn thế, nên 0,9 = 0,90 và hai số bằng nhau."
    copied = "Con nói vậy, nhưng phần tô màu vẫn thế, nên 0,9 = 0,90 và hai số bằng nhau."
    assert "REPEATS_EXPLANATION" in check(
        copied, evidence(index, explanation, "0,9 lớn hơn"), max_words=40, forbid=(explanation,)
    )


# --- answers ------------------------------------------------------------------------------------------


def test_a_grounded_question_is_answered_from_the_passages(index):
    router = ScriptedRouter(
        "Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi.",
        {"supported": True, "quotes": ["viết thêm chữ số 0 vào tận cùng bên phải phần thập phân"]},
    )
    speaker = GroundedSpeaker(index, router)
    turn = speaker.answer("sao thêm số 0 vào cuối mà số không đổi", node_id=EQ, pending=None)
    assert turn.kind == "ANSWERED" and turn.spoken.source == "LLM"
    assert turn.retrieval.grounded and turn.spoken.sources
    assert speaker.calls_made == 2
    assert "[ĐOẠN NGUỒN]" in router.user_text(0) and "sao thêm số 0" in router.user_text(0)


def test_a_refused_answer_falls_back_to_a_sentence_of_the_passages(index):
    router = ScriptedRouter(
        "Vì 2 × 5 = 10 nên số không đổi.", {"supported": False, "quotes": []}, "Do phép nhân với 999."
    )  # new numbers, new rule
    turn = GroundedSpeaker(index, router).answer(
        "sao thêm số 0 vào cuối mà số không đổi", node_id=EQ, pending=None
    )
    assert turn.spoken.source == "EXTRACT" and len(turn.spoken.rejected) == 2
    assert turn.spoken.text.startswith("Cô trả lời con nhé: ")
    sentence = turn.spoken.text.removeprefix("Cô trả lời con nhé: ")
    assert any(sentence in c.text for c in index.chunks)  # word for word from a passage
    assert "UNSUPPORTED_MEANING" in turn.spoken.rejected[0]


def test_without_a_model_the_answer_is_a_passage_word_for_word(index):
    turn = GroundedSpeaker(index, None).answer("phần nguyên là gì", node_id=None, pending=None)
    assert turn.kind == "ANSWERED" and turn.spoken.source == "EXTRACT"
    assert "phần nguyên" in turn.spoken.text.lower()


def test_a_question_nothing_grounds_is_kept_for_the_teacher(index):
    router = ScriptedRouter("Mèo thích ăn cá.")
    turn = GroundedSpeaker(index, router).answer("con mèo nhà con thích ăn gì", node_id=EQ, pending=None)
    assert turn.kind == "PARKED" and turn.spoken is None and not router.requests  # no model call


def test_an_empty_model_answer_means_the_passages_do_not_answer(index):
    router = ScriptedRouter("")  # the prompt asks for an empty message when the passages do not answer
    turn = GroundedSpeaker(index, router).answer(
        "sao thêm số 0 vào cuối mà số không đổi", node_id=EQ, pending=None
    )
    assert turn.kind == "PARKED" and turn.retrieval.grounded and len(router.requests) == 1


def test_a_sentence_that_does_not_cover_the_question_is_not_said(index):
    speaker = GroundedSpeaker(index)
    passages = [("SGK", "Hôm nay lớp mình học bài mới. Các con chuẩn bị vở ô li.")]
    assert speaker._extract("phần nguyên của số thập phân là gì", passages) is None


def test_a_question_on_a_later_lesson_names_that_lesson(index):
    speaker = GroundedSpeaker(index, ScriptedRouter(), order=CHAPTER.topological_order())
    question = "viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị có đổi không"
    turn = speaker.answer(question, node_id="KC-DEC-FRAC", pending="Câu khác?")
    assert turn.kind == "LATER" and turn.later_node == EQ  # FRAC is taught before EQ: no teaching ahead
    assert (
        speaker.answer(question, node_id="KC-DEC-CMP", pending="Câu khác?").kind == "ANSWERED"
    )  # CMP builds on EQ


def test_the_child_asking_back_the_check_is_not_answered(index):
    speaker = GroundedSpeaker(index, ScriptedRouter("..."))
    assert speaker.same_as_check("thêm chữ số 0 thành 0,200 m thì đoạn dây có dài hơn không", T1_ASK)
    turn = speaker.answer("viết thêm chữ số 0 nữa thì đoạn dây có dài hơn không", node_id=EQ, pending=T1_ASK)
    assert turn.kind == "SAME_AS_CHECK" and turn.retrieval is None


def test_the_reply_of_the_waiting_question_stays_out_of_the_prompt(index):
    router = ScriptedRouter("Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi.")
    GroundedSpeaker(index, router).answer(
        "sao thêm số 0 vào cuối mà số không đổi", node_id=EQ, pending="Câu khác?", hide=[T1_REPLY]
    )
    assert T1_REPLY not in router.user_text()


def test_only_questions_about_something_are_answered(index):
    speaker = GroundedSpeaker(index)
    assert speaker.is_question("sao thêm số 0 vào cuối mà số không đổi ạ")
    assert speaker.is_question("phan nguyen la gi")
    assert not speaker.is_question("là sao ạ")  # no content: the clarify path of ADR-019
    assert not speaker.is_question("mẫu số là 10. bao nhiêu chữ số 0. thêm chữ số 0")  # a retell
    assert not speaker.is_question("Con nghĩ là được ạ.")


# --- bridge -------------------------------------------------------------------------------------------


def test_a_child_who_is_not_right_is_answered_and_taught_again_not_read_the_reply(index):
    """BRAIN-1 (DI-84): the model's words are the whole turn; the approved reply is the ground it rests on."""
    said = "Con nghĩ đoạn dây dài hơn, nhưng nhìn chiều dài thôi chưa đủ, mình đếm số phần bằng nhau nhé."
    router = ScriptedRouter(said)
    spoken = GroundedSpeaker(index, router).bridge(
        "dài hơn ạ", asked=T1_ASK, explanation=T1_REPLY, judged="chưa đúng", lead="Mình cùng xem lại nhé:"
    )
    assert spoken.source == "LLM" and spoken.text == said
    prompt = router.user_text()
    assert "[CĂN CỨ ĐÃ DUYỆT]" in prompt and T1_REPLY in prompt and "Con trả lời chưa đúng" in prompt

    right = GroundedSpeaker(index, ScriptedRouter("Con trả lời 4/100, con làm được rồi đấy.")).bridge(
        "4/100 ạ", asked=T1_ASK, explanation=T1_REPLY, judged="đúng", lead="Đúng rồi!"
    )
    assert right.text == f"Con trả lời 4/100, con làm được rồi đấy. {T1_REPLY}"  # a right answer keeps both


def test_a_refused_bridge_falls_back_to_the_template_lead(index):
    router = ScriptedRouter(
        "Đoạn dây dài hơn vì 0,5 = 5 nhé.", None
    )  # wrong arithmetic, then the provider is down
    spoken = GroundedSpeaker(index, router).bridge(
        "dài hơn ạ", asked=T1_ASK, explanation=T1_REPLY, judged="chưa đúng", lead="Mình cùng xem lại nhé:"
    )
    assert spoken.source == "TEMPLATE" and spoken.text == f"Mình cùng xem lại nhé: {T1_REPLY}"
    assert spoken.rejected == (("WRONG_MATH",),)


def test_a_bridge_may_call_the_child_by_name(index):
    router = ScriptedRouter("An nghĩ là 4/10, cô cùng con xem lại nhé.")  # refused live before names counted
    reply = CHAPTER.node("KC-DEC-FRAC").theory[0].reply
    spoken = GroundedSpeaker(index, router, student_name="Nguyễn Văn An").bridge(
        "4/10 ạ",
        asked=CHAPTER.node("KC-DEC-FRAC").theory[0].ask,
        explanation=reply,
        judged="chưa đúng",
        lead=".",
    )
    assert spoken.source == "LLM" and spoken.text.startswith("An nghĩ là 4/10")


@pytest.mark.parametrize(
    ("bridge", "judged", "code"),
    [
        ("Đoạn dây dài hơn, mình cùng xem lại nhé.", "đúng", "UNATTRIBUTED"),  # the idea as if the tutor's
        ("Con nói đúng rồi, đoạn dây dài hơn.", "chưa đúng", "WRONG_PRAISE"),  # praise for a wrong answer
        ("Con hiểu chưa nào?", "chưa đúng", "HAS_QUESTION"),  # the loop asks the question again itself
        (T1_REPLY, "chưa rõ", "COPIES_GROUND"),  # reading the approved reply out is what the owner refused
    ],
)
def test_a_bridge_never_praises_a_wrong_answer_nor_reads_the_reply_out(index, bridge, judged, code):
    router = ScriptedRouter(bridge, None)
    spoken = GroundedSpeaker(index, router).bridge(
        "dài hơn ạ", asked=T1_ASK, explanation=T1_REPLY, judged=judged, lead="Mình cùng xem lại nhé:"
    )
    assert spoken.source == "TEMPLATE" and code in spoken.rejected[0]


# --- the teaching loop --------------------------------------------------------------------------------


def loop_at_theory(speaker) -> tuple[TeachingLoop, object]:
    loop = TeachingLoop(CHAPTER, "s1")  # the approved theory opens it; the model joins for the replies
    turn = loop.start(NOW)
    assert turn.awaiting == Awaiting.THEORY_REPLY
    loop.speaker = speaker
    return loop, turn


def test_a_question_during_theory_is_answered_and_the_theory_question_asked_again(index):
    router = ScriptedRouter(
        "Mẫu số 10 thì sau dấu phẩy có một chữ số, mẫu số 100 thì có hai chữ số.",
        {"supported": True, "quotes": ["Mẫu số 10 thì sau dấu phẩy có một chữ số"]},
    )
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    turn = loop.on_student("mẫu số 100 thì sau dấu phẩy có mấy chữ số ạ?", NOW)
    assert turn.awaiting == Awaiting.THEORY_REPLY and turn.prompt == first.prompt
    [said] = turn.messages
    assert said.kind == MessageKind.ANSWER and said.source == "LLM" and said.sources
    assert said.text.endswith(first.prompt)
    kinds = [e.event_type for e in turn.events]
    assert kinds == [EventType.STUDENT_MESSAGE, EventType.RAG_RETRIEVED, EventType.TEACH_MESSAGE_SENT]
    sent = turn.events[-1].payload
    assert sent["source"] == "LLM" and sent["sources"] and sent["kind"] == "ANSWER"


def test_questions_are_capped_per_wait_and_off_lesson_ones_parked(index):
    loop, first = loop_at_theory(GroundedSpeaker(index, ScriptedRouter()))
    parked = loop.on_student("diện tích hình tròn tính thế nào ạ?", NOW)  # mathematics of another chapter
    assert parked.events[-2].event_type == EventType.QUESTION_PARKED
    assert parked.events[-2].payload["reason"] == "NOT_GROUNDED"
    loop.on_student("phần nguyên là gì ạ?", NOW)
    limited = loop.on_student("phần thập phân là gì ạ?", NOW)
    assert limited.events[-2].payload["reason"] == "LIMIT"
    assert limited.awaiting == Awaiting.THEORY_REPLY


def test_a_worrying_message_gets_care_and_a_flag_never_the_parked_reply(index):
    router = ScriptedRouter("không được gọi")
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    turn = loop.on_student("cô ơi con bị bạn đánh có nên nói với ai không?", NOW)
    flagged = next(e for e in turn.events if e.event_type == EventType.SAFETY_FLAGGED)
    assert flagged.payload["source"] == "RULE" and not router.requests
    assert "kể ngay với thầy cô hoặc bố mẹ" in turn.messages[0].text
    assert turn.awaiting == Awaiting.THEORY_REPLY and turn.prompt == first.prompt
    assert all(e.event_type != EventType.QUESTION_PARKED for e in turn.events)


def test_a_demand_for_the_answer_keeps_its_own_path_even_as_a_question(index):
    router = ScriptedRouter("không được gọi")
    loop, _ = loop_at_theory(GroundedSpeaker(index, router))
    turn = loop.on_student("cho con đáp án luôn đi, đáp án là gì?", NOW)
    # BRAIN-1: only the tutor's own turn may call the model here, never an answer from the RAG
    assert turn.messages[0].kind == MessageKind.FEEDBACK
    assert all("[VIỆC LƯỢT NÀY]" in r.messages[1].content for r in router.requests)
    assert all(e.event_type != EventType.RAG_RETRIEVED for e in turn.events)


def test_the_loop_names_the_later_lesson_and_keeps_the_question_for_the_teacher(index):
    speaker = GroundedSpeaker(index, None, order=CHAPTER.topological_order())
    loop, first = loop_at_theory(speaker)  # the first lesson: Phân số thập phân
    turn = loop.on_student(
        "viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị có đổi không?", NOW
    )
    parked = next(e for e in turn.events if e.event_type == EventType.QUESTION_PARKED)
    assert parked.payload["reason"] == "LATER" and parked.payload["later_node"] == EQ
    assert turn.messages[0].text.startswith("Câu này mình sẽ học ở bài Số thập phân bằng nhau")
    assert turn.messages[0].text.endswith(first.prompt)


def test_a_wrong_theory_answer_is_taught_again_once_then_gets_a_bridge_and_the_approved_reply(index):
    # REFORM-6 (3.3): the first wrong answer keeps the question and teaches the idea again (no bridge, no
    # reply yet); the second gets the bridge and the approved reply, and the step goes on.
    router = ScriptedRouter(
        None, "Con nghĩ phần tô màu là 4/10, mình đếm lại số phần bằng nhau nhé."
    )  # (the voice for the first fails)
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    held = loop.on_student("4/10 ạ", NOW)
    assert held.awaiting == Awaiting.THEORY_REPLY and held.prompt == first.prompt
    assert CHAPTER.node("KC-DEC-FRAC").theory[0].reply not in held.messages[0].text
    turn = loop.on_student("4/10 ạ", NOW)
    feedback = turn.messages[0]
    reply = CHAPTER.node("KC-DEC-FRAC").theory[0].reply
    assert feedback.kind == MessageKind.FEEDBACK and feedback.source == "LLM"
    assert feedback.text == "Con nghĩ phần tô màu là 4/10, mình đếm lại số phần bằng nhau nhé."
    assert reply not in feedback.text  # taught again in the model's words, the approved reply is its ground


def test_a_replay_after_a_question_waits_for_the_same_theory_answer(index):
    loop, first = loop_at_theory(GroundedSpeaker(index, None))
    loop.on_student("phần nguyên là gì ạ?", NOW)
    again = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)  # no speaker: nothing is called again
    assert again.awaiting == Awaiting.THEORY_REPLY and again.current_turn().prompt == first.prompt


# --- through the API ----------------------------------------------------------------------------------

MINH = {"X-Demo-Student": "hs-minh"}
TEACHER = {"X-Demo-Teacher": "1"}


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)
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
    get_settings.cache_clear()


def test_a_question_through_the_session_api_is_answered_and_shown_to_the_teacher(client):
    created = client.post("/v1/sessions", json={"student_display_name": "Minh"}, headers=MINH).json()
    sid = created["session_id"]
    state = client.post(f"/v1/sessions/{sid}/join", headers=MINH).json()
    prompt = state["teaching"]["prompt"]
    body = {
        "item_attempt_id": state["teaching"]["input_id"],
        "kind": "ANSWER",
        "content": {"text": "phân số thập phân là gì ạ?"},
        "expected_state_version": state["state_version"],
    }
    sent = client.post(f"/v1/sessions/{sid}/responses", json=body, headers={**MINH, "Idempotency-Key": "q1"})
    assert sent.status_code == 200, sent.text
    state = client.get(f"/v1/sessions/{sid}/state", headers=MINH).json()
    assert state["teaching"]["awaiting"] == "THEORY_REPLY" and state["teaching"]["prompt"] == prompt
    assert state["transcript"][-1]["kind"] == "ANSWER" and state["transcript"][-1]["text"].endswith(prompt)

    transcript = client.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER).json()
    teach = [t["teach"] for s in transcript["segments"] for t in s["turns"] if t.get("teach")]
    answer = teach[-1]
    assert answer["kind"] == "ANSWER" and answer["source"] == "EXTRACT"  # no model in tests: a passage
    assert answer["grounded"] is True and answer["grounding"].startswith("độ phủ từ khóa")
    assert answer["sources"] and answer["parked"] is None


@pytest.mark.parametrize(
    ("text", "worrying"),
    [
        ("cô ơi con bị bạn đánh có nên nói với ai không?", True),
        ("con bi ban danh", True),
        ("bạn ấy bắt nạt con", True),
        ("con muốn chết", True),
        ("con đánh dấu phẩy ở đâu ạ", False),
        ("số bị chia là gì", False),
        ("con bị nhầm ạ", False),
        ("chán quá", False),
    ],
)
def test_worrying_words_are_told_from_lesson_words(text, worrying):
    assert signals_distress(text) is worrying


# --- REFORM-1b: the loop's fixed leads become a bridge when a speaker is live ------------------------------

FRAC = CHAPTER.node("KC-DEC-FRAC")


@pytest.mark.parametrize(
    ("said", "bridge", "judged"),
    [
        # "ko" to "phân số nào?" is "con không biết": was "Không sao đâu, cô giải thích nhé:"
        ("ko", "Con nói con chưa biết, không sao đâu nhé.", "chưa rõ"),
        ("4/100 ạ", "Con trả lời 4/100, con làm được rồi đấy.", "đúng"),  # was "Đúng rồi!"
        ("chán quá cô ơi", "Con thấy phần này hơi chán, cô hiểu mà.", "chưa rõ"),  # was theory_affect
    ],
)
def test_the_reply_to_a_theory_question_starts_with_a_bridge(index, said, bridge, judged):
    # REFORM-6: "ko" is taught again once first (the voice for that is down here); the bridge comes second
    router = ScriptedRouter(None, bridge) if said == "ko" else ScriptedRouter(bridge)
    loop, _ = loop_at_theory(GroundedSpeaker(index, router))
    if said == "ko":
        loop.on_student(said, NOW)
    feedback = loop.on_student(said, NOW).messages[0]
    assert (feedback.kind, feedback.source) == (MessageKind.FEEDBACK, "LLM")
    if judged == "đúng":
        assert feedback.text == f"{bridge} {FRAC.theory[0].reply}"  # a right answer: praise, then the reply
        assert f"[ĐÁNH GIÁ] {judged}" in router.user_text()
    else:
        assert feedback.text == bridge  # BRAIN-1: the model's turn is the whole turn
        assert FRAC.theory[0].reply in router.user_text()  # and the approved reply is its ground


def test_talk_outside_the_lesson_gets_a_bridge_then_the_same_question(index):
    router = ScriptedRouter("Con nói con thích đá bóng, chuyện đó để lúc nghỉ nhé.")
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    turn = loop.on_student("cô ơi con thích đá bóng lắm", NOW)
    assert turn.messages[0].source == "LLM" and turn.awaiting == Awaiting.THEORY_REPLY
    assert turn.messages[0].text == f"Con nói con thích đá bóng, chuyện đó để lúc nghỉ nhé. {first.prompt}"


def test_without_a_model_the_loop_keeps_its_approved_leads(index):
    loop, _ = loop_at_theory(GroundedSpeaker(index, ScriptedRouter()))  # the provider is down
    loop.on_student("ko", NOW)  # taught again once (REFORM-6)
    feedback = loop.on_student("ko", NOW).messages[0]
    assert feedback.source == "TEMPLATE"
    assert feedback.text == f"Không sao đâu, cô giải thích nhé: {FRAC.theory[0].reply}"


def test_a_retell_the_child_cannot_give_gets_a_bridge_then_the_main_idea(index):
    loop, _ = loop_at_theory(GroundedSpeaker(index, ScriptedRouter()))
    turn = loop.on_student("4/100", NOW)
    while turn.awaiting != Awaiting.RETELL:
        turn = loop.on_student(
            {Awaiting.THEORY_REPLY: "con nghĩ là được ạ"}.get(turn.awaiting, "con không biết"), NOW
        )
    loop.speaker = GroundedSpeaker(index, ScriptedRouter(None, "Con nói con chưa nhớ, không sao đâu nhé."))
    loop.on_student("con không nhớ ạ", NOW)  # the retell is kept and one part of the rule asked (REFORM-6)
    feedback = loop.on_student("con không nhớ ạ", NOW).messages[0]
    assert feedback.source == "LLM"
    assert feedback.text == "Con nói con chưa nhớ, không sao đâu nhé."
    goal = brain.child_voice(FRAC.description)  # the plan's goal, said to the child
    assert any(goal in r.messages[1].content for r in loop.speaker.router.requests)


# --- REFORM-1b: what a lead may and may not say -------------------------------------------------------------

# Seen live (Qwen 3.8 and gpt-oss-120b, 2026-10-26): a good lead on "ko" was refused as UNSUPPORTED_CLAIM and
# UNATTRIBUTED, though it repeats nothing the child said about the lesson.
REAL_LEAD = "Cô hiểu Vương chưa chắc chắn, mình cùng xem lại nhé."


def test_a_lead_on_how_the_child_feels_needs_no_idea_of_the_child_to_be_attributed(index):
    spoken = GroundedSpeaker(index, ScriptedRouter(REAL_LEAD), student_name="Vương").bridge(
        "ko", asked=T1_ASK, explanation=T1_REPLY, judged="chưa rõ", lead="Mình cùng xem lại nhé:"
    )
    assert spoken.source == "LLM" and spoken.text == REAL_LEAD


@pytest.mark.parametrize(
    ("said", "lead"),
    [
        ("4/10 ạ", "Phần tô màu là 4/10, mình cùng xem lại nhé."),  # the child's number, as the tutor's own
        ("dài hơn ạ", "Đoạn dây dài hơn, mình cùng xem lại nhé."),  # the child's idea, as the tutor's own
    ],
)
def test_a_lead_that_repeats_what_the_child_said_about_the_lesson_still_says_whose_it_is(index, said, lead):
    spoken = GroundedSpeaker(index, ScriptedRouter(lead, None)).bridge(
        said, asked=T1_ASK, explanation=T1_REPLY, judged="đúng", lead="Mình cùng xem lại nhé:"
    )
    assert spoken.source == "TEMPLATE" and "UNATTRIBUTED" in spoken.rejected[0]


def test_a_lead_before_a_right_answer_may_not_claim_something_about_the_lesson_with_ordinary_words(index):
    """The support check stays for a lead that says something about the lesson: here a rule of the chapter.
    (A turn that teaches again is free to explain: its arithmetic is what is checked.)"""
    lead = "Cô nói rồi, chia càng nhiều phần thì mỗi phần càng nhỏ đó con."
    spoken = GroundedSpeaker(index, ScriptedRouter(lead, None)).bridge(
        "ko", asked=T1_ASK, explanation=T1_REPLY, judged="đúng", lead="Mình cùng xem lại nhé:"
    )
    assert spoken.source == "TEMPLATE" and "UNSUPPORTED_CLAIM" in spoken.rejected[0]


class CappedRouter(ScriptedRouter):
    max_calls_per_session = 10


def test_a_lead_leaves_the_last_fifth_of_the_calls_to_explanations_and_questions(index):
    router = CappedRouter(REAL_LEAD)
    speaker = GroundedSpeaker(index, router, student_name="Vương", calls_used=8)  # the last 2 are kept
    spoken = speaker.bridge("ko", asked=T1_ASK, explanation=T1_REPLY, judged="chưa rõ", lead="Xem lại nhé:")
    assert spoken.source == "TEMPLATE" and spoken.text == f"Xem lại nhé: {T1_REPLY}"
    assert router.requests == [] and speaker.calls_made == 0
    again = GroundedSpeaker(index, CappedRouter(REAL_LEAD), student_name="Vương", calls_used=7)
    assert again.bridge("ko", asked=T1_ASK, explanation=T1_REPLY, judged="chưa rõ", lead=".").source == "LLM"


def test_the_words_about_feelings_are_free_only_in_a_bridge(index):
    """An answer to a question of the child keeps the strict list: "chắc chắn" there is a claim."""
    said = "Cô hiểu con ngại, khó và chưa chắc chắn."
    assert "UNSUPPORTED_CLAIM" in check(said, evidence(index, "phần nguyên là gì"), max_words=50)
    assert "UNSUPPORTED_CLAIM" not in check(
        said, evidence(index, "phần nguyên là gì"), max_words=50, bridge=True
    )
