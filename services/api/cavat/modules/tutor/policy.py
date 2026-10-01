"""Adaptive hint policy: a deterministic rule engine (blueprint PART 15.2).

``decide`` maps one ``PolicyInput`` to a ``PolicyDecision`` (or ``None`` when the tutor should keep
waiting). Every rule has a ``rule_id`` (R-*) that is recorded in the decision, so each decision can be
explained, tested rule by rule and replayed. The LLM never picks the move, the target or the level.

Input convention: ``inp.state`` already reflects the message being decided on (the item loop bumps
``attempt_no``, ``unproductive_turns``... before calling ``decide``), so ``attempt_no == 1`` with a
WRONG check is the first wrong answer. For the EXPLANATION trigger (the reply to VERIFY or TEACH_BACK),
``inp.check`` is None for a real explanation, or carries the intent (NO_RESPONSE, HELP_REQUEST...) when
the reply is not one.

Thresholds taken from the blueprint table are marked [FACT]; the others are declared interpretations
(DI) and live in ``PolicyConfig`` so that a change is a versioned config change, not a code change.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, replace

from cavat.core.pedagogy import (
    HINT_MOVES,
    ActivityType,
    ErrorClass,
    HintLevel,
    HintTarget,
    ItemResolution,
    Move,
    Outcome,
    resolution_for,
)
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, PolicyInput

POLICY_VERSION = "hint-policy/0.2.0"

# DI: the activities where R-FULL may give H7 ("chỉ ở activity practice").
PRACTICE_ACTIVITIES = frozenset({ActivityType.GUIDED_PRACTICE, ActivityType.INDEPENDENT_PRACTICE})

# DI: hint target when no rule picks one, from the diagnosed error class.
_TARGET_FOR_ERROR: dict[ErrorClass, HintTarget] = {
    ErrorClass.CONCEPTUAL: HintTarget.CONCEPT,
    ErrorClass.PROCEDURAL: HintTarget.STEP,
    ErrorClass.CALCULATION: HintTarget.SELF_CHECK,
    ErrorClass.REASONING: HintTarget.STRATEGY,
    ErrorClass.FORMAT: HintTarget.FORMAT,
    ErrorClass.UNKNOWN: HintTarget.STEP,
}

# Outcomes (besides the HINT_REQUEST trigger) that show no progress after worked guidance (R-FULL).
_STALLED = frozenset({Outcome.WRONG, Outcome.HELP_REQUEST, Outcome.ANSWER_DEMAND})

# Replies to a "vì sao" or teach-back question that carry no explanation.
_NO_EXPLANATION = frozenset({Outcome.NO_RESPONSE, Outcome.HELP_REQUEST, Outcome.ANSWER_DEMAND})


@dataclass(frozen=True)
class PolicyConfig:
    misconception_high: float = 0.7  # [FACT] R-MISC-HIGH
    strong_mastery: float = 0.75  # [FACT] R-STRONG-PRIOR
    strong_confidence: float = 0.6  # [FACT] R-STRONG-PRIOR
    weak_mastery: float = 0.4  # [FACT] R-WEAK-PRIOR
    high_hint_dependency: float = 0.5  # DI: mean recent hint level >= H3.5 (hint_dependency = level/7)
    wait_s: float = 45.0  # DI: middle of the 30-60 s range of R-NO-RESPONSE
    wait_s_strong: float = 60.0  # DI: top of the range (R-STRONG-PRIOR "tăng wait_s")
    wait_s_weak: float = 30.0  # DI: bottom of the range (R-WEAK-PRIOR "giảm wait_s")
    frustration_turns: int = 3  # [FACT] R-FRUSTRATION
    stuck_s: float = 300.0  # DI: stuck_s of R-FRUSTRATION
    escalation_step: int = 1  # [FACT] R-ESCALATE
    affect_escalation_step: int = 2  # [FACT] R-ESCALATE "tối đa +2 nếu affect tiêu cực"
    affect_nudges: int = 2  # DI: >= 2 silence nudges on the item is a negative affect signal
    affect_help_requests: int = 2  # DI: >= 2 help requests on the item is a negative affect signal
    max_hint_level: HintLevel = HintLevel.H5  # H6/H7 come only from R-FRUSTRATION and R-FULL
    assessment_cap: HintLevel = HintLevel.H1  # [FACT] R-ASSESS-CAP (Math ladder)
    verify_rate: float = 0.3  # DI: share of items whose correct answer is followed by "vì sao" (R-VERIFY)


DEFAULT_CONFIG = PolicyConfig()


@dataclass(frozen=True)
class ItemFacts:
    """Facts about the item and its lesson package that ``PolicyInput`` does not carry.

    The item loop fills them from the ``Item`` and ``LessonPackage``.
    """

    kc_ids: tuple[str, ...] = ()
    counterexamples: frozenset[str] = frozenset()  # misconception ids with a counterexample in the package
    mandatory_objective: bool = False  # the item belongs to a mandatory objective (R-FULL)
    expected_item_s: float = 90.0  # DI: expected time to finish the item (R-TIME)
    requires_explanation: bool = False  # R-VERIFY always asks "vì sao" after a correct answer


def decide(
    inp: PolicyInput,
    facts: ItemFacts | None = None,
    config: PolicyConfig = DEFAULT_CONFIG,
) -> PolicyDecision | None:
    """Choose the tutor's move for one turn. ``None`` means keep waiting (only for SILENCE or TICK)."""
    facts = facts if facts is not None else ItemFacts()
    decision = _base(inp, facts, config)
    if decision is None:
        return None
    decision = _time_pressure(decision, inp, facts, config)
    decision = _strong_prior_verify(decision, inp, facts, config)
    return _assessment_cap(decision, inp, config)


def wait_seconds(
    inp: PolicyInput,
    facts: ItemFacts | None = None,
    config: PolicyConfig = DEFAULT_CONFIG,
) -> float:
    """Silence allowed before R-NO-RESPONSE nudges; the item loop schedules SILENCE with it."""
    facts = facts if facts is not None else ItemFacts()
    if _weak_prior(inp, facts, config):
        return config.wait_s_weak
    if _strong_prior(inp, facts, config):
        return config.wait_s_strong
    return config.wait_s


def _base(inp: PolicyInput, facts: ItemFacts, cfg: PolicyConfig) -> PolicyDecision | None:
    st, chk = inp.state, inp.check
    outcome = chk.outcome if chk is not None else None

    if inp.trigger == "START":
        return PolicyDecision(move=Move.PRESENT, reason_codes=("ITEM_START",), rule_ids=("R-PRESENT",))
    if inp.trigger == "EXPLANATION":
        return _after_explanation(st, outcome)
    if outcome == Outcome.CORRECT:
        return _correct(st, facts, cfg)

    stalled = outcome in _STALLED or inp.trigger == "HINT_REQUEST"
    time_up = inp.time_left_s <= inp.assessment_reserve_s and st.activity != ActivityType.EXIT_ASSESSMENT
    full = _full(st, facts, stalled=stalled, time_up=time_up)
    if full is not None:
        return full
    if time_up:
        return _close("R-TIME", "TIME_UP", "MOVE_TO_ASSESSMENT")
    if not st.worked_shown and (
        st.unproductive_turns >= cfg.frustration_turns or st.seconds_since_shown > cfg.stuck_s
    ):
        return PolicyDecision(
            move=Move.WORKED_GUIDANCE,
            level=HintLevel.H6,
            target=HintTarget.STEP,
            reason_codes=("FRUSTRATION", "NEXT_TWIN_ITEM_H0"),
            rule_ids=("R-FRUSTRATION",),
        )

    if inp.trigger == "SILENCE" or outcome == Outcome.NO_RESPONSE:
        if inp.trigger == "SILENCE" and st.seconds_since_last_message < wait_seconds(inp, facts, cfg):
            return None
        return PolicyDecision(
            move=Move.NUDGE,
            level=HintLevel.H1,
            target=HintTarget.TASK,
            reason_codes=("NO_RESPONSE", "NOT_COUNTED_AS_WRONG"),
            rule_ids=("R-NO-RESPONSE",),
        )
    if inp.trigger == "HINT_REQUEST" or outcome in (Outcome.HELP_REQUEST, Outcome.ANSWER_DEMAND):
        return PolicyDecision(
            move=Move.OFFER_CHOICE,
            level=_clamp(st.max_hint_level + 1, cfg.max_hint_level),
            target=st.hint_targets[-1] if st.hint_targets else HintTarget.TASK,
            reason_codes=("HELP_REQUEST",),
            rule_ids=("R-HELP-REQUEST",),
        )
    if chk is None:  # TICK with nothing to do
        return None
    if outcome == Outcome.NEEDS_CONFIRMATION:
        return PolicyDecision(
            move=Move.ASK_CONFIRM, reason_codes=("NEEDS_CONFIRMATION",), rule_ids=("R-ASK-CONFIRM",)
        )
    if outcome == Outcome.PARTIAL and st.hint_levels:
        return PolicyDecision(
            move=Move.HINT,
            level=_clamp(st.hint_levels[-1] - 1, cfg.max_hint_level),
            target=st.hint_targets[-1] if st.hint_targets else HintTarget.STEP,
            reason_codes=("STEP_CORRECT_AFTER_HINT", "FADING"),
            rule_ids=("R-DEESCALATE",),
        )
    if outcome in (Outcome.WRONG, Outcome.PARTIAL):
        return _wrong(inp, facts, cfg)
    return PolicyDecision(
        move=Move.REDIRECT, target=HintTarget.TASK, reason_codes=("UNREADABLE",), rule_ids=("R-REDIRECT",)
    )


def _correct(st: ItemState, facts: ItemFacts, cfg: PolicyConfig) -> PolicyDecision:
    """R-TEACH-BACK after worked guidance, else R-VERIFY ("vì sao") when required or sampled."""
    if st.worked_shown:
        return PolicyDecision(
            move=Move.TEACH_BACK,
            reason_codes=("CORRECT_AFTER_WORKED",),
            rule_ids=("R-TEACH-BACK",),
        )
    if facts.requires_explanation:
        return PolicyDecision(
            move=Move.VERIFY, reason_codes=("CORRECT", "REQUIRES_EXPLANATION"), rule_ids=("R-VERIFY",)
        )
    if (
        not st.verified
        and st.activity != ActivityType.EXIT_ASSESSMENT
        and _sampled(st.item_id, cfg.verify_rate)
    ):
        return PolicyDecision(
            move=Move.VERIFY, reason_codes=("CORRECT", "VERIFY_SAMPLED"), rule_ids=("R-VERIFY",)
        )
    return PolicyDecision(
        move=Move.CONFIRM_ADVANCE,
        resolution=resolution_for(st.max_hint_level),
        reason_codes=("CORRECT",),
        rule_ids=("R-CORRECT",),
    )


def _after_explanation(st: ItemState, outcome: Outcome | None) -> PolicyDecision:
    """End the item once the student answered (or skipped) the VERIFY / TEACH_BACK question."""
    rule = "R-TEACH-BACK" if st.worked_shown else "R-VERIFY"
    resolution = resolution_for(st.max_hint_level)
    if outcome in _NO_EXPLANATION:
        return PolicyDecision(
            move=Move.CLOSE_ITEM, resolution=resolution, reason_codes=("NO_EXPLANATION",), rule_ids=(rule,)
        )
    return PolicyDecision(
        move=Move.CONFIRM_ADVANCE,
        resolution=resolution,
        reason_codes=("EXPLANATION_RECEIVED",),
        rule_ids=(rule,),
    )


def _sampled(item_id: str, rate: float) -> bool:
    """DI: deterministic sampling for R-VERIFY, from a hash of the item id (replayable, no RNG)."""
    return zlib.crc32(item_id.encode("utf-8")) % 1000 < rate * 1000


def _full(st: ItemState, facts: ItemFacts, *, stalled: bool, time_up: bool) -> PolicyDecision | None:
    if not ((st.worked_shown and stalled) or (time_up and facts.mandatory_objective)):
        return None
    if st.activity not in PRACTICE_ACTIVITIES:
        return _close("R-FULL", "H7_PRACTICE_ONLY")
    if st.max_hint_level >= HintLevel.H7:
        return _close("R-FULL", "FULL_ALREADY_SHOWN")
    return PolicyDecision(
        move=Move.FULL_EXPLANATION,
        level=HintLevel.H7,
        target=HintTarget.STEP,
        reason_codes=("FULL_EXPLANATION", "NEXT_TEACH_BACK", "NEXT_TWIN_ITEM"),
        rule_ids=("R-FULL",),
    )


def _wrong(inp: PolicyInput, facts: ItemFacts, cfg: PolicyConfig) -> PolicyDecision:
    st, chk = inp.state, inp.check
    assert chk is not None
    first = st.attempt_no <= 1 and not st.hint_levels
    mis = chk.misconception_id
    move = Move.HINT
    target: HintTarget
    level: int
    rules: list[str] = []
    reasons: list[str] = []

    if chk.detail.get("probe_option"):
        # The chosen option has two possible causes (lesson.yaml `probe`): ask the probe before any hint.
        return PolicyDecision(move=Move.PROBE, reason_codes=("SEPARATE_CAUSES",), rule_ids=("R-PROBE-CAUSE",))
    if chk.error_class == ErrorClass.CALCULATION:
        # DI: the checker reports CALCULATION only when the method was right (a slip).
        return PolicyDecision(
            move=Move.HINT,
            level=HintLevel.H1,
            target=HintTarget.SELF_CHECK,
            reason_codes=("SLIP",),
            rule_ids=("R-SLIP",),
        )
    if mis and chk.misconception_confidence >= cfg.misconception_high:
        target = HintTarget.CONCEPT
        level = max(HintLevel.H2, st.max_hint_level)
        rules.append("R-MISC-HIGH")
        reasons.append("MISCONCEPTION_HIGH")
        if mis in facts.counterexamples:
            move = Move.COGNITIVE_CONFLICT
            reasons.append("COUNTEREXAMPLE")
    elif mis and first and _weak_prior(inp, facts, cfg):
        target, level = HintTarget.CONCEPT, HintLevel.H2
        rules.append("R-WEAK-PRIOR")
        reasons.append("WEAK_PRIOR_EARLY_H2")
    elif first:
        return PolicyDecision(
            move=Move.PROBE,
            reason_codes=("FIRST_WRONG", "NEXT_LEVEL_H1"),
            rule_ids=("R-FIRST-WRONG",),
        )
    else:
        target = _TARGET_FOR_ERROR[chk.error_class or ErrorClass.UNKNOWN]
        level = max(HintLevel.H1, st.max_hint_level)
        reasons.append("LADDER")

    if st.hint_levels and st.hint_targets and st.hint_targets[-1] == target:
        negative_affect = st.nudges_sent >= cfg.affect_nudges or st.help_requests >= cfg.affect_help_requests
        step = cfg.affect_escalation_step if negative_affect else cfg.escalation_step
        level = max(level, st.hint_levels[-1] + step)
        rules.append("R-ESCALATE")
        reasons.append("REPEATED_WRONG_SAME_TARGET")
        if negative_affect:
            reasons.append("NEGATIVE_AFFECT")

    return PolicyDecision(
        move=move,
        level=_clamp(level, cfg.max_hint_level),
        target=target,
        misconception_id=mis,
        reason_codes=tuple(reasons),
        rule_ids=tuple(rules) or ("R-LADDER",),
    )


def _time_pressure(
    d: PolicyDecision, inp: PolicyInput, facts: ItemFacts, cfg: PolicyConfig
) -> PolicyDecision:
    """R-TIME (soft part): when the item may not fit before the reserve, escalate faster."""
    if inp.state.activity == ActivityType.EXIT_ASSESSMENT:
        return d
    if inp.time_left_s > inp.assessment_reserve_s + facts.expected_item_s:
        return d
    if d.move == Move.PROBE and inp.check is not None:
        error = inp.check.error_class or ErrorClass.UNKNOWN
        d = replace(d, move=Move.HINT, level=HintLevel.H1, target=_TARGET_FOR_ERROR[error])
    elif "R-ESCALATE" in d.rule_ids and d.level is not None:
        d = replace(d, level=_clamp(d.level + 1, cfg.max_hint_level))
    else:
        return d
    return _tag(d, "R-TIME", "TIME_SHORT")


def _strong_prior_verify(
    d: PolicyDecision, inp: PolicyInput, facts: ItemFacts, cfg: PolicyConfig
) -> PolicyDecision:
    """R-STRONG-PRIOR: ask "vì sao" (VERIFY) instead of a light hint, once per item."""
    if d.move != Move.HINT or d.level is None or d.level > HintLevel.H1 or inp.state.verified:
        return d
    if not _strong_prior(inp, facts, cfg):
        return d
    return _tag(replace(d, move=Move.VERIFY, level=None), "R-STRONG-PRIOR", "VERIFY_BEFORE_HINT")


def _assessment_cap(d: PolicyDecision, inp: PolicyInput, cfg: PolicyConfig) -> PolicyDecision:
    """R-ASSESS-CAP: at most H1 in EXIT_ASSESSMENT and every hint there is *supported* evidence."""
    st = inp.state
    if st.activity != ActivityType.EXIT_ASSESSMENT:
        return d
    cap = cfg.assessment_cap
    if d.level is not None and d.level > cap:
        if st.max_hint_level >= cap:
            return PolicyDecision(
                move=Move.CLOSE_ITEM,
                resolution=ItemResolution.UNRESOLVED,
                reason_codes=(*d.reason_codes, "ASSESS_CAP_REACHED"),
                rule_ids=(*d.rule_ids, "R-ASSESS-CAP"),
            )
        move = d.move if d.move not in (Move.WORKED_GUIDANCE, Move.FULL_EXPLANATION) else Move.HINT
        reasons = tuple(r for r in d.reason_codes if not r.startswith("NEXT_"))
        d = _tag(replace(d, move=move, level=cap, reason_codes=reasons), "R-ASSESS-CAP", "ASSESS_CAP")
    if d.move in HINT_MOVES:
        d = _tag(d, "R-ASSESS-CAP", "EVIDENCE_SUPPORTED")
    return d


def _prior(inp: PolicyInput, facts: ItemFacts) -> tuple[float, float] | None:
    """(mastery, confidence) of the item's weakest known KC (DI: the weakest KC decides)."""
    snap = inp.snapshot
    known = [k for k in facts.kc_ids if k in snap.kc_mastery]
    if not known:
        return None
    return min(snap.kc_mastery[k] for k in known), min(snap.kc_confidence.get(k, 0.0) for k in known)


def _weak_prior(inp: PolicyInput, facts: ItemFacts, cfg: PolicyConfig) -> bool:
    if inp.snapshot.hint_dependency >= cfg.high_hint_dependency:
        return True
    prior = _prior(inp, facts)
    return prior is not None and prior[0] < cfg.weak_mastery


def _strong_prior(inp: PolicyInput, facts: ItemFacts, cfg: PolicyConfig) -> bool:
    prior = _prior(inp, facts)
    if prior is None or _weak_prior(inp, facts, cfg):
        return False
    return prior[0] >= cfg.strong_mastery and prior[1] >= cfg.strong_confidence


def _clamp(level: int, highest: HintLevel) -> HintLevel:
    return HintLevel(min(max(level, HintLevel.H1), highest))


def _close(rule: str, *reasons: str) -> PolicyDecision:
    return PolicyDecision(
        move=Move.CLOSE_ITEM,
        resolution=ItemResolution.UNRESOLVED,
        reason_codes=reasons,
        rule_ids=(rule,),
    )


def _tag(d: PolicyDecision, rule: str, reason: str) -> PolicyDecision:
    rules = d.rule_ids if rule in d.rule_ids else (*d.rule_ids, rule)
    return replace(d, rule_ids=rules, reason_codes=(*d.reason_codes, reason))
