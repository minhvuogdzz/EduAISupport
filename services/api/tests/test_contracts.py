"""The tutor contracts are the seam between parallel tasks; these tests keep them stable."""

from pathlib import Path

import pytest
from cavat.core.events import (
    PAYLOAD_MODELS,
    AnswerSubmitted,
    EventType,
    ItemResolved,
    PolicyDecisionMade,
    QuestionShown,
)
from cavat.core.pedagogy import ActivityType, ErrorClass, HintLevel, ItemResolution, Move, Outcome
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.tutor.contracts import (
    ItemState,
    PolicyDecision,
    PolicyInput,
    RenderContext,
    ValidationCode,
    ValidationIssue,
    ValidationResult,
)
from pydantic import ValidationError

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"


@pytest.fixture(scope="module")
def pkg():
    return load_lesson_package(LESSON)


def test_item_state_tracks_the_highest_hint():
    st = ItemState(item_id="GP-01", activity=ActivityType.GUIDED_PRACTICE)
    assert st.max_hint_level == HintLevel.H0
    st.hint_levels += [HintLevel.H1, HintLevel.H4, HintLevel.H2]
    assert st.max_hint_level == HintLevel.H4


def test_contract_objects_build_with_real_lesson_data(pkg):
    item = pkg.item("GP-02")
    state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
    inp = PolicyInput(item=item, state=state, check=None, trigger="START")
    assert inp.time_left_s == float("inf")
    decision = PolicyDecision(move=Move.PRESENT, rule_ids=("R-START",))
    ctx = RenderContext(decision=decision, item=item, package=pkg, state=state)
    assert ctx.max_words == 60 and ctx.persona.tutor_self == "cô"


def test_policy_decision_is_immutable():
    d = PolicyDecision(move=Move.HINT, level=HintLevel.H2)
    with pytest.raises(AttributeError):
        d.level = HintLevel.H3  # type: ignore[misc]


def test_validation_result_reports_codes():
    assert ValidationResult().ok
    bad = ValidationResult(issues=(ValidationIssue(ValidationCode.ANSWER_LEAK, "0,25 < 0,3"),))
    assert not bad.ok and bad.codes == ("ANSWER_LEAK",)


def test_every_payload_model_is_keyed_by_a_known_event_type():
    assert set(PAYLOAD_MODELS) <= set(EventType)
    assert EventType.ITEM_RESOLVED in PAYLOAD_MODELS and EventType.ANSWER_SUBMITTED in PAYLOAD_MODELS


def test_payloads_round_trip_as_json():
    payload = ItemResolved(
        item_id="GP-03",
        purpose="PRACTICE",
        kc_ids=["KC-DEC-PLACE", "KC-DEC-CMP"],
        cognitive_level="B",
        difficulty=0.5,
        resolution=ItemResolution.SUPPORTED,
        max_hint_level=3,
        attempts=2,
        hints_count=2,
        misconception_ids=["DEC-M03"],
        final_error_class=ErrorClass.CONCEPTUAL,
        explained=True,
    )
    stored = payload.model_dump(mode="json")
    assert stored["resolution"] == "SUPPORTED" and stored["final_error_class"] == "CONCEPTUAL"
    assert PAYLOAD_MODELS[EventType.ITEM_RESOLVED].model_validate(stored) == payload


def test_payloads_reject_unknown_fields_and_bad_ranges():
    with pytest.raises(ValidationError):
        AnswerSubmitted(item_id="x", attempt_no=0, raw_text="<", outcome=Outcome.CORRECT)
    with pytest.raises(ValidationError):
        QuestionShown(
            item_id="x",
            activity_type=ActivityType.GUIDED_PRACTICE,
            purpose="PRACTICE",
            kc_ids=[],
            cognitive_level="B",
            difficulty=1.5,
        )
    with pytest.raises(ValidationError):
        PolicyDecisionMade(item_id="x", move=Move.HINT, hint_level=8)
    with pytest.raises(ValidationError):
        PolicyDecisionMade(item_id="x", move=Move.HINT, surprise="field")  # type: ignore[call-arg]
