"""VERIFY-1 (DI-65): "vì sao" follows a right answer by how sure the child is of the KC, not a flat 30%.

The owner approved on 2026-10-22: the first right answer on a KC of the session and a right answer on a KC
below 0.6 mastery always get "vì sao" (the self-explanation helps most while the knowledge is new); a KC the
child holds, or one with no mastery yet past its first right answer, keeps the 30% sample. Offline."""

from __future__ import annotations

from typing import cast

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, Move, Outcome
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.content.lesson_package import Item
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.contracts import ItemState, PolicyInput, StudentSnapshot
from cavat.modules.tutor.policy import ItemFacts, _sampled, decide
from test_teaching_loop import CHAPTER, T0, correct_text

NOT_SAMPLED = next(f"I{n}" for n in range(100) if not _sampled(f"I{n}", 0.3))


def right(activity=ActivityType.GUIDED_PRACTICE, **facts) -> PolicyInput:
    return PolicyInput(
        item=cast(Item, object()),
        state=ItemState(item_id=NOT_SAMPLED, activity=activity, attempt_no=1),
        check=CheckResult(Outcome.CORRECT),
        trigger="ANSWER",
        snapshot=StudentSnapshot(),
    ), ItemFacts(**facts)


@pytest.mark.parametrize(
    ("facts", "move", "reason"),
    [
        ({"first_on_kc": True}, Move.VERIFY, "FIRST_ON_KC"),
        ({"kc_mastery": 0.45}, Move.VERIFY, "WEAK_KC"),
        ({"kc_mastery": 0.8}, Move.CONFIRM_ADVANCE, "CORRECT"),  # held: the sample decides, and it says no
        ({}, Move.CONFIRM_ADVANCE, "CORRECT"),  # no mastery yet, not the first: the sample too
    ],
)
def test_why_follows_a_right_answer_on_a_new_or_weak_kc(facts, move, reason):
    inp, f = right(**facts)
    d = decide(inp, f)
    assert d is not None and d.move == move and d.reason_codes[-1] == reason


def test_a_test_never_asks_why():
    inp, f = right(ActivityType.EXIT_ASSESSMENT, first_on_kc=True, kc_mastery=0.2)
    d = decide(inp, f)
    assert d is not None and d.move == Move.CONFIRM_ADVANCE


def solve_first_item() -> tuple[TeachingLoop, list]:
    loop = TeachingLoop(CHAPTER, "s1")
    turn = loop.start(T0)
    while turn.awaiting != Awaiting.ANSWER:
        turn = loop.on_student("Con nghĩ là được ạ.", T0)
    assert loop.tutor is not None and loop.tutor.facts.first_on_kc  # nothing solved yet this session
    first = loop.tutor.item
    turn = loop.on_student(correct_text(first.id), T0)
    if loop.tutor is not None and loop.tutor.item.id == first.id:  # the "vì sao" of the first right answer
        assert loop.tutor.phase.name == "VERIFYING"
        turn = loop.on_student("vì mẫu số là 10 nên có một chữ số sau dấu phẩy", T0)
    return loop, first.kc_ids


def test_the_session_knows_which_kcs_were_solved_and_a_rebuild_agrees():
    loop, kcs = solve_first_item()
    solved = [e for e in loop.events if e.event_type == EventType.ITEM_RESOLVED]
    assert solved and set(kcs) <= set(solved[-1].payload["kc_ids"])
    turn = None
    while loop.tutor is None or set(loop.tutor.item.kc_ids) - set(kcs):
        turn = loop.on_student("Con nghĩ là được ạ.", T0)  # theory replies, until an item on the same KCs
        if turn.awaiting == Awaiting.NOTHING:
            pytest.skip("the chapter moved on before a second item on the same KCs")
        if loop.tutor is not None and set(loop.tutor.item.kc_ids) - set(kcs):
            loop.on_student(correct_text(loop.tutor.item.id), T0)
    assert not loop.tutor.facts.first_on_kc  # a KC solved earlier in the session
    rebuilt = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)
    assert rebuilt.tutor is not None and rebuilt.tutor.facts == loop.tutor.facts
