"""ENG-5g (ADR-070, DI-156–163): the teaching and grading faults of the English session found when the student
Vuong learned Unit 11 on the real server (session 01a1df0f…, 15/11/2026). One test (or a few) per fault, each
on the words the child said that day. Offline: the template renderer, scripted model outputs, no network.

1. retell loop at VOCAB ("Con nói đúng ý rồi." then the same question again): DI-156
2. sentences of Mathematics in the English lesson ("kết quả bài trên thẻ", "những số"): DI-157
3. a right answer after PROBE read as an explanation / taught again: DI-158
4. right sentences graded WRONG or PARTIAL ("We took many photos.", the keychain, "ate" alone): DI-159, DI-161
5. a right Vietnamese "vì sao" judged vague then "Cô nói rõ hơn nhé. Mình sang câu tiếp theo nhé.": DI-160
6. "cô giảng lại" -> "Cô chưa thể giải thích tiếp", "souvenirs là gì" -> the whole theory again: DI-162
7. hints off the item ("Did you…?" on a comprehension item of VOCAB): DI-163
8. off the lesson: the same template every time, "buồn" -> "phần này hơi khó", "Vuông", invented quotes:
   DI-157, DI-163
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move, Outcome
from cavat.modules.ai_gateway.base import ChatResult, Usage
from cavat.modules.ai_gateway.router import ChatOutcome
from cavat.modules.assessment.answer_check import check_answer
from cavat.modules.assessment.english_checker import english_intent
from cavat.modules.assessment.math_checker import classify_intent
from cavat.modules.assessment.reason import judge_reason
from cavat.modules.session import chapter_service
from cavat.modules.teaching.loop import PHRASES, Awaiting, TeachingLoop
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
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
from cavat.modules.tutor.reader import Reading
from cavat.modules.tutor.renderer import PHRASES as ITEM_PHRASES
from cavat.modules.tutor.renderer import TemplateRenderer

UNIT = "eng-g5-u11-family-time"
NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)
MATH_WORDS = ("những số", "trên thẻ", "từ bước nào", "phép tính", "kết quả bài")


def unit():
    return chapter_service.chapters("english")[UNIT]


MATH = chapter_service.chapters()[chapter_service.DEFAULT_CHAPTER_ID]


def english_loop(**kw) -> TeachingLoop:
    return TeachingLoop(unit(), "s-eng5g", [], **loop_options(unit()), **kw)


def first_reply(loop: TeachingLoop) -> str:
    """What a student who learned the unit says to what waits (the unit's approved answers)."""
    ch = unit()
    if loop.awaiting == Awaiting.THEORY_REPLY:
        node = ch.node(loop._node)
        variant = next(t for t in node.theory if t.id == loop._ref)
        return variant.accept[0] if variant.accept else "Con hiểu rồi ạ."
    if loop.awaiting == Awaiting.RETELL:
        return ". ".join(p[0] for p in ch.node(loop._node).explain.key_ideas)
    item = ch.item(loop.tutor.item.id)
    if loop.tutor.phase in (Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON):
        return item.explanation or "Vì con nhớ mẫu câu của bài."
    accept = getattr(item.answer, "accept", None)
    if accept:
        return accept[0]
    return getattr(item.answer, "sample", None) or "A"


def until(loop: TeachingLoop, done, steps: int = 80) -> None:
    for _ in range(steps):
        if done(loop):
            return
        loop.on_student(first_reply(loop), NOW)
    pytest.fail("the state wanted was not reached")


def tutor_texts(turn) -> list[str]:
    return [m.text for m in turn.messages]


# ------------------------------------------------------------- 1. retell loop (DI-156)

PARTIAL_RETELL = "Con nhớ cụm bằng hình ảnh trong tranh và luôn nói cả câu, ví dụ We bought souvenirs."


def test_a_retell_with_an_idea_missing_says_which_and_asks_for_it_not_the_same_question():
    """L-2: rubric 0,667 (idea 2 "việc làm/động từ" missing). Before: "Con nói đúng ý rồi." and the
    retell question again, word for word, three times. Now the missing idea is named, and asked again the
    retell asks for that idea, never the same words as before."""
    loop = english_loop()
    loop.start(NOW)
    until(loop, lambda lp: lp.awaiting == Awaiting.RETELL and lp._node == "ENG5-U11-VOCAB")
    first_prompt = loop._prompt
    turn = loop.on_student(PARTIAL_RETELL, NOW)
    said = " ".join(tutor_texts(turn))
    assert "Con nói đúng ý rồi." not in said
    assert "Còn một ý con chưa nói" in said and "động từ" in said, said
    if loop.awaiting == Awaiting.RETELL and loop._node == "ENG5-U11-VOCAB":
        assert loop._prompt != first_prompt
        assert "ý còn thiếu" in loop._prompt and "động từ" in loop._prompt, loop._prompt
    judged = [e.payload for e in loop.events if e.event_type == EventType.RETELL_JUDGED]
    assert judged[-1]["ideas_found"] == [0, 2]  # grading is the same rubric: only the words changed


def test_the_retell_asked_again_asks_for_the_missing_idea_not_the_same_words():
    """L-2, the second half: the node policy asks the retell again (EXPLANATION_MISSING). It used to be
    "Con đã làm thêm nhiều bài rồi." and the same question, word for word, 3 times in a row."""
    from cavat.core.events import NodeDecisionMade
    from cavat.core.pedagogy import TeachAction

    loop = english_loop()
    loop.start(NOW)
    until(loop, lambda lp: lp.awaiting == Awaiting.RETELL and lp._node == "ENG5-U11-VOCAB")
    first_prompt = loop._prompt
    loop.on_student(PARTIAL_RETELL, NOW)
    again = NodeDecisionMade(
        action=TeachAction.ASK_RETELL,
        node_id="ENG5-U11-VOCAB",
        rule_ids=["N-CHECK"],
        reason_codes=["EXPLANATION_MISSING"],
        policy_version="node-policy/0.5.0",
    )
    turn = loop._carry_out(again, NOW, [], [])
    prompt = tutor_texts(turn)[-1]
    assert prompt != first_prompt and "Con đã làm thêm nhiều bài rồi" not in prompt
    assert "ý còn thiếu" in prompt and "động từ" in prompt, prompt
    # every idea said the last time: asked once more with other words, still not the old ones
    loop.events.append(
        SimpleNamespace(
            event_type=EventType.RETELL_JUDGED,
            payload={
                "node_id": "ENG5-U11-VOCAB", "text": "x", "ideas_found": [0, 1, 2], "ideas_total": 3,
                "score": 1.0, "purpose": "RETELL",
            },
        )
    )  # fmt: skip
    prompt = tutor_texts(loop._carry_out(again, NOW, [], []))[-1]
    assert prompt.startswith("Lần trước con đã nói đủ ý rồi."), prompt


def test_a_mathematics_retell_still_says_the_shared_words():
    loop = TeachingLoop(MATH, "s-math", [])
    assert loop._phrase("retell_good") == PHRASES["retell_good"].format(**loop._persona)
    assert not loop._english


# ------------------------------------------------------------- 2. sentences of Mathematics (DI-157)


def _ctx(item_id: str, move: Move, *, reasons=(), check=None, level=None, attempt=1) -> RenderContext:
    ch = unit()
    item, pkg = ch.item(item_id), ch.lesson_of(item_id)
    return RenderContext(
        decision=PolicyDecision(move=move, level=level, target=HintTarget.TASK, reason_codes=tuple(reasons)),
        item=item,
        package=pkg,
        state=ItemState(item_id=item_id, activity=ActivityType.GUIDED_PRACTICE, attempt_no=attempt),
        check=check,
        resume_prompt="Con nói câu đó bằng tiếng Anh giúp cô nhé?",
    )


ALL_ITEMS = [i.id for lesson in unit().lessons.values() for i in lesson.items]
TALK = [("VAGUE",), ("NEGATIVE_AFFECT",), ("HELP_REQUEST",), ("CONVERSATION", "CONTINUE"), ()]


@pytest.mark.parametrize("move", [Move.PROBE, Move.VERIFY, Move.CONFIRM_ADVANCE, Move.REDIRECT, Move.HINT])
def test_no_template_of_an_english_item_speaks_of_mathematics(move):
    renderer = TemplateRenderer()
    for item_id in ALL_ITEMS:
        for reasons in TALK:
            text = renderer.render(_ctx(item_id, move, reasons=reasons, level=HintLevel.H1)).text
            low = text.lower()
            assert not any(w in low for w in MATH_WORDS), (item_id, move, reasons, text)
            assert "hơi khó" not in low, (item_id, move, reasons, text)


def test_the_question_an_english_item_still_waits_for_is_never_the_mathematics_one():
    ch = unit()
    for item_id in ("U11-WD-CP-01", "U11-VO-CC-01", "U11-TR-CC-01"):
        t = ItemTutor(
            ch.item(item_id), ch.lesson_of(item_id), ActivityType.GUIDED_PRACTICE, TemplateRenderer(),
            session_validator(english_tools(ch).lexicon), DEFAULT_CONFIG,
        )  # fmt: skip
        t.start()
        for phase in (None, Phase.AWAITING_REASON, Phase.VERIFYING):
            if phase is not None:
                t.phase = phase
            asked = t._resume_question()
            assert asked and not any(w in asked.lower() for w in MATH_WORDS), (item_id, phase, asked)


def test_mathematics_templates_are_the_shared_ones():
    """A Mathematics item says the shared words, whatever PHRASES_EN holds."""
    pkg, item = next(
        (lesson, i) for lesson in MATH.lessons.values() for i in lesson.items if i.answer.type != "choice"
    )
    for move, key in ((Move.PROBE, "probe"), (Move.CONFIRM_ADVANCE, "confirm_advance")):
        ctx = RenderContext(
            decision=PolicyDecision(move=move),
            item=item,
            package=pkg,
            state=ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE),
        )
        assert TemplateRenderer().render(ctx).text == ITEM_PHRASES[key].format(
            S="Con", s="con", T="Cô", t="cô"
        )


# ------------------------------------------------------------- 3. after PROBE (DI-158)


class RepairReader:
    """A listener that reads everything as REPAIR, as the live one read the right sentence on 15/11."""

    model = object()
    semantic = True

    def __init__(self, only_phase: str | None = None) -> None:
        self.only_phase = only_phase

    def read_dialogue(self, *, phase="", **_):
        if self.only_phase and self.only_phase not in phase:
            return Reading("PASS")
        return Reading("REPAIR", focus="con chưa hiểu")

    def read(self, **_):
        return None


def test_a_right_sentence_after_the_probe_is_graded_not_taught_again():
    """L-4: U11-WD-CP-01, the words in a wrong order, the tutor asks how; the child then says the sentence
    right. It used to be read as REPAIR and answered with the theory (EXPLAIN); it is an answer, graded."""
    ch = unit()
    item_id = "U11-WD-CP-01"
    t = ItemTutor(
        ch.item(item_id), ch.lesson_of(item_id), ActivityType.GUIDED_PRACTICE, TemplateRenderer(),
        session_validator(english_tools(ch).lexicon), DEFAULT_CONFIG,
        reader=RepairReader("AWAITING_REASON"),
    )  # fmt: skip
    t.start()
    t.on_student(
        "What your family did in Ha Long? We took a boat trip around the bay.", 5, dialogue_version=3
    )
    assert t.phase == Phase.AWAITING_REASON, t.phase  # the tutor asked how (PROBE)
    right = ch.item(item_id).answer.accept[0]
    turn = t.on_student(right, 5, dialogue_version=3)
    graded = [e.payload for e in t.events if e.type == EventType.ANSWER_SUBMITTED]
    assert graded[-1]["outcome"] == "CORRECT", graded
    assert turn.move != Move.EXPLAIN


# ------------------------------------------------------------- 4. grading (DI-159, DI-161)


def _check(item_id: str, text: str):
    ch = unit()
    return check_answer(ch.item(item_id), text, ch.lesson_of(item_id))


def test_right_sentences_of_the_live_run_are_graded_right():
    assert _check("U11-VO-TR-04", "We took many photos.").outcome == Outcome.CORRECT
    assert _check("U11-VO-TR-04", "We took a lot of photos.").outcome == Outcome.CORRECT
    assert _check("U11-VO-TR-03", "I bought a keychain and a hat in Da Lat.").outcome == Outcome.CORRECT
    # what the items test is still tested
    assert _check("U11-VO-TR-04", "We take many photos.").outcome == Outcome.WRONG
    assert _check("U11-VO-TR-03", "I buy a keychain.").outcome != Outcome.CORRECT


def test_the_right_word_alone_is_partial_and_the_tutor_asks_for_the_whole_sentence():
    """L-6: "ate" for "Yesterday we … seafood." was WRONG with a hint that never said "cả câu"."""
    check = _check("U11-PA-CP-01", "ate")
    assert check.outcome == Outcome.PARTIAL and check.detail.get("whole_sentence") is True
    assert _check("U11-PA-CP-01", "seafood").outcome == Outcome.WRONG  # the stem gives it
    assert _check("U11-PA-CP-01", "eated").outcome == Outcome.WRONG
    text = TemplateRenderer().render(_ctx("U11-PA-CP-01", Move.HINT, check=check, level=HintLevel.H1)).text
    assert "cả câu" in text, text


# ------------------------------------------------------------- 5. the Vietnamese "vì sao" (DI-160)


def test_a_right_vietnamese_explanation_is_not_vague():
    ch = unit()
    for item_id, text in [
        ("U11-WD-CP-01", "Vì chuyến đi đã qua rồi nên dùng took, quá khứ của take."),
        ("U11-TR-CC-01", "Vì con đọc câu đầu của đoạn văn, có Ha Long Bay và last weekend."),
    ]:
        judged = judge_reason(ch.item(item_id), text, ch.lesson_of(item_id))
        assert not judged.vague and judged.quality >= 0.6, (item_id, judged)
    assert judge_reason(ch.item("U11-WD-CP-01"), "Vì cô dạy thế.", ch.lesson_of("U11-WD-CP-01")).vague


def test_english_words_quoted_in_an_explanation_are_not_a_question():
    """ "Ha Long" without its marks reads "hả": the explanation was taken for "là sao?" and closed."""
    item = unit().item("U11-TR-CC-01")
    text = (
        "Chỗ này ạ: Last weekend, Linda and her family visited Ha Long Bay. "
        "Nên gia đình Linda đã đến Ha Long Bay."
    )
    assert classify_intent(text) == Outcome.CLARIFY_REQUEST  # the shared reading, unchanged
    assert english_intent(text, item) is None
    assert english_intent("hả?", item) == Outcome.CLARIFY_REQUEST
    assert english_intent("Ha Long Bay là sao ạ?", item) == Outcome.CLARIFY_REQUEST


def test_after_a_right_answer_a_right_explanation_closes_the_item_with_praise():
    ch = unit()
    item_id = "U11-WD-CP-01"
    t = ItemTutor(
        ch.item(item_id), ch.lesson_of(item_id), ActivityType.GUIDED_PRACTICE, TemplateRenderer(),
        session_validator(english_tools(ch).lexicon), replace(DEFAULT_CONFIG, verify_rate=1.0),
    )  # fmt: skip
    t.start()
    first = t.on_student(ch.item(item_id).answer.accept[0], 5)
    assert first.move == Move.VERIFY
    turn = t.on_student("Vì chuyến đi đã qua rồi nên dùng took, quá khứ của take.", 5)
    assert turn.move == Move.CONFIRM_ADVANCE, turn
    assert not any(w in turn.text.lower() for w in MATH_WORDS)
    assert "nói rõ hơn" not in turn.text


# ------------------------------------------------------------- 6. taught again (DI-162)

THEORY_WAIT = lambda lp: lp.awaiting == Awaiting.THEORY_REPLY  # noqa: E731


def test_souvenirs_la_gi_gets_the_sentence_on_souvenirs_not_the_whole_theory():
    loop = english_loop()
    loop.start(NOW)
    until(loop, THEORY_WAIT)
    node = unit().node(loop._node)
    turn = loop.on_student("Con chưa hiểu 'souvenirs' là gì ạ", NOW)
    said = " ".join(tutor_texts(turn))
    assert "souvenirs" in said.lower(), said
    assert "chưa thể giải thích" not in said
    theory = next(t.text for t in node.theory if t.id == loop._ref)
    assert theory not in said  # not the whole theory pasted again


class StubSpeaker:
    """The grounded speaker of an English session: no model (DI-140)."""

    router = None
    allow_knowledge = True
    knowledge_active = True
    name = None

    def is_question(self, text):
        return False


def test_asking_twice_to_be_taught_again_gets_two_different_short_explanations():
    loop = english_loop()
    loop.start(NOW)
    until(loop, THEORY_WAIT)
    loop.speaker, loop.item_reader = StubSpeaker(), RepairReader()
    one = " ".join(tutor_texts(loop.on_student("con chưa hiểu, cô giảng lại giúp con", NOW)))
    two = " ".join(tutor_texts(loop.on_student("con chưa hiểu, cô giảng lại giúp con", NOW)))
    for said in (one, two):
        assert said and "chưa thể giải thích" not in said, said
        assert said.rstrip().endswith("?") or "nhé" in said
    assert one != two


def test_the_english_brain_teaches_again_when_it_may_and_its_words_are_checked():
    loop = english_loop()
    loop.start(NOW)
    until(loop, THEORY_WAIT)
    router = ScriptedRouter(
        [
            "Con Vuông nói: [[en: We bought a car.]] Cô giảng lại nhé?",  # invented quote: refused
            "Souvenirs là quà lưu niệm, mình mua mang về: We buy souvenirs. "
            "Con thử trả lời lại câu của cô nhé?",
        ]
    )
    loop.item_renderer = english_renderer_for(router, name="Vuong")
    turn = loop.on_student("Con chưa hiểu 'souvenirs' là gì ạ", NOW)
    said = " ".join(tutor_texts(turn))
    assert "quà lưu niệm" in said and "Vuông" not in said
    assert [m.source for m in turn.messages][-1] == "LLM"
    assert len(router.requests) == 2  # the first output was refused, the second kept


# ------------------------------------------------------------- 7. hints on the item (DI-163)


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


def english_renderer_for(router, name=None, knowledge=True) -> EnglishRenderer:
    tools = knowledge_tools(english_tools(unit()), knowledge)
    return EnglishRenderer(
        router,
        TemplateRenderer(),
        validator_for("english", lexicon=tools.lexicon),
        tools,
        student_name=name,
        knowledge=knowledge,
    )


def test_a_hint_teaching_another_node_is_refused_and_the_approved_hint_is_the_ground():
    """L-7: H1 on U11-VO-CC-01 (what did Lan do?) was "Con nghĩ sao: Did you collect seashells…?"."""
    router = ScriptedRouter(
        [
            "Con nghĩ sao: Did you collect seashells with your brother?",
            "Con nghĩ sao: Did you collect seashells with your brother?",
        ]
    )
    renderer = english_renderer_for(router)
    ctx = _ctx("U11-VO-CC-01", Move.HINT, level=HintLevel.H1)
    message = renderer.render(ctx)
    assert "Did you" not in message.text and message.source != "LLM"
    assert "OFF_ITEM_ENGLISH" in renderer.last_trace.rejected[0]
    approved = TemplateRenderer().render(ctx).text
    assert approved in router.requests[0].messages[1].content


def test_a_hint_on_the_item_is_kept():
    router = ScriptedRouter(["Bạn Lan kể việc làm cùng anh trai ở bãi biển. Con đọc lại câu của bạn ấy nhé?"])
    message = english_renderer_for(router).render(_ctx("U11-VO-CC-01", Move.HINT, level=HintLevel.H1))
    assert message.source == "LLM"


# ------------------------------------------------------------- 8. off the lesson (DI-157, DI-163)


def test_the_childs_name_is_written_as_it_is():
    router = ScriptedRouter(["Con Vuông: con nhớ lại câu của bạn Lan nhé. Bạn ấy làm gì cùng anh trai?"])
    message = english_renderer_for(router, name="Vuong").render(
        _ctx("U11-VO-CC-01", Move.HINT, level=HintLevel.H1)
    )
    assert "Vuông" not in message.text
    assert message.source != "LLM" or "Vuong" in message.text


def test_a_quote_of_words_the_child_did_not_say_is_refused():
    router = ScriptedRouter(["Con nói: Yes, I did. I took photos. Vì sao con nói như vậy?"] * 2)
    ctx = replace(_ctx("U11-DY-CP-01", Move.VERIFY), student_text="Vì cô hỏi Did you swim.")
    message = english_renderer_for(router).render(ctx)
    assert message.source != "LLM"


def test_questions_of_another_subject_are_not_answered_with_the_same_sentence_each_time():
    loop = english_loop()
    loop.start(NOW)
    until(loop, lambda lp: lp.awaiting == Awaiting.ANSWER)
    one = tutor_texts(loop.on_student("0,5 + 0,25 bằng mấy ạ?", NOW))[0]
    two = tutor_texts(loop.on_student("cô ơi diện tích hình thang tính sao ạ?", NOW))[0]
    assert one != two
    for said in (one, two):
        assert "0,5" not in said and "hình thang" not in said


def test_a_long_passage_is_not_pasted_again_after_a_question_of_another_subject():
    ch = unit()
    loop = english_loop()
    loop.start(NOW)
    until(loop, lambda lp: lp.awaiting == Awaiting.ANSWER)
    stem = (
        "Con đọc đoạn này nhé: "
        + " ".join(["Linda and her family visited Ha Long Bay."] * 12)
        + " Where did they go?"
    )
    loop.tutor.item = loop.tutor.item.model_copy(update={"stem": stem})
    loop.tutor.last_tutor = stem
    said = tutor_texts(loop.on_student("0,5 + 0,25 bằng mấy ạ?", NOW))[0]
    assert stem not in said and "Where did they go?" in said
    assert ch  # the unit's own data is untouched


def test_a_sad_child_is_not_told_the_lesson_is_hard():
    loop = english_loop()
    loop.start(NOW)
    until(loop, THEORY_WAIT)
    said = " ".join(tutor_texts(loop.on_student("hôm nay con buồn", NOW)))
    assert "hơi khó" not in said


def test_english_teaching_messages_record_their_own_templates_version():
    loop = english_loop()
    turn = loop.start(NOW)
    versions = {
        e.payload.get("templates_version")
        for e in turn.events
        if e.event_type == EventType.TEACH_MESSAGE_SENT
    }
    assert versions == {"teaching-templates-en/0.1.0"}
    math = TeachingLoop(MATH, "s-math", []).start(NOW)
    versions = {
        e.payload.get("templates_version")
        for e in math.events
        if e.event_type == EventType.TEACH_MESSAGE_SENT
    }
    assert versions == {"teaching-templates/0.19.0"}


def test_no_math_word_in_the_new_english_phrases():
    from cavat.modules.teaching.loop import PHRASES_EN
    from cavat.modules.tutor.english_validator import math_terms_in
    from cavat.modules.tutor.renderer import LEADS_EN
    from cavat.modules.tutor.renderer import PHRASES_EN as ITEM_EN

    for table in (PHRASES_EN, ITEM_EN, LEADS_EN):
        for variants in table.values():
            for text in variants:
                assert not math_terms_in(text) and not any(w in text for w in MATH_WORDS), text
    assert re.search(r"\{part\}", PHRASES_EN["retell_partial"][0])


# --------- 9. the model is the way, templates the last resort (DI-164)


def test_a_refused_model_turn_is_asked_again_and_the_third_is_kept_not_the_template():
    router = ScriptedRouter(
        [
            "Đúng rồi! Con nói đúng. Con còn nhớ vì sao không? Con kể cô nghe nhé?",  # two questions
            "Con nói đúng rồi, chữ nào trong câu giúp con chọn A? Cô nghe nhé?",  # two questions again
            "Đúng rồi, Lan nhặt vỏ sò cùng anh trai. Mình sang câu tiếp theo nhé.",
        ]
    )
    ctx = replace(_ctx("U11-VO-CC-01", Move.CONFIRM_ADVANCE), student_text="A")
    message = english_renderer_for(router).render(ctx)
    assert message.source == "LLM" and "vỏ sò" in message.text
    assert len(router.requests) == 3


ZOO = "Con nhớ câu: [[en: We went to the zoo.]] Vì sao con chọn cách nói đó?"


def test_the_model_may_use_standard_grade_5_english_around_the_units_words():
    """BRAIN-4 for English: an example with everyday words outside the unit ("zoo") is allowed when
    ENGLISH_ALLOW_TUTOR_KNOWLEDGE is on, refused when it is off."""
    ctx = replace(_ctx("U11-VO-CC-01", Move.VERIFY), student_text="A")
    kept = english_renderer_for(ScriptedRouter([ZOO])).render(ctx)
    assert kept.source == "LLM"
    strict = english_renderer_for(ScriptedRouter([ZOO] * 3), knowledge=False).render(ctx)
    assert strict.source != "LLM"


def test_knowledge_off_keeps_the_strict_constitution():
    from cavat.modules.tutor.english import english_system_prompt

    assert english_system_prompt(True) != english_system_prompt(False)
    assert "kiến thức tiếng Anh chuẩn lớp 5" in english_system_prompt(True)
    assert "kiến thức tiếng Anh chuẩn lớp 5" not in english_system_prompt(False)


# ------------------------------------------------------------- 10. B then A (owner's screenshot)


def test_a_wrong_choice_then_the_right_letter_are_both_graded_and_the_item_is_not_a_first_try():
    """ "B" (wrong) -> PROBE -> "A" (right): two graded attempts, the item resolves with its two attempts, the
    answer after the probe is an answer (never an explanation), and no message talks of another item."""
    ch = unit()
    item_id = next(
        i.id
        for lesson in ch.lessons.values()
        for i in lesson.items
        if "Do you swim with your mother" in i.stem
    )
    t = ItemTutor(
        ch.item(item_id), ch.lesson_of(item_id), ActivityType.GUIDED_PRACTICE, TemplateRenderer(),
        session_validator(english_tools(ch).lexicon), DEFAULT_CONFIG, reader=RepairReader("AWAITING_REASON"),
    )  # fmt: skip
    t.start()
    t.on_student("B", 5, dialogue_version=3)
    assert t.phase == Phase.AWAITING_REASON
    t.on_student("A", 5, dialogue_version=3)
    graded = [e.payload for e in t.events if e.type == EventType.ANSWER_SUBMITTED]
    assert [g["outcome"] for g in graded] == ["WRONG", "CORRECT"]
    assert [g["attempt_no"] for g in graded] == [1, 2]
    resolved = (
        [e.payload for e in t.events if e.type == EventType.ITEM_RESOLVED][-1]
        if t.phase == Phase.RESOLVED
        else None
    )
    if resolved is not None:
        assert resolved["attempts"] == 2


def test_a_letter_is_not_an_answer_to_an_item_without_options():
    for item_id in ("U11-PA-CP-01", "U11-WD-CP-01", "U11-VO-TR-04"):
        assert _check(item_id, "A").outcome != Outcome.CORRECT, item_id
