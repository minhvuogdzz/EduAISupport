"""Teaching state of one session: a fold over its node decisions, item results and retells.

The node policy (``node_policy.py``) reads this state and the node mastery projection, and decides the
next step. Nothing else is stored: replaying the session's events rebuilds the same state (rule 3), so
a session document only needs its event log. Thresholds come from ``NodePolicyConfig``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from cavat.core.events import EventType, ItemResolved, NodeDecisionMade, RetellJudged
from cavat.core.pedagogy import ItemResolution, TeachAction
from cavat.modules.assessment.projector import DEFAULT_POLICY

NODE_POLICY_VERSION = "node-policy/0.2.0"  # 0.2.0: DI-49, items that add a form or level first

Phase = Literal["NEW", "CHECK", "CHECK_FAILED", "PRACTICE"]


@dataclass(frozen=True)
class NodePolicyConfig:
    """Numbers of the node policy. All are DIs (plan v1, 5.4 and section 9)."""

    version: str = NODE_POLICY_VERSION
    retell_pass: float = 0.5  # share of key ideas for "kiểm tra hiểu đạt"
    practice_before_transfer: int = 2  # practice successes before the transfer item
    max_retells: int = 3  # retell prompts in one visit of a node
    remediate_after_check_failures: int = 2  # "kiểm tra hiểu sai hai lần mà node tiên quyết yếu"
    success_max_hint: int = DEFAULT_POLICY.success_max_hint  # the projector's success, kept identical
    support_bands: tuple[float, ...] = (40, 60, 75, 90)  # DI-8: lower bounds of GUIDED .. CHALLENGE


DEFAULT_CONFIG = NodePolicyConfig()


class EventLike(Protocol):
    event_type: str
    payload: Mapping[str, Any]


@dataclass
class Visit:
    """One stay at a node, from ENTER_NODE (or a switch to it) to PASS_NODE, STOP_NODE or a switch away."""

    node_id: str
    phase: Phase = "NEW"
    taught: list[str] = field(default_factory=list)  # theory variants, this visit
    examples: list[str] = field(default_factory=list)  # worked examples, this visit
    items: int = 0  # items asked at this node, this visit (N-BUDGET)
    pending: str | None = None  # the item asked last, until its result arrives
    pending_action: TeachAction | None = None
    warmup_node: str | None = None
    warmup_item: str | None = None
    warmup_ok: bool | None = None
    completion_asked: bool = False
    check_item: str | None = None  # since the last teaching
    check_ok: bool | None = None
    retell_asked: bool = False  # since the last teaching
    retell_pending: bool = False
    retells: int = 0
    check_failures: int = 0
    practice_successes: int = 0


@dataclass
class TeachingState:
    current: Visit | None = None
    waiting: list[str] = field(default_factory=list)  # nodes put on hold by N-REMEDIATE (a stack)
    asked: set[str] = field(default_factory=set)  # items asked in this session
    variants_used: dict[str, list[str]] = field(default_factory=dict)  # per node, this session
    examples_used: dict[str, list[str]] = field(default_factory=dict)
    evidence_nodes: set[str] = field(default_factory=set)  # nodes with an item result in this session
    passed: list[str] = field(default_factory=list)  # in order, this session
    stopped: set[str] = field(default_factory=set)
    remediated: set[tuple[str, str]] = field(default_factory=set)  # (node put on hold, prerequisite)
    review_due: bool = False
    finished: bool = False


def teaching_state(events: Iterable[EventLike], config: NodePolicyConfig = DEFAULT_CONFIG) -> TeachingState:
    """Fold the events of one session, in order. Other event types are ignored."""
    state = TeachingState()
    for event in events:
        if event.event_type == EventType.NODE_DECISION:
            _decision(state, NodeDecisionMade.model_validate(event.payload))
        elif event.event_type == EventType.ITEM_RESOLVED:
            _item(state, ItemResolved.model_validate(event.payload), config)
        elif event.event_type == EventType.RETELL_JUDGED:
            _retell(state, RetellJudged.model_validate(event.payload), config)
    return state


def is_success(p: ItemResolved, config: NodePolicyConfig = DEFAULT_CONFIG) -> bool:
    solved = p.resolution in (ItemResolution.INDEPENDENT, ItemResolution.SUPPORTED)
    return solved and p.max_hint_level <= config.success_max_hint and not p.guessed


def _decision(state: TeachingState, d: NodeDecisionMade) -> None:
    visit, action = state.current, d.action
    if action == TeachAction.ENTER_NODE:
        assert d.node_id is not None
        if state.waiting and state.waiting[-1] == d.node_id:
            state.waiting.pop()
        state.current, state.review_due = Visit(d.node_id), False
    elif action == TeachAction.SWITCH_TO_PREREQUISITE:
        assert visit is not None and d.node_id is not None
        state.waiting.append(visit.node_id)
        state.remediated.add((visit.node_id, d.node_id))
        state.current = Visit(d.node_id)
    elif action == TeachAction.PASS_NODE:
        assert d.node_id is not None
        state.passed.append(d.node_id)
        state.current, state.review_due = None, True
    elif action == TeachAction.STOP_NODE:
        assert d.node_id is not None
        state.stopped.add(d.node_id)
        state.current = None
    elif action == TeachAction.FINISH:
        state.finished = True
    elif action == TeachAction.REVIEW_ITEM:
        assert d.ref is not None
        state.asked.add(d.ref)
        state.review_due = False
    elif visit is not None:
        _visit_decision(state, visit, d)


def _visit_decision(state: TeachingState, visit: Visit, d: NodeDecisionMade) -> None:
    action, ref = d.action, d.ref
    if action == TeachAction.TEACH_THEORY:
        assert ref is not None
        visit.taught.append(ref)
        state.variants_used.setdefault(visit.node_id, []).append(ref)
        visit.phase, visit.check_item, visit.check_ok, visit.retell_asked = "CHECK", None, None, False
    elif action == TeachAction.SHOW_WORKED_EXAMPLE:
        assert ref is not None
        visit.examples.append(ref)
        state.examples_used.setdefault(visit.node_id, []).append(ref)
        if visit.phase == "CHECK_FAILED":  # no theory variant left: the example is the re-teaching
            visit.phase = "PRACTICE"
    elif action == TeachAction.ASK_RETELL:
        visit.retell_asked, visit.retell_pending = True, True
        visit.retells += 1
    elif action == TeachAction.WARMUP_ITEM:
        assert ref is not None
        visit.warmup_node, visit.warmup_item = d.node_id, ref
        visit.pending, visit.pending_action = ref, action
        state.asked.add(ref)
    else:  # CHECK_ITEM, COMPLETION_ITEM, PRACTICE_ITEM, TRANSFER_ITEM
        assert ref is not None
        if action == TeachAction.CHECK_ITEM:
            visit.check_item = ref
        elif action == TeachAction.COMPLETION_ITEM:
            visit.completion_asked = True
        visit.items += 1
        visit.pending, visit.pending_action = ref, action
        state.asked.add(ref)


def _item(state: TeachingState, p: ItemResolved, config: NodePolicyConfig) -> None:
    state.evidence_nodes.update(p.kc_ids)
    visit = state.current
    if visit is None or visit.pending != p.item_id:
        return  # a review item: its evidence only goes to the projection
    action, visit.pending, visit.pending_action = visit.pending_action, None, None
    success = is_success(p, config)
    if action == TeachAction.WARMUP_ITEM:
        visit.warmup_ok = success
    elif action == TeachAction.CHECK_ITEM:
        visit.check_ok = success
    elif action == TeachAction.PRACTICE_ITEM and success:
        visit.practice_successes += 1


def _retell(state: TeachingState, p: RetellJudged, config: NodePolicyConfig) -> None:
    visit = state.current
    if visit is None or visit.node_id != p.node_id or not visit.retell_pending:
        return
    visit.retell_pending = False
    good = p.score >= config.retell_pass
    if visit.phase == "CHECK":
        good = good and visit.check_ok is not False
    if visit.phase in ("CHECK", "PRACTICE"):
        if good:
            visit.phase = "PRACTICE"
        else:
            visit.phase = "CHECK_FAILED"
            visit.check_failures += 1
