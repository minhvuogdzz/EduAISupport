"""Adaptive hint policy (T02): exactly one test per R-* rule of blueprint PART 15.2."""

from __future__ import annotations

from typing import Any, cast

from cavat.core.pedagogy import (
    ActivityType,
    ErrorClass,
    HintLevel,
    HintTarget,
    ItemResolution,
    Move,
    Outcome,
)
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.content.lesson_package import Item
from cavat.modules.tutor.contracts import (
    ItemState,
    PolicyDecision,
    PolicyInput,
    StudentSnapshot,
    TurnTrigger,
)
from cavat.modules.tutor.policy import DEFAULT_CONFIG, ItemFacts, decide, wait_seconds

H1, H2, H3, H6, H7 = (HintLevel(n) for n in (1, 2, 3, 6, 7))
ITEM = cast(Item, object())  # the policy reads nothing from Item; ItemFacts carries what it needs
STRONG = StudentSnapshot(kc_mastery={"KC1": 0.9}, kc_confidence={"KC1": 0.8})
WEAK = StudentSnapshot(kc_mastery={"KC1": 0.2}, kc_confidence={"KC1": 0.8})
KC1 = ItemFacts(kc_ids=("KC1",))


def _inp(
    check: CheckResult | None = None,
    *,
    trigger: TurnTrigger = "ANSWER",
    activity: ActivityType = ActivityType.GUIDED_PRACTICE,
    snapshot: StudentSnapshot | None = None,
    time_left_s: float = float("inf"),
    reserve_s: float = 0.0,
    **state: Any,
) -> PolicyInput:
    return PolicyInput(
        item=ITEM,
        state=ItemState(item_id="I1", activity=activity, **state),
        check=check,
        trigger=trigger,
        snapshot=snapshot or StudentSnapshot(),
        time_left_s=time_left_s,
        assessment_reserve_s=reserve_s,
    )


def _check(
    outcome: Outcome = Outcome.WRONG,
    error: ErrorClass | None = None,
    mis: str | None = None,
    conf: float = 0.0,
) -> CheckResult:
    return CheckResult(
        outcome=outcome, error_class=error, misconception_id=mis, misconception_confidence=conf
    )


def _decide(inp: PolicyInput, facts: ItemFacts | None = None) -> PolicyDecision:
    decision = decide(inp, facts)
    assert decision is not None
    return decision


def test_r_slip() -> None:
    # A repeated calculation slip stays a SELF_CHECK at H1: no escalation, never towards CONCEPT.
    d = _decide(
        _inp(
            _check(error=ErrorClass.CALCULATION),
            attempt_no=2,
            hint_levels=[H1],
            hint_targets=[HintTarget.SELF_CHECK],
        )
    )
    assert (d.move, d.target, d.level) == (Move.HINT, HintTarget.SELF_CHECK, H1)
    assert d.rule_ids == ("R-SLIP",)


def test_r_misc_high() -> None:
    wrong = _check(error=ErrorClass.CONCEPTUAL, mis="M1", conf=0.8)
    with_counterexample = _decide(_inp(wrong, attempt_no=1), ItemFacts(counterexamples=frozenset({"M1"})))
    assert (with_counterexample.move, with_counterexample.target) == (
        Move.COGNITIVE_CONFLICT,
        HintTarget.CONCEPT,
    )
    assert with_counterexample.level == H2
    assert with_counterexample.misconception_id == "M1"
    assert "R-MISC-HIGH" in with_counterexample.rule_ids

    already_h3 = _decide(_inp(wrong, attempt_no=2, hint_levels=[H3], hint_targets=[HintTarget.STEP]))
    assert (already_h3.move, already_h3.target, already_h3.level) == (
        Move.HINT,
        HintTarget.CONCEPT,
        H3,
    )


def test_r_first_wrong() -> None:
    first = _decide(_inp(_check(), attempt_no=1))
    assert first.move == Move.PROBE
    assert first.level is None
    assert first.rule_ids == ("R-FIRST-WRONG",)

    after_probe = _decide(_inp(_check(), attempt_no=2))
    assert (after_probe.move, after_probe.level) == (Move.HINT, H1)


def test_r_no_response() -> None:
    wait = wait_seconds(_inp())
    assert 30 <= wait <= 60
    assert decide(_inp(trigger="SILENCE", seconds_since_last_message=wait - 1)) is None

    d = _decide(_inp(trigger="SILENCE", seconds_since_last_message=wait))
    assert (d.move, d.target, d.level) == (Move.NUDGE, HintTarget.TASK, H1)
    assert "NOT_COUNTED_AS_WRONG" in d.reason_codes
    assert d.resolution is None
    assert d.rule_ids == ("R-NO-RESPONSE",)


def test_r_help_request() -> None:
    d = _decide(_inp(trigger="HINT_REQUEST", hint_levels=[H1], hint_targets=[HintTarget.STEP]))
    assert (d.move, d.level, d.target) == (Move.OFFER_CHOICE, H2, HintTarget.STEP)
    assert d.rule_ids == ("R-HELP-REQUEST",)

    demand = _decide(_inp(_check(Outcome.ANSWER_DEMAND)))
    assert (demand.move, demand.level) == (Move.OFFER_CHOICE, H1)


def test_r_escalate() -> None:
    state = {"attempt_no": 2, "hint_levels": [H1], "hint_targets": [HintTarget.STEP]}
    wrong = _check(error=ErrorClass.PROCEDURAL)

    d = _decide(_inp(wrong, **state))
    assert (d.move, d.target, d.level) == (Move.HINT, HintTarget.STEP, H2)
    assert d.rule_ids == ("R-ESCALATE",)

    upset = _decide(_inp(wrong, nudges_sent=2, **state))
    assert upset.level == H3
    assert "NEGATIVE_AFFECT" in upset.reason_codes


def test_r_deescalate() -> None:
    d = _decide(
        _inp(
            _check(Outcome.PARTIAL),
            attempt_no=3,
            hint_levels=[H2, H3],
            hint_targets=[HintTarget.STEP, HintTarget.STEP],
        )
    )
    assert (d.move, d.target, d.level) == (Move.HINT, HintTarget.STEP, H2)
    assert d.rule_ids == ("R-DEESCALATE",)


def test_r_frustration() -> None:
    by_turns = _decide(_inp(_check(), attempt_no=3, hint_levels=[H1, H2], unproductive_turns=3))
    assert (by_turns.move, by_turns.level) == (Move.WORKED_GUIDANCE, H6)
    assert "NEXT_TWIN_ITEM_H0" in by_turns.reason_codes
    assert by_turns.rule_ids == ("R-FRUSTRATION",)

    by_time = _decide(_inp(trigger="TICK", seconds_since_shown=DEFAULT_CONFIG.stuck_s + 1))
    assert by_time.move == Move.WORKED_GUIDANCE


def test_r_full() -> None:
    after_worked = {"attempt_no": 4, "hint_levels": [H2, H6], "worked_shown": True}

    d = _decide(_inp(_check(), **after_worked))
    assert (d.move, d.level) == (Move.FULL_EXPLANATION, H7)
    assert {"NEXT_TEACH_BACK", "NEXT_TWIN_ITEM"} <= set(d.reason_codes)
    assert d.rule_ids == ("R-FULL",)

    out_of_practice = _decide(_inp(_check(), activity=ActivityType.CONCEPT_CHECK, **after_worked))
    assert (out_of_practice.move, out_of_practice.resolution) == (
        Move.CLOSE_ITEM,
        ItemResolution.UNRESOLVED,
    )

    time_up = _decide(
        _inp(trigger="TICK", time_left_s=60, reserve_s=120), ItemFacts(mandatory_objective=True)
    )
    assert (time_up.move, time_up.level) == (Move.FULL_EXPLANATION, H7)


def test_r_assess_cap() -> None:
    exit_test = ActivityType.EXIT_ASSESSMENT
    misconception = _check(error=ErrorClass.CONCEPTUAL, mis="M1", conf=0.9)

    capped = _decide(_inp(misconception, activity=exit_test, attempt_no=1))
    assert (capped.move, capped.level) == (Move.HINT, H1)
    assert "EVIDENCE_SUPPORTED" in capped.reason_codes
    assert "R-ASSESS-CAP" in capped.rule_ids

    beyond_cap = _decide(_inp(misconception, activity=exit_test, attempt_no=2, hint_levels=[H1]))
    assert (beyond_cap.move, beyond_cap.resolution) == (Move.CLOSE_ITEM, ItemResolution.UNRESOLVED)

    solved = _decide(_inp(_check(Outcome.CORRECT), activity=exit_test, hint_levels=[H1]))
    assert (solved.move, solved.resolution) == (Move.CONFIRM_ADVANCE, ItemResolution.SUPPORTED)


def test_r_strong_prior() -> None:
    assert wait_seconds(_inp(snapshot=STRONG), KC1) > wait_seconds(_inp(), KC1)
    silence = _inp(trigger="SILENCE", snapshot=STRONG, seconds_since_last_message=DEFAULT_CONFIG.wait_s)
    assert decide(silence, KC1) is None

    d = _decide(_inp(_check(error=ErrorClass.CALCULATION), snapshot=STRONG, attempt_no=1), KC1)
    assert d.move == Move.VERIFY
    assert d.level is None
    assert "R-STRONG-PRIOR" in d.rule_ids


def test_r_weak_prior() -> None:
    assert wait_seconds(_inp(snapshot=WEAK), KC1) < wait_seconds(_inp(), KC1)

    wrong = _check(error=ErrorClass.CONCEPTUAL, mis="M1", conf=0.4)
    d = _decide(_inp(wrong, snapshot=WEAK, attempt_no=1), KC1)
    assert (d.move, d.target, d.level) == (Move.HINT, HintTarget.CONCEPT, H2)
    assert d.rule_ids == ("R-WEAK-PRIOR",)

    dependent = _decide(_inp(wrong, snapshot=StudentSnapshot(hint_dependency=0.6), attempt_no=1))
    assert dependent.level == H2


def test_r_time() -> None:
    short = {"time_left_s": 150.0, "reserve_s": 120.0}  # less than reserve + expected item time

    hurried = _decide(_inp(_check(error=ErrorClass.PROCEDURAL), attempt_no=1, **short))
    assert (hurried.move, hurried.target, hurried.level) == (Move.HINT, HintTarget.STEP, H1)
    assert "R-TIME" in hurried.rule_ids

    escalated = _decide(
        _inp(
            _check(error=ErrorClass.PROCEDURAL),
            attempt_no=2,
            hint_levels=[H1],
            hint_targets=[HintTarget.STEP],
            **short,
        )
    )
    assert escalated.level == H3

    out_of_time = _decide(_inp(_check(), attempt_no=1, time_left_s=100.0, reserve_s=120.0))
    assert (out_of_time.move, out_of_time.resolution) == (Move.CLOSE_ITEM, ItemResolution.UNRESOLVED)
    assert out_of_time.rule_ids == ("R-TIME",)
