"""ADR-059 (DI-105): the teaching cycle has six steps, and sessions saved with seven still read right."""

from __future__ import annotations

import pytest
from cavat.core.pedagogy import TeachAction
from cavat.modules.session.chapter_service import (
    LEGACY_STEP_TO_STEP,
    STEP_OF,
    STEP_SCHEME,
    current_step,
)

SIX = {1, 2, 3, 4, 5, 6}


def test_every_decision_that_teaches_belongs_to_one_of_six_steps():
    assert set(STEP_OF.values()) == SIX
    # Bookkeeping decisions carry no step, as before.
    unnumbered = set(TeachAction) - set(STEP_OF)
    assert unnumbered == {TeachAction.ENTER_NODE, TeachAction.SWITCH_TO_PREREQUISITE, TeachAction.FINISH}


def test_revising_the_base_and_teaching_it_are_one_step():
    revise_and_teach = {TeachAction.WARMUP_ITEM, TeachAction.RECALL_PRIOR, TeachAction.TEACH_THEORY}
    assert {STEP_OF[a] for a in revise_and_teach} == {1}
    assert STEP_OF[TeachAction.CHECK_ITEM] == STEP_OF[TeachAction.ASK_RETELL] == 2
    assert STEP_OF[TeachAction.SHOW_WORKED_EXAMPLE] == STEP_OF[TeachAction.COMPLETION_ITEM] == 3
    assert STEP_OF[TeachAction.PRACTICE_ITEM] == 4
    assert STEP_OF[TeachAction.TRANSFER_ITEM] == 5
    deciding = {TeachAction.PASS_NODE, TeachAction.REVIEW_ITEM, TeachAction.STOP_NODE}
    assert {STEP_OF[a] for a in deciding} == {6}


def test_only_the_first_two_old_steps_merge():
    assert LEGACY_STEP_TO_STEP == {1: 1, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}
    assert sorted(set(LEGACY_STEP_TO_STEP.values())) == sorted(SIX)


@pytest.mark.parametrize(("saved", "shown"), [(1, 1), (2, 1), (3, 2), (4, 3), (5, 4), (6, 5), (7, 6)])
def test_a_session_saved_with_seven_steps_shows_the_six_step_number(saved, shown):
    assert current_step({"step": saved}) == shown


def test_a_session_saved_with_six_steps_is_left_alone():
    for step in SIX:
        assert current_step({"step": step, "step_scheme": STEP_SCHEME}) == step


def test_no_step_stays_no_step():
    assert current_step({"step": None}) is None
    assert current_step({}) is None
