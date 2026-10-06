"""Node mastery projector: a pure fold from the event log to the state of every node of a chapter.

Plan v1 section 5.3 and ADR-018. Formulas come from blueprint PART 25.2 and 26.1 (DI-1 to DI-6, DI-11,
DI-12); the node pass rule is DI-15 and the starting score is DI-16. Rule 3: the projection is
deterministic, versioned (``MasteryPolicy.version``) and replayable. The LLM never writes mastery; an
LLM label is only evidence with a weight (PART 26.5).

Each node has one Beta(alpha, beta) per dimension C, R, A, T, I, S, D. An evidence with score s in [0, 1]
and weight w adds w*s to alpha and w*(1-s) to beta: a correct answer raises the score, a wrong one lowers
it. Evidence comes from three events:

- ITEM_RESOLVED: the answer dimension of the item (C for levels A-B, R for C, A for D, T for E or a
  transfer item, D for DIAG); independence I from the highest hint; R = 0 when the student was asked
  "vì sao" and gave no explanation, guessed, or left a conceptual error unresolved;
- EXPLANATION_SUBMITTED: an item-level "vì sao" reply (R);
- RETELL_JUDGED: the node retell judged against its key ideas (R).

Retention S only comes from delayed probes (milestone 2), so it stays empty here.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from cavat.core.events import EventType, ExplanationSubmitted, ItemResolved, QuestionShown, RetellJudged
from cavat.core.pedagogy import ErrorClass, ItemResolution
from cavat.modules.content.chapter_package import Chapter

MASTERY_POLICY_VERSION = "node-mastery/0.1.0"

DIMENSIONS = ("C", "R", "A", "T", "I", "S", "D")
APPLICATION_DIMENSIONS = frozenset({"A", "T"})  # DI-6 "application evidence": level D/E or transfer items
LEVEL_STATES = ("LEARNING", "RECOGNIZED", "PROCEDURAL", "CONCEPTUAL", "APPLIED", "PROVISIONALLY_MASTERED")


class EventLike(Protocol):
    """What the projector reads from an event (``SessionEvent`` fits). Events must be in order."""

    event_type: str
    payload: Mapping[str, Any]
    session_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class MasteryPolicy:
    """Every number of the projection. [FACT] comes from the evaluation framework; the rest are DIs."""

    version: str = MASTERY_POLICY_VERSION
    weights: Mapping[str, float] = field(
        default_factory=lambda: {"C": 0.20, "R": 0.20, "A": 0.15, "T": 0.15, "I": 0.10, "S": 0.10, "D": 0.10}
    )  # §20 [FACT]
    independence: tuple[float, ...] = (
        1.0,
        0.85,
        0.70,
        0.60,
        0.50,
        0.35,
        0.20,
        0.0,
    )  # §11 [FACT]; H3, H5: DI-2
    min_support: float = 0.3  # DI-5: a correct answer after H7 still counts, with a low weight
    error_scores: Mapping[ErrorClass, float] = field(
        default_factory=lambda: {ErrorClass.CALCULATION: 0.5, ErrorClass.FORMAT: 0.7}
    )  # §34 + DI-3: other errors score 0
    guess_factor: float = 0.5  # DI-3 GUESS
    completion_factor: float = 0.5  # DI: a "cùng làm" item gives part of the solution
    unjudged_explanation_weight: float = 0.3  # DI: a "vì sao" reply nobody judged, like an unverified label
    label_min_confidence: float = 0.6  # PART 26.5
    low_confidence_factor: float = 0.3  # PART 26.5
    min_evidence: float = 1.0  # DI-1: a dimension enters M from this much effective evidence
    prior_mass: float = 2.0  # DI-12: prior Beta(1, 1); DI-16 keeps this mass and moves the mean
    success_max_hint: int = 3  # DI: a success (UNDERSTOOD) is solved by H3; H4 and above show the steps
    resolve_after: int = 2  # DI: successes after the last detection that resolve a misconception
    bands: tuple[float, ...] = (20, 40, 60, 75, 90)  # §4-§8 [FACT]: lower bounds of levels 1 to 5
    explanation_gate: float = 0.6  # DI-6: mu_R for level CONCEPTUAL and for passing a node
    provisional: tuple[float, float, float] = (85, 75, 0.8)  # §53 without S: M, confidence, mu_A


DEFAULT_POLICY = MasteryPolicy()


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Evidence(_Out):
    seq: int  # index of the source event in the projected stream
    node_id: str
    dimension: str
    score: float
    weight: float
    reason: str
    item_id: str | None = None


class DimensionState(_Out):
    alpha: float
    beta: float
    n_eff: float
    mean: float
    in_mastery: bool


class MisconceptionState(_Out):
    id: str
    severity: str
    count: int
    status: Literal["ACTIVE", "RESOLVING", "RESOLVED"]
    last_seq: int


class NodeState(_Out):
    node_id: str
    prior: float  # starting mean of every dimension (DI-16)
    dimensions: dict[str, DimensionState]
    mastery: float | None  # M on 0-100; None before any dimension has enough evidence
    confidence: float  # 0-100 (DI-11)
    level: int  # 0-5 (§4-§8, capped by DI-6)
    state: str
    insufficient_data: bool  # DI-7: show "chưa đủ dữ liệu" rather than a number
    items: int
    successes: int
    levels: list[str]
    forms: list[str]
    understood: bool  # §52 gate with the node's pass rule
    has_explanation: bool
    has_application: bool
    misconceptions: list[MisconceptionState]
    pass_now: bool  # the pass rule (DI-15) holds on the evidence so far
    passed_at: int | None  # first event index where it held; unlocks the next nodes
    missing: list[str]  # MASTERY, UNDERSTOOD, EXPLANATION, APPLICATION, MISCONCEPTION


class ChapterProjection(_Out):
    policy_version: str
    chapter_id: str
    chapter_version: str
    nodes: dict[str, NodeState]
    evidence: list[Evidence]


def answer_dimension(cognitive_level: str, transfer: str) -> str:
    """The dimension an item's answer is evidence for (PART 26.1; DI for an item fitting two rows)."""
    if cognitive_level == "DIAG":
        return "D"
    if cognitive_level == "E":
        return "T"
    if cognitive_level == "D":
        return "A"
    if transfer != "none":
        return "T"
    return "R" if cognitive_level == "C" else "C"


def project_chapter(
    events: Iterable[EventLike], chapter: Chapter, policy: MasteryPolicy = DEFAULT_POLICY
) -> ChapterProjection:
    """Fold the events, in order, into the state of every node. Invalid payloads raise."""
    projector = _Projector(chapter, policy)
    for seq, event in enumerate(events):
        projector.add(seq, event)
    return projector.result()


@dataclass
class _Misconception:
    severity: str
    count: int = 0
    streak: int = 0
    status: Literal["ACTIVE", "RESOLVING", "RESOLVED"] = "ACTIVE"
    last_seq: int = 0
    context: set[str] = field(default_factory=set)  # KCs where it was seen, plus its home KC


@dataclass
class _Node:
    sums: dict[str, list[float]] = field(default_factory=lambda: {d: [0.0, 0.0, 0.0] for d in DIMENSIONS})
    prior: float | None = None  # frozen at the first evidence (DI-16)
    items: int = 0
    levels_seen: set[str] = field(default_factory=set)
    successes: list[tuple[str, str]] = field(default_factory=list)  # (cognitive level, question form)
    application: bool = False
    scores: list[float] = field(default_factory=list)  # scores of the non-I evidence, in order
    sessions: set[str] = field(default_factory=set)
    first_at: datetime | None = None
    last_at: datetime | None = None
    misconceptions: dict[str, _Misconception] = field(default_factory=dict)
    passed_at: int | None = None


class _Projector:
    def __init__(self, chapter: Chapter, policy: MasteryPolicy) -> None:
        self.chapter, self.policy = chapter, policy
        self.nodes = {n.id: _Node() for n in chapter.nodes}
        self.evidence: list[Evidence] = []
        self.item_kcs: dict[str, list[str]] = {}
        self.misconception_info = {
            m.id: m for lesson in chapter.lessons.values() for m in lesson.misconceptions
        }
        self._event: EventLike | None = None

    # ------------------------------------------------------------------ events

    def add(self, seq: int, event: EventLike) -> None:
        self._event = event
        kind = event.event_type
        if kind == EventType.QUESTION_SHOWN:
            shown = QuestionShown.model_validate(event.payload)
            self.item_kcs[shown.item_id] = list(shown.kc_ids)
            return
        if kind == EventType.ITEM_RESOLVED:
            touched = self._item(seq, ItemResolved.model_validate(event.payload))
        elif kind == EventType.EXPLANATION_SUBMITTED:
            touched = self._explanation(seq, ExplanationSubmitted.model_validate(event.payload))
        elif kind == EventType.RETELL_JUDGED:
            touched = self._retell(seq, RetellJudged.model_validate(event.payload))
        else:
            return
        for node_id in dict.fromkeys(touched):
            if self.nodes[node_id].passed_at is None and self._state(node_id).pass_now:
                self.nodes[node_id].passed_at = seq

    def _item(self, seq: int, p: ItemResolved) -> list[str]:
        pol = self.policy
        kcs = [k for k in p.kc_ids if k in self.nodes]
        resolved = p.resolution != ItemResolution.UNRESOLVED
        support = pol.independence[p.max_hint_level]
        dimension = answer_dimension(p.cognitive_level, p.transfer)
        scaffolded = any(p.item_id in self.chapter.node(k).completion for k in kcs)
        scaffold = pol.completion_factor if scaffolded else 1.0
        success = resolved and p.max_hint_level <= pol.success_max_hint and not p.guessed and not scaffolded
        form = self._form(p.item_id)
        for node_id in kcs:
            acc = self.nodes[node_id]
            acc.items += 1
            acc.levels_seen.add(p.cognitive_level)
            if resolved:
                weight = (0.5 + p.difficulty) * max(support, pol.min_support) * scaffold
                if p.guessed:
                    weight *= pol.guess_factor
                self._record(seq, node_id, dimension, 1.0, weight, "ANSWER", p.item_id)
                self._record(seq, node_id, "I", support, scaffold, "INDEPENDENCE", p.item_id)
            else:
                score = pol.error_scores.get(p.final_error_class, 0.0) if p.final_error_class else 0.0
                weight = (1.5 - p.difficulty) * scaffold
                self._record(seq, node_id, dimension, score, weight, "ANSWER", p.item_id)
                if p.final_error_class == ErrorClass.CONCEPTUAL:
                    self._record(seq, node_id, "R", 0.0, weight, "CONCEPTUAL_ERROR", p.item_id)
            if p.explained is False:
                self._record(seq, node_id, "R", 0.0, 1.0, "NO_EXPLANATION", p.item_id)
            if p.guessed:
                self._record(seq, node_id, "R", 0.0, 1.0, "GUESS", p.item_id)
            if success:
                acc.successes.append((p.cognitive_level, form))
                acc.application = acc.application or dimension in APPLICATION_DIMENSIONS
        return kcs + self._misconceptions(seq, p, kcs, success)

    def _misconceptions(self, seq: int, p: ItemResolved, kcs: list[str], success: bool) -> list[str]:
        """Detections make a misconception ACTIVE; later successes where it could show resolve it."""
        homes: list[str] = []
        for mis_id in p.misconception_ids:
            info = self.misconception_info.get(mis_id)
            home = info.kc_id if info is not None else (kcs[0] if kcs else None)
            if home not in self.nodes:
                continue
            severity = info.severity if info is not None else "NORMAL"
            mis = self.nodes[home].misconceptions.setdefault(mis_id, _Misconception(severity=severity))
            mis.count, mis.streak, mis.status, mis.last_seq = mis.count + 1, 0, "ACTIVE", seq
            mis.context.update([*kcs, home])
            homes.append(home)
        if success:
            for node_id, acc in self.nodes.items():
                for mis_id, mis in acc.misconceptions.items():
                    if (
                        mis_id in p.misconception_ids
                        or mis.status == "RESOLVED"
                        or not mis.context & set(kcs)
                    ):
                        continue
                    mis.streak += 1
                    mis.status = "RESOLVED" if mis.streak >= self.policy.resolve_after else "RESOLVING"
                    homes.append(node_id)
        return homes

    def _explanation(self, seq: int, p: ExplanationSubmitted) -> list[str]:
        if p.label_source == "NONE":
            score, weight = 1.0, self.policy.unjudged_explanation_weight
        else:
            score = p.reasoning_quality if p.reasoning_quality is not None else 1.0
            weight = self._label_weight(p.label_source, p.label_confidence)
        kcs = [k for k in self._kcs_of(p.item_id) if k in self.nodes]
        for node_id in kcs:
            self._record(seq, node_id, "R", score, weight, "EXPLANATION", p.item_id)
        return kcs

    def _retell(self, seq: int, p: RetellJudged) -> list[str]:
        if p.node_id not in self.nodes:
            return []
        weight = self._label_weight(p.label_source, p.label_confidence)
        self._record(seq, p.node_id, "R", p.score, weight, "RETELL", None)
        return [p.node_id]

    def _record(
        self,
        seq: int,
        node_id: str,
        dimension: str,
        score: float,
        weight: float,
        reason: str,
        item_id: str | None,
    ) -> None:
        acc = self.nodes[node_id]
        if acc.prior is None:
            acc.prior = self._prior(node_id)
        sums = acc.sums[dimension]
        sums[0] += weight * score
        sums[1] += weight * (1.0 - score)
        sums[2] += weight
        if dimension != "I":
            acc.scores.append(score)
        assert self._event is not None
        acc.sessions.add(self._event.session_id)
        at = self._event.occurred_at
        acc.first_at = at if acc.first_at is None else min(acc.first_at, at)
        acc.last_at = at if acc.last_at is None else max(acc.last_at, at)
        self.evidence.append(
            Evidence(
                seq=seq,
                node_id=node_id,
                dimension=dimension,
                score=round(score, 4),
                weight=round(weight, 4),
                reason=reason,
                item_id=item_id,
            )
        )

    # ------------------------------------------------------------------ helpers

    def _label_weight(self, source: str, confidence: float) -> float:
        low = source == "LLM" and confidence < self.policy.label_min_confidence
        return self.policy.low_confidence_factor if low else 1.0

    def _kcs_of(self, item_id: str) -> list[str]:
        if item_id in self.item_kcs:
            return self.item_kcs[item_id]
        try:
            return list(self.chapter.item(item_id).kc_ids)
        except KeyError:
            return []

    def _form(self, item_id: str) -> str:
        try:
            return self.chapter.item(item_id).answer.type
        except KeyError:
            return "unknown"

    def _prior(self, node_id: str) -> float:
        """DI-16 (cold start, 2T-KT): the mean mastery of the prerequisites learned so far, else 0.5."""
        known = [m for p in self.chapter.prerequisites(node_id) if (m := self._mastery(p)) is not None]
        return sum(known) / len(known) / 100 if known else 0.5

    def _dimensions(self, node_id: str) -> tuple[float, dict[str, DimensionState]]:
        acc, pol = self.nodes[node_id], self.policy
        prior = acc.prior if acc.prior is not None else self._prior(node_id)
        out = {}
        for d in DIMENSIONS:
            a_ev, b_ev, n = acc.sums[d]
            alpha, beta = pol.prior_mass * prior + a_ev, pol.prior_mass * (1 - prior) + b_ev
            out[d] = DimensionState(
                alpha=alpha, beta=beta, n_eff=n, mean=alpha / (alpha + beta), in_mastery=n >= pol.min_evidence
            )
        return prior, out

    def _mastery(self, node_id: str) -> float | None:
        if not any(n >= self.policy.min_evidence for _, _, n in self.nodes[node_id].sums.values()):
            return None
        return _composite(self._dimensions(node_id)[1], self.policy)

    def _confidence(self, acc: _Node) -> float:
        """DI-11: 100 * f_n * f_div * f_span * f_cons (PART 26.3)."""
        n_eff = sum(acc.sums[d][2] for d in DIMENSIONS if d != "I")
        if n_eff == 0 or acc.first_at is None or acc.last_at is None:
            return 0.0
        f_n = 1 - math.exp(-n_eff / 6)
        f_div = 0.4 + 0.6 * min(1.0, len(acc.levels_seen) / 4)
        if len(acc.sessions) < 2:
            f_span = 0.70
        else:
            f_span = 1.0 if acc.last_at - acc.first_at >= timedelta(days=3) else 0.85
        recent = acc.scores[-8:]
        f_cons = min(1.0, max(0.5, 1 - 2 * statistics.pstdev(recent))) if len(recent) > 1 else 1.0
        return 100 * f_n * f_div * f_span * f_cons

    # ------------------------------------------------------------------ state

    def _state(self, node_id: str) -> NodeState:
        pol, acc, rule = self.policy, self.nodes[node_id], self.chapter.node(node_id).pass_rule
        prior, dims = self._dimensions(node_id)
        mastery = self._mastery(node_id)
        confidence = self._confidence(acc)
        has_explanation = dims["R"].in_mastery and dims["R"].mean >= pol.explanation_gate
        critical = [
            m for m in acc.misconceptions.values() if m.severity == "CRITICAL" and m.status != "RESOLVED"
        ]

        level = 0 if mastery is None else sum(mastery >= b for b in pol.bands)
        if level >= 3 and not has_explanation:  # DI-6
            level = 2
        if level >= 4 and not acc.application:  # DI-6
            level = 3
        m_min, c_min, a_min = pol.provisional
        provisional = mastery is not None and mastery >= m_min and confidence >= c_min and not critical
        if level == 5 and not (provisional and dims["A"].in_mastery and dims["A"].mean >= a_min):
            level = 4

        levels = sorted({lv for lv, _ in acc.successes} - {"DIAG"})
        forms = sorted({f for _, f in acc.successes})
        understood = (
            len(acc.successes) >= rule.min_successes
            and len(levels) >= rule.min_levels
            and len(forms) >= rule.min_forms
        )
        missing = []
        if mastery is None or mastery < 100 * rule.min_mastery:
            missing.append("MASTERY")
        if not understood:
            missing.append("UNDERSTOOD")
        if rule.require_explanation and not has_explanation:
            missing.append("EXPLANATION")
        if rule.require_application and not acc.application:
            missing.append("APPLICATION")
        if critical:
            missing.append("MISCONCEPTION")

        return NodeState(
            node_id=node_id,
            prior=round(prior, 4),
            dimensions={d: _rounded(s) for d, s in dims.items()},
            mastery=None if mastery is None else round(mastery, 1),
            confidence=round(confidence, 1),
            level=level,
            state="NOT_LEARNED" if mastery is None else LEVEL_STATES[level],
            insufficient_data=confidence < 30,
            items=acc.items,
            successes=len(acc.successes),
            levels=levels,
            forms=forms,
            understood=understood,
            has_explanation=has_explanation,
            has_application=acc.application,
            misconceptions=[
                MisconceptionState(
                    id=k, severity=m.severity, count=m.count, status=m.status, last_seq=m.last_seq
                )
                for k, m in sorted(acc.misconceptions.items())
            ],
            pass_now=not missing,
            passed_at=acc.passed_at,
            missing=missing,
        )

    def result(self) -> ChapterProjection:
        pkg = self.chapter.package
        return ChapterProjection(
            policy_version=self.policy.version,
            chapter_id=pkg.chapter_id,
            chapter_version=pkg.version,
            nodes={n.id: self._state(n.id) for n in pkg.nodes},
            evidence=self.evidence,
        )


def _composite(dims: Mapping[str, DimensionState], policy: MasteryPolicy) -> float | None:
    """§20 with DI-1: dimensions without enough evidence are left out and the weights renormalized."""
    available = [d for d in DIMENSIONS if dims[d].in_mastery]
    if not available:
        return None
    total = sum(policy.weights[d] for d in available)
    return 100 * sum(policy.weights[d] * dims[d].mean for d in available) / total


def _rounded(s: DimensionState) -> DimensionState:
    return s.model_copy(
        update={
            "alpha": round(s.alpha, 4),
            "beta": round(s.beta, 4),
            "n_eff": round(s.n_eff, 4),
            "mean": round(s.mean, 4),
        }
    )
