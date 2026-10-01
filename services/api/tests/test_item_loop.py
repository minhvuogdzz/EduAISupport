"""Item loop (T04): conversation tests on the real lesson package, offline, template renderer only.

Every scenario must end with exactly one ITEM_RESOLVED, every payload must validate with
``PAYLOAD_MODELS`` and no message may be rejected by the validator (so nothing leaks the answer).
"""

from dataclasses import replace
from pathlib import Path

from cavat.core.events import PAYLOAD_MODELS, EventType
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.tutor.contracts import RenderContext, RenderedMessage
from cavat.modules.tutor.item_loop import MAX_STUDENT_TURNS, ItemTutor, Phase, TutorEvent, TutorTurn
from cavat.modules.tutor.policy import DEFAULT_CONFIG
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"
PKG = load_lesson_package(LESSON)
NO_VERIFY = replace(DEFAULT_CONFIG, verify_rate=0.0)
ALWAYS_VERIFY = replace(DEFAULT_CONFIG, verify_rate=1.0)


def tutor(item_id: str, cfg=NO_VERIFY, renderer=None) -> ItemTutor:
    return ItemTutor(
        PKG.item(item_id),
        PKG,
        ActivityType.GUIDED_PRACTICE,
        renderer or TemplateRenderer(),
        validate_message,
        cfg,
    )


def talk(t: ItemTutor, *replies: str) -> list[TutorTurn]:
    turns = [t.start()]
    for reply in replies:
        turns.append(t.on_student(reply, 10))
    return turns


def of_type(events: list[TutorEvent], event_type: EventType) -> list[dict]:
    return [e.payload for e in events if e.type == event_type]


def resolved(t: ItemTutor) -> dict:
    """Shared end-of-scenario checks; returns the ITEM_RESOLVED payload."""
    assert t.phase == Phase.RESOLVED
    for e in t.events:
        PAYLOAD_MODELS[e.type].model_validate(e.payload)
    assert [e.type for e in t.events].count(EventType.ITEM_RESOLVED) == 1
    assert t.events[-1].type == EventType.ITEM_RESOLVED
    assert of_type(t.events, EventType.OUTPUT_REJECTED) == []
    assert all(m["source"] != "FALLBACK" for m in of_type(t.events, EventType.TUTOR_MESSAGE_SENT))
    decisions = of_type(t.events, EventType.POLICY_DECISION)
    assert all(d["rule_ids"] for d in decisions)
    return t.events[-1].payload


def moves(turns: list[TutorTurn]) -> list[Move]:
    return [turn.move for turn in turns]


def test_student_with_m01() -> None:
    t = tutor("GP-01", ALWAYS_VERIFY)
    turns = talk(t, "0,25 > 0,3", "0,25 < 0,3", "vì ở hàng phần mười 2 bé hơn 3")
    assert moves(turns) == [Move.PRESENT, Move.COGNITIVE_CONFLICT, Move.VERIFY, Move.CONFIRM_ADVANCE]
    assert "0,25 mét" in turns[1].text  # the counter-example of DEC-M01, filled with the item numbers
    assert turns[2].text == PKG.item("GP-01").verify_prompt
    detected = of_type(t.events, EventType.MISCONCEPTION_DETECTED)
    assert [(d["misconception_id"], d["source"]) for d in detected] == [("DEC-M01", "BUG_RULE")]
    assert len(of_type(t.events, EventType.EXPLANATION_SUBMITTED)) == 1
    end = resolved(t)
    assert end["resolution"] == "SUPPORTED"
    assert (end["attempts"], end["max_hint_level"], end["hints_count"]) == (2, 2, 1)
    assert end["misconception_ids"] == ["DEC-M01"]
    assert end["explained"] is True


def test_student_asks_for_a_hint() -> None:
    t = tutor("GP-01")
    turns = talk(t, "con không biết", "cô gợi ý đi", "0,25 < 0,3")
    assert moves(turns) == [Move.PRESENT, Move.OFFER_CHOICE, Move.HINT, Move.CONFIRM_ADVANCE]
    assert turns[1].phase == Phase.AWAITING_CHOICE
    hints = of_type(t.events, EventType.HINT_DELIVERED)
    assert [(h["hint_level"], h["hint_target"], h["source"]) for h in hints] == [(1, "TASK", "TEMPLATE")]
    end = resolved(t)
    assert (end["resolution"], end["attempts"], end["max_hint_level"]) == ("SUPPORTED", 1, 1)
    assert end["explained"] is None


def test_the_reply_to_the_probe_is_not_a_second_wrong_answer() -> None:
    """The owner's trial on GP-01 (2026-10-01): "=", then "thì nó bằng thật mà", then "Xin gợi ý".

    Before: the reply was graded as a second wrong answer, the request counted as a third unproductive
    turn and the tutor went straight to the worked solution without giving one hint of the lesson.
    """
    t = tutor("GP-01")
    turns = talk(t, "=", "thì nó bằng thật mà", "con cần gợi ý", "con cần gợi ý", "=")
    assert moves(turns) == [
        Move.PRESENT,
        Move.PROBE,
        Move.HINT,  # the item's level 1 hint, not the fixed fallback sentence
        Move.OFFER_CHOICE,  # asking for help is not "stuck": the next hint is offered
        Move.HINT,
        Move.HINT,  # second wrong answer: one more rung, still no worked solution
    ]
    assert turns[1].phase == Phase.AWAITING_REASON
    assert (t.state.attempt_no, t.state.unproductive_turns, t.state.probes_sent) == (2, 2, 1)
    assert t.state.worked_shown is False
    hints = of_type(t.events, EventType.HINT_DELIVERED)
    assert [(h["hint_level"], h["source"], h["template_ref"]) for h in hints] == [
        (1, "TEMPLATE", "GP-01:TASK:H1"),
        (2, "TEMPLATE", "GP-01:CONCEPT:H2"),
        (3, "TEMPLATE", "GP-01:STRATEGY:H3"),
    ]
    answers = of_type(t.events, EventType.ANSWER_SUBMITTED)
    assert [(a["attempt_no"], a["raw_text"]) for a in answers] == [(1, "="), (2, "=")]
    reasons = of_type(t.events, EventType.EXPLANATION_SUBMITTED)
    assert [r["text"] for r in reasons] == ["thì nó bằng thật mà"]

    turns.append(t.on_student("0,25 < 0,3", 10))
    end = resolved(t)
    assert (end["resolution"], end["attempts"], end["max_hint_level"]) == ("SUPPORTED", 3, 3)


def test_words_after_the_probe_get_the_first_hint_not_a_redirect() -> None:
    t = tutor("GP-01")
    turns = talk(t, "=", "con thấy hai số giống nhau")
    assert moves(turns) == [Move.PRESENT, Move.PROBE, Move.HINT]
    assert (t.state.attempt_no, t.state.unproductive_turns) == (1, 1)
    assert turns[2].phase == Phase.AWAITING


def test_a_new_answer_after_the_probe_is_graded() -> None:
    corrected = tutor("GP-01")
    turns = talk(corrected, "=", "à con nhầm, 0,25 < 0,3")
    assert moves(turns) == [Move.PRESENT, Move.PROBE, Move.CONFIRM_ADVANCE]
    end = resolved(corrected)
    assert (end["resolution"], end["attempts"]) == ("INDEPENDENT", 2)

    changed = tutor("GP-01")
    talk(changed, "=", "0,25 > 0,3")  # another wrong answer is a second attempt
    assert (changed.state.attempt_no, changed.state.unproductive_turns) == (2, 2)

    asks = tutor("GP-01")
    turns = talk(asks, "=", "con không biết")
    assert moves(turns)[-1] == Move.OFFER_CHOICE and asks.state.attempt_no == 1


def test_asking_for_hints_climbs_the_ladder_then_shows_the_worked_steps() -> None:
    t = tutor("GP-01")
    t.start()
    seen = []
    for _ in range(11):
        seen.append(t.on_student("con cần gợi ý", 5).move)
    assert seen == [Move.OFFER_CHOICE, Move.HINT] * 5 + [Move.WORKED_GUIDANCE]
    assert [int(level) for level in t.state.hint_levels] == [1, 2, 3, 4, 5, 6]
    assert t.state.unproductive_turns == 0 and t.state.help_requests == 6


def test_silent_student() -> None:
    t = tutor("GP-01")
    t.start()
    turns = []
    while t.phase != Phase.RESOLVED:
        turns.append(t.on_student("", 50))
    assert len(turns) <= MAX_STUDENT_TURNS
    # Two nudges, R-FRUSTRATION on the third silent turn, then R-FULL: silence after H6 is "stalled"
    # (DI approved 2026-10-01), so the tutor explains in full and invites a teach-back.
    assert moves(turns) == [
        Move.NUDGE,
        Move.NUDGE,
        Move.WORKED_GUIDANCE,
        Move.FULL_EXPLANATION,
        Move.CLOSE_ITEM,
    ]
    assert of_type(t.events, EventType.ANSWER_SUBMITTED) == []  # silence is never a wrong answer
    end = resolved(t)
    assert (end["resolution"], end["attempts"]) == ("UNRESOLVED", 0)  # never solved, never retold
    assert (end["max_hint_level"], end["explained"]) == (7, False)


def test_silent_student_who_retells_after_the_full_explanation() -> None:
    t = tutor("GP-01")
    turns = talk(t, "", "", "", "", "so sánh hàng phần mười trước, 2 bé hơn 3")
    assert moves(turns)[3:] == [Move.WORKED_GUIDANCE, Move.FULL_EXPLANATION, Move.CONFIRM_ADVANCE]
    end = resolved(t)
    assert (end["resolution"], end["max_hint_level"], end["explained"]) == ("WORKED", 7, True)
    assert end["attempts"] == 0


def test_correct_at_once() -> None:
    t = tutor("GP-01")
    turns = talk(t, "0,25 < 0,3")
    assert moves(turns) == [Move.PRESENT, Move.CONFIRM_ADVANCE]
    end = resolved(t)
    assert (end["resolution"], end["attempts"], end["max_hint_level"]) == ("INDEPENDENT", 1, 0)
    assert end["explained"] is None and end["final_error_class"] is None


def test_requires_explanation_is_always_verified() -> None:
    t = tutor("GP-09")  # boolean item with requires_explanation, verify_rate 0
    turns = talk(t, "sai", "vì bạn An so sánh 25 với 3 như số tự nhiên")
    assert moves(turns) == [Move.PRESENT, Move.VERIFY, Move.CONFIRM_ADVANCE]
    assert turns[1].phase == Phase.VERIFYING
    end = resolved(t)
    assert (end["resolution"], end["explained"]) == ("INDEPENDENT", True)


def test_probe_compared_wrongly_is_dec_m01() -> None:
    t = tutor("GP-08")
    turns = talk(t, "Lan", "9,75 lớn hơn", "Hoa")
    assert moves(turns) == [Move.PRESENT, Move.PROBE, Move.COGNITIVE_CONFLICT, Move.CONFIRM_ADVANCE]
    assert turns[1].text == "Con so sánh giúp cô: 9,8 và 9,75, số nào lớn hơn?"
    assert turns[1].phase == Phase.AWAITING_PROBE
    first = of_type(t.events, EventType.ANSWER_SUBMITTED)[0]
    assert first["misconception_id"] is None  # nothing attributed before the probe answer
    detected = of_type(t.events, EventType.MISCONCEPTION_DETECTED)
    assert [d["misconception_id"] for d in detected] == ["DEC-M01"]
    end = resolved(t)
    assert end["misconception_ids"] == ["DEC-M01"]
    assert (end["resolution"], end["attempts"]) == ("SUPPORTED", 2)


def test_probe_compared_correctly_is_apply_time_speed() -> None:
    t = tutor("GP-08")
    turns = talk(t, "Lan", "9,8 lớn hơn", "Hoa")
    assert moves(turns)[1] == Move.PROBE
    end = resolved(t)
    assert end["misconception_ids"] == ["APPLY-TIME-SPEED"]


def test_probe_without_answer_attributes_nothing() -> None:
    t = tutor("GP-08")
    turns = talk(t, "Lan", "", "Hoa")
    assert moves(turns)[1:3] == [Move.PROBE, Move.NUDGE]
    assert of_type(t.events, EventType.MISCONCEPTION_DETECTED) == []
    assert resolved(t)["misconception_ids"] == []


def test_ambiguous_misconceptions_are_not_attributed() -> None:
    t = tutor("GP-05")
    t.start()
    turn = t.on_student("0,50 > 0,5", 10)
    submitted = of_type(t.events, EventType.ANSWER_SUBMITTED)[0]
    assert submitted["misconception_id"] is None
    assert turn.move != Move.COGNITIVE_CONFLICT
    assert of_type(t.events, EventType.MISCONCEPTION_DETECTED) == []
    t.on_student("0,50 = 0,5", 10)
    assert resolved(t)["misconception_ids"] == []


def test_worked_then_teach_back() -> None:
    t = tutor("GP-01")
    turns = talk(t, "0,25 > 0,3", "0,25 > 0,3", "0,25 > 0,3", "0,25 < 0,3", "so sánh hàng phần mười trước")
    assert moves(turns)[3:] == [Move.WORKED_GUIDANCE, Move.TEACH_BACK, Move.CONFIRM_ADVANCE]
    end = resolved(t)
    assert (end["resolution"], end["max_hint_level"], end["explained"]) == ("WORKED", 6, True)


class _LeakyRenderer:
    """Always states the answer; the loop must retry once, then fall back to a fixed sentence."""

    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self.fail_times = fail_times
        self.inner = TemplateRenderer()

    def render(self, ctx: RenderContext) -> RenderedMessage:
        self.calls += 1
        if ctx.decision.move == Move.PRESENT or self.calls > self.fail_times + 1:
            return self.inner.render(ctx)
        return RenderedMessage(text="Đáp án là 0,25 < 0,3 nhé?", source="LLM")


def test_rejected_output_retries_then_falls_back() -> None:
    t = tutor("GP-01", renderer=_LeakyRenderer(fail_times=2))
    turn = talk(t, "0,25 > 0,3")[1]
    rejected = of_type(t.events, EventType.OUTPUT_REJECTED)
    assert len(rejected) == 2 and "ANSWER_LEAK" in rejected[0]["issue_codes"]
    sent = of_type(t.events, EventType.TUTOR_MESSAGE_SENT)[-1]
    assert (sent["source"], sent["attempts_to_pass_validator"]) == ("FALLBACK", 3)
    assert "0,25 < 0,3" not in turn.text
    assert of_type(t.events, EventType.HINT_DELIVERED) == []  # no hint content reached the student

    retry = tutor("GP-01", renderer=_LeakyRenderer(fail_times=1))
    talk(retry, "0,25 > 0,3")
    assert len(of_type(retry.events, EventType.OUTPUT_REJECTED)) == 1
    assert of_type(retry.events, EventType.TUTOR_MESSAGE_SENT)[-1]["attempts_to_pass_validator"] == 2
