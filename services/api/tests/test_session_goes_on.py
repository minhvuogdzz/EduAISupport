"""FLOW-1 (DI-75): a period the child cannot pass no longer ends the session.

The owner (2026-10-26): a child who has not understood is taught again and the session goes on to the next
lesson; a child who has understood goes on too. Before, the stopped period kept every later period locked, so
one weak first period ended the whole session with "0/11 passed". Offline, templates only."""

from __future__ import annotations

from datetime import timedelta

from cavat.modules.teaching.loop import Awaiting, MessageKind, TeachingLoop
from test_teaching_loop import CHAPTER, EXPLAINING, T0, Learner

FIRST = "KC-DEC-FRAC"


class Struggler(Learner):
    """Gets every question of the first period wrong, and is right everywhere else."""

    def reply(self, turn) -> str:
        if turn.awaiting == Awaiting.ANSWER and turn.node_id == FIRST and turn.item_phase not in EXPLAINING:
            return "123"
        return super().reply(turn)


def _whole_session():
    loop, learner = TeachingLoop(CHAPTER, "s1"), Struggler()
    turns = [loop.start(T0)]
    for i in range(900):
        if turns[-1].awaiting == Awaiting.NOTHING:
            return turns
        turns.append(loop.on_student(learner.reply(turns[-1]), T0 + timedelta(seconds=10 * i), 10))
    raise AssertionError("the session never finished")


def _messages(turns):
    return [m for t in turns for m in t.messages]


def test_the_session_goes_on_to_the_next_periods_after_one_the_child_could_not_pass():
    messages = _messages(_whole_session())
    kinds = [(m.kind, m.node_id) for m in messages]
    stop = next(i for i, (kind, node) in enumerate(kinds) if kind == MessageKind.STOP and node == FIRST)
    assert any(kind == MessageKind.PASS for kind, _ in kinds[stop + 1 :])  # later periods are passed
    assert (MessageKind.PASS, FIRST) not in kinds  # the weak one is never marked as passed
    assert messages[-1].kind == MessageKind.SUMMARY


def test_the_stop_message_says_the_method_again_and_the_summary_lists_the_weak_period():
    messages = _messages(_whole_session())
    stop = next(m for m in messages if m.kind == MessageKind.STOP)
    assert CHAPTER.node(FIRST).method.rule in stop.text
    assert "dừng ở đây" not in stop.text
    assert CHAPTER.node(FIRST).name in messages[-1].text  # "còn cần ôn thêm"


class SlowStarter(Learner):
    """FLOW-2: misses the check and the "cùng làm" question of the first period the first time it is
    taught, and is right the second time (the period is entered again)."""

    def __init__(self) -> None:
        super().__init__()
        self.visits = 0

    def reply(self, turn) -> str:
        self.visits += sum(
            m.kind == MessageKind.NODE
            and m.node_id == FIRST
            and ("cùng học" in m.text or "một lần nữa" in m.text)
            for m in turn.messages
        )
        if (
            turn.awaiting == Awaiting.ANSWER
            and turn.item_id in ("TP-CC-01", "TP-CP-01")
            and turn.item_phase not in EXPLAINING
            and self.visits < 2
        ):
            return "123"
        return super().reply(turn)


def _session_of(learner):
    loop = TeachingLoop(CHAPTER, "s1")
    turns = [loop.start(T0)]
    for i in range(900):
        if turns[-1].awaiting == Awaiting.NOTHING:
            return turns
        turns.append(loop.on_student(learner.reply(turns[-1]), T0 + timedelta(seconds=10 * i), 10))
    raise AssertionError("the session never finished")


def test_a_period_stopped_today_is_taught_again_at_the_end_with_another_example():
    """FLOW-2 (DI-80): the owner (2026-10-26): back to the weak period once more in the same session."""
    messages = _messages(_session_of(SlowStarter()))
    kinds = [(m.kind, m.node_id) for m in messages]
    stop = next(i for i, k in enumerate(kinds) if k == (MessageKind.STOP, FIRST))
    opening = next(m for m in messages[stop:] if m.kind == MessageKind.NODE and m.node_id == FIRST)
    assert CHAPTER.node(FIRST).name in opening.text and "một lần nữa" in opening.text
    examples = [m for m in messages if m.kind == MessageKind.EXAMPLE and m.node_id == FIRST]
    assert len(examples) == 2 and examples[0].ref != examples[1].ref  # another example, not the same one
    assert (MessageKind.PASS, FIRST) in kinds[stop:]
    assert "Còn cần ôn thêm" not in messages[-1].text  # passed on the second pass: no longer to revise
    assert CHAPTER.node(FIRST).name in messages[-1].text  # ... and listed among the periods learnt today


def test_a_period_stopped_twice_stays_to_revise_and_is_not_taught_a_third_time():
    messages = _messages(_whole_session())
    kinds = [(m.kind, m.node_id) for m in messages]
    assert kinds.count((MessageKind.STOP, FIRST)) == 2
    assert (
        sum(m.kind == MessageKind.NODE and m.node_id == FIRST and "cùng học" in m.text for m in messages) == 1
    )
    assert sum("một lần nữa" in m.text for m in messages if m.node_id == FIRST) == 1
    assert (MessageKind.PASS, FIRST) not in kinds
    assert "Còn cần ôn thêm" in messages[-1].text and CHAPTER.node(FIRST).name in messages[-1].text
