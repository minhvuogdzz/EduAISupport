"""LLMRenderer (T06b) driven by a scripted FakeChatModel: no network, no API key.

The fake applies the same 3.000-token check as the real adapter, so every call here also proves the
prompt fits the Groq budget.
"""

from pathlib import Path

import pytest
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move
from cavat.modules.ai_gateway.base import ModelClass, QuotaExceeded
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter, default_chat_chains
from cavat.modules.content.lesson_package import OpenAnswer, load_lesson_package
from cavat.modules.tutor.contracts import (
    ItemState,
    MessageRenderer,
    PolicyDecision,
    RenderContext,
)
from cavat.modules.tutor.llm_renderer import (
    ANCHOR_SLACK,
    TEMPLATE_ONLY_MOVES,
    LLMRenderer,
    word_cap,
)
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"
PKG = load_lesson_package(LESSON)
TEMPLATE = TemplateRenderer()
QWEN, GPT_OSS = default_chat_chains()[ModelClass.TUTOR_REASONING]
LLM_MOVES = [m for m in Move if m not in TEMPLATE_ONLY_MOVES]
HINT_H3 = {"level": HintLevel.H3, "target": HintTarget.STRATEGY}

# A faithful rewording of the STRATEGY H3 template of GP-01 (the anchor of HINT_H3).
GOOD_HINT = (
    "Con thử viết 0,3 thành 0,30 để hai số cùng có hai chữ số ở phần thập phân nhé, "
    "rồi con so sánh 0,25 và 0,30 được không?"
)
GOOD_PROBE = "Con nói cho cô nghe con đã làm thế nào để ra câu trả lời đó được không?"
LEAK = "0,25 bé hơn 0,3 đó con. Con thấy chưa?"
# A faithful rewording of the CONCEPT H2 template of GP-01.
ON_ANCHOR_H2 = (
    "Khi hai số có phần nguyên bằng nhau, mình so sánh hàng nào trước, con nhỉ: "
    "hàng phần mười hay hàng phần trăm?"
)
SECRET_EXIT = PKG.items_for("EXIT")[0].model_copy(
    update={
        "id": "EX-T",
        "answer": OpenAnswer(type="open", rubric="RUBRIC-SECRET", sample_answer="SAMPLE-SECRET"),
        "worked_solution": ["WORKED-SECRET-1", "WORKED-SECRET-2"],
        "explanation": "EXPLANATION-SECRET",
        "verify_prompt": "VERIFY-SECRET?",
    }
)


def turn(message, safety_flag=False, policy_feedback=""):
    return {"message": message, "safety_flag": safety_flag, "policy_feedback": policy_feedback}


def ctx_for(item, move, student_text=None, **decision_kw):
    item = PKG.item(item) if isinstance(item, str) else item
    state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
    decision = PolicyDecision(move=move, **decision_kw)
    return RenderContext(decision=decision, item=item, package=PKG, state=state, student_text=student_text)


def make(script, *, max_calls=15, calls_used=0, student_name=None):
    fake = FakeChatModel(script)
    router = AIRouter(chat_provider=fake, max_calls_per_session=max_calls)
    renderer = LLMRenderer(
        router, TEMPLATE, validate_message, calls_used=calls_used, student_name=student_name
    )
    return renderer, fake


def user_prompt(fake, call):
    return fake.calls[call][1].messages[-1].content


@pytest.mark.parametrize("move", sorted(TEMPLATE_ONLY_MOVES))
def test_template_only_moves_never_call_the_model(move):
    renderer, fake = make([])
    ctx = ctx_for("GP-01", move, "0,25 < 0,3")
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert fake.calls == [] and renderer.calls_used == 0


def test_valid_model_output_is_used():
    renderer, fake = make([turn(GOOD_HINT)])
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)
    msg = renderer.render(ctx)
    assert (msg.text, msg.source) == (GOOD_HINT, "LLM")
    assert msg.hint_ref == TEMPLATE.render(ctx).hint_ref == "GP-01:STRATEGY:H3"
    assert renderer.calls_used == 1
    model, request = fake.calls[0]
    assert model == QWEN and request.json_schema is not None
    assert renderer.last_trace.fallback_reason is None and renderer.last_trace.rejected == ()


def test_llm_renderer_is_a_message_renderer():
    renderer: MessageRenderer = make([turn(GOOD_PROBE)])[0]
    assert renderer.render(ctx_for("GP-01", Move.PROBE, "0,25 > 0,3")).source == "LLM"


@pytest.mark.parametrize(
    ("item_id", "leaks"),
    [
        ("GP-01", [LEAK, "Đúng là 0,3 lớn hơn 0,25 rồi. Con hiểu chưa?"]),
        ("GP-09", ["Bạn An nói sai rồi, con biết vì sao không?", "Vậy An nhầm ở đâu, con thấy chưa?"]),
    ],
)
def test_answer_leak_is_blocked_then_the_template_is_used(item_id, leaks):
    renderer, fake = make([turn(t) for t in leaks])
    ctx = ctx_for(item_id, Move.HINT, "con không biết", **HINT_H3)
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert len(fake.calls) == 2 and renderer.calls_used == 2
    assert "[LẦN TRƯỚC BỊ TỪ CHỐI] ANSWER_LEAK" in user_prompt(fake, 1)
    assert renderer.last_trace.fallback_reason == "validation"
    assert [codes[0] for codes in renderer.last_trace.rejected] == ["ANSWER_LEAK", "ANSWER_LEAK"]


def test_retry_carries_the_codes_and_a_valid_second_answer_is_used():
    renderer, fake = make([turn(LEAK), turn(GOOD_HINT)])
    msg = renderer.render(ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3))
    assert (msg.text, msg.source) == (GOOD_HINT, "LLM")
    assert "[LẦN TRƯỚC BỊ TỪ CHỐI]" not in user_prompt(fake, 0)
    assert "[LẦN TRƯỚC BỊ TỪ CHỐI] ANSWER_LEAK (đã nêu đáp án)" in user_prompt(fake, 1)
    assert [codes[0] for codes in renderer.last_trace.rejected] == ["ANSWER_LEAK"]


def test_output_without_a_message_is_rejected_as_empty():
    renderer, _ = make([{"text": GOOD_HINT}, turn(GOOD_HINT)])
    assert renderer.render(ctx_for("GP-01", Move.HINT, **HINT_H3)).source == "LLM"
    assert renderer.last_trace.rejected == (("EMPTY",),)


def test_429_uses_the_template_at_once():
    renderer, fake = make(
        {QWEN: [QuotaExceeded("429", model=QWEN)], GPT_OSS: [QuotaExceeded("429", model=GPT_OSS)]}
    )
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert [model for model, _ in fake.calls] == [QWEN, GPT_OSS]  # the router's chain, no retry after it
    assert renderer.last_trace.fallback_reason == "quota_exceeded"
    assert renderer.calls_used == 2


def test_known_exhausted_quota_uses_the_template_without_any_call():
    renderer, fake = make([])
    for model in (QWEN, GPT_OSS):
        fake.quota.mark_exhausted(model, reset_at=None)
    ctx = ctx_for("GP-01", Move.PROBE, "0,25 > 0,3")
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert fake.calls == [] and renderer.last_trace.fallback_reason == "quota_exceeded"


def test_renderer_counts_its_calls_and_the_session_cap_falls_back_to_the_template():
    renderer, fake = make([turn(GOOD_PROBE)], max_calls=1)
    assert renderer.render(ctx_for("GP-01", Move.PROBE, "0,25 > 0,3")).source == "LLM"
    assert renderer.calls_used == 1
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert len(fake.calls) == 1 and renderer.last_trace.fallback_reason == "session_cap"


def test_calls_already_used_in_the_session_count_towards_the_cap():
    renderer, fake = make([], max_calls=15, calls_used=15)
    ctx = ctx_for("GP-01", Move.PROBE, "0,25 > 0,3")
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert fake.calls == [] and renderer.calls_used == 15


def test_cap_reached_before_the_retry_uses_the_template():
    renderer, fake = make([turn(LEAK)], max_calls=1)
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert len(fake.calls) == 1
    assert renderer.last_trace.fallback_reason == "session_cap"
    assert [codes[0] for codes in renderer.last_trace.rejected] == ["ANSWER_LEAK"]


def test_without_api_key_the_template_is_used():
    renderer = LLMRenderer(AIRouter(), TEMPLATE, validate_message)
    ctx = ctx_for("GP-01", Move.PROBE, "0,25 > 0,3")
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert renderer.last_trace.fallback_reason == "no_provider" and renderer.calls_used == 0


def test_safety_flag_is_kept_even_when_the_message_is_rejected():
    renderer, _ = make([turn(GOOD_HINT, safety_flag=True, policy_feedback="nên hỏi thăm")])
    renderer.render(ctx_for("GP-01", Move.HINT, "con buồn lắm", **HINT_H3))
    assert renderer.last_trace.safety_flag is True
    assert renderer.last_trace.policy_feedback == "nên hỏi thăm"

    renderer, _ = make([turn(LEAK, safety_flag=True), turn(LEAK)])
    assert renderer.render(ctx_for("GP-01", Move.HINT, "con buồn lắm", **HINT_H3)).source == "TEMPLATE"
    assert renderer.last_trace.safety_flag is True


def test_recent_turns_of_the_item_go_into_the_next_prompt():
    renderer, fake = make([turn(GOOD_PROBE), turn(GOOD_HINT), turn(GOOD_PROBE)])
    renderer.render(ctx_for("GP-01", Move.PROBE, "0,25 > 0,3"))
    renderer.render(ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3))
    second = user_prompt(fake, 1)
    assert "Học sinh: 0,25 > 0,3" in second and f"Gia sư: {GOOD_PROBE}" in second
    assert second.index("[HỘI THOẠI GẦN ĐÂY]") < second.index("[CON VỪA NÓI]")
    renderer.render(ctx_for("GP-02", Move.PROBE, "con chọn A"))
    assert "[HỘI THOẠI GẦN ĐÂY]" not in user_prompt(fake, 2)  # a new item starts a new conversation


def test_only_the_given_name_reaches_the_model():
    renderer, fake = make([turn(GOOD_PROBE)], student_name="Nguyễn Văn An")
    renderer.render(ctx_for("GP-01", Move.PROBE, "0,25 > 0,3"))
    sent = "\n".join(m.content for m in fake.calls[0][1].messages)
    assert "Tên gọi của học sinh: An." in sent
    assert "Nguyễn" not in sent and "Văn" not in sent


@pytest.mark.parametrize("move", LLM_MOVES)
def test_exit_items_never_call_the_model(move):
    """An assessment item gets the approved template only: nothing about it reaches the model."""
    renderer, fake = make([turn("Con đọc lại đề bài giúp cô nhé?")])
    ctx = ctx_for(SECRET_EXIT, move, "con không biết", level=HintLevel.H1, target=HintTarget.TASK)
    msg = renderer.render(ctx)
    assert not fake.calls and msg.source != "LLM" and renderer.calls_used == 0


def test_a_new_example_is_free_when_its_arithmetic_is_true_and_refused_when_it_is_not():
    """BRAIN-1 (D): the keyword and number checks of v8 are gone; what is checked is that a claim is true."""
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", level=HintLevel.H2, target=HintTarget.CONCEPT)
    wrong = "Con nhìn hàng phần mười nhé: 0,7 < 0,5 nên số 0,5 bé hơn. Còn 0,25 và 0,3 thì sao con?"
    true = "Con nhìn hàng phần mười nhé: 0,5 < 0,7 nên số 0,5 bé hơn. Còn 0,25 và 0,3 thì sao con?"
    renderer, fake = make([turn(wrong), turn(true)])
    msg = renderer.render(ctx)
    assert (msg.text, msg.source) == (true, "LLM")
    assert renderer.last_trace.rejected == (("WRONG_MATH",),)
    assert "WRONG_MATH (có phép tính hoặc so sánh sai)" in fake.calls[1][1].messages[1].content


def test_a_message_that_repeats_an_earlier_tutor_turn_is_rejected():
    """Real Qwen output: asked for a stronger hint, it sent back the sentence it had just said."""
    said = ON_ANCHOR_H2
    # v3: reworded freely, the anchor's terms kept ("mười hay trăm" alone would lose "hàng phần mười")
    fresh = (
        "Con ơi, khi phần nguyên của hai số bằng nhau thì mình so sánh hàng nào trước: "
        "hàng phần mười hay hàng phần trăm?"
    )
    renderer, fake = make([turn(said), turn(said.upper()), turn(fresh)])
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", level=HintLevel.H2, target=HintTarget.CONCEPT)
    assert renderer.render(ctx).text == said
    again = renderer.render(ctx)
    assert again.text == fresh and again.source == "LLM"
    assert renderer.last_trace.rejected == (("REPEATS_PREVIOUS",),)
    assert "REPEATS_PREVIOUS" in fake.calls[2][1].messages[1].content


def test_the_first_why_names_what_the_child_wrote_and_cannot_ask_about_the_comma_after_9_over_10():
    """The owner's session (2026-10-26): a child answered 9/10 and was asked why they put the comma."""
    ctx = ctx_for("GP-01", Move.VERIFY, "9/10", reason_codes=("CORRECT",))
    comma = "Con giải thích cho cô vì sao con đặt dấu phẩy ở chỗ đó được không?"
    named = "Con viết 9/10. Con nói cho cô nghe vì sao mẫu số lại là 10 vậy con?"
    renderer, fake = make([turn(comma), turn(named)])
    msg = renderer.render(ctx)
    assert (msg.text, msg.source) == (named, "LLM")
    assert renderer.last_trace.rejected == (("OFF_TARGET",),)
    assert "OFF_TARGET" in fake.calls[1][1].messages[1].content


@pytest.mark.parametrize(
    ("move", "decision"),
    [
        (Move.CLOSE_ITEM, {}),  # the item ends unresolved: the fixed words of calm
        (Move.CLOSE_ITEM, {"reason_codes": ("NO_EXPLANATION", "OFF_TOPIC")}),  # talk keeps its own lead
    ],
)
def test_fixed_words_are_said_with_the_template(move, decision):
    renderer, fake = make([turn(GOOD_HINT)])
    ctx = ctx_for("GP-01", move, "<", **decision)
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert fake.calls == [] and renderer.calls_used == 0


# REFORM-1 (Task 1.3): the moves that answer an unclear or empty reply are said by Qwen too.
@pytest.mark.parametrize(
    ("move", "decision", "said", "reply"),
    [
        (
            Move.ASK_CONFIRM,
            {},
            "ki",
            "Cô chưa hiểu chữ “ki” của con. Con muốn điền dấu nào giữa 0,25 và 0,3?",
        ),
        (Move.TEACH_BACK, {}, "<", "Con điền đúng rồi đó. Con kể cô nghe con đã so sánh hai số thế nào nhé?"),
        (
            Move.VERIFY,
            {"reason_codes": ("ASK_AGAIN",)},
            "là sao cô",
            "Cô hỏi con cách con nghĩ ra dấu đó thôi. Vì sao 0,25 bé hơn 0,3 hả con?",
        ),
        (
            Move.WORKED_GUIDANCE,
            {"level": HintLevel.H6, "target": HintTarget.STEP},
            "con không biết",
            "Không sao, mình cùng làm nhé. Phần nguyên đều là 0, ở hàng phần mười 0,25 có chữ số 2, "
            "còn 0,3 có chữ số 3. Vậy con điền dấu nào?",
        ),
    ],
)
def test_moves_that_answer_an_unclear_reply_are_said_by_the_model(move, decision, said, reply):
    renderer, fake = make([turn(reply)])
    msg = renderer.render(ctx_for("GP-01", move, said, **decision))
    assert (msg.text, msg.source) == (reply, "LLM") and len(fake.calls) == 1


def test_worked_guidance_still_may_not_give_the_last_step():
    leak = "Ở hàng phần mười 0,25 có chữ số 2, còn 0,3 có chữ số 3, nên 0,25 < 0,3. Con thấy chưa?"
    renderer, fake = make([turn(leak), turn(leak)])
    ctx = ctx_for("GP-01", Move.WORKED_GUIDANCE, "con không biết", level=HintLevel.H6, target=HintTarget.STEP)
    assert renderer.render(ctx) == TEMPLATE.render(ctx) and len(fake.calls) == 2
    assert all("ANSWER_LEAK" in codes for codes in renderer.last_trace.rejected)


# REFORM-1 (Task 1.2, DI-70): the anchor is what the turn must do, not words to keep.
def test_the_model_may_answer_the_childs_question_in_its_own_terms():
    """The owner's session: anchor "quay lại câu đang làm", the child asked what a word means. The answer
    used the child's term and was replaced by the template (NEW_MATH_TERM, OFF_ANCHOR)."""
    reply = "Hàng phần mười là chữ số đứng ngay sau dấu phẩy. Ở 0,25 và 0,3, chữ số hàng phần mười là mấy?"
    renderer, fake = make([turn(reply)])
    msg = renderer.render(ctx_for("GP-01", Move.REDIRECT, "hàng phần mười là gì cô"))
    assert (msg.text, msg.source) == (reply, "LLM") and renderer.last_trace.rejected == ()


def test_one_term_of_the_anchor_keeps_its_idea():
    """H2 CONCEPT anchor with six terms (phần nguyên, bằng nhau, so sánh, hàng, phần mười, phần trăm): v5
    asked for 60% of them."""
    reply = "Con nhìn chữ số ngay sau dấu phẩy của hai số trước nhé. Ở hàng phần mười, số nào lớn hơn?"
    renderer, fake = make([turn(reply)])
    msg = renderer.render(
        ctx_for("GP-01", Move.HINT, "con không biết", level=HintLevel.H2, target=HintTarget.CONCEPT)
    )
    assert (msg.text, msg.source) == (reply, "LLM")


def test_a_number_from_nowhere_is_allowed_when_it_is_not_a_false_claim():
    reply = "Con thử so sánh 0,25 với 0,7 trước nhé, rồi so sánh 0,25 và 0,30 được không?"
    renderer, _ = make([turn(reply)])
    assert renderer.render(ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)).source == "LLM"


# DI-60 (LLM-1): the S1 sessions rejected 16 of 20 drafts, all for form. The cap follows the anchor, and two
# form slips are repaired in place, the repaired text going through every check again.
NO_QUESTION_HINT = "Con thử viết 0,3 thành 0,30 để hai số cùng có hai chữ số ở phần thập phân nhé."
EM_HINT = GOOD_HINT.replace("Con thử", "Em thử").replace("rồi con", "rồi em")


def test_a_hint_without_its_question_is_asked_again_with_the_reason():
    renderer, fake = make([turn(NO_QUESTION_HINT), turn(GOOD_HINT)])
    msg = renderer.render(ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3))
    assert (msg.text, msg.source) == (GOOD_HINT, "LLM")
    assert renderer.last_trace.rejected == (("MISSING_QUESTION",),)


def test_the_child_called_em_is_refused_then_asked_again():
    renderer, fake = make([turn(EM_HINT), turn(GOOD_HINT)])
    msg = renderer.render(ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3))
    assert (msg.text, msg.source) == (GOOD_HINT, "LLM") and len(fake.calls) == 2
    assert renderer.last_trace.rejected == (("WRONG_ADDRESS",),)


def test_a_leak_is_refused_twice_and_the_template_is_said():
    leaky = LEAK.replace("Con thấy chưa?", "Em thấy chưa?")
    renderer, fake = make([turn(leaky), turn(leaky)])
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)
    assert renderer.render(ctx) == TEMPLATE.render(ctx) and len(fake.calls) == 2
    assert all("ANSWER_LEAK" in codes for codes in renderer.last_trace.rejected)


def test_the_word_cap_leaves_room_for_a_long_anchor():
    ctx = ctx_for("GP-01", Move.HINT, **HINT_H3)
    assert word_cap(ctx, "một hai ba") == 60
    assert word_cap(ctx, " ".join(["chữ"] * 52)) == 52 + ANCHOR_SLACK


def test_a_draft_cut_short_is_not_patched_with_a_question():
    cut = "Con thử viết 0,3 thành 0,30 để hai số cùng có"
    renderer, fake = make([turn(cut), turn(cut)])
    ctx = ctx_for("GP-01", Move.HINT, "con không biết", **HINT_H3)
    assert renderer.render(ctx) == TEMPLATE.render(ctx) and len(fake.calls) == 2


# DI-61 (LLM-2), DI-71 (REFORM-1): 40 calls a session; EXPLAIN and REDIRECT may use every one, every other
# move leaves them the last fifth (8 calls). PROBE and NUDGE no longer stop at the first third.
@pytest.mark.parametrize(
    ("move", "decision", "used", "calls"),
    [
        (Move.PROBE, {}, 20, 1),  # v5 stopped PROBE at a third of the cap
        (Move.PROBE, {}, 31, 1),
        (Move.PROBE, {}, 32, 0),
        (Move.HINT, HINT_H3, 31, 1),
        (Move.HINT, HINT_H3, 32, 0),
        (Move.REDIRECT, {}, 39, 1),
        (Move.EXPLAIN, {}, 39, 1),
    ],
)
def test_the_session_calls_are_kept_for_the_moves_that_need_them(move, decision, used, calls):
    renderer, fake = make(
        [turn(GOOD_HINT if move == Move.HINT else GOOD_PROBE)] * 2, max_calls=40, calls_used=used
    )
    renderer.render(ctx_for("GP-01", move, "cô ơi con thích đá bóng", **decision))
    assert (len(fake.calls) > 0) == (calls > 0)
    if calls == 0:
        assert renderer.last_trace.fallback_reason == "call_budget"


# REFORM-1b (DI-81): opening an item, praising a right answer and offering a hint or another try.
def test_the_offer_of_a_hint_or_another_try_is_said_by_the_model_and_keeps_both_choices():
    good = "Không sao đâu con, câu này hơi khó. Con muốn cô gợi ý thêm hay con tự thử lại một lần nữa?"
    one_choice = "Không sao đâu con. Con có muốn cô gợi ý thêm không?"
    renderer, fake = make([turn(good)])
    msg = renderer.render(ctx_for("GP-01", Move.OFFER_CHOICE, "con không biết"))
    assert (msg.text, msg.source) == (good, "LLM")
    renderer, fake = make([turn(one_choice), turn(one_choice)])
    ctx = ctx_for("GP-01", Move.OFFER_CHOICE, "con không biết")
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert all("CHOICE_MISSING" in codes for codes in renderer.last_trace.rejected)


def test_a_right_answer_is_praised_for_what_the_child_did():
    praise = "Đúng rồi, con so sánh từ hàng phần mười nên ra dấu bé hơn. Mình sang câu tiếp theo nhé!"
    renderer, fake = make([turn(praise)])
    msg = renderer.render(ctx_for("GP-01", Move.CONFIRM_ADVANCE, "vì 2 bé hơn 3 ở hàng phần mười"))
    assert (msg.text, msg.source) == (praise, "LLM")


def test_moving_on_asks_nothing():
    asks = "Đúng rồi, con làm cẩn thận lắm. Con sẵn sàng sang câu tiếp chưa?"
    renderer, fake = make([turn(asks), turn(asks)])
    ctx = ctx_for("GP-01", Move.CONFIRM_ADVANCE, "vì 2 bé hơn 3")
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert all("ASKS_ON_ADVANCE" in codes for codes in renderer.last_trace.rejected)


def test_an_explanation_the_child_could_not_give_is_taught_again_with_the_childs_numbers():
    """REFORM-2 (DI-68) then BRAIN-1: no praise, and not the approved text read out: the model explains."""
    ctx = ctx_for("GP-01", Move.CONFIRM_ADVANCE, "ki", reason_codes=("EXPLAIN_AND_ADVANCE",))
    taught = (
        "Cô nói lại cho dễ hiểu nhé. Hàng phần mười của 0,25 là 2, của 0,3 là 3, mà 2 < 3. "
        "Mình sang câu sau nhé!"
    )
    renderer, fake = make([turn(taught)])
    msg = renderer.render(ctx)
    assert (msg.text, msg.source) == (taught, "LLM")
    assert "chính số của câu" in user_prompt(fake, 0)  # the job: teach again with the numbers of the question
    praised = "Đúng rồi, con cố gắng lắm."
    renderer, fake = make([turn(praised), turn(praised)])
    assert renderer.render(ctx) == TEMPLATE.render(ctx)
    assert all("WRONG_PRAISE" in codes for codes in renderer.last_trace.rejected)


def test_an_item_is_opened_with_its_stem_and_no_call():
    """The item loop opens an item with no message of the child, and the CONFIRM_ADVANCE before it already
    says the move on (a lead for PRESENT never fired in the measured sessions: 24 opens, none with words)."""
    renderer, fake = make([turn("không được gọi")])
    assert Move.PRESENT in TEMPLATE_ONLY_MOVES
    assert renderer.render(ctx_for("GP-01", Move.PRESENT, "chán quá cô ơi")).text == PKG.item("GP-01").stem
    assert fake.calls == []
