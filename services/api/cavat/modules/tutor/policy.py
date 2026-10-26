"""Adaptive hint policy: a deterministic rule engine (blueprint PART 15.2).

``decide`` maps one ``PolicyInput`` to a ``PolicyDecision`` (or ``None`` when the tutor should keep
waiting). Every rule has a ``rule_id`` (R-*) that is recorded in the decision, so each decision can be
explained, tested rule by rule and replayed. The LLM never picks the move, the target or the level on
its own: ``options`` (AUTO-1, ADR-031) may offer it a few allowed moves for a turn, none giving more help
than the policy's own, and ``accept`` plays its pick only when it is one of them.

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
from collections.abc import Sequence
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
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, PolicyInput

# 0.12.0: REFORM-5 (DI-76), a few letters nothing reads are asked about once, then the child is helped
# 0.11.0: REFORM-2 (DI-67, DI-68), a right step advances, no praise without an explanation
# 0.10.0: VERIFY-1 (DI-65), "vì sao" by how sure the child is of the KC
POLICY_VERSION = "hint-policy/0.12.0"

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
# DI, approved by the owner on 2026-10-01: silence after H6 also means "H6 không hiệu quả", so the student
# gets the full explanation and is asked to retell it, instead of nudges until the turn limit.
_STALLED = frozenset({Outcome.WRONG, Outcome.HELP_REQUEST, Outcome.ANSWER_DEMAND, Outcome.NO_RESPONSE})

STEP_ADVANCE_TOP = HintLevel.H5  # DI-67: a right step leads to the next hint, never to the worked steps

# Replies to a "vì sao" or teach-back question that carry no explanation.
_NO_EXPLANATION = frozenset(
    {
        Outcome.NO_RESPONSE,
        Outcome.HELP_REQUEST,
        Outcome.ANSWER_DEMAND,
        Outcome.CLARIFY_REQUEST,
        Outcome.OFF_TOPIC,
        Outcome.NEGATIVE_AFFECT,
    }
)

# REFORM-5 (DI-76): MESSAGE_READ labels of a few letters nothing reads, and the reason each one puts on
# ASK_CONFIRM (the renderer words the question by it).
UNCLEAR_READS = frozenset({"AMBIGUOUS_TYPO", "GIBBERISH"})
UNCLEAR_REASONS = frozenset({"TYPO", "GIBBERISH"})
_REASON_OF_READ = {"AMBIGUOUS_TYPO": "TYPO", "GIBBERISH": "GIBBERISH"}


def unclear_read(chk: CheckResult | None) -> str | None:
    """The label of a check that says "a few letters nothing reads, to ask about" (the item loop sets it),
    or None."""
    if chk is None or chk.outcome != Outcome.NEEDS_CONFIRMATION:
        return None
    read = chk.detail.get("read")
    return read if read in UNCLEAR_READS else None


def unclear_twice(state: ItemState, chk: CheckResult | None) -> bool:
    """Asked once what the letters meant and the next message is as unreadable (R-ASK-CONFIRM does not ask
    again)."""
    return state.confirm_open and unclear_read(chk) is not None


# ADR-019: reasons of the moves that answer what the student said rather than how they answered.
INTENT_REASONS = frozenset({"OFF_TOPIC", "CLARIFY", "NEGATIVE_AFFECT", "ANSWER_DEMAND", "HELP_REQUEST"})


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
    # DI, approved by the owner on 2026-10-01. Items are picked by a hash of the item id, so the same
    # items always ask (lesson 1: 9 of the 21 items that do not already require an explanation).
    verify_rate: float = 0.3  # share of items whose correct answer is followed by "vì sao" (R-VERIFY)
    # DI-65 (VERIFY-1, approved by the owner on 2026-10-22): "vì sao" always follows the first right answer
    # on a KC of the session and a right answer on a KC still below this mastery; the sample above is
    # only for a KC the child already holds or has no mastery for yet.
    verify_mastery: float = 0.6
    # DI-42 (CTX-1, drafted for the owner's review): questions about the hint or a word explained per item;
    # asked again past it, the child gets the next hint instead.
    max_explanations: int = 2


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
    top_hint_level: int = HintLevel.H5  # DI-37: the strongest hint this item has (its own or a fitting one)
    first_on_kc: bool = False  # DI-65: no item of the session was solved yet on one of the item's KCs
    kc_mastery: float | None = None  # DI-65: mastery (0..1) of the item's node so far, None when unknown


def decide(
    inp: PolicyInput,
    facts: ItemFacts | None = None,
    config: PolicyConfig = DEFAULT_CONFIG,
) -> PolicyDecision | None:
    """Choose the tutor's move for one turn. ``None`` means keep waiting (only for SILENCE or TICK)."""
    facts = facts if facts is not None else ItemFacts()
    twice = unclear_twice(inp.state, inp.check)
    if twice:
        # REFORM-5 (3.1, anti-loop): the tutor asked what a few letters meant and the child sent letters
        # nothing reads again. A third question would be the loop the owner saw; a child who keeps typing
        # "kkk" or "tt" is stuck or out of patience, and that is a request for help (the next hint, or the
        # explanation to go on).
        assert inp.check is not None
        inp = replace(inp, check=replace(inp.check, outcome=Outcome.HELP_REQUEST))
    decision = _base(inp, facts, config)
    if decision is None:
        return None
    if twice:
        decision = _tag(decision, "R-ASK-CONFIRM", "UNCLEAR_TWICE")
    decision = _time_pressure(decision, inp, facts, config)
    decision = _strong_prior_verify(decision, inp, facts, config)
    return _assessment_cap(decision, inp, config)


@dataclass(frozen=True)
class MoveOption:
    """One move the policy allows this turn (AUTO-1). ``"A"`` is always the policy's own move."""

    id: str
    decision: PolicyDecision


# AUTO-1 (DI-62): the moves another one may replace, and the rules whose move is never traded: time, the
# worked steps, the probe of a two-cause option, the assessment cap, a slip, "vì sao" before a hint.
_OPEN_MOVES = frozenset({Move.PROBE, Move.HINT, Move.COGNITIVE_CONFLICT, Move.OFFER_CHOICE, Move.EXPLAIN})
_FIXED_RULES = frozenset(
    {
        "R-TIME",
        "R-FRUSTRATION",
        "R-FULL",
        "R-PROBE-CAUSE",
        "R-ASSESS-CAP",
        "R-SLIP",
        "R-STRONG-PRIOR",
        "R-DEESCALATE",
        "R-TURN-LIMIT",
    }
)
CHOICE_RULE = "R-CHOICE"
MAX_OPTIONS = 3


def options(
    inp: PolicyInput,
    decision: PolicyDecision,
    facts: ItemFacts | None = None,
    config: PolicyConfig = DEFAULT_CONFIG,
) -> tuple[MoveOption, ...]:
    """AUTO-1 (ADR-031, DI-62): the moves allowed this turn besides the policy's own ``decision``.

    Empty when the turn has no free choice (an end-of-lesson test, a move that ends the item, a fixed rule,
    a turn that is not the child's). Every other option gives **no more help** than the policy's own move:
    the same rung of the ladder or a lower one, never the worked steps, never past the item's ladder.
    """
    facts = facts if facts is not None else ItemFacts()
    st, d = inp.state, decision
    why = _why_option(inp, d)
    if why is not None:
        return (MoveOption("A", d), MoveOption("B", why))
    if (
        inp.trigger not in ("ANSWER", "HINT_REQUEST")
        or st.activity == ActivityType.EXIT_ASSESSMENT
        or d.resolution is not None
        or d.move not in _OPEN_MOVES
        or _FIXED_RULES.intersection(d.rule_ids)
    ):
        return ()
    alts: list[PolicyDecision] = []
    level, target = d.level, d.target
    if d.move == Move.PROBE:
        # R-FIRST-WRONG says the next rung is H1: the first hint instead of "con làm thế nào?"
        error = (inp.check.error_class if inp.check is not None else None) or ErrorClass.UNKNOWN
        alts.append(replace(d, move=Move.HINT, level=HintLevel.H1, target=_TARGET_FOR_ERROR[error]))
    elif d.move in (Move.HINT, Move.COGNITIVE_CONFLICT) and not INTENT_REASONS.intersection(d.reason_codes):
        # After a wrong answer: ask how the child did it (once per item), a smaller step up the ladder,
        # or the concept hint instead of the counterexample.
        if st.probes_sent == 0:
            alts.append(replace(d, move=Move.PROBE, level=None, target=None))
        if d.move == Move.COGNITIVE_CONFLICT:
            alts.append(replace(d, move=Move.HINT))
        if level is not None and level - 1 > st.max_hint_level and level - 1 >= HintLevel.H1:
            alts.append(replace(d, level=HintLevel(level - 1)))
    elif d.move in (Move.OFFER_CHOICE, Move.EXPLAIN) and level is not None:
        # The hint the offer or the explanation stands for, given at once (the same rung).
        alts.append(replace(d, move=Move.HINT, target=target or HintTarget.TASK))
    elif d.move == Move.HINT and "R-AFFECT" in d.rule_ids and not st.choice_offered:
        alts.append(replace(d, move=Move.OFFER_CHOICE))  # let a discouraged child choose (DI-35 asks once)
    top = _top(facts, config)
    allowed = [
        a for a in alts if a.level is None or (a.level <= top and (d.level is None or a.level <= d.level))
    ]
    if not allowed:
        return ()
    ids = "ABCDEFG"
    return tuple(MoveOption(ids[i], x) for i, x in enumerate([d, *allowed][:MAX_OPTIONS]))


def _why_option(inp: PolicyInput, d: PolicyDecision) -> PolicyDecision | None:
    """AUTO-5 (DI-62): a correct answer the policy closes at once (R-VERIFY sampled the item out) may get
    "vì sao" instead. Asking why gives no help, and the item closes after the reply with the same resolution;
    the chooser asks it where the right answer may be luck (after mistakes or hints on the item)."""
    st = inp.state
    if (
        inp.trigger != "ANSWER"
        or d.move != Move.CONFIRM_ADVANCE
        or d.rule_ids != ("R-CORRECT",)
        or st.verified
        or st.worked_shown
        or st.activity == ActivityType.EXIT_ASSESSMENT
    ):
        return None
    return PolicyDecision(move=Move.VERIFY, reason_codes=("CORRECT", "VERIFY_CHOSEN"), rule_ids=("R-VERIFY",))


def accept(menu: Sequence[MoveOption], option_id: str) -> PolicyDecision | None:
    """The policy's check of a pick (AUTO-1): only a move of the menu is played, tagged ``R-CHOICE``."""
    chosen = next((o for o in menu if o.id == option_id), None)
    if chosen is None:
        return None
    if chosen.id == "A":
        return chosen.decision
    return _tag(chosen.decision, CHOICE_RULE, "MODEL_CHOICE")


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
        return _after_explanation(st, outcome, chk)
    if outcome == Outcome.CORRECT:
        return _correct(st, facts, cfg)

    # A SILENCE tick counts as stalled only once the whole wait time has passed (same as R-NO-RESPONSE).
    waited_out = inp.trigger == "SILENCE" and st.seconds_since_last_message >= wait_seconds(inp, facts, cfg)
    stalled = outcome in _STALLED or inp.trigger == "HINT_REQUEST" or waited_out
    time_up = inp.time_left_s <= inp.assessment_reserve_s and st.activity != ActivityType.EXIT_ASSESSMENT
    full = _full(st, facts, stalled=stalled, time_up=time_up)
    if full is not None:
        return full
    if time_up:
        return _close("R-TIME", "TIME_UP", "MOVE_TO_ASSESSMENT")
    not_an_attempt = _not_an_attempt(st, outcome, facts, cfg)
    if not_an_attempt is not None:
        return not_an_attempt
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
        reason = "ANSWER_DEMAND" if outcome == Outcome.ANSWER_DEMAND else "HELP_REQUEST"
        asked_hint = chk is not None and bool(chk.detail.get("asked_hint"))
        if (
            st.choice_offered
            or asked_hint
            or reason == "ANSWER_DEMAND"
            or st.max_hint_level >= _top(facts, cfg)
        ):
            # DI-35: "gợi ý thêm hay tự thử lại?" once per item, and never after "Xin gợi ý" or a demand
            # for the answer (DI-36: refuse kindly and give the next hint). A student who has had every
            # hint of this item gets the worked steps (the ladder of the item, DI-37).
            d = _next_hint(st, facts, cfg, reason, "R-HELP-REQUEST")
            return _tag(d, "R-HELP-REQUEST", "ASKED_HINT") if asked_hint else d
        return PolicyDecision(
            move=Move.OFFER_CHOICE,
            level=_clamp(st.max_hint_level + 1, _top(facts, cfg)),
            target=st.hint_targets[-1] if st.hint_targets else HintTarget.TASK,
            reason_codes=(reason,),
            rule_ids=("R-HELP-REQUEST",),
        )
    if chk is None:  # TICK with nothing to do
        return None
    if outcome == Outcome.NEEDS_CONFIRMATION:
        return _ask_confirm(chk)
    if outcome == Outcome.PARTIAL and st.hint_levels:
        # REFORM-2 (DI-67): the child answered the question of the hint (a step, or the right value in the
        # other form). That is progress: the next rung leads to the next step, up to H5, and the tutor says
        # so. It used to step back a rung, which asked the same question again. The assessment cap applies
        # after this rule (R-ASSESS-CAP).
        return PolicyDecision(
            move=Move.HINT,
            level=_clamp(min(st.hint_levels[-1] + 1, STEP_ADVANCE_TOP), cfg.max_hint_level),
            target=st.hint_targets[-1] if st.hint_targets else HintTarget.STEP,
            reason_codes=("STEP_CORRECT_AFTER_HINT", "STEP_PRAISE"),
            rule_ids=("R-DEESCALATE",),
        )
    if outcome in (Outcome.WRONG, Outcome.PARTIAL):
        return _wrong(inp, facts, cfg)
    return PolicyDecision(
        move=Move.REDIRECT, target=HintTarget.TASK, reason_codes=("UNREADABLE",), rule_ids=("R-REDIRECT",)
    )


def _ask_confirm(chk: CheckResult | None) -> PolicyDecision:
    """R-ASK-CONFIRM: the tutor asks again what the child meant, and nothing is graded, praised or counted.
    A key slip or a likely typo (REFORM-5) says so in its reason, for the words of the question."""
    kind = _REASON_OF_READ.get(unclear_read(chk) or "")
    return PolicyDecision(
        move=Move.ASK_CONFIRM,
        reason_codes=("NEEDS_CONFIRMATION", *((kind,) if kind else ())),
        rule_ids=("R-ASK-CONFIRM",),
    )


def _not_an_attempt(
    st: ItemState, outcome: Outcome | None, facts: ItemFacts, cfg: PolicyConfig
) -> PolicyDecision | None:
    """ADR-019: talk outside the lesson, "là sao ạ?" and "chán quá" are not answers and not stalled turns.

    R-OFF-TOPIC (DI-33): a short friendly word, then back to the question; no hint, nothing counted.
    R-CLARIFY (DI-34): the task said again (the item's TASK hint at H1), the next hint when asked again.
    R-AFFECT (DI-34): the feeling acknowledged, then an easier step: the next hint, +2 levels from the
    second sign (R-ESCALATE "tối đa +2 nếu affect tiêu cực").
    In EXIT_ASSESSMENT beyond the H1 cap the question is only said again, never closed for it.
    """
    if outcome == Outcome.OFF_TOPIC:
        return PolicyDecision(
            move=Move.REDIRECT,
            target=HintTarget.TASK,
            reason_codes=("OFF_TOPIC", "NOT_COUNTED_AS_WRONG"),
            rule_ids=("R-OFF-TOPIC",),
        )
    if outcome == Outcome.ASKS_ABOUT:
        # R-EXPLAIN (CTX-1, DI-42): the child asks what the hint or a word means. Said from approved
        # content, never the answer. It is help: the next rung of the ladder (what "mẫu số đặc biệt" means
        # is the H2 concept hint), so a later hint does not say it again and the item counts as supported.
        # In an end-of-lesson test the question is only said again; asked again past the limit, a hint.
        if st.activity == ActivityType.EXIT_ASSESSMENT:
            return PolicyDecision(
                move=Move.REDIRECT,
                target=HintTarget.TASK,
                reason_codes=("ASKS_ABOUT", "ASSESSMENT"),
                rule_ids=("R-EXPLAIN",),
            )
        if st.explanations >= cfg.max_explanations:
            return _next_hint(st, facts, cfg, "ASKS_ABOUT", "R-EXPLAIN")
        return PolicyDecision(
            move=Move.EXPLAIN,
            level=_clamp(st.max_hint_level + 1, _top(facts, cfg)),
            target=HintTarget.CONCEPT,
            reason_codes=("ASKS_ABOUT", "NOT_COUNTED_AS_WRONG"),
            rule_ids=("R-EXPLAIN",),
        )
    if outcome not in (Outcome.CLARIFY_REQUEST, Outcome.NEGATIVE_AFFECT):
        return None
    clarify = outcome == Outcome.CLARIFY_REQUEST
    reason, rule = ("CLARIFY", "R-CLARIFY") if clarify else ("NEGATIVE_AFFECT", "R-AFFECT")
    if st.activity == ActivityType.EXIT_ASSESSMENT and st.max_hint_level >= cfg.assessment_cap:
        return PolicyDecision(
            move=Move.REDIRECT, target=HintTarget.TASK, reason_codes=(reason, "ASSESS_CAP"), rule_ids=(rule,)
        )
    if clarify and not st.hint_levels and not st.worked_shown:
        return PolicyDecision(
            move=Move.HINT,
            level=HintLevel.H1,
            target=HintTarget.TASK,
            reason_codes=(reason, "NOT_COUNTED_AS_WRONG"),
            rule_ids=(rule,),
        )
    second_sign = not clarify and st.affect_signals >= 2
    step = cfg.affect_escalation_step if second_sign else cfg.escalation_step
    return _next_hint(st, facts, cfg, reason, rule, step)


def _top(facts: ItemFacts, cfg: PolicyConfig) -> HintLevel:
    """The strongest hint the ladder may give on this item (DI-37)."""
    return HintLevel(max(HintLevel.H1, min(cfg.max_hint_level, facts.top_hint_level)))


def _next_hint(
    st: ItemState, facts: ItemFacts, cfg: PolicyConfig, reason: str, rule: str, step: int | None = None
) -> PolicyDecision:
    """The next rung of the item's ladder; the worked steps when the item has no stronger hint (DI-37);
    the full explanation (or the end of the item) once the worked steps were shown."""
    if st.worked_shown:
        full = _full(st, facts, stalled=True, time_up=False)
        assert full is not None
        return _tag(full, rule, reason)
    top = _top(facts, cfg)
    if st.max_hint_level >= top:
        return PolicyDecision(
            move=Move.WORKED_GUIDANCE,
            level=HintLevel.H6,
            target=HintTarget.STEP,
            reason_codes=(reason, "LADDER_EXHAUSTED", "NEXT_TWIN_ITEM_H0"),
            rule_ids=(rule, "R-FRUSTRATION"),
        )
    step = cfg.escalation_step if step is None else step
    return PolicyDecision(
        move=Move.HINT,
        level=_clamp(st.max_hint_level + step, top),
        target=st.hint_targets[-1] if st.hint_targets else HintTarget.TASK,
        reason_codes=(reason,),
        rule_ids=(rule,),
    )


def _correct(st: ItemState, facts: ItemFacts, cfg: PolicyConfig) -> PolicyDecision:
    """R-TEACH-BACK after worked guidance, else R-VERIFY ("vì sao") when required, on a new or weak KC
    (DI-65), or sampled."""
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
    if not st.verified and st.activity != ActivityType.EXIT_ASSESSMENT:
        # DI-65: the self-explanation helps most while the KC is new or weak; once held, a sample only.
        if facts.first_on_kc:
            reason = "FIRST_ON_KC"
        elif facts.kc_mastery is not None and facts.kc_mastery < cfg.verify_mastery:
            reason = "WEAK_KC"
        elif _sampled(st.item_id, cfg.verify_rate):
            reason = "VERIFY_SAMPLED"
        else:
            reason = None
        if reason is not None:
            return PolicyDecision(move=Move.VERIFY, reason_codes=("CORRECT", reason), rule_ids=("R-VERIFY",))
    return PolicyDecision(
        move=Move.CONFIRM_ADVANCE,
        resolution=resolution_for(st.max_hint_level),
        reason_codes=("CORRECT",),
        rule_ids=("R-CORRECT",),
    )


# ADR-019: replies to "vì sao" that ask something back; the question is asked once more (DI-38).
_ASK_AGAIN_REASON = {
    Outcome.CLARIFY_REQUEST: "CLARIFY",
    Outcome.OFF_TOPIC: "OFF_TOPIC",
    Outcome.NEGATIVE_AFFECT: "NEGATIVE_AFFECT",
}


def _after_explanation(
    st: ItemState, outcome: Outcome | None, chk: CheckResult | None = None
) -> PolicyDecision:
    """End the item once the student answered (or skipped) the VERIFY / TEACH_BACK question.

    "Là sao ạ?", talk outside the lesson or "chán quá" in reply to "vì sao" gets the question once more,
    with a word for what the child said (DI-38); the second time the item ends as before.
    A few letters nothing reads ("ki", "kkk") are asked about first (REFORM-5): the item goes on waiting
    for the explanation, and the "vì sao" is not yet asked again.
    """
    if outcome == Outcome.NEEDS_CONFIRMATION:
        return _ask_confirm(chk)
    rule = "R-TEACH-BACK" if st.worked_shown else "R-VERIFY"
    again = _ASK_AGAIN_REASON.get(outcome) if outcome is not None else None
    if again is not None and not st.explanation_asked_again:
        move = Move.TEACH_BACK if st.worked_shown else Move.VERIFY
        return PolicyDecision(move=move, reason_codes=(again, "ASK_AGAIN"), rule_ids=(rule,))
    if outcome is None and st.last_explanation_vague and not st.explanation_asked_again:
        # DI-55: "vì con làm theo quy tắc" says nothing of this item: asked once, for the step and numbers.
        move = Move.TEACH_BACK if st.worked_shown else Move.VERIFY
        return PolicyDecision(move=move, reason_codes=("VAGUE", "ASK_AGAIN"), rule_ids=(rule,))
    resolution = resolution_for(st.max_hint_level)
    if outcome in _NO_EXPLANATION:
        reasons: tuple[str, ...] = ("NO_EXPLANATION", *((again,) if again else ()))
        if st.max_hint_level >= HintLevel.H7:
            # DI, approved by the owner on 2026-10-01: H7 goes only to a student who has not answered
            # correctly, and nothing is graded after it. Without the teach-back the item was "closed
            # without a correct answer": UNRESOLVED, not WORKED.
            resolution, reasons = ItemResolution.UNRESOLVED, ("NO_EXPLANATION", "NOT_SOLVED")
        return PolicyDecision(
            move=Move.CLOSE_ITEM, resolution=resolution, reason_codes=reasons, rule_ids=(rule,)
        )
    if st.last_explanation_vague:
        # REFORM-3.2 (DI-68): asked once more and the child still says nothing of this item ("không", "ki",
        # "vì con làm theo quy tắc"). No "Đúng rồi!": the tutor says the approved explanation and goes on.
        return PolicyDecision(
            move=Move.CONFIRM_ADVANCE,
            resolution=resolution,
            reason_codes=("EXPLAIN_AND_ADVANCE",),
            rule_ids=(rule,),
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
    # The reply to the probe is not a new attempt (item loop), so the probe itself must count here.
    first = st.attempt_no <= 1 and not st.hint_levels and st.probes_sent == 0
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
    if INTENT_REASONS.intersection(d.reason_codes):
        return d  # the student asked something: answer it, do not turn it into "vì sao"
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
