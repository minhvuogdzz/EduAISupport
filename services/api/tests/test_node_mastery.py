"""Node mastery projector (M1-3) on the decimals chapter: scoring, gates, cold start, determinism."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cavat.core.events import EventType, ExplanationSubmitted, ItemResolved, RetellJudged
from cavat.core.pedagogy import ErrorClass, ItemResolution
from cavat.core.vi_text import contains_phrase, fold, normalize
from cavat.modules.assessment.projector import MasteryPolicy, answer_dimension, project_chapter
from cavat.modules.assessment.retell import judge_retell
from cavat.modules.content.chapter_package import load_chapter

CHAPTER = load_chapter(
    Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"
)
T0 = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
FRAC, CONCEPT = "KC-DEC-FRAC", "KC-DEC-CONCEPT"


@dataclass(frozen=True)
class Ev:
    event_type: str
    payload: dict = field(default_factory=dict)
    session_id: str = "s1"
    occurred_at: datetime = T0


def item(
    item_id, *, hint=0, resolution=None, error=None, explained=None, misconceptions=(), guessed=False, **ev
):
    it = CHAPTER.item(item_id)
    if resolution is None:
        resolution = ItemResolution.INDEPENDENT if hint == 0 else ItemResolution.SUPPORTED
    payload = ItemResolved(
        item_id=item_id,
        purpose=it.purpose,
        kc_ids=list(it.kc_ids),
        cognitive_level=it.cognitive_level,
        difficulty=it.difficulty,
        transfer=it.transfer,
        resolution=resolution,
        max_hint_level=hint,
        attempts=1,
        hints_count=hint,
        misconception_ids=list(misconceptions),
        final_error_class=error,
        explained=explained,
        guessed=guessed,
    )
    return Ev(EventType.ITEM_RESOLVED, payload.model_dump(mode="json"), **ev)


def failed(item_id, error=ErrorClass.CONCEPTUAL, **kw):
    return item(item_id, resolution=ItemResolution.UNRESOLVED, error=error, **kw)


def retell(node_id, score=1.0, source="RUBRIC_RULE", confidence=1.0, **ev):
    payload = RetellJudged(
        node_id=node_id,
        text="...",
        ideas_total=3,
        score=score,
        label_source=source,
        label_confidence=confidence,
    )
    return Ev(EventType.RETELL_JUDGED, payload.model_dump(mode="json"), **ev)


# A strong student on the first node: check, worked-together item, retell, two practice items, transfer.
STRONG_FRAC = [
    item("TP-CC-01"),
    item("TP-CP-01"),
    retell(FRAC),
    item("TP-PR-01"),
    item("TP-PR-02"),
    item("TP-TR-01"),
]


def node(events, node_id=FRAC, policy=None):
    projection = project_chapter(events, CHAPTER, policy or MasteryPolicy())
    return projection.nodes[node_id]


def test_nothing_is_learned_before_any_evidence():
    projection = project_chapter([], CHAPTER)
    assert projection.policy_version == "node-mastery/0.3.0" and projection.evidence == []
    for state in projection.nodes.values():
        assert (state.mastery, state.state, state.level, state.confidence) == (None, "NOT_LEARNED", 0, 0.0)
        assert state.prior == 0.5 and not state.pass_now and state.passed_at is None
        assert state.missing == ["MASTERY", "UNDERSTOOD", "EXPLANATION", "APPLICATION"]


def test_a_strong_student_passes_the_first_node_with_the_transfer_item():
    state = node(STRONG_FRAC)
    # C: 1 + 0.7 + 0.85*0.5 + 0.8 + 0.9 over beta 1; R: 2/3; I: 5.5/6.5; A has 0.95 < 1 evidence (DI-1).
    assert state.dimensions["C"].mean == pytest.approx(3.825 / 4.825, abs=1e-4)
    assert state.dimensions["R"].mean == pytest.approx(2 / 3, abs=1e-4)
    assert not state.dimensions["A"].in_mastery
    assert state.mastery == 75.3
    assert (state.level, state.state, state.understood) == (4, "APPLIED", True)
    assert state.forms == ["choice", "numeric"] and state.levels == ["A", "B", "D"]
    assert state.successes == 4  # the worked-together item is not a success
    assert state.pass_now and state.passed_at == 5 and state.missing == []


def _two_sessions(rounds):
    """STRONG_FRAC on day 0, then `rounds` x (transfer, retell, practice) four days later."""
    later = [item("TP-TR-01"), retell(FRAC), item("TP-PR-02")] * rounds
    return [
        *STRONG_FRAC,
        *(Ev(e.event_type, e.payload, "s2", T0 + timedelta(days=4)) for e in later),
    ]


def test_provisional_mastery_starts_at_85_as_in_the_framework_not_at_the_90_band():
    state = node(_two_sessions(4))
    assert 85 <= state.mastery < 90 and state.confidence >= 75 and state.dimensions["A"].mean >= 0.8
    assert (state.level, state.state) == (5, "PROVISIONALLY_MASTERED")
    stricter = MasteryPolicy(provisional=(90, 75, 0.8))
    assert node(_two_sessions(4), policy=stricter).level == 4
    assert node(_two_sessions(2)).level == 4  # M 83: below §53


def test_one_step_hint_is_not_a_success_and_lowers_the_score():
    events = [*STRONG_FRAC]
    events[4] = item("TP-PR-02", hint=4)
    state = node(events)
    assert state.successes == 3 and state.understood  # still 3 successes on 3 levels and 2 forms
    assert state.mastery < 75 and state.missing == ["MASTERY"]


def test_a_weak_retell_closes_the_explanation_gate_and_caps_the_level():
    events = [*STRONG_FRAC]
    events[2] = retell(FRAC, score=1 / 3)
    state = node(events)
    assert not state.has_explanation and "EXPLANATION" in state.missing
    assert state.level <= 2  # DI-6: CONCEPTUAL and above need mu_R >= 0.6


def test_without_application_evidence_the_node_stays_below_applied():
    state = node(STRONG_FRAC[:5])
    assert not state.has_application and "APPLICATION" in state.missing and state.level <= 3


def test_a_critical_misconception_blocks_the_pass_until_two_successes_resolve_it():
    events = [item("TP-CC-01"), failed("TP-PR-01", misconceptions=["FRAC-M01"])]
    first = node(events).misconceptions
    assert [(m.id, m.severity, m.status) for m in first] == [("FRAC-M01", "CRITICAL", "ACTIVE")]
    assert "MISCONCEPTION" in node(events).missing
    events.append(item("TP-PR-02"))
    assert node(events).misconceptions[0].status == "RESOLVING"
    events.append(item("TP-TR-01"))
    state = node(events)
    assert state.misconceptions[0].status == "RESOLVED" and "MISCONCEPTION" not in state.missing


def test_error_classes_weigh_differently():
    calculation = node([failed("TP-PR-01", error=ErrorClass.CALCULATION)])
    conceptual = node([failed("TP-PR-01", error=ErrorClass.CONCEPTUAL)])
    assert calculation.dimensions["C"].mean > conceptual.dimensions["C"].mean
    assert calculation.dimensions["R"].n_eff == 0 and conceptual.dimensions["R"].n_eff == pytest.approx(1.2)


def test_a_guess_counts_half_and_is_no_explanation():
    guess = node([item("TP-PR-01", guessed=True)])
    assert guess.dimensions["C"].n_eff == pytest.approx(0.4) and guess.successes == 0
    assert guess.dimensions["R"].mean < 0.5


def test_explanations_unjudged_or_with_low_llm_confidence_are_weak_evidence():
    unjudged = Ev(
        EventType.EXPLANATION_SUBMITTED, ExplanationSubmitted(item_id="TP-PR-01", text="vì...").model_dump()
    )
    assert node([unjudged]).dimensions["R"].n_eff == pytest.approx(0.3)
    assert node([retell(FRAC, source="LLM", confidence=0.4)]).dimensions["R"].n_eff == pytest.approx(0.3)
    assert node([retell(FRAC, source="LLM", confidence=0.9)]).dimensions["R"].n_eff == pytest.approx(1.0)
    silent = node([item("TP-PR-01", explained=False)])
    assert silent.dimensions["R"].mean < 0.5


def test_a_new_node_starts_from_its_prerequisites_and_keeps_that_start():
    frac_mastery = node(STRONG_FRAC).mastery
    assert node(STRONG_FRAC, CONCEPT).prior == pytest.approx(frac_mastery / 100, abs=1e-4)
    started = [*STRONG_FRAC, item("KN-CC-01")]
    later = [*started, failed("TP-PR-01"), failed("TP-PR-02")]  # FRAC drops after CONCEPT started
    assert node(later, FRAC).mastery < frac_mastery
    assert node(later, CONCEPT).prior == node(started, CONCEPT).prior


def test_an_item_of_two_nodes_is_evidence_for_both():
    projection = project_chapter([item("GP-03")], CHAPTER)
    assert projection.nodes["KC-DEC-PLACE"].items == projection.nodes["KC-DEC-CMP"].items == 1
    assert {e.node_id for e in projection.evidence} == {"KC-DEC-PLACE", "KC-DEC-CMP"}


def test_other_events_and_nodes_outside_the_chapter_are_ignored():
    outside = ItemResolved(
        item_id="X-1",
        purpose="PRACTICE",
        kc_ids=["KC-OTHER"],
        cognitive_level="B",
        difficulty=0.5,
        resolution=ItemResolution.INDEPENDENT,
        max_hint_level=0,
        attempts=1,
        hints_count=0,
    )
    events = [Ev(EventType.ITEM_RESOLVED, outside.model_dump(mode="json")), Ev(EventType.TUTOR_MESSAGE_SENT)]
    assert project_chapter(events, CHAPTER).evidence == []


def test_confidence_grows_with_sessions_spread_over_days():
    one = node(STRONG_FRAC).confidence
    later = [
        *STRONG_FRAC[:3],
        *(Ev(e.event_type, e.payload, "s2", T0 + timedelta(days=4)) for e in STRONG_FRAC[3:]),
    ]
    assert node(later).confidence == pytest.approx(one / 0.70, abs=0.2)


def test_the_projection_is_deterministic_and_carries_its_policy_version():
    first = project_chapter(STRONG_FRAC, CHAPTER).model_dump(mode="json")
    again = project_chapter(list(STRONG_FRAC), CHAPTER).model_dump(mode="json")
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)
    custom = project_chapter(STRONG_FRAC, CHAPTER, MasteryPolicy(version="node-mastery/test"))
    assert custom.policy_version == "node-mastery/test"


@pytest.mark.parametrize(
    ("level", "transfer", "dimension"),
    [
        ("A", "none", "C"),
        ("B", "none", "C"),
        ("C", "none", "R"),
        ("D", "near", "A"),
        ("E", "none", "T"),
        ("B", "near", "T"),
        ("DIAG", "none", "D"),
    ],
)
def test_the_answer_dimension_follows_the_framework_table(level, transfer, dimension):
    assert answer_dimension(level, transfer) == dimension


def test_the_retell_rubric_finds_key_ideas_with_or_without_diacritics():
    spec = CHAPTER.node(CONCEPT).explain
    full = judge_retell(
        CONCEPT, "So thap phan co phan nguyen va phan thap phan, ngan cach boi dau phay.", spec
    )
    assert (full.ideas_found, full.score) == ([0, 1, 2], 1.0)
    assert judge_retell(CONCEPT, "con không biết", spec).score == 0.0
    assert judge_retell(CONCEPT, "Bên trái là phần nguyên.", spec).ideas_found == [0]


def test_vietnamese_normalization_keeps_numbers():
    assert normalize("Số 0,25 lớn hơn 7/100, đúng không?") == "số 0,25 lớn hơn 7/100 đúng không"
    assert fold("phần nguyên Đúng") == "phan nguyen Dung"
    assert contains_phrase("PHẦN NGUYÊN là 3", "phần nguyên") and not contains_phrase(
        "phần nguyênx", "phần nguyên"
    )
