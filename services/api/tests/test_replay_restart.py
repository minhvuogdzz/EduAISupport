"""FIX-4: a session whose open item replays differently with today's code is not stuck.

A session of 2026-10-12 stopped answering on 2026-10-19 ("Chưa gửi được"): its first "không" had been read
by Qwen as "con không biết", today's checker grades it as a wrong answer, so the replay of the item took
other moves and closed it before the child's words ran out ("item already resolved"). Now the item starts
again, ITEM_RESTARTED is recorded before the next input, and later rebuilds replay from that mark.
Offline: the change of code is a checker swapped during the replay."""

from __future__ import annotations

from dataclasses import replace

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import Outcome
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor import item_loop
from test_safety import CHAPTER, NOW, loop_at_first_item

WORDS = ["3/7", "10/3"]


def live_session() -> TeachingLoop:
    """The child answers the first item wrongly twice, with today's code: the item stays open."""
    loop = loop_at_first_item()
    for said in WORDS:
        assert loop.awaiting == Awaiting.ANSWER
        loop.on_student(said, NOW)
    assert loop.awaiting == Awaiting.ANSWER and loop.tutor is not None
    return loop


@pytest.fixture
def code_change(monkeypatch):
    """``apply()``: the code that rebuilds the session grades "3/7" as right, so its replay closes the item
    early; ``undo()``: the code of the live session again."""
    real = item_loop.check_answer

    def check(item, text, package=None):
        result = real(item, text, package)
        if text.strip() == "3/7":
            return replace(result, outcome=Outcome.CORRECT, error_class=None)
        return result

    class Change:
        @staticmethod
        def apply():
            monkeypatch.setattr(item_loop, "check_answer", check)

        @staticmethod
        def undo():
            monkeypatch.setattr(item_loop, "check_answer", real)

    return Change


def test_a_replay_that_closes_the_item_early_starts_it_again(code_change):
    events = live_session().events
    code_change.apply()
    rebuilt = TeachingLoop.resume(CHAPTER, "s1", [], events)  # no "item already resolved"
    assert rebuilt.awaiting == Awaiting.ANSWER and rebuilt.tutor is not None
    assert rebuilt.tutor.state.attempt_no == 0  # the item starts again
    item = rebuilt.tutor.item.id

    turn = rebuilt.on_student("là sao ạ", NOW)
    kinds = [e.event_type for e in turn.events]
    assert kinds[:2] == [EventType.ITEM_RESTARTED, EventType.STUDENT_MESSAGE]
    assert turn.events[0].payload == {"item_id": item, "reason": "REPLAY_DIVERGED"}
    live = rebuilt.tutor

    again = TeachingLoop.resume(CHAPTER, "s1", [], [*events, *turn.events])  # only what follows the mark
    assert again.tutor is not None and again._restart is None
    assert again.tutor.phase == live.phase and again.tutor.state.hint_levels == live.state.hint_levels

    code_change.undo()  # with the code of the live session too, the mark keeps the replay on the new start
    once_more = TeachingLoop.resume(CHAPTER, "s1", [], [*events, *turn.events])
    assert once_more.tutor is not None and once_more.tutor.phase == live.phase


def test_a_replay_that_agrees_records_no_mark():
    loop = live_session()
    rebuilt = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)
    assert rebuilt._restart is None
    assert rebuilt.tutor is not None and rebuilt.tutor.state.attempt_no == loop.tutor.state.attempt_no
    turn = rebuilt.on_student("7/10", NOW)
    assert EventType.ITEM_RESTARTED not in [e.event_type for e in turn.events]
