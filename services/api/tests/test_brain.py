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
    router = ModelRouter(OTHER_WORDS, OTHER_WORDS.replace("bánh", "thước").replace("ăn", "tô"))
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
