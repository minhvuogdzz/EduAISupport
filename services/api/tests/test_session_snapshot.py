"""PRIOR-1 (DI-66): the item tutor of a session reads the Student Model, so R-STRONG-PRIOR and R-WEAK-PRIOR
can fire (blueprint 25.3: the snapshot is frozen at the start and updated within the session). Before, a
session passed no snapshot and both rules never ran. A rebuild reads the same snapshot. Offline."""

from __future__ import annotations

from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.contracts import StudentSnapshot
from test_teaching_loop import CHAPTER, T0, correct_text


def test_the_item_tutor_gets_the_childs_mastery_and_a_rebuild_agrees():
    loop = TeachingLoop(CHAPTER, "s1")
    turn = loop.start(T0)
    assert loop.tutor is None or loop.tutor.snapshot == StudentSnapshot()  # nothing known at the start
    for _ in range(400):
        if loop.tutor is not None and loop.tutor.snapshot.kc_mastery:
            break
        if turn.awaiting == Awaiting.NOTHING:
            break
        if loop.tutor is not None and loop.tutor.phase.name == "AWAITING":
            turn = loop.on_student(correct_text(loop.tutor.item.id), T0)
        else:
            turn = loop.on_student("vì mẫu số là 10 nên con viết một chữ số sau dấu phẩy", T0)
    assert loop.tutor is not None, "the session ended before any mastery was known"
    snap = loop.tutor.snapshot
    assert snap.kc_mastery and all(0.0 <= m <= 1.0 for m in snap.kc_mastery.values())
    assert set(snap.kc_confidence) == set(snap.kc_mastery)
    assert 0.0 <= snap.hint_dependency <= 1.0
    rebuilt = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)
    assert rebuilt.tutor is not None and rebuilt.tutor.snapshot == snap
