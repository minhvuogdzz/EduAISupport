"""ENG-5h (ADR-071, DI-165–176): the faults of the English session left after the second live run of the
student Vuong (session 01a1e020…, cavat_dev, 15/11/2026, main f9be05d). One test or a few per fault, on the
words the child and the model really said that day (read from the session's events). Offline: the template
renderer, scripted model outputs, no network.

1. a feeling ("con đói quá cô ơi", "hôm nay con buồn") not answered: DI-165
2. "We ate seafod." told to answer "bằng một câu trọn vẹn": DI-166
3. CONFIRM_ADVANCE telling what comes next ("sang việc cả nhà đi dạo biển"): DI-170
4. "Chưa đúng. They seashells collected." praised without the word order: DI-167
5. hints that do not climb, the same words again: DI-170
6. an English question the lesson does not have, an emoji: DI-171, DI-172
7. "trả lời giúp cô câu này nhé: Con thử nói theo cô nha?": DI-173
8. "Câu có 'yesterday'…" on an item without yesterday: DI-168
9. "Con thử nói lại theo cô nhé" and then the next question: DI-169, DI-170
10. the retell's missing idea pasted with the whole list of phrases: DI-173
11. the parent's report: DI-176 (test_english_parent_report.py has the API side)
12. Gemini HTTP 400 "api version v1", three MODEL_FALLBACK a turn: DI-174, DI-175
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move, Outcome
from cavat.modules.ai_gateway.base import ChatResult, Usage
from cavat.modules.ai_gateway.router import ChatOutcome
from cavat.modules.assessment.answer_check import check_answer
from cavat.modules.session import chapter_service
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
from cavat.modules.tutor.english import SAY_AFTER_ME_LADDER, task_for_en
from cavat.modules.tutor.english_session import (
    EnglishRenderer,
    english_tools,
    knowledge_tools,
    loop_options,
    session_validator,
)
from cavat.modules.tutor.english_validator import validator_for
from cavat.modules.tutor.item_loop import ItemTutor, Phase
from cavat.modules.tutor.policy import DEFAULT_CONFIG
from cavat.modules.tutor.prompt_builder import Turn
from cavat.modules.tutor.renderer import TemplateRenderer, counter_example, feeling_of

UNIT = "eng-g5-u11-family-time"
NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
BOAT = "We took a boat trip around the bay."


def unit():
    return chapter_service.chapters("english")[UNIT]


MATH = chapter_service.chapters()[chapter_service.DEFAULT_CHAPTER_ID]


def tutor(item_id: str, renderer=None, **kw) -> ItemTutor:
    ch = unit()
    validator = session_validator(knowledge_tools(english_tools(ch), True).lexicon)
    return ItemTutor(
        ch.item(item_id), ch.lesson_of(item_id), ActivityType.GUIDED_PRACTICE, renderer or TemplateRenderer(),
        validator, DEFAULT_CONFIG, **kw,
    )  # fmt: skip


def ctx(item_id: str, move: Move, *, student="", check=None, level=None, reasons=(), attempt=1):
    ch = unit()
    item = ch.item(item_id)
    return RenderContext(
        decision=PolicyDecision(move=move, level=level, target=HintTarget.TASK, reason_codes=tuple(reasons)),
        item=item,
        package=ch.lesson_of(item_id),
        state=ItemState(item_id=item_id, activity=ActivityType.GUIDED_PRACTICE, attempt_no=attempt),
        student_text=student,
        check=check,
        solved=check is not None and check.outcome == Outcome.CORRECT,
    )


class ScriptedRouter:
    """Answers each TUTOR_REASONING request with the next scripted message."""

    def __init__(self, messages):
        self.messages, self.requests = list(messages), []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append(request)
        text = self.messages.pop(0) if self.messages else ""
        data = {"message": text, "safety_flag": False, "policy_feedback": ""}
        result = ChatResult(
            model="m", text=json.dumps(data, ensure_ascii=False), data=data, usage=Usage(1, 1, 2)
        )
        return ChatOutcome(result=result if text else None, fallback_reason=None, calls_made=1)


def brain(messages, *, history=(), item=None, name="Vuong") -> tuple[EnglishRenderer, ScriptedRouter]:
    router = ScriptedRouter(messages)
    tools = knowledge_tools(english_tools(unit()), True)
    renderer = EnglishRenderer(
        router,
        TemplateRenderer(),
        validator_for("english", lexicon=tools.lexicon),
        tools,
        student_name=name,
        history=history,
        history_item=item,
    )
    return renderer, router


def rejected(renderer: EnglishRenderer) -> set[str]:
    return {code for group in renderer.last_trace.rejected for code in group}


# ------------------------------------------------------------- 1. a feeling first (DI-165)


@pytest.mark.parametrize(("said", "word"), [("con đói quá cô ơi", "đói"), ("hôm nay con buồn", "buồn")])
def test_a_feeling_is_answered_before_the_lesson_and_the_sentence_is_not_read_again(said, word):
    t = tutor("U11-VO-CP-01")
    t.start()
    turn = t.on_student(said, 5)
    assert word in turn.text, turn.text
    assert BOAT not in turn.text and "con có muốn" not in turn.text.lower(), turn.text
    assert feeling_of(said) == word


def test_the_models_answer_to_a_hungry_child_must_hear_the_feeling():
    """Live: REDIRECT for "con đói quá cô ơi" was "Con có muốn thử nói câu We took… không?" (gpt-oss-20b)."""
    bad = "Con có muốn thử nói câu We took a boat trip around the bay không?"
    good = "Con đói bụng rồi à, cô hiểu mà. Mình làm nốt câu này rồi con đi ăn nhé, được không?"
    renderer, router = brain([bad, good])
    message = renderer.render(ctx("U11-VO-CP-01", Move.REDIRECT, student="con đói quá cô ơi"))
    assert message.source == "LLM" and message.text == good
    assert "FEELING_IGNORED" in rejected(renderer)
    assert "cảm giác" in router.requests[0].messages[1].content  # the task says what to answer first


def test_a_mathematics_turn_does_not_read_feelings_this_way():
    pkg, item = next((lesson, i) for lesson in MATH.lessons.values() for i in lesson.items)
    math_ctx = RenderContext(
        decision=PolicyDecision(move=Move.REDIRECT, reason_codes=("OFF_TOPIC",)),
        item=item,
        package=pkg,
        state=ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE),
        student_text="con đói quá cô ơi",
    )
    assert "đói" not in TemplateRenderer().render(math_ctx).text


# ------------------------------------------------------------- 2. a spelling slip (DI-166)


def test_a_spelling_slip_is_named_not_asked_for_a_whole_sentence():
    ch = unit()
    check = check_answer(ch.item("U11-VO-PR-02"), "We ate seafod.", ch.lesson_of("U11-VO-PR-02"))
    assert check.detail["en_code"] == "EN_SLIP" and check.detail["slips"] == ["seafod"]
    text = TemplateRenderer().render(ctx("U11-VO-PR-02", Move.HINT, check=check, level=HintLevel.H2)).text
    assert "seafod" in text and "chính tả" in text and "trọn vẹn" not in text, text
    assert "seafood" not in text  # the right spelling is the child's to find


def test_the_live_hint_after_seafod_names_the_spelling():
    t = tutor("U11-VO-PR-02")
    t.start()
    t.on_student("We eat seafood.", 5)
    turn = t.on_student("We ate seafod.", 5)
    assert "chính tả" in turn.text and "trọn vẹn" not in turn.text, turn.text


def test_a_model_hint_that_misses_the_slip_is_refused():
    renderer, _ = brain(["Con trả lời bằng một câu tiếng Anh trọn vẹn giúp cô nhé?"] * 3)
    ch = unit()
    check = check_answer(ch.item("U11-VO-PR-02"), "We ate seafod.", ch.lesson_of("U11-VO-PR-02"))
    message = renderer.render(
        ctx("U11-VO-PR-02", Move.HINT, student="We ate seafod.", check=check, level=HintLevel.H2)
    )
    assert "MISSES_SLIP" in rejected(renderer) and "chính tả" in message.text


# ------------------------------------------------------------- 3. CONFIRM_ADVANCE never tells what comes next


def test_confirm_advance_does_not_promise_the_next_question():
    live = (
        "A, con nhớ đúng chữ ate rồi đấy! Cô thấy con kiên trì lắm. Giờ mình thử chuyển sang việc cả nhà đi "
        "dạo biển nhé."
    )
    good = "Con nhớ đúng chữ ate rồi đấy, cô thấy con kiên trì lắm! Mình sang câu tiếp theo nhé."
    renderer, _ = brain([live, good])
    ch = unit()
    check = check_answer(ch.item("U11-VO-PR-02"), "We ate seafood.", ch.lesson_of("U11-VO-PR-02"))
    message = renderer.render(
        ctx("U11-VO-PR-02", Move.CONFIRM_ADVANCE, student="We ate seafood.", check=check, attempt=3)
    )
    assert message.text == good and "PREVIEWS_NEXT" in rejected(renderer)
    assert "Không nói trước câu sau" in task_for_en(Move.CONFIRM_ADVANCE)


# ------------------------------------------------------------- 4. the word order of a correction (DI-167)


def test_a_correction_in_a_wrong_word_order_is_named():
    ch = unit()
    item = ch.item("U11-VO-PR-04")
    check = check_answer(item, "Chưa đúng. They seashells collected.", ch.lesson_of(item.id))
    assert check.outcome == Outcome.CORRECT  # the item grades the judgment: unchanged
    assert check.detail["word_order"] == "They collected seashells."
    right = check_answer(item, "Chưa đúng. They collected seashells.", ch.lesson_of(item.id))
    assert "word_order" not in right.detail
    t = tutor("U11-VO-PR-04")
    t.start()
    turn = t.on_student("Chưa đúng. They seashells collected.", 5)
    assert turn.move == Move.VERIFY and "trật tự" in turn.text and "They collected seashells." in turn.text


def test_the_live_praise_without_the_word_order_is_refused():
    live = "Con đã nói đúng! Nhớ rằng buy là mua, còn collect là nhặt. Con làm sao nhớ được sự khác nhau này?"
    renderer, router = brain([live] * 3)
    ch = unit()
    check = check_answer(
        ch.item("U11-VO-PR-04"), "Chưa đúng. They seashells collected.", ch.lesson_of("U11-VO-PR-04")
    )
    renderer.render(
        ctx("U11-VO-PR-04", Move.VERIFY, student="Chưa đúng. They seashells collected.", check=check)
    )
    assert "MISSES_WORD_ORDER" in rejected(renderer)
    # a live gpt-oss-20b answer of 16/11: praise of the order itself is no naming of the error
    praise = (
        "Chúc mừng Vuong, câu của con đúng rồi! Bạn đã sắp xếp từ đúng rồi. "
        "Con có thể cho mình biết vì sao không?"
    )
    renderer, _ = brain([praise] * 3)
    renderer.render(
        ctx("U11-VO-PR-04", Move.VERIFY, student="Chưa đúng. They seashells collected.", check=check)
    )
    assert "MISSES_WORD_ORDER" in rejected(renderer)
    assert "trật tự" in router.requests[0].messages[1].content  # the verdict tells the model


# ------------------------------------------------------------- 5. hints climb, words are not said again


def test_the_help_of_a_say_after_me_item_climbs_with_the_level():
    tasks = [task_for_en(Move.HINT, level=lv, say_after_me=True) for lv in (1, 2, 3, 4, 6)]
    tasks.append(task_for_en(Move.FULL_EXPLANATION, level=7, say_after_me=True))
    assert len(set(tasks)) == 5  # 1, 2, 3 (and 4), 5 (6), 7
    assert tasks[0].startswith(SAY_AFTER_ME_LADDER[1]) and tasks[-1].startswith(SAY_AFTER_ME_LADDER[7])


def test_the_same_hint_twice_is_refused():
    """Live: HINT/3 and HINT/4 on U11-VO-CP-01 were the same words, letter for letter."""
    live = (
        "Con ơi, cô đọc mẫu cho con nghe nhé. Câu này kể chuyện đi thuyền: "
        "We took a boat trip around the bay. "
        "Con thử nói theo cô nha?"
    )
    history = (Turn("tutor", live), Turn("student", "cô cho con đáp án luôn đi"))
    renderer, _ = brain([live] * 3, history=history, item="U11-VO-CP-01")
    renderer.render(ctx("U11-VO-CP-01", Move.HINT, student="cô cho con đáp án luôn đi", level=HintLevel.H4))
    assert "REPEATS_EARLIER" in rejected(renderer)


def test_the_model_sentence_said_twice_is_not_read_again_in_a_hint():
    history = (
        Turn("tutor", "Cô đọc trước, con nói theo cô cả câu nhé: We took a boat trip around the bay."),
        Turn("tutor", "Con ơi, câu này kể chuyện đi thuyền quanh vịnh: We took a boat trip around the bay."),
    )
    again = "Cô chia nhỏ nhé, phần đầu là took a boat trip: We took a boat trip around the bay. Con nói nhé?"
    chunks = (
        "Cô chia nhỏ nhé: took a boat trip là đi thuyền, around the bay là quanh vịnh. Con nói từng phần nhé?"
    )
    renderer, _ = brain([again, chunks], history=history, item="U11-VO-CP-01")
    message = renderer.render(ctx("U11-VO-CP-01", Move.HINT, level=HintLevel.H2))
    assert message.text == chunks and "REPEATS_EARLIER" in rejected(renderer)


# ------------------------------------------------------------- 6. invented English, emoji (DI-171, DI-172)


def test_an_english_question_the_item_does_not_have_is_refused():
    live = (
        "Con nói đúng rồi, Vuong ơi: We took many photos. Cô thấy con dùng took rất chuẩn, đúng với câu hỏi "
        "Did you take photos?. Tiếp theo mình sẽ tiếp tục câu tiếp theo nhé."
    )
    renderer, _ = brain([live] * 3)
    ch = unit()
    check = check_answer(ch.item("U11-VO-TR-04"), "We took many photos.", ch.lesson_of("U11-VO-TR-04"))
    message = renderer.render(
        ctx("U11-VO-TR-04", Move.CONFIRM_ADVANCE, student="We took many photos.", check=check)
    )
    assert "INVENTED_QUESTION" in rejected(renderer) and "Did you take photos" not in message.text


def test_an_emoji_is_never_said():
    live = (
        "Vuong ơi, con nhớ đúng từ collected seashells rồi, cho thấy hành động đã xảy ra rồi. 😊 Cô vui lắm. "
        "Mình sang câu tiếp theo nhé."
    )
    renderer, _ = brain([live])
    ch = unit()
    check = check_answer(ch.item("U11-VO-CC-01"), "A", ch.lesson_of("U11-VO-CC-01"))
    message = renderer.render(
        ctx("U11-VO-CC-01", Move.CONFIRM_ADVANCE, student="Vì bạn Lan nói collected.", check=check)
    )
    assert "😊" not in message.text
    raw = validator_for("english", lexicon=english_tools(unit()).lexicon)(
        live, ctx("U11-VO-CC-01", Move.CONFIRM_ADVANCE, check=check)
    )
    assert "EMOJI" in raw.codes


# ------------------------------------------------------------- 7. another subject: the item asked again


def english_loop() -> TeachingLoop:
    return TeachingLoop(unit(), "s-eng5h", [], **loop_options(unit()))


def test_after_a_math_question_the_item_is_asked_again_not_an_invitation():
    loop = english_loop()
    loop.start(NOW)
    for _ in range(80):
        if loop.awaiting == Awaiting.ANSWER:
            break
        loop.on_student("Con hiểu rồi ạ.", NOW)
    loop.tutor.last_tutor = (
        "Con ơi, câu này kể chuyện đi thuyền: We took a boat trip around the bay. Con thử nói theo cô nha?"
    )
    said = loop.on_student("cô ơi diện tích hình thang tính sao ạ?", NOW).messages[0].text
    assert "câu này nhé: Con thử nói theo cô nha?" not in said, said
    assert "Toán" in said and "hình thang" not in said


# ------------------------------------------------------------- 8. a counterexample only with its cue (DI-168)


def test_the_yesterday_counterexample_needs_yesterday_in_the_item():
    ch = unit()
    item = ch.item("U11-VO-PR-02")  # "… We ate …", no yesterday
    pkg = ch.lesson_of(item.id)
    for shown in range(3):
        found = counter_example(item, pkg, "ENG5-U11-M04", shown)
        assert found is None or "yesterday" not in found[0].lower()
    with_cue = next(
        i for lesson in ch.lessons.values() for i in lesson.items if "yesterday" in i.stem.lower()
    )
    texts = {counter_example(with_cue, ch.lesson_of(with_cue.id), "ENG5-U11-M04", k)[0] for k in range(2)}
    assert any("yesterday" in t for t in texts)


def test_mathematics_counterexamples_are_untouched():
    for lesson in MATH.lessons.values():
        for mis in lesson.misconceptions:
            for item in lesson.items[:3]:
                found = counter_example(item, lesson, mis.id)
                usable = [c for c in mis.counter_examples if "{" not in c]
                if usable and found is not None:
                    assert found[0] in mis.counter_examples or "{" in "".join(mis.counter_examples)


# ------------------------------------------------------------- 9. "nói lại" waits for the child (DI-169)


def test_after_the_model_sentence_a_wrong_repeat_waits_for_the_sentence_again():
    t = tutor("U11-VO-CP-01")
    t.start()
    t.phase = Phase.TEACH_BACK  # the tutor has just read the model sentence (H7, FULL_EXPLANATION)
    turn = t.on_student("We took a bot trip around the bay.", 5)
    assert not turn.resolved and turn.phase == Phase.AWAITING
    assert "bot" in turn.text and BOAT in turn.text, turn.text
    graded = [e.payload for e in t.events if e.type == EventType.ANSWER_SUBMITTED]
    assert graded[-1]["raw_text"] == "We took a bot trip around the bay."
    turn = t.on_student(BOAT, 5)
    graded = [e.payload for e in t.events if e.type == EventType.ANSWER_SUBMITTED]
    assert graded[-1]["outcome"] == "CORRECT"


def test_closing_an_item_does_not_ask_to_say_it_again():
    live = (
        "Con ơi, câu này dùng khi chúng ta kể về chuyến đi bằng thuyền quanh vịnh: "
        "Con thử nói lại theo cô nhé: "
        "We took a boat trip around the bay."
    )
    renderer, _ = brain([live] * 3)
    renderer.render(ctx("U11-VO-CP-01", Move.CONFIRM_ADVANCE, student="We took a bot trip around the bay."))
    assert "INVITES_AFTER_CLOSE" in rejected(renderer)
    assert task_for_en(Move.CONFIRM_ADVANCE, say_after_me=True).startswith("Vui cùng con")


# ------------------------------------------------------------- 10. the missing idea without the list


def test_a_partial_retell_names_the_missing_idea_without_the_whole_list():
    loop = english_loop()
    loop.start(NOW)
    from tests.test_english_teaching_fixes import PARTIAL_RETELL, until

    until(loop, lambda lp: lp.awaiting == Awaiting.RETELL and lp._node == "ENG5-U11-VOCAB")
    said = " ".join(m.text for m in loop.on_student(PARTIAL_RETELL, NOW).messages)
    assert "Còn một ý con chưa nói" in said and "động từ" in said, said
    assert "take photos; collect seashells" not in said and "ví dụ" in said, said


# ------------------------------------------------------------- 12. Gemini (DI-174, DI-175)


def test_gemini_clients_name_the_api_version():
    from cavat.modules.ai_gateway.gemini import GEMINI_API_VERSION, GeminiChat, GeminiEmbeddings, GeminiVision

    assert GEMINI_API_VERSION == "v1beta"
    for client in (GeminiChat("k", timeout_s=10), GeminiVision("k"), GeminiEmbeddings("k")):
        options = client._client._api_client._http_options
        assert options.api_version == "v1beta"
    assert GeminiChat("k", timeout_s=10)._client._api_client._http_options.timeout == 10_000


def test_a_model_skipped_without_sending_is_no_fallback_event():
    from cavat.modules.ai_gateway.base import ModelClass
    from cavat.modules.ai_gateway.router import Attempt as ModelAttemptInfo
    from cavat.modules.ai_gateway.router import ChatCall
    from cavat.modules.session.model_calls import model_call_events

    attempts = (
        ModelAttemptInfo(model="gemini-4-argon", sent=False, error="QuotaExceeded"),
        ModelAttemptInfo(model="gemini-2.5-flash", sent=False, error="ModelUnavailable"),
        ModelAttemptInfo(model="openai/gpt-oss-120b", sent=True, error="QuotaExceeded"),
        ModelAttemptInfo(model="qwen/qwen3.8-27b", sent=True, error=None),
    )
    result = ChatResult(model="qwen/qwen3.8-27b", text="{}", data={}, usage=Usage(1, 1, 2))
    outcome = ChatOutcome(result=result, fallback_reason=None, calls_made=1, attempts=attempts)
    call = ChatCall(ModelClass.TUTOR_REASONING, "tutor_turn_en", outcome, 10, 10, 0, 2)
    events = model_call_events([call])
    fallbacks = [e for e in events if e.event_type == EventType.MODEL_FALLBACK]
    assert [f.payload["from_model"] for f in fallbacks] == ["openai/gpt-oss-120b"]
    called = next(e for e in events if e.event_type == EventType.MODEL_CALLED)
    assert len(called.payload["attempts"]) == 4  # the skipped ones are still on record


def test_replace_keeps_unknown_detail():  # guard: the word order detail rides on the shared CheckResult
    ch = unit()
    check = check_answer(
        ch.item("U11-VO-PR-04"), "Chưa đúng. They seashells collected.", ch.lesson_of("U11-VO-PR-04")
    )
    assert replace(check, outcome=Outcome.CORRECT).detail["word_order"]
