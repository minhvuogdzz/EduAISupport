"""BRAIN-1 (ADR-034, DI-84): the tutor answers; the three faults the owner saw on 2026-10-26.

1. the first "vì sao" was a sentence fixed for the whole lesson ("…vì sao con đặt dấu phẩy ở chỗ đó"): a child
   who answered 9/10 was asked about the comma;
2. a child who answered right and could not say why was told only "Mình sang câu tiếp theo nhé.";
3. a child who asked "là sao nhỉ" heard the approved rule read again, word for word.

Offline: a scripted router stands in for the model, the real policy, checker and validator run.
"""

from datetime import UTC, datetime

import pytest
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.ai_gateway.base import ChatResult
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.content.lesson_package import NumericAnswer
from cavat.modules.session import chapter_service
from cavat.modules.tutor.brain import math_errors, names_childs_answer
from cavat.modules.tutor.item_loop import ItemTutor
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message
from test_grounded import FRAC, GroundedSpeaker, index, loop_at_theory  # noqa: F401  (index: a fixture)
from test_grounded import ScriptedRouter as ModelRouter

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
CHAPTER = chapter_service.chapters()["math-g5-decimals"]
BASE = CHAPTER.item("TP-PR-01")
MOVE_ON = "Mình sang câu tiếp theo nhé."
COMMA = "Đúng rồi! Con giải thích cho cô vì sao con đặt dấu phẩy ở chỗ đó được không?"
EXPLANATION = "Mẫu số 10 cho biết phần thập phân có một chữ số: chín phần mười viết là 0,9."


class ScriptedRouter:
    """Answers each request with the next scripted message (None: the provider is down)."""

    max_calls_per_session = 40

    def __init__(self, *messages: str | None) -> None:
        self.messages = list(messages)
        self.requests: list = []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append(request)
        message = self.messages.pop(0) if self.messages else None
        if message is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        data = {"message": message, "safety_flag": False, "policy_feedback": ""}
        return ChatOutcome(ChatResult("fake-model", message, data), None, 1)

    def user_text(self, i: int = -1) -> str:
        return self.requests[i].messages[1].content


def item_0_9(**update):
    """The item "0,9 = ……" asks 9/10, and its approved "vì sao" is about the comma."""
    fields = {
        "stem": "Viết số thập phân sau thành phân số thập phân (không rút gọn): a) 0,9 = ……",
        "answer": NumericAnswer(type="numeric", value="9/10", form="fraction"),
        "verify_prompt": COMMA,
        "hints": [],
        "explanation": EXPLANATION,
        "worked_solution": ["Mẫu số là 10 nên phần thập phân có một chữ số.", "Vậy 0,9 = 9/10."],
        "requires_explanation": True,
        **update,
    }
    return BASE.model_copy(update=fields)


def tutor(router, item=None) -> ItemTutor:
    item = item or item_0_9()
    renderer = LLMRenderer(router, TemplateRenderer(), validate_message)
    t = ItemTutor(
        item,
        CHAPTER.lesson_of(BASE.id),
        ActivityType.GUIDED_PRACTICE,
        renderer,
        validate_message,
        first_on_kc=True,
    )
    t.start()
    return t


# --- fault 1: the first "vì sao" is about what the child wrote ----------------------------------------------


def test_the_first_why_is_written_from_the_childs_answer_not_the_fixed_sentence():
    asked = "Con viết 9/10. Con nói cho cô nghe vì sao 0,9 lại viết được thành 9/10, mẫu số 10 từ đâu ra?"
    router = ScriptedRouter(asked)
    turn = tutor(router).on_student("9/10")
    assert turn.move == Move.VERIFY and turn.text == asked and turn.text != COMMA
    prompt = router.user_text()
    assert "Câu trả lời của con" in prompt and "ĐÚNG" in prompt and "9/10" in prompt
    assert (
        "dấu phẩy" in prompt
    )  # the teacher's own "vì sao" is a ground, an idea to rest on, not words to read


def test_a_why_about_the_comma_is_refused_when_the_child_wrote_a_fraction():
    comma = "Con giải thích cho cô vì sao con đặt dấu phẩy ở chỗ đó được không?"
    named = "Cô thấy con viết 9/10. Vì sao mẫu số lại là 10 hả con?"
    router = ScriptedRouter(comma, named)
    turn = tutor(router).on_student("9/10")
    assert turn.text == named and len(router.requests) == 2
    assert "OFF_TARGET" in router.user_text(1)


def test_when_no_model_can_speak_the_approved_why_is_said():
    turn = tutor(ScriptedRouter()).on_student("9/10")
    assert turn.move == Move.VERIFY and turn.text == COMMA  # the fallback is the teacher's sentence


@pytest.mark.parametrize(
    ("question", "said", "named"),
    [
        ("Vì sao con đặt dấu phẩy ở chỗ đó?", "9/10", False),
        ("Vì sao con viết 9/10?", "9/10", True),
        ("Mẫu số 10 từ đâu ra vậy con?", "9/10", True),  # a part of the fraction the child wrote
        ("Con giải thích giúp cô nhé?", "con làm theo cách hôm qua", True),  # no number to name
    ],
)
def test_a_question_names_a_number_the_child_wrote(question, said, named):
    assert names_childs_answer(question, said) is named


# --- fault 2: a child who cannot say why is taught again, never only moved on -----------------------


def stuck(t: ItemTutor):
    """The child answered right, then says twice that they do not know why."""
    t.on_student("9/10")
    turn = t.on_student("con không biết")
    while not turn.resolved:
        turn = t.on_student("con không biết")
    return turn


def test_a_child_who_cannot_say_why_is_taught_again_with_the_numbers_of_the_question():
    taught = (
        "Không sao con nhé. 0,9 có một chữ số sau dấu phẩy, nên là 9 phần mười, viết 9/10. "
        "Mình sang câu sau nhé."
    )
    router = ScriptedRouter("Con viết 9/10, vì sao mẫu số lại là 10 hả con?", taught)
    turn = stuck(tutor(router))
    assert turn.move == Move.CLOSE_ITEM and turn.text == taught
    assert "chính số của câu" in router.user_text() and EXPLANATION in router.user_text()


def test_a_taught_again_turn_with_a_wrong_calculation_is_refused():
    wrong = "Không sao con nhé. 0,9 = 9/100, nên mình sang câu sau."
    router = ScriptedRouter(None, None, wrong, wrong)
    turn = stuck(tutor(router))
    assert turn.text != wrong and turn.text != MOVE_ON


@pytest.mark.parametrize(
    "item",
    [
        item_0_9(),
        item_0_9(explanation=None),  # only the worked steps
        item_0_9(explanation=None, worked_solution=[]),  # nothing approved on the item: its answer, at least
    ],
)
def test_without_a_model_the_item_still_ends_with_the_idea_said_again(item):
    turn = stuck(tutor(ScriptedRouter(), item))
    assert turn.move == Move.CLOSE_ITEM and turn.text != MOVE_ON
    assert turn.text.endswith("Bây giờ mình sang câu tiếp theo nhé!")
    assert "9/10" in turn.text or "một chữ số" in turn.text


# --- the net ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "wrong"),
    [
        ("Vì 0,9 = 9/10 nên con viết đúng rồi.", []),
        ("0,9 = 9/10 = 90/100 = 900/1000", []),
        ("0,25 bé hơn 0,3 vì 0,25 < 0,30", []),
        ("2 × 5 = 10 và 10 - 3 = 7", []),
        ("0,9 = 9 phần 10 nhé con", []),  # a phrase, not a value to compare
        ("Con viết 0,9 = 9 là chưa đúng", ["0,9 = 9"]),
        ("3/4 < 1/2 con nhé", ["3/4 < 1/2"]),
        ("1,25 lớn hơn 1,3 đó", ["1,25 lớn hơn 1,3"]),
        ("3 + 4 = 8", ["3 + 4 = 8"]),
        ("5 cm + 3 cm = 8 cm", []),
    ],
)
def test_the_arithmetic_of_a_turn_is_checked_exactly(text, wrong):
    assert math_errors(text) == wrong


# --- fault 3: "là sao nhỉ" is explained in other words, the approved rule is not read out ------------

REPLY = FRAC.theory[0].reply
OTHER_WORDS = (
    "Cô nói lại cho dễ nhé: lấy một cái bánh chia làm 10 phần bằng nhau, con ăn 3 phần thì là 3/10. "
    "Mẫu số 10 là số phần bằng nhau của cả cái bánh."
)


def test_a_child_who_asks_la_sao_is_explained_in_other_words_not_read_the_rule(index):  # noqa: F811
    second = (
        "Thử nghĩ về cái thước nhé: thước dài 1 m chia làm 10 đoạn bằng nhau, tô 3 đoạn thì là 3/10. "
        "Mẫu số 10 là số đoạn bằng nhau của cả cái thước."
    )
    router = ModelRouter(OTHER_WORDS, second)
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    for _ in range(2):  # the first "là sao nhỉ" teaches again (REFORM-6), the second answers and goes on
        turn = loop.on_student("là sao nhỉ", NOW)
        said = turn.messages[0]
        assert said.source == "LLM" and REPLY not in said.text
        assert "bánh" in said.text or "thước" in said.text
    assert any(REPLY in r.messages[1].content for r in router.requests)  # the approved text is the ground
    assert all("[CĂN CỨ ĐÃ DUYỆT]" in r.messages[1].content for r in router.requests)


def test_reading_the_rule_back_to_the_child_is_refused_and_the_arithmetic_is_checked(index):  # noqa: F811
    read_out = f"Cô nhắc lại nhé: {REPLY}"
    router = ModelRouter(read_out, "3/10 = 3/100 nhé con.", None)
    spoken = GroundedSpeaker(index, router).teach(
        "là sao nhỉ",
        asked=FRAC.theory[0].ask,
        ground=REPLY,
        judged="chưa rõ",
        lead="Cô nói theo cách khác nhé:",
    )
    assert spoken.source == "TEMPLATE" and spoken.text == f"Cô nói theo cách khác nhé: {REPLY}"
    assert spoken.rejected == (("COPIES_GROUND",), ("WRONG_MATH",))


# --- rule 2 and the record -------------------------------------------------------------------------------


def test_the_answer_and_the_solution_of_an_unsolved_item_never_reach_the_prompt():
    """An item the child has not solved: the explanation and the worked steps stay out of the pack."""
    router = ScriptedRouter("Con đọc lại đề rồi nói cô nghe 0,9 có mấy chữ số sau dấu phẩy nhé?")
    turn = tutor(router).on_student("9/100")  # wrong
    assert turn.text.startswith("Con đọc lại đề") or turn.move != Move.CLOSE_ITEM
    prompt = "\n".join(m.content for r in router.requests for m in r.messages)
    assert EXPLANATION not in prompt and "Vậy 0,9 = 9/10." not in prompt
    assert "CHƯA ĐÚNG" in prompt


def test_the_model_that_wrote_a_message_is_in_the_event_and_a_template_names_none():
    t = tutor(ScriptedRouter("Con viết 9/10. Vì sao mẫu số lại là 10 hả con?"))
    turn = t.on_student("9/10")
    sent = [e for e in turn.events if e.type.value == "TUTOR_MESSAGE_SENT"][0].payload
    assert sent["source"] == "LLM" and sent["model"] == "fake-model"
    fallback = tutor(ScriptedRouter()).on_student("9/10")
    sent = [e for e in fallback.events if e.type.value == "TUTOR_MESSAGE_SENT"][0].payload
    assert sent["source"] != "LLM" and sent["model"] is None


def test_the_owner_chooses_the_voice_with_one_line(monkeypatch):
    from cavat.config import Settings
    from cavat.modules.ai_gateway.base import ModelClass
    from cavat.modules.ai_gateway.router import ChatDispatcher, build_router

    for name in ("TUTOR_MODELS", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(
        _env_file=None,
        groq_api_key="gsk_test",
        gemini_api_key="gm_test",
        tts="off",
        tutor_models="openai/gpt-oss-120b, gemini-3.8-flash",
    )
    router = build_router(settings)
    assert router.chain(ModelClass.TUTOR_REASONING) == ("openai/gpt-oss-120b", "gemini-3.8-flash")
    assert isinstance(router._chat, ChatDispatcher) and router._chat._gemini is not None
    # not asked for, Gemini is not given the children's words
    plain = build_router(
        Settings(_env_file=None, groq_api_key="gsk_test", gemini_api_key="gm_test", tts="off")
    )
    assert plain._chat._gemini is None


# --- the owner's two cases of 2026-10-26 (account "Nam"): G, a long stem with a figure; D, a retell ----

from cavat.core.pedagogy import Outcome  # noqa: E402
from cavat.modules.assessment.math_checker import classify_intent  # noqa: E402
from cavat.modules.assessment.student_intent import wants_other_question  # noqa: E402
from cavat.modules.teaching.loop import Awaiting, TeachingLoop  # noqa: E402
from cavat.modules.tutor.brain import child_voice, teacher_voice  # noqa: E402
from cavat.modules.tutor.renderer import visible_stem  # noqa: E402

LONG_STEM = (
    "[Hình: Hình 1: Tam giác ABC nhọn, đường cao AH nét đứt vuông góc với đáy BC tại H nằm trong đoạn BC. "
    "Hình 2: Tam giác DEF vuông tại D, đường cao là cạnh DE. Hình 3: Tam giác MNP tù, đường cao MK nằm ngoài "
    "tam giác.] Trong ba hình tam giác trên, hình nào có đường cao nằm ngoài tam giác?"
)
GOAL = "Bé nhận ra 3/10, 27/100 viết được thành 0,3 và 0,27. Bé đọc, viết được số thập phân đơn giản."


def test_a_long_stem_with_a_figure_is_asked_again_by_its_question_only():
    shown = visible_stem(LONG_STEM)
    assert (
        "[Hình" not in shown
        and shown == "Trong ba hình tam giác trên, hình nào có đường cao nằm ngoài tam giác?"
    )
    assert visible_stem("Viết 0,9 thành phân số thập phân.") == "Viết 0,9 thành phân số thập phân."


def test_the_tutor_never_prints_the_whole_stem_again_after_la_sao():
    item = item_0_9(
        stem=LONG_STEM, answer=NumericAnswer(type="numeric", value="3", form=None), verify_prompt=None
    )
    router = ScriptedRouter(
        "Mình tìm hình có đường cao nằm ngoài tam giác. Con nhìn xem hình nào có đường cao nằm ngoài nhé?"
    )
    t = tutor(router, item)
    turn = t.on_student("là sao")
    assert "[Hình" not in turn.text and len(turn.text.split()) < 40
    assert "Tam giác ABC nhọn" in router.user_text()  # the description stays the brain's context
    plain = tutor(ScriptedRouter(), item).on_student("là sao")  # no model: the template says the question
    assert "[Hình" not in plain.text and "Tam giác ABC" not in plain.text


def test_a_model_that_reads_the_figure_description_out_is_refused():
    read = "Hình 1: Tam giác ABC nhọn, đường cao AH. [Hình: Tam giác ABC] Con chọn hình nào?"
    router = ScriptedRouter(read, "Con nhìn lại ba hình rồi chọn hình có đường cao ở ngoài nhé?")
    item = item_0_9(
        stem=LONG_STEM, answer=NumericAnswer(type="numeric", value="3", form=None), verify_prompt=None
    )
    turn = tutor(router, item).on_student("là sao")
    assert "[Hình" not in turn.text and "FIGURE_TEXT" in router.user_text(1)


@pytest.mark.parametrize(
    "text",
    [
        GOAL,
        "Cô nhắc lại nhé: Bé nhận ra 3/10 viết được thành 0,3.",
        "Học sinh biết so sánh hai số thập phân.",
    ],
)
def test_a_goal_written_for_the_teacher_is_never_read_to_the_child(text):
    assert teacher_voice(text)
    assert not teacher_voice(child_voice(text))
    assert child_voice(GOAL).startswith("Con nhận ra 3/10")


def test_the_retell_fallbacks_say_the_goal_to_the_child_not_as_the_plan_writes_it(index):  # noqa: F811
    """The owner's case D4: "Cô nhắc lại đúng nhé: Bé nhận ra 3/10…" was read out."""
    loop = TeachingLoop(CHAPTER, "s1")
    turn = loop.start(NOW)
    said = []
    for _ in range(14):
        reply = {Awaiting.THEORY_REPLY: "con nghĩ là được ạ"}.get(turn.awaiting, "con không biết")
        turn = loop.on_student(reply, NOW)
        said += [m.text for m in turn.messages]
        if turn.awaiting == Awaiting.NOTHING:
            break
    assert said and not [t for t in said if teacher_voice(t)]


@pytest.mark.parametrize(
    "text", ["hỏi cái khác mà", "cô hỏi khác đi", "đổi câu khác đi cô", "hỏi cách khác đi"]
)
def test_a_child_who_asks_for_another_question_is_understood(text):
    assert wants_other_question(text)
    assert not wants_other_question("con không biết")


def test_talk_about_the_time_is_outside_the_lesson():
    assert classify_intent("mấy giờ rồi") == Outcome.OFF_TOPIC


def test_a_child_who_asks_the_time_in_a_wait_is_answered_like_a_person_then_the_question_waits(index):  # noqa: F811
    router = ModelRouter("Giờ này cô không xem được đâu con, mình làm tiếp nhé.")
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    turn = loop.on_student("mấy giờ rồi", NOW)
    said = turn.messages[0]
    assert (
        said.source == "LLM"
        and said.text == f"Giờ này cô không xem được đâu con, mình làm tiếp nhé. {first.prompt}"
    )
    assert turn.awaiting == Awaiting.THEORY_REPLY and REPLY not in said.text


def test_a_child_who_wants_another_question_gets_the_same_idea_asked_another_way(index):  # noqa: F811
    again = "Được con, cô hỏi cách khác nhé: một phân số có mẫu số 10, 100 hay 1000 thì mình gọi là gì?"
    router = ModelRouter(again)
    loop, first = loop_at_theory(GroundedSpeaker(index, router))
    turn = loop.on_student("hỏi cái khác mà", NOW)
    said = turn.messages[0]
    assert said.source == "LLM" and said.text == again and turn.awaiting == Awaiting.THEORY_REPLY
    assert not teacher_voice(said.text) and turn.prompt == first.prompt  # the wait is the approved question
    fallback_loop, first = loop_at_theory(GroundedSpeaker(index, ModelRouter()))  # no model
    said = fallback_loop.on_student("hỏi cái khác mà", NOW).messages[0]
    assert said.source == "TEMPLATE" and said.text == f"Được con, cô hỏi lại nhé: {first.prompt}"


def test_the_invitation_to_say_it_back_is_written_for_what_the_child_did(index):  # noqa: F811
    node = CHAPTER.node("KC-DEC-FRAC")
    invite = "Con vừa làm đúng 7/10 rồi đó. Con nói lại cho cô nghe, phân số thập phân là phân số thế nào?"
    spoken = GroundedSpeaker(index, ModelRouter(invite)).invite_retell(
        node, prompt=node.explain.prompt, recent=[("student", "7/10")]
    )
    assert (spoken.text, spoken.source) == (invite, "LLM")
    # the goal read out, then a question about something else: both refused, the plan's sentence stays
    router = ModelRouter(GOAL, "Hôm nay trời đẹp quá phải không?")
    refused = GroundedSpeaker(index, router).invite_retell(node, prompt=node.explain.prompt)
    assert (
        refused.text == "" and "TEACHER_VOICE" in refused.rejected[0] and "OFF_TARGET" in refused.rejected[1]
    )


def test_a_tutor_on_a_script_is_refused_the_same_opening_twice():
    from cavat.modules.tutor.brain import repeats
    from cavat.modules.tutor.prompt_builder import Turn

    said = [Turn("tutor", "Cô thấy con viết 7/10. Vì sao mẫu số lại là 10?"), Turn("student", "vì có một số")]
    assert repeats("Cô thấy con viết 0,3 rồi. Con nói cô nghe vì sao nhé?", said)
    assert not repeats("7/10, đúng rồi con. Mẫu số 10 từ đâu ra vậy?", said)
