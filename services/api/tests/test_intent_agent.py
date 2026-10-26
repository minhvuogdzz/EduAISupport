"""REFORM-5 (Task 3.1): the tutor does not take "ki", "kt", "ể", "kkk", "không" for an answer, an explanation
or
praise. The owner's live session of 2026-10-25 (`Số thập phân · CAVAT.pdf`): the child typed "ki", "kkk",
"tt",
"ể" and "không", and the tutor said "Đúng rồi! Con đã suy nghĩ và kiểm tra rất cẩn thận".

Two tiers, offline here (a scripted router stands in for the model):
- tier 1, no token: a bare "không"/"chưa" is "con không biết" (HELP_REQUEST) unless the question takes it as
an
  answer; a few letters nothing reads ("ki", "kk", "ể") are a typo or a key slip: the tutor asks once
  (ASK_CONFIRM), and on the second time helps instead of asking a third time;
- tier 2, one model call at most for such a message: the label, a guess and the question to ask
(``clarification``),
  checked by the validator before the child sees it, recorded in MESSAGE_READ so a replay never asks again.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cavat.core.events import PAYLOAD_MODELS, EventType
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move, Outcome
from cavat.modules.ai_gateway.base import ChatResult
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.assessment.math_checker import CheckResult, check_answer, classify_intent
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.session import chapter_service
from cavat.modules.teaching.conductor import clean
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.contracts import ItemState, PolicyInput
from cavat.modules.tutor.item_loop import ItemTutor, Phase
from cavat.modules.tutor.policy import DEFAULT_CONFIG, ItemFacts, decide
from cavat.modules.tutor.reader import LiveReader, ModelReader, recorded
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

DOCS = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5"
CHAPTER = chapter_service.chapters()["math-g5-decimals"]
CAKE = CHAPTER.item("TP-TR-01")  # numeric, 0,3: "Lan ăn 3 phần trong 10 phần bằng nhau. Viết số thập phân."
CHOICE = CHAPTER.item("TP-CC-01")  # "Phân số nào dưới đây là phân số thập phân: 3/7, 7/10 hay 10/3?"
PKG = load_lesson_package(DOCS / "so-sanh-so-thap-phan/lesson.yaml")
NO_VERIFY = replace(DEFAULT_CONFIG, verify_rate=0.0)
ALWAYS_VERIFY = replace(DEFAULT_CONFIG, verify_rate=1.0)

# What the conductor hands the loop for the strings of the owner's session (it keeps "kkk", it does not read
# it as "k").
UNREADABLE = ["ki", "kt", "ể", "êr", "tt", "kk", "kkk"]
NOT_KNOWING = ["không", "ko", "k", "chưa", "không ạ", "không mà", "hông"]
ASKING = ["hả", "j"]
PRAISE = ("Đúng rồi", "Chính xác", "suy nghĩ và kiểm tra rất cẩn thận")
WORDS = (Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON, Phase.AWAITING_PROBE)


# --------------------------------------------------------------------------- scenes: one per phase


def chapter_tutor(item, cfg=NO_VERIFY, reader=None, renderer=None) -> ItemTutor:
    t = ItemTutor(
        item,
        CHAPTER.lesson_of(item.id),
        ActivityType.GUIDED_PRACTICE,
        renderer or TemplateRenderer(),
        validate_message,
        cfg,
        reader=reader,
    )
    t.start()
    return t


def lesson_tutor(item_id: str, cfg=NO_VERIFY, reader=None) -> ItemTutor:
    t = ItemTutor(
        PKG.item(item_id),
        PKG,
        ActivityType.GUIDED_PRACTICE,
        TemplateRenderer(),
        validate_message,
        cfg,
        reader=reader,
    )
    t.start()
    return t


def scene(name: str, reader=None) -> ItemTutor:
    if name == "answer":
        t, phase = chapter_tutor(CAKE, reader=reader), Phase.AWAITING
    elif name == "choice":
        t, phase = chapter_tutor(CHOICE, reader=reader), Phase.AWAITING
    elif name == "reason":  # "con làm thế nào?" after the first wrong answer
        t = chapter_tutor(CAKE, reader=reader)
        t.on_student("5")
        phase = Phase.AWAITING_REASON
    elif name == "probe":  # the comparison that separates two causes
        t = lesson_tutor("GP-08", reader=reader)
        t.on_student("Lan")
        phase = Phase.AWAITING_PROBE
    elif name == "verify":  # "vì sao" after a right answer
        t = chapter_tutor(CAKE, ALWAYS_VERIFY, reader=reader)
        t.on_student("0,3")
        phase = Phase.VERIFYING
    elif name == "teach_back":  # "con giảng lại" after the worked steps
        t = lesson_tutor("GP-01", reader=reader)
        for said in ("0,25 > 0,3", "0,25 > 0,3", "0,25 > 0,3", "0,25 < 0,3"):
            t.on_student(said)
        phase = Phase.TEACH_BACK
    else:
        raise AssertionError(name)
    assert t.phase == phase, (name, t.phase)
    return t


SCENES = ["answer", "choice", "reason", "probe", "verify", "teach_back"]


def counts(t: ItemTutor) -> tuple[int, int]:
    return t.state.attempt_no, t.state.unproductive_turns


def of_type(t: ItemTutor, event_type: EventType) -> list[dict]:
    return [e.payload for e in t.events if e.type == event_type]


def praised(text: str) -> bool:
    return any(p in text for p in PRAISE)


# --------------------------------------------------------------------------- tier 1: the strings


@pytest.mark.parametrize("said", ["ki", "kt", "kk", "kkk", "tt", "ể", "êr", "hihi", "haha", "qwe"])
def test_a_few_letters_nothing_reads_are_flagged(said):
    from cavat.modules.assessment.student_intent import is_gibberish_or_ambiguous_short

    assert is_gibberish_or_ambiguous_short(said)


@pytest.mark.parametrize(
    "said",
    ["không", "ko", "k", "chưa", "bé", "lớn", "đúng", "sai", "có", "dạ", "ok", "0,3", "3/10", "ba", "mười"]
    + ["bằng", "hả", "j", "cm", "ừ", "dung", "be hon", "một chữ số thập phân", "con không biết làm"],
)
def test_words_the_tutor_reads_are_not_flagged(said):
    from cavat.modules.assessment.student_intent import is_gibberish_or_ambiguous_short

    assert not is_gibberish_or_ambiguous_short(said)


def test_a_word_of_the_item_is_known_to_the_child_who_types_it():
    from cavat.modules.assessment.student_intent import is_gibberish_or_ambiguous_short

    assert is_gibberish_or_ambiguous_short("Lan")
    assert not is_gibberish_or_ambiguous_short("Lan", known=frozenset({"lan"}))


@pytest.mark.parametrize("said", NOT_KNOWING)
def test_a_bare_no_is_i_do_not_know(said):
    assert classify_intent(said) == Outcome.HELP_REQUEST


@pytest.mark.parametrize("said", ["không biết", "không phải", "ko phải 0,3", "không 0,3", "không bằng"])
def test_a_no_with_something_in_it_is_not_a_bare_no(said):
    from cavat.modules.assessment.student_intent import is_bare_negation

    assert not is_bare_negation(said)


def test_a_question_that_a_no_answers_keeps_it():
    boolean = PKG.item("GP-09")  # "đúng hay sai"
    assert check_answer(boolean, "không", PKG).outcome == Outcome.CORRECT
    zero = CAKE.model_copy(update={"answer": CAKE.answer.model_copy(update={"value": "0"})})
    assert check_answer(zero, "không", CHAPTER.lesson_of(CAKE.id)).outcome != Outcome.HELP_REQUEST
    assert check_answer(CAKE, "không", CHAPTER.lesson_of(CAKE.id)).outcome == Outcome.HELP_REQUEST


@pytest.mark.parametrize("said", ["hả", "j"])
def test_hả_and_j_ask_what(said):
    assert classify_intent(clean(said).text) == Outcome.CLARIFY_REQUEST


@pytest.mark.parametrize(("raw", "text"), [("kkk", "kkk"), ("kk", "kk"), ("kkkkkkkk", "kkk"), ("tt", "tt")])
def test_laughter_is_not_shrunk_to_a_letter_that_means_no(raw, text):
    assert clean(raw).text == text


def test_a_stretched_word_is_still_shrunk():
    assert clean("đúnggggg!!!").text == "đúng!"
    assert clean("khôngggg").text == "không"


# --------------------------------------------------------------------------- the phases


@pytest.mark.parametrize("name", SCENES)
@pytest.mark.parametrize("said", UNREADABLE)
def test_an_unreadable_message_is_asked_about_once_and_never_graded_nor_praised(name, said):
    t = scene(name)
    before = counts(t)
    phase = t.phase
    turn = t.on_student(clean(said).text)
    assert turn.move == Move.ASK_CONFIRM, (name, said, turn.text)
    assert not praised(turn.text) and turn.text.count("?") == 1
    assert counts(t) == before  # no attempt, no unproductive turn
    assert t.phase == (phase if phase in WORDS else Phase.AWAITING_CONFIRM)
    read = of_type(t, EventType.MESSAGE_READ)[-1]
    assert read["label"] in ("AMBIGUOUS_TYPO", "GIBBERISH") and read["source"] == "RULE"
    assert not of_type(t, EventType.ANSWER_SUBMITTED) or all(
        e["raw_text"] != said for e in of_type(t, EventType.ANSWER_SUBMITTED)
    )


@pytest.mark.parametrize("name", SCENES)
@pytest.mark.parametrize("said", ["ki", "kkk", "ể"])
def test_the_second_time_in_a_row_the_tutor_helps_instead_of_asking_again(name, said):
    t = scene(name)
    before = counts(t)
    t.on_student(clean(said).text)
    again = t.on_student(clean("kt" if said == "ki" else said).text)  # not even the same letters
    assert again.move != Move.ASK_CONFIRM, (name, again.text)
    assert not praised(again.text)
    assert counts(t) == before
    if name in ("verify", "teach_back"):  # the tutor says the approved explanation and goes on
        assert t.phase == Phase.RESOLVED
        end = of_type(t, EventType.POLICY_DECISION)[-1]
        assert "UNCLEAR_TWICE" in end["reason_codes"] or "NO_EXPLANATION" in end["reason_codes"]
        assert t.item.explanation in again.text or " ".join(t.item.worked_solution) in again.text
    else:  # a hint, or the offer of one
        assert again.move in (Move.HINT, Move.OFFER_CHOICE, Move.WORKED_GUIDANCE), (name, again.move)
        assert t.state.help_requests == 1


@pytest.mark.parametrize("name", SCENES)
def test_after_the_question_a_real_reply_goes_on_as_usual(name):
    t = scene(name)
    t.on_student("ki")
    assert not t.state.confirm_open or t.phase != Phase.RESOLVED
    reply = {
        "answer": "0,3",
        "choice": "B",
        "reason": "con lấy 3 chia 10",
        "probe": "9,8 lớn hơn",
        "verify": "vì 3/10 có mẫu số 10 nên phần thập phân có một chữ số",
        "teach_back": "so sánh hàng phần mười trước",
    }[name]
    turn = t.on_student(reply)
    assert turn.move != Move.ASK_CONFIRM


@pytest.mark.parametrize("name", SCENES)
@pytest.mark.parametrize("said", NOT_KNOWING)
def test_a_bare_no_is_help_in_every_phase_and_never_praised(name, said):
    t = scene(name)
    before = counts(t)
    turn = t.on_student(said)
    assert turn.move != Move.ASK_CONFIRM and not praised(turn.text), (name, said, turn.text)
    assert counts(t) == before
    if name in ("verify", "teach_back"):
        assert t.phase == Phase.RESOLVED and (
            t.item.explanation in turn.text or " ".join(t.item.worked_solution) in turn.text
        )
    elif name == "choice" and said in ("hông",):
        assert turn.move in (Move.HINT, Move.OFFER_CHOICE, Move.WORKED_GUIDANCE)
    else:
        assert turn.move in (Move.HINT, Move.OFFER_CHOICE, Move.WORKED_GUIDANCE), (name, said, turn.move)


@pytest.mark.parametrize("name", SCENES)
@pytest.mark.parametrize("said", ASKING)
def test_hả_and_j_get_the_task_said_again_not_a_confirmation(name, said):
    t = scene(name)
    before = counts(t)
    turn = t.on_student(clean(said).text)
    assert turn.move != Move.ASK_CONFIRM and not praised(turn.text), (name, said, turn.text)
    assert counts(t) == before


def test_an_item_whose_words_the_child_types_is_not_asked_about():
    item = CHAPTER.item("TP-TR-01")
    t = chapter_tutor(item)
    turn = t.on_student("Lan")  # the name in the task: not a key slip
    assert turn.move != Move.ASK_CONFIRM


def test_nothing_the_child_typed_instead_of_answering_becomes_an_attempt():
    t = scene("answer")
    for said in ["ki", "tt", "ể", "kkk", "ko", "kt"]:
        t.on_student(clean(said).text)
    assert t.state.attempt_no == 0 and t.state.unproductive_turns == 0
    assert not t.state.worked_shown  # six slips do not open the worked steps
    assert of_type(t, EventType.ANSWER_SUBMITTED) == []


def test_every_event_of_the_new_readings_is_a_valid_payload():
    t = scene("verify")
    t.on_student("kt")
    for e in t.events:
        PAYLOAD_MODELS[e.type].model_validate(e.payload)


# --------------------------------------------------------------------------- the policy


def _inp(chk: CheckResult, trigger="ANSWER", **state) -> PolicyInput:
    base = {"attempt_no": 1, "hint_levels": [HintLevel.H1], "hint_targets": [HintTarget.TASK]}
    return PolicyInput(
        item=CAKE,
        state=ItemState(item_id=CAKE.id, activity=ActivityType.GUIDED_PRACTICE, **{**base, **state}),
        check=chk,
        trigger=trigger,
    )


@pytest.mark.parametrize("read", ["GIBBERISH", "AMBIGUOUS_TYPO"])
def test_the_policy_asks_once_then_helps(read):
    chk = CheckResult(Outcome.NEEDS_CONFIRMATION, normalized="ki", detail={"read": read})
    first = decide(_inp(chk), ItemFacts(top_hint_level=5), NO_VERIFY)
    assert first is not None and first.move == Move.ASK_CONFIRM
    assert first.rule_ids == ("R-ASK-CONFIRM",)
    assert "TYPO" in first.reason_codes or "GIBBERISH" in first.reason_codes

    second = decide(_inp(chk, confirm_open=True), ItemFacts(top_hint_level=5), NO_VERIFY)
    assert second is not None and second.move in (Move.HINT, Move.OFFER_CHOICE)
    assert "UNCLEAR_TWICE" in second.reason_codes and "R-ASK-CONFIRM" in second.rule_ids


def test_a_confirmation_about_a_number_is_still_asked_again():
    """ "0.3" read as 0,3 (ASK_CONFIRM, DI-ambiguous separator) is not a slip: the old rule stands."""
    chk = CheckResult(Outcome.NEEDS_CONFIRMATION, normalized="0,3", detail={"interpretation": "0,3"})
    d = decide(_inp(chk, confirm_open=True), ItemFacts(top_hint_level=5), NO_VERIFY)
    assert d is not None and d.move == Move.ASK_CONFIRM


# --------------------------------------------------------------------------- tier 2: the model


class ScriptedRouter:
    """Answers each request with the next scripted JSON object (None: the provider is down)."""

    max_calls_per_session = 40

    def __init__(self, *answers: dict | None) -> None:
        self.answers = list(answers)
        self.requests: list = []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append((model_class, request))
        data = self.answers.pop(0) if self.answers else None
        if data is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        return ChatOutcome(ChatResult("gpt-oss-test", str(data), data), None, 1)


def reading(label, meaning="", question="", focus="", answer=""):
    return {
        "label": label,
        "focus": focus,
        "answer": answer,
        "guessed_meaning": meaning,
        "clarification": question,
    }


GUESS = "Cô đoán con muốn nói là con chưa biết làm, đúng không, hay con định gõ ý khác?"


def test_the_model_guesses_and_its_question_is_what_the_child_reads():
    from cavat.modules.ai_gateway.base import ModelClass

    router = ScriptedRouter(reading("AMBIGUOUS_TYPO", "chưa biết làm", GUESS))
    t = scene("verify", reader=LiveReader(ModelReader(router)))
    before = counts(t)
    turn = t.on_student("kt")
    assert turn.move == Move.ASK_CONFIRM and turn.text == GUESS
    assert len(router.requests) == 1 and router.requests[0][0] == ModelClass.INTENT_AGENT
    read = of_type(t, EventType.MESSAGE_READ)[-1]
    assert read["label"] == "AMBIGUOUS_TYPO" and read["source"] == "LLM"
    assert read["guessed_meaning"] == "chưa biết làm" and read["clarification"] == GUESS
    sent = of_type(t, EventType.TUTOR_MESSAGE_SENT)[-1]
    assert sent["source"] == "LLM" and sent["move"] == Move.ASK_CONFIRM
    assert t.phase == Phase.VERIFYING and counts(t) == before


@pytest.mark.parametrize(
    ("meaning", "said"),
    [("con chưa biết làm", "chưa biết làm"), ("chưa biết làm.", "chưa biết làm"), ("con", None), ("", None)],
)
def test_the_guess_is_said_without_a_second_subject(meaning, said):
    """A model may write "con chưa biết làm" for the guess: the question must not say "con con"."""
    router = ScriptedRouter(reading("AMBIGUOUS_TYPO", meaning, ""))
    t = scene("answer", reader=LiveReader(ModelReader(router)))
    turn = t.on_student("kt")
    assert turn.move == Move.ASK_CONFIRM and "con con" not in turn.text and turn.text.count("?") == 1
    assert (said in turn.text) if said else ("chưa biết làm" not in turn.text)
    # the same in a theory question: nothing raises on a guess that is only the subject
    loop = TeachingLoop(
        CH, "s1", item_reader=LiveReader(ModelReader(ScriptedRouter(reading("AMBIGUOUS_TYPO", meaning, ""))))
    )
    waiting, n = until(Awaiting.THEORY_REPLY, loop, loop.start(T0))
    asked = loop.on_student("kt", clock(n + 1), 10)
    assert asked.awaiting == Awaiting.THEORY_REPLY and "con con" not in " ".join(
        m.text for m in asked.messages
    )


def test_the_model_is_not_called_for_laughter_nor_for_the_second_time_nor_for_what_is_read():
    router = ScriptedRouter(reading("GIBBERISH"), reading("GIBBERISH"), reading("GIBBERISH"))
    t = scene("answer", reader=LiveReader(ModelReader(router)))
    t.on_student("kkk")  # a key held down: the rule reads it
    t.on_student("hihi")  # laughter, the second time in a row: the child is helped
    t.on_student("không")  # read by the lists
    assert router.requests == []
    t.on_student("kt")  # nothing else reads it: the model may be asked, once
    assert len(router.requests) == 1
    t.on_student("êr")  # the second time in a row: no second call
    assert len(router.requests) == 1


def test_the_intent_agent_leaves_the_second_half_of_the_calls_to_the_tutors_voice():
    router = ScriptedRouter(reading("GIBBERISH"), reading("GIBBERISH"))
    late = ModelReader(router, calls_used=20)  # 20 of the 40 calls of the session are spent
    assert late.read(stem="Đề", last_tutor="Con làm đi?", said="kt", turn=1) is None
    assert router.requests == []
    assert late.read(stem="Đề", last_tutor="Con làm đi?", said="con chưa hiểu đề này", turn=2) is not None
    early = ModelReader(router, calls_used=19)
    assert early.read(stem="Đề", last_tutor="Con làm đi?", said="kt", turn=3) is not None
    t = scene("answer", reader=LiveReader(ModelReader(ScriptedRouter(), calls_used=39)))
    assert t.on_student("kt").move == Move.ASK_CONFIRM  # no call left: the template asks


def test_at_most_two_model_readings_an_item():
    router = ScriptedRouter(*[reading("GIBBERISH")] * 6)
    t = scene("answer", reader=LiveReader(ModelReader(router)))
    for said in ("ki", "tuyệt", "kt", "tuyệt", "ể", "tuyệt", "êr"):
        t.on_student(said)
    assert len(router.requests) <= 2


@pytest.mark.parametrize(
    ("question", "why"),
    [
        ("Con muốn nói đáp án là 0,3 đúng không?", "the answer"),
        ("Con gõ gì vậy? Con nói lại được không?", "two questions"),
        ("Em muốn nói gì vậy em?", "em"),
        ("Đúng rồi! Con muốn nói gì thế?", "praise"),
        ("Con muốn nói là con chưa biết làm.", "no question"),
        ("Con cho cô số điện thoại được không?", "personal data"),
    ],
)
def test_a_question_the_validator_refuses_is_not_said(question, why):
    router = ScriptedRouter(reading("AMBIGUOUS_TYPO", "chưa biết làm", question))
    t = scene("answer", reader=LiveReader(ModelReader(router)))
    turn = t.on_student("kt")
    assert turn.move == Move.ASK_CONFIRM and turn.text != question, why
    assert turn.text.count("?") == 1 and "Cô" in turn.text
    sent = of_type(t, EventType.TUTOR_MESSAGE_SENT)[-1]
    assert sent["source"] != "LLM" and sent["source"] != "FALLBACK"
    rejected = of_type(t, EventType.OUTPUT_REJECTED)
    assert rejected and rejected[-1]["source"] == "LLM"


def test_no_model_or_a_model_that_is_down_asks_with_the_template():
    for reader in (None, LiveReader(None), LiveReader(ModelReader(ScriptedRouter(None)))):
        t = scene("answer", reader=reader)
        turn = t.on_student("ki")
        assert turn.move == Move.ASK_CONFIRM and turn.text.count("?") == 1 and not praised(turn.text)
        assert of_type(t, EventType.MESSAGE_READ)[-1]["source"] == "RULE"


def test_a_key_next_to_the_o_is_guessed_without_a_model():
    """ "ki": the i sits next to the o on the keyboard, so the child most likely typed "ko" (không)."""
    t = scene("answer")
    turn = t.on_student("ki")
    read = of_type(t, EventType.MESSAGE_READ)[-1]
    assert read["label"] == "AMBIGUOUS_TYPO" and read["guessed_meaning"]
    assert "phải không" in turn.text or "đúng không" in turn.text


def test_the_model_never_gets_a_phone_number_the_child_or_the_tutor_wrote():
    router = ScriptedRouter(reading("GIBBERISH"))
    ModelReader(router).read(
        stem="Gọi số 0912 345 678 hoặc mail an@x.vn", last_tutor="Con gọi 0912345678 nhé?", said="kt", turn=1
    )
    sent = " ".join(m.content for m in router.requests[0][1].messages)
    assert "0912" not in sent and "an@x.vn" not in sent


def test_a_model_label_that_is_not_one_of_the_two_still_asks_and_never_decides():
    # the model says the child answered; for a few letters nothing is graded and the tutor asks
    router = ScriptedRouter(reading("ANSWER", answer="0,3"))
    t = scene("answer", reader=LiveReader(ModelReader(router)))
    turn = t.on_student("kt")
    assert turn.move == Move.ASK_CONFIRM
    assert counts(t) == (0, 0)


def test_a_session_rebuilt_from_its_events_reads_the_record_and_never_asks_the_model_again():
    router = ScriptedRouter(reading("AMBIGUOUS_TYPO", "chưa biết làm", GUESS))
    live = scene("answer", reader=LiveReader(ModelReader(router)))
    first = live.on_student("kt")
    assert len(router.requests) == 1
    payloads = of_type(live, EventType.MESSAGE_READ)

    other = ScriptedRouter(reading("GIBBERISH"))
    replay = scene("answer", reader=recorded(payloads))
    again = replay.on_student("kt")
    assert other.requests == []
    assert (again.move, again.text) == (first.move, first.text)  # the question the child saw, word for word
    assert counts(replay) == counts(live)


# --------------------------------------------------------------------------- the teaching loop: theory,
# retell

CH = load_chapter(DOCS / "chuong-so-thap-phan/chapter.yaml")
T0 = datetime(2026, 10, 26, 8, 0, tzinfo=UTC)


def clock(n: int) -> datetime:
    return T0 + timedelta(seconds=10 * n)


def until(awaiting: Awaiting, loop: TeachingLoop, turn, n: int = 0):
    """Answers like a child who knows the lesson until the loop waits for ``awaiting``."""
    while turn.awaiting != awaiting:
        assert turn.awaiting != Awaiting.NOTHING
        if turn.awaiting == Awaiting.THEORY_REPLY:
            said = "Con nghĩ là được ạ."
        elif turn.awaiting == Awaiting.RETELL:
            said = ". ".join(ideas[0] for ideas in CH.node(turn.node_id).explain.key_ideas)
        else:
            from test_teaching_loop import correct_text

            item = CH.item(turn.item_id)
            said = (
                item.explanation
                if turn.item_phase in (Phase.VERIFYING, Phase.TEACH_BACK)
                else correct_text(turn.item_id)
            )
        n += 1
        turn = loop.on_student(said, clock(n), 10)
    return turn, n


@pytest.mark.parametrize("wait", [Awaiting.THEORY_REPLY, Awaiting.RETELL])
@pytest.mark.parametrize("said", ["ki", "kt", "ể", "kkk"])
def test_theory_and_retell_ask_once_and_stay_on_the_same_question(wait, said):
    loop = TeachingLoop(CH, "s1")
    turn = loop.start(T0)
    turn, n = until(wait, loop, turn)
    decisions = [e for e in loop.events if e.event_type == EventType.NODE_DECISION]
    judged = [e for e in loop.events if e.event_type == EventType.RETELL_JUDGED]
    asked = loop.on_student(clean(said).text, clock(n + 1), 10)
    assert asked.awaiting == wait and asked.prompt == turn.prompt and asked.node_id == turn.node_id
    assert [e for e in loop.events if e.event_type == EventType.NODE_DECISION] == decisions  # no step taken
    assert [e for e in loop.events if e.event_type == EventType.RETELL_JUDGED] == judged  # not judged
    text = " ".join(m.text for m in asked.messages)
    assert text.count("?") == 1 and not praised(text) and "cô" in text.lower()
    read = [e.payload for e in asked.events if e.event_type == "MESSAGE_READ"]
    assert read and read[-1]["label"] in ("AMBIGUOUS_TYPO", "GIBBERISH")


@pytest.mark.parametrize("wait", [Awaiting.THEORY_REPLY, Awaiting.RETELL])
def test_theory_and_retell_help_the_second_time_in_a_row(wait):
    loop = TeachingLoop(CH, "s1")
    turn = loop.start(T0)
    turn, n = until(wait, loop, turn)
    loop.on_student("ki", clock(n + 1), 10)
    helped = loop.on_student("tt", clock(n + 2), 10)
    text = " ".join(m.text for m in helped.messages)
    assert not praised(text)
    assert "Không sao" in text or "nhắc lại" in text  # the main idea, as for "con không biết"


@pytest.mark.parametrize("wait", [Awaiting.THEORY_REPLY, Awaiting.RETELL])
def test_a_resumed_session_knows_it_already_asked(wait):
    loop = TeachingLoop(CH, "s1")
    turn, n = until(wait, loop, loop.start(T0))
    loop.on_student("ki", clock(n + 1), 10)
    resumed = TeachingLoop.resume(CH, "s1", [], list(loop.events))
    a, b = loop.on_student("tt", clock(n + 2), 10), resumed.on_student("tt", clock(n + 2), 10)
    assert a.messages == b.messages and a.events == b.events


def test_a_bare_no_to_a_yes_no_theory_question_is_an_answer():
    from cavat.modules.teaching.loop import _yes_no

    assert _yes_no("Số 0,5 có lớn hơn 0,49 không?")
    assert classify_intent("không", verdict=True) is None
