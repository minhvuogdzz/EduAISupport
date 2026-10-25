"""PRIOR-3 (DI-66): R-STRONG-PRIOR changes a move in a real session once the Student Model is sure enough.

PRIOR-1/2 measured that the rule never fired: a child passes a period inside one session, and the DI-11
confidence of a period seen in one session is at most 0.70 * f_n * f_div * f_cons, under the 0.6 [FACT]. A
period whose evidence spans two sessions at least 3 days apart gets f_span = 1.0; the next wrong answers
of that child then get "vì sao" (VERIFY) instead of a light hint. Two sessions on the same day keep
f_span = 0.85 and the rule stays off. Offline, templates only."""

from __future__ import annotations

from datetime import timedelta

from cavat.core.events import EventType
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from test_teaching_loop import CHAPTER, EXPLAINING, T0, Learner

NODE = "KC-DEC-EQ"


class WrongTwice(Learner):
    """Answers every item wrong twice, then as the strong learner does."""

    def __init__(self) -> None:
        super().__init__()
        self.tries: dict[str, int] = {}

    def reply(self, turn) -> str:
        if turn.awaiting == Awaiting.ANSWER and turn.item_id and turn.item_phase not in EXPLAINING:
            tries = self.tries.get(turn.item_id, 0)
            if tries < 2:
                self.tries[turn.item_id] = tries + 1
                return "123"
        return super().reply(turn)


def _resolved_on(loop: TeachingLoop, node_id: str) -> int:
    return sum(
        1
        for e in loop.events
        if e.event_type == EventType.ITEM_RESOLVED and node_id in e.payload.get("kc_ids", [])
    )


def _second_session(gap: timedelta) -> tuple[TeachingLoop, float]:
    """Session 1 stops after two items of NODE; session 2 starts ``gap`` later. Returns it, top confidence."""
    first, learner = TeachingLoop(CHAPTER, "s1"), Learner()
    turn = first.start(T0)
    for i in range(800):
        if turn.awaiting == Awaiting.NOTHING or _resolved_on(first, NODE) >= 2:
            break
        turn = first.on_student(learner.reply(turn), T0 + timedelta(seconds=10 * i), 10)
    assert _resolved_on(first, NODE) == 2
    start = T0 + gap
    second, learner = TeachingLoop(CHAPTER, "s2", first.events), WrongTwice()
    turn, top = second.start(start), 0.0
    for i in range(800):
        if turn.awaiting == Awaiting.NOTHING:
            return second, top
        if second.tutor is not None:
            top = max(top, second.tutor.snapshot.kc_confidence.get(NODE, 0.0))
        turn = second.on_student(learner.reply(turn), start + timedelta(seconds=10 * i), 10)
    raise AssertionError("the second session never finished")


def _strong_prior_moves(loop: TeachingLoop) -> list[str]:
    return [
        e.payload.get("move")
        for e in loop.events
        if e.event_type == EventType.POLICY_DECISION and "R-STRONG-PRIOR" in e.payload.get("rule_ids", ())
    ]


def test_a_period_learnt_over_two_sessions_days_apart_turns_a_light_hint_into_why():
    loop, top = _second_session(timedelta(days=4))
    assert top >= 0.6
    assert _strong_prior_moves(loop) == ["VERIFY"]  # once per item, and only on a light hint


def test_two_sessions_on_the_same_day_are_not_enough_evidence():
    loop, top = _second_session(timedelta(hours=5))
    assert top < 0.6
    assert _strong_prior_moves(loop) == []
