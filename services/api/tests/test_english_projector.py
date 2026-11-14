"""English mastery policy ``node-mastery-en/0.1.0`` on the shared projector (ENG-4, ADR-060 §6-§7, ADR-063).

Synthetic event logs on Unit 11 "Family time": the L1 class (DI-107), "nói theo cô" and the H7 model
sentence (DI-108), the ASR confidence of voice answers (DI-109, DI-130), the gate and the vocabulary node
(DI-111), the policy chosen by subject and never mixed with Mathematics. Offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cavat.core.events import EventType, ItemResolved, RetellJudged
from cavat.core.pedagogy import ErrorClass, ItemResolution
from cavat.modules.assessment.projector import (
    DEFAULT_POLICY,
    ENGLISH_POLICY,
    policy_for,
    project_chapter,
)
from cavat.modules.content.chapter_package import load_chapter

ROOT = Path(__file__).resolve().parents[3]
UNIT = load_chapter(ROOT / "docs/pedagogy/english-g5/unit-11-family-time/chapter.yaml")
MATH = load_chapter(ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml")
T0 = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)
VOCAB, DIDYOU, WHATDID = "ENG5-U11-VOCAB", "ENG5-U11-DIDYOU", "ENG5-U11-WHATDID"


@dataclass(frozen=True)
class Ev:
    event_type: str
    payload: dict = field(default_factory=dict)
    session_id: str = "en1"
    occurred_at: datetime = T0


def item(item_id, *, chapter=UNIT, hint=0, resolution=None, error=None, voice=False, q=None, **kw):
    it = chapter.item(item_id)
    if resolution is None:
        resolution = (
            ItemResolution.INDEPENDENT
            if hint == 0
            else (ItemResolution.SUPPORTED if hint <= 5 else ItemResolution.WORKED)
        )
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
        final_error_class=error,
        modality="VOICE" if voice else "TEXT",
        asr_confidence=q,
        **kw,
    )
    return Ev(EventType.ITEM_RESOLVED, payload.model_dump(mode="json"))


def failed(item_id, error=ErrorClass.CONCEPTUAL, **kw):
    return item(item_id, resolution=ItemResolution.UNRESOLVED, error=error, **kw)


def retell(node_id, score=1.0):
    payload = RetellJudged(node_id=node_id, text="...", ideas_total=2, score=score)
    return Ev(EventType.RETELL_JUDGED, payload.model_dump(mode="json"))


def project(events, policy=None):
    return project_chapter(events, UNIT, policy)


def answers(projection, item_id):
    return [e for e in projection.evidence if e.item_id == item_id]


# --------------------------------------------------------------------------- policy by subject


def test_the_policy_is_chosen_by_the_subject_of_the_chapter():
    assert policy_for(UNIT) is ENGLISH_POLICY and policy_for(MATH) is DEFAULT_POLICY
    assert project([]).policy_version == "node-mastery-en/0.1.0"
    assert project_chapter([], MATH).policy_version == "node-mastery/0.3.0"


def test_a_policy_of_the_other_subject_is_refused():
    with pytest.raises(ValueError):
        project_chapter([], UNIT, DEFAULT_POLICY)
    with pytest.raises(ValueError):
        project_chapter([], MATH, ENGLISH_POLICY)


def test_the_english_policy_keeps_every_number_of_mathematics_but_its_own():
    """ADR-060 §6: weights, independence, gates, bands, confidence as Mathematics; only the English fields
    differ. The Mathematics policy has every English rule off."""
    same = {"weights", "independence", "min_support", "guess_factor", "completion_factor", "bands",
            "explanation_gate", "provisional", "success_max_hint", "resolve_after", "min_evidence",
            "prior_mass", "label_min_confidence", "low_confidence_factor"}  # fmt: skip
    for name in same:
        assert getattr(ENGLISH_POLICY, name) == getattr(DEFAULT_POLICY, name), name
    assert dict(ENGLISH_POLICY.error_scores) == {ErrorClass.FORMAT: 0.7, ErrorClass.L1: 0.3}
    assert DEFAULT_POLICY.asr_threshold is None and DEFAULT_POLICY.completion_max_independence is None
    assert DEFAULT_POLICY.voice_low_forms == frozenset() and ErrorClass.L1 not in DEFAULT_POLICY.error_scores


# --------------------------------------------------------------------------- DI-107 L1 and errors


def test_an_item_closed_in_vietnamese_scores_point_three():
    ev = answers(project([failed("U11-WD-PR-01", error=ErrorClass.L1)]), "U11-WD-PR-01")
    answer = next(e for e in ev if e.reason == "ANSWER")
    assert answer.score == 0.3 and answer.dimension == "C"
    assert not [e for e in ev if e.reason == "CONCEPTUAL_ERROR"]  # L1 takes nothing from R


def test_error_classes_score_as_the_table_says():
    scores = {
        cls: next(
            e.score for e in project([failed("U11-WD-PR-01", error=cls)]).evidence if e.reason == "ANSWER"
        )
        for cls in (ErrorClass.CONCEPTUAL, ErrorClass.PROCEDURAL, ErrorClass.FORMAT, ErrorClass.L1)
    }
    assert scores == {ErrorClass.CONCEPTUAL: 0.0, ErrorClass.PROCEDURAL: 0.0, ErrorClass.FORMAT: 0.7,
                      ErrorClass.L1: 0.3}  # fmt: skip


# --------------------------------------------------------------------------- DI-108


def test_say_after_me_is_worked_together_at_most_as_independent_as_h6():
    p = project([item("U11-VO-CP-01")])  # a completion item of VOCAB, right at H0
    ev = {e.reason: e for e in answers(p, "U11-VO-CP-01")}
    d = UNIT.item("U11-VO-CP-01").difficulty
    assert ev["ANSWER"].weight == round((0.5 + d) * 0.3 * 0.5, 4)  # max(0.20, 0.3) * completion 0.5
    assert ev["INDEPENDENCE"].score == 0.2 and ev["INDEPENDENCE"].weight == 0.5
    assert p.nodes[VOCAB].successes == 0
    # Mathematics keeps the independence of the hint on its own "cùng làm" items
    m = project_chapter([item("TP-CP-01", chapter=MATH)], MATH)
    assert next(e for e in m.evidence if e.reason == "INDEPENDENCE").score == 1.0


def test_right_after_the_tutor_read_the_whole_sentence_is_worked_and_not_a_success():
    p = project([item("U11-WD-PR-01", hint=7)])
    ev = {e.reason: e for e in answers(p, "U11-WD-PR-01")}
    d = UNIT.item("U11-WD-PR-01").difficulty
    assert ev["ANSWER"].weight == round((0.5 + d) * 0.3, 4) and ev["INDEPENDENCE"].score == 0.0
    assert p.nodes[WHATDID].successes == 0


def test_a_child_who_only_repeats_after_the_tutor_passes_no_node():
    events = []
    for _ in range(10):
        for node in UNIT.nodes:
            events += [item(i) for i in node.completion]
            events.append(retell(node.id))
    p = project(events)
    assert all(n.successes == 0 and not n.understood and n.passed_at is None for n in p.nodes.values())


# --------------------------------------------------------------------------- DI-109, DI-130


def test_a_clear_voice_answer_is_ordinary_evidence():
    """A choice said clearly (q >= 0.6) is the same evidence as typed; a choice is not a target sentence."""
    text, voice = project([item("U11-WD-CC-01")]), project([item("U11-WD-CC-01", voice=True, q=0.92)])
    assert text.evidence == voice.evidence and voice.nodes[WHATDID].successes == 1


def test_a_right_voice_answer_heard_with_doubt_counts_little_and_is_not_a_success():
    clear = {e.reason: e for e in project([item("U11-WD-PR-01")]).evidence}
    p = project([item("U11-WD-PR-01", voice=True, q=0.45)])
    low = {e.reason: e for e in p.evidence}
    assert low["ANSWER"].weight == round(clear["ANSWER"].weight * 0.3, 4)
    assert low["INDEPENDENCE"].weight == round(clear["INDEPENDENCE"].weight * 0.3, 4)
    assert p.nodes[WHATDID].successes == 0


def test_a_wrong_voice_answer_heard_with_doubt_is_no_evidence_and_never_lowers_mastery():
    base = [item("U11-WD-PR-01"), item("U11-WD-PR-02"), retell(WHATDID)]
    before = project(base)
    doubt = failed("U11-WD-PR-03", voice=True, q=0.3, misconception_ids=["ENG5-U11-M07"])
    after = project([*base, doubt])
    note = [e for e in after.evidence if e.item_id == "U11-WD-PR-03"]
    assert [(e.reason, e.weight) for e in note] == [("ASR_UNCERTAIN", 0.0)]
    a, b = before.nodes[WHATDID], after.nodes[WHATDID]
    assert (a.mastery, a.confidence, a.items, a.misconceptions) == (
        b.mastery,
        b.confidence,
        b.items,
        b.misconceptions,
    )
    assert after.trace == before.trace  # nothing moved


def test_a_voice_answer_without_a_confidence_is_uncertain():
    p = project([item("U11-WD-PR-01", voice=True, q=None)])
    assert p.nodes[WHATDID].successes == 0
    assert [e.reason for e in project([failed("U11-WD-PR-01", voice=True)]).evidence] == ["ASR_UNCERTAIN"]


def test_a_typed_answer_is_never_read_for_asr():
    assert project([item("U11-WD-PR-01", q=0.1)]).evidence == project([item("U11-WD-PR-01")]).evidence


def test_voice_answers_to_target_sentences_count_as_uncertain_until_measured():
    """DI-109 point 7: a ``phrase`` or ``word_order`` said by voice is uncertain whatever q, until the false
    accepts of Whisper are measured (ENG-9); the same sentence typed is ordinary evidence."""
    assert ENGLISH_POLICY.voice_low_forms == {"phrase", "word_order"}
    assert UNIT.item("U11-WD-PR-01").answer.type == "phrase"
    said = project([item("U11-WD-PR-01", voice=True, q=0.95)])
    typed = project([item("U11-WD-PR-01")])
    assert said.nodes[WHATDID].successes == 0 and typed.nodes[WHATDID].successes == 1
    said_ev = {e.reason: e.weight for e in said.evidence}
    typed_ev = {e.reason: e.weight for e in typed.evidence}
    assert said_ev["ANSWER"] == round(typed_ev["ANSWER"] * 0.3, 4)
    assert [e.reason for e in project([failed("U11-WD-PR-01", voice=True, q=0.95)]).evidence] == [
        "ASR_UNCERTAIN"
    ]


def test_mathematics_ignores_the_asr_confidence():
    """english-module-rules M4: the Mathematics policy reads no modality and no ASR confidence."""
    for build in (
        lambda **kw: item("TP-PR-01", chapter=MATH, **kw),
        lambda **kw: failed("TP-PR-01", chapter=MATH, **kw),
    ):
        text = project_chapter([build()], MATH)
        voice = project_chapter([build(voice=True, q=0.05)], MATH)
        assert text.model_dump() == voice.model_dump()


# --------------------------------------------------------------------------- DI-106, DI-111


def test_the_form_of_the_gate_is_the_answer_type_not_the_modality():
    events = [item("U11-WD-CC-01"), item("U11-WD-CC-01", voice=True, q=0.9), item("U11-WD-PR-04")]
    n = project(events).nodes[WHATDID]
    assert n.successes == 3 and n.forms == ["choice"] and not n.understood  # one form only
    n = project([*events, item("U11-WD-PR-01")]).nodes[WHATDID]
    assert n.forms == ["choice", "phrase"]  # DI-125: phrase is a form of its own


def test_the_vocabulary_node_gets_reasoning_from_its_why_item_and_the_retell():
    events = [item("U11-VO-PR-02"), item("U11-VO-PR-03"), retell(VOCAB)]
    n = project(events).nodes[VOCAB]
    assert n.dimensions["R"].in_mastery and n.has_explanation


def test_a_strong_learner_passes_the_unit_nodes_in_text():
    events = []
    for node in UNIT.nodes:
        for i in node.checks + node.practice + node.transfer:
            events.append(item(i))
        events.append(retell(node.id))
    p = project(events)
    passed = {k for k, n in p.nodes.items() if n.passed_at is not None}
    assert {VOCAB, "ENG5-U11-PAST", DIDYOU, WHATDID, "ENG5-U11-TRIP"} <= passed


# --------------------------------------------------------------------------- replay and isolation


def mixed_log():
    days = [T0 + timedelta(days=d) for d in (0, 0, 1, 3)]
    out = [
        item("U11-VO-CC-01"), item("U11-VO-CP-01"), item("U11-VO-PR-02", voice=True, q=0.81),
        failed("U11-VO-PR-03", error=ErrorClass.L1), retell(VOCAB, 0.5),
        item("U11-DY-PR-02", voice=True, q=0.4), failed("U11-DY-PR-03", voice=True, q=0.2),
        failed("U11-DY-TR-01", error=ErrorClass.CONCEPTUAL, misconception_ids=["ENG5-U11-M03"]),
        item("U11-DY-TR-01", hint=7), item("U11-WD-PR-01", hint=2),
        failed("U11-WD-PR-02", error=ErrorClass.FORMAT),
    ]  # fmt: skip
    return [replace(e, occurred_at=days[i % 4], session_id=f"en{i % 2}") for i, e in enumerate(out)]


def test_the_same_english_log_gives_the_same_projection():
    first = json.dumps(project(mixed_log()).model_dump(mode="json"), sort_keys=True)
    again = json.dumps(project(list(mixed_log())).model_dump(mode="json"), sort_keys=True)
    assert first == again


def test_no_evidence_goes_to_the_other_subject():
    """english-module-rules §5: 0 mastery in the wrong subject. Items name the nodes of their own subject."""
    math_events = [item("TP-PR-01", chapter=MATH), item("TP-CC-01", chapter=MATH), retell("KC-DEC-FRAC")]
    english = project([*mixed_log(), *math_events])
    assert english.evidence and all(e.node_id.startswith("ENG5-") for e in english.evidence)
    assert [e.model_dump(exclude={"seq"}) for e in english.evidence] == [
        e.model_dump(exclude={"seq"}) for e in project(mixed_log()).evidence
    ]
    math_only = project_chapter(mixed_log(), MATH)
    assert math_only.evidence == [] and all(n.mastery is None for n in math_only.nodes.values())
    both = project_chapter([*mixed_log(), *math_events], MATH)
    alone = project_chapter(math_events, MATH)
    assert {k: n.mastery for k, n in both.nodes.items()} == {k: n.mastery for k, n in alone.nodes.items()}
