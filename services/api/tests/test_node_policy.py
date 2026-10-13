"""Node teaching policy (M1-4) on the decimals chapter: the cycle rule by rule, with scripted students."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cavat.core.events import EventType, ItemResolved, NodeDecisionMade, RetellJudged
from cavat.core.pedagogy import ITEM_ACTIONS, ErrorClass, ItemResolution, PracticeSupport, TeachAction
from cavat.modules.assessment.projector import project_chapter
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.teaching.node_policy import PendingResult, decide, misconceptions_probed
from cavat.modules.teaching.state import teaching_state

CHAPTER = load_chapter(
    Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"
)
T0 = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
A = TeachAction


@dataclass(frozen=True)
class Ev:
    event_type: str
    payload: dict = field(default_factory=dict)
    session_id: str = "s1"
    occurred_at: datetime = T0


def resolved(item_id, success=True, misconception=None, session="s1"):
    it = CHAPTER.item(item_id)
    payload = ItemResolved(
        item_id=item_id,
        purpose=it.purpose,
        kc_ids=list(it.kc_ids),
        cognitive_level=it.cognitive_level,
        difficulty=it.difficulty,
        transfer=it.transfer,
        resolution=ItemResolution.INDEPENDENT if success else ItemResolution.UNRESOLVED,
        max_hint_level=0,
        attempts=1,
        hints_count=0,
        misconception_ids=[misconception] if misconception else [],
        final_error_class=None if success else ErrorClass.PROCEDURAL,
    )
    return Ev(EventType.ITEM_RESOLVED, payload.model_dump(mode="json"), session)


@dataclass
class Student:
    """Right on everything, except the listed items, and the retells of the listed nodes (as many times)."""

    wrong: dict[str, str | None] = field(default_factory=dict)  # item id -> misconception shown
    weak_retells: dict[str, int] = field(default_factory=dict)  # node id -> failed retells left
    weak_recalls: set[str] = field(default_factory=set)  # DI-52: earlier nodes the student cannot recall

    def answer(self, d: NodeDecisionMade, session: str) -> Ev:
        if d.ref in self.wrong:
            return resolved(d.ref, success=False, misconception=self.wrong.pop(d.ref), session=session)
        return resolved(d.ref, session=session)

    def retell(self, d: NodeDecisionMade, session: str) -> Ev:
        failures = self.weak_retells.get(d.node_id, 0)
        self.weak_retells[d.node_id] = max(failures - 1, 0)
        payload = RetellJudged(node_id=d.node_id, text="...", ideas_total=3, score=0.0 if failures else 1.0)
        return Ev(EventType.RETELL_JUDGED, payload.model_dump(mode="json"), session)

    def recall(self, d: NodeDecisionMade, session: str) -> Ev:
        score = 0.0 if d.ref in self.weak_recalls else 1.0
        payload = RetellJudged(node_id=d.ref, text="...", ideas_total=2, score=score, purpose="RECALL")
        return Ev(EventType.RETELL_JUDGED, payload.model_dump(mode="json"), session)


def run(student, history=(), session="s1", steps=400):
    events = list(history)
    for _ in range(steps):
        projection = project_chapter(events, CHAPTER)
        d = decide(CHAPTER, projection, teaching_state(e for e in events if e.session_id == session))
        events.append(Ev(EventType.NODE_DECISION, d.model_dump(mode="json"), session))
        if d.action == A.FINISH:
            return events
        if d.action in ITEM_ACTIONS:
            events.append(student.answer(d, session))
        elif d.action == A.ASK_RETELL:
            events.append(student.retell(d, session))
        elif d.action == A.RECALL_PRIOR:
            events.append(student.recall(d, session))
    raise AssertionError("the session never finished")


def decisions(events, session=None):
    out = []
    for e in events:
        if e.event_type == EventType.NODE_DECISION and session in (None, e.session_id):
            d = NodeDecisionMade.model_validate(e.payload)
            out.append((d.action, d.node_id, d.ref, d.rule_ids[0], tuple(d.reason_codes)))
    return out


def short(events, session=None):
    return [(a, n, r, rule) for a, n, r, rule, _ in decisions(events, session)]


FRAC_CYCLE = [
    (A.ENTER_NODE, "KC-DEC-FRAC", None, "N-NEXT"),
    (A.TEACH_THEORY, "KC-DEC-FRAC", "T1", "N-TEACH"),
    (A.CHECK_ITEM, "KC-DEC-FRAC", "TP-CC-01", "N-CHECK"),
    (A.ASK_RETELL, "KC-DEC-FRAC", None, "N-CHECK"),
    (A.SHOW_WORKED_EXAMPLE, "KC-DEC-FRAC", "W1", "N-METHOD"),
    (A.COMPLETION_ITEM, "KC-DEC-FRAC", "TP-CP-01", "N-METHOD"),
    (A.PRACTICE_ITEM, "KC-DEC-FRAC", "TP-PR-01", "N-PRACTICE"),
    (A.PRACTICE_ITEM, "KC-DEC-FRAC", "TP-PR-02", "N-PRACTICE"),
    (A.TRANSFER_ITEM, "KC-DEC-FRAC", "TP-TR-01", "N-TRANSFER"),
    (A.PASS_NODE, "KC-DEC-FRAC", None, "N-PASS"),
]


def test_a_strong_student_learns_the_whole_chapter_through_the_teaching_cycle():
    events = run(Student())
    steps = short(events)
    assert steps[: len(FRAC_CYCLE)] == FRAC_CYCLE
    passed = [n for a, n, _, _ in steps if a == A.PASS_NODE]
    assert passed == CHAPTER.topological_order()
    assert steps[-1] == (A.FINISH, None, None, "N-FINISH")
    projection = project_chapter(events, CHAPTER)
    assert all(state.passed_at is not None for state in projection.nodes.values())


def test_a_failed_check_is_retaught_another_way_before_the_method():
    steps = short(run(Student(weak_retells={"KC-DEC-FRAC": 1})))
    assert steps[3:7] == [
        (A.ASK_RETELL, "KC-DEC-FRAC", None, "N-CHECK"),
        (A.TEACH_THEORY, "KC-DEC-FRAC", "T2", "N-RETEACH"),
        (A.ASK_RETELL, "KC-DEC-FRAC", None, "N-CHECK"),  # the only check item was used already
        (A.SHOW_WORKED_EXAMPLE, "KC-DEC-FRAC", "W1", "N-METHOD"),
    ]


def test_with_no_variant_left_the_reteaching_is_a_worked_example():
    steps = short(run(Student(weak_retells={"KC-DEC-FRAC": 2})))
    assert steps[4:8] == [
        (A.TEACH_THEORY, "KC-DEC-FRAC", "T2", "N-RETEACH"),
        (A.ASK_RETELL, "KC-DEC-FRAC", None, "N-CHECK"),
        (A.SHOW_WORKED_EXAMPLE, "KC-DEC-FRAC", "W1", "N-RETEACH"),  # both variants used
        (A.COMPLETION_ITEM, "KC-DEC-FRAC", "TP-CP-01", "N-METHOD"),  # the example was the model already
    ]


def frac_passed_in_an_earlier_session():
    return [e for e in run(Student(), session="s0") if e.session_id == "s0"]


def test_a_new_session_warms_up_with_a_prerequisite_item_before_teaching():
    history = frac_passed_in_an_earlier_session()
    history = history[: next(i for i, e in enumerate(history) if _is_pass(e, "KC-DEC-FRAC")) + 1]
    steps = short(run(Student(), history, session="s1"), session="s1")
    assert steps[:3] == [
        (A.ENTER_NODE, "KC-DEC-CONCEPT", None, "N-NEXT"),
        (A.WARMUP_ITEM, "KC-DEC-FRAC", "TP-PR-01", "N-WARMUP"),
        (A.TEACH_THEORY, "KC-DEC-CONCEPT", "T1", "N-TEACH"),  # DI-52: the warm-up item is the recall
    ]


def test_a_failed_warmup_sends_the_student_back_to_the_prerequisite_and_then_resumes():
    history = frac_passed_in_an_earlier_session()
    history = history[: next(i for i, e in enumerate(history) if _is_pass(e, "KC-DEC-FRAC")) + 1]
    steps = decisions(run(Student(wrong={"TP-PR-01": None}), history, session="s1"), session="s1")
    switch = next(i for i, s in enumerate(steps) if s[0] == A.SWITCH_TO_PREREQUISITE)
    assert steps[switch][1:5] == ("KC-DEC-FRAC", None, "N-REMEDIATE", ("WARMUP_FAILED",))
    resume = next(i for i, s in enumerate(steps) if s[4] == ("RESUME",))
    assert steps[resume][:2] == (A.ENTER_NODE, "KC-DEC-CONCEPT") and resume > switch
    assert (A.PASS_NODE, "KC-DEC-FRAC") in [s[:2] for s in steps[switch:resume]]


def test_a_critical_misconception_of_an_earlier_node_sends_the_student_back_to_it():
    steps = decisions(run(Student(wrong={"GP-01": "DEC-M03"})))
    failed_at = next(i for i, s in enumerate(steps) if s[2] == "GP-01")
    assert steps[failed_at + 1][:5] == (
        A.SWITCH_TO_PREREQUISITE,
        "KC-DEC-PLACE",
        None,
        "N-REMEDIATE",
        ("MISCONCEPTION:DEC-M03",),
    )


def test_two_failed_checks_with_a_weak_prerequisite_go_back_to_it():
    history = frac_passed_in_an_earlier_session()
    history = history[: next(i for i, e in enumerate(history) if _is_pass(e, "KC-DEC-FRAC")) + 1]
    history += [resolved(i, success=False, session="s0") for i in ("TP-PR-01", "TP-PR-02", "TP-TR-01")]
    assert not project_chapter(history, CHAPTER).nodes["KC-DEC-FRAC"].pass_now
    student = Student(weak_retells={"KC-DEC-CONCEPT": 2})
    steps = decisions(run(student, history, session="s1"), session="s1")
    switch = next(s for s in steps if s[0] == A.SWITCH_TO_PREREQUISITE)
    assert switch[1:5] == ("KC-DEC-FRAC", None, "N-REMEDIATE", ("CHECK_FAILED_TWICE",))


def test_a_node_without_progress_is_stopped_and_its_dependents_stay_locked():
    wrong = {i: None for i in ("TP-CC-01", "TP-CP-01", "TP-PR-01", "TP-PR-02", "TP-TR-01")}
    steps = decisions(run(Student(wrong=wrong)))
    assert steps[-2][:4] == (A.STOP_NODE, "KC-DEC-FRAC", None, "N-BUDGET") and "NO_ITEMS_LEFT" in steps[-2][4]
    assert steps[-1][0] == A.FINISH
    assert all(s[1] in (None, "KC-DEC-FRAC") for s in steps)


def test_after_a_pass_an_earlier_node_is_reviewed():
    history = frac_passed_in_an_earlier_session()
    history = history[: next(i for i, e in enumerate(history) if _is_pass(e, "KC-DEC-FRAC")) + 1]
    steps = short(run(Student(), history, session="s1"), session="s1")
    passed = steps.index((A.PASS_NODE, "KC-DEC-CONCEPT", None, "N-PASS"))
    assert steps[passed + 1] == (A.REVIEW_ITEM, "KC-DEC-FRAC", "TP-PR-02", "N-REVIEW")


def test_the_loop_must_finish_an_item_before_the_next_decision():
    events = []
    for _ in range(3):  # ENTER, TEACH, CHECK_ITEM
        d = decide(CHAPTER, project_chapter(events, CHAPTER), teaching_state(events))
        events.append(Ev(EventType.NODE_DECISION, d.model_dump(mode="json")))
    with pytest.raises(PendingResult):
        decide(CHAPTER, project_chapter(events, CHAPTER), teaching_state(events))


def test_decisions_are_deterministic_and_carry_the_policy_version():
    first, again = run(Student()), run(Student())
    assert decisions(first) == decisions(again)
    versions = {e.payload["policy_version"] for e in first if e.event_type == EventType.NODE_DECISION}
    assert versions == {"node-policy/0.3.1"}


def test_item_decisions_carry_the_support_of_the_mastery_band():
    events = run(Student())
    items = [
        NodeDecisionMade.model_validate(e.payload)
        for e in events
        if e.event_type == EventType.NODE_DECISION and e.payload["action"] == A.PRACTICE_ITEM
    ]
    # FRAC is at M 68.1 after the check, the retell and the worked-together item: DI-8 band 60-74.
    assert items[0].ref == "TP-PR-01" and items[0].support == PracticeSupport.ASK_WHY
    assert all(d.support is not None for d in items)


def test_misconceptions_probed_by_an_item_come_from_its_answer():
    assert misconceptions_probed(CHAPTER.item("TP-CP-01")) == {"FRAC-M01"}
    assert misconceptions_probed(CHAPTER.item("CC-05")) == {"DEC-M01"}
    assert misconceptions_probed(CHAPTER.item("GP-01")) == set()


def _is_pass(event, node_id):
    return (
        event.event_type == EventType.NODE_DECISION
        and event.payload["action"] == A.PASS_NODE
        and event.payload["node_id"] == node_id
    )


def test_an_item_of_a_missing_form_comes_before_the_budget_runs_out():
    """DI-49: twelve fill-in items in a row would spend the budget of a node that needs two forms."""
    from types import SimpleNamespace

    from cavat.modules.teaching.node_policy import _Policy as NodePolicy

    numeric = [
        i.id
        for n in CHAPTER.nodes
        for i in CHAPTER.lesson_of(n.practice[0]).items
        if i.answer.type == "numeric"
    ]
    other = next(
        i.id
        for n in CHAPTER.nodes
        for i in CHAPTER.lesson_of(n.practice[0]).items
        if i.answer.type == "compare"
    )
    ns = SimpleNamespace(forms=["numeric"], levels=["A", "B", "C"])
    policy = SimpleNamespace(chapter=CHAPTER)
    long_list = [*numeric[:1] * 10, other]
    assert NodePolicy._covering(policy, long_list, ns, budget_left=6)[0] == other
    assert NodePolicy._covering(policy, long_list, ns, budget_left=12) == long_list  # it fits: file order
    assert NodePolicy._covering(policy, [numeric[0], other], ns, budget_left=6) == [numeric[0], other]


# --------------------------------------------------------------------------- DI-52: N-RECALL


def recalls(events):
    return [(n, r, why) for a, n, r, _, why in decisions(events) if a == A.RECALL_PRIOR]


def test_a_node_with_a_prerequisite_learnt_starts_by_recalling_it():
    steps = short(run(Student()))
    start = steps.index((A.ENTER_NODE, "KC-DEC-CONCEPT", None, "N-NEXT"))
    assert steps[start + 1 : start + 3] == [
        (A.RECALL_PRIOR, "KC-DEC-CONCEPT", "KC-DEC-FRAC", "N-RECALL"),
        (A.TEACH_THEORY, "KC-DEC-CONCEPT", "T1", "N-TEACH"),
    ]
    assert steps[1] == (A.TEACH_THEORY, "KC-DEC-FRAC", "T1", "N-TEACH")  # nothing to recall before the first


def test_each_node_recalls_each_related_node_once_and_a_prerequisite_first():
    found = recalls(run(Student()))
    assert len(found) == len(set((n, r) for n, r, _ in found))
    assert all(r in CHAPTER.prerequisites(n) for n, r, _ in found)
    assert {n for n, _, _ in found} == set(CHAPTER.topological_order()[1:])  # every node with a prerequisite


def test_a_failed_check_recalls_the_other_prerequisite_before_reteaching():
    events = run(Student(weak_retells={"KC-DEC-CMP": 1}))
    cmp_recalls = [(r, why) for n, r, why in recalls(events) if n == "KC-DEC-CMP"]
    assert [why for _, why in cmp_recalls] == [("AT_ENTRY",), ("CHECK_FAILED",)]
    assert [r for r, _ in cmp_recalls] == ["KC-DEC-EQ", "KC-DEC-PLACE"]  # the closest prerequisite first
    steps = short(events)
    second = steps.index((A.RECALL_PRIOR, "KC-DEC-CMP", cmp_recalls[1][0], "N-RECALL"))
    assert steps[second + 1][0] == A.TEACH_THEORY and steps[second + 1][3] == "N-RETEACH"


def test_a_node_with_one_prerequisite_reteaches_at_once_after_a_failed_check():
    events = run(Student(weak_retells={"KC-DEC-CONCEPT": 1}))
    assert [why for n, _, why in recalls(events) if n == "KC-DEC-CONCEPT"] == [("AT_ENTRY",)]


def test_a_failed_recall_lowers_the_earlier_node_but_never_takes_its_pass_back():
    good, weak = run(Student()), run(Student(weak_recalls={"KC-DEC-FRAC"}))

    def cut(events):  # up to the first recall judged
        return events[: next(i for i, e in enumerate(events) if e.payload.get("purpose") == "RECALL") + 1]

    before, after = project_chapter(cut(good), CHAPTER), project_chapter(cut(weak), CHAPTER)
    assert after.nodes["KC-DEC-FRAC"].mastery < before.nodes["KC-DEC-FRAC"].mastery
    assert after.nodes["KC-DEC-FRAC"].passed_at is not None


def test_the_recall_can_be_turned_off():
    from cavat.modules.teaching.state import NodePolicyConfig

    off = NodePolicyConfig(recall_prior=False)
    events = []
    for _ in range(400):
        d = decide(CHAPTER, project_chapter(events, CHAPTER), teaching_state(events, off), off)
        events.append(Ev(EventType.NODE_DECISION, d.model_dump(mode="json")))
        assert d.action != A.RECALL_PRIOR
        if d.action == A.FINISH:
            break
        if d.action in ITEM_ACTIONS:
            events.append(Student().answer(d, "s1"))
        elif d.action == A.ASK_RETELL:
            events.append(Student().retell(d, "s1"))


def test_a_recall_waits_for_its_answer():
    events = []
    for e in run(Student()):
        events.append(e)
        if e.event_type == EventType.NODE_DECISION and e.payload["action"] == A.RECALL_PRIOR:
            break
    with pytest.raises(PendingResult, match="recall of KC-DEC-FRAC"):
        decide(CHAPTER, project_chapter(events, CHAPTER), teaching_state(events))


# --------------------------------------------------------------------------- DI-56: the only item of a form


def test_the_only_item_of_a_missing_form_is_asked_once_more_after_a_miss():
    node = CHAPTER.node("KC-DEC-CONCEPT")
    every = [*node.checks, *node.completion, *node.practice, *node.transfer]
    (only,) = [i for i in every if CHAPTER.item(i).answer.type == "choice"]
    events = run(Student(wrong={only: None}))
    asked = [(r, why) for a, n, r, _, why in decisions(events) if n == "KC-DEC-CONCEPT" and r == only]
    assert len(asked) == 2 and "RETRY_FORM" in asked[1][1]
    assert project_chapter(events, CHAPTER).nodes["KC-DEC-CONCEPT"].passed_at is not None


def test_an_item_is_never_retried_twice():
    node = CHAPTER.node("KC-DEC-CONCEPT")
    every = [*node.checks, *node.completion, *node.practice, *node.transfer]
    (only,) = [i for i in every if CHAPTER.item(i).answer.type == "choice"]

    class AlwaysWrong(Student):
        def answer(self, d, session):
            return resolved(d.ref, success=d.ref != only, session=session)

    events = run(AlwaysWrong())
    assert sum(1 for _, n, r, _, _ in decisions(events) if r == only) == 2
