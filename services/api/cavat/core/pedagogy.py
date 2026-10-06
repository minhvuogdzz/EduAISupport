"""Shared pedagogy vocabulary (shared kernel) used by every module.

Names follow the blueprint: PART 13 (Socratic loop), PART 15 (hint ladder), PART 26 (assessment).
"""

from enum import IntEnum, StrEnum


class HintLevel(IntEnum):
    """Math hint ladder H0–H7 (blueprint PART 15.1)."""

    H0 = 0  # không gợi ý
    H1 = 1  # câu hỏi định hướng
    H2 = 2  # nhắc khái niệm
    H3 = 3  # gợi ý chiến lược
    H4 = 4  # cho một bước trung gian
    H5 = 5  # chia nhỏ bài (scaffold mạnh)
    H6 = 6  # cùng làm từng bước
    H7 = 7  # giải thích đầy đủ


# Independence weight per hint level. Source: Math framework §11; H3 and H5 are
# declared interpretations (DI-2) interpolated between the published values.
INDEPENDENCE_WEIGHT: dict[HintLevel, float] = {
    HintLevel.H0: 1.00,
    HintLevel.H1: 0.85,
    HintLevel.H2: 0.70,
    HintLevel.H3: 0.60,
    HintLevel.H4: 0.50,
    HintLevel.H5: 0.35,
    HintLevel.H6: 0.20,
    HintLevel.H7: 0.00,
}


class HintTarget(StrEnum):
    """What a hint is aimed at (the second axis of the hint engine)."""

    TASK = "TASK"
    CONCEPT = "CONCEPT"
    STRATEGY = "STRATEGY"
    STEP = "STEP"
    SELF_CHECK = "SELF_CHECK"
    FORMAT = "FORMAT"


class Move(StrEnum):
    """Pedagogical move chosen by the tutor policy for one tutor turn."""

    PRESENT = "PRESENT"
    PROBE = "PROBE"
    HINT = "HINT"
    COGNITIVE_CONFLICT = "COGNITIVE_CONFLICT"
    NUDGE = "NUDGE"
    REDIRECT = "REDIRECT"
    OFFER_CHOICE = "OFFER_CHOICE"
    ASK_CONFIRM = "ASK_CONFIRM"
    VERIFY = "VERIFY"
    CONFIRM_ADVANCE = "CONFIRM_ADVANCE"
    WORKED_GUIDANCE = "WORKED_GUIDANCE"
    FULL_EXPLANATION = "FULL_EXPLANATION"
    TEACH_BACK = "TEACH_BACK"
    CLOSE_ITEM = "CLOSE_ITEM"


# Moves whose message must end with exactly one question to the student.
MOVES_REQUIRING_QUESTION = frozenset(
    {
        Move.PROBE,
        Move.HINT,
        Move.COGNITIVE_CONFLICT,
        Move.NUDGE,
        Move.REDIRECT,
        Move.OFFER_CHOICE,
        Move.ASK_CONFIRM,
        Move.VERIFY,
        Move.WORKED_GUIDANCE,
        Move.FULL_EXPLANATION,
        Move.TEACH_BACK,
    }
)

# Moves that are allowed to state the final answer before the student has solved the item.
MOVES_ALLOWED_TO_REVEAL = frozenset({Move.FULL_EXPLANATION})

# Moves that deliver hint content and therefore raise the support level.
HINT_MOVES = frozenset({Move.HINT, Move.COGNITIVE_CONFLICT, Move.WORKED_GUIDANCE, Move.FULL_EXPLANATION})


class Outcome(StrEnum):
    """Result of reading one student message against the current item."""

    CORRECT = "CORRECT"
    WRONG = "WRONG"
    PARTIAL = "PARTIAL"
    UNPARSEABLE = "UNPARSEABLE"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NEEDS_LLM = "NEEDS_LLM"
    NO_RESPONSE = "NO_RESPONSE"
    HELP_REQUEST = "HELP_REQUEST"
    ANSWER_DEMAND = "ANSWER_DEMAND"


# Outcomes that count as a graded attempt at the item.
GRADED_OUTCOMES = frozenset({Outcome.CORRECT, Outcome.WRONG, Outcome.PARTIAL})


class ErrorClass(StrEnum):
    CONCEPTUAL = "CONCEPTUAL"
    PROCEDURAL = "PROCEDURAL"
    CALCULATION = "CALCULATION"
    FORMAT = "FORMAT"
    REASONING = "REASONING"
    UNKNOWN = "UNKNOWN"


class ActivityType(StrEnum):
    OPENING = "OPENING"
    WARMUP_REVIEW = "WARMUP_REVIEW"
    CONCEPT_CHECK = "CONCEPT_CHECK"
    TEACH = "TEACH"
    GUIDED_PRACTICE = "GUIDED_PRACTICE"
    INDEPENDENT_PRACTICE = "INDEPENDENT_PRACTICE"
    EXIT_ASSESSMENT = "EXIT_ASSESSMENT"
    SUMMARY = "SUMMARY"


class TeachAction(StrEnum):
    """What the node teaching policy decides (plan v1, 5.4). One action per decision."""

    ENTER_NODE = "ENTER_NODE"
    WARMUP_ITEM = "WARMUP_ITEM"  # step 1: a quick item of a prerequisite
    SWITCH_TO_PREREQUISITE = "SWITCH_TO_PREREQUISITE"  # the current node waits; teach the prerequisite
    TEACH_THEORY = "TEACH_THEORY"  # step 2 (and re-teaching): one theory variant
    CHECK_ITEM = "CHECK_ITEM"  # step 3: a concept-check item
    ASK_RETELL = "ASK_RETELL"  # step 3: "con nói lại" the rule in the student's own words
    SHOW_WORKED_EXAMPLE = "SHOW_WORKED_EXAMPLE"  # step 4: "cô làm mẫu"
    COMPLETION_ITEM = "COMPLETION_ITEM"  # step 4: "cô làm nửa, con làm nửa"
    PRACTICE_ITEM = "PRACTICE_ITEM"  # step 5
    TRANSFER_ITEM = "TRANSFER_ITEM"  # step 6
    REVIEW_ITEM = "REVIEW_ITEM"  # interleaved review of a node passed before
    PASS_NODE = "PASS_NODE"  # step 7
    STOP_NODE = "STOP_NODE"  # step 7: out of budget or items, "cần học lại"
    FINISH = "FINISH"


# Actions that put an item in front of the student (the item loop runs it to the end).
ITEM_ACTIONS = frozenset(
    {
        TeachAction.WARMUP_ITEM,
        TeachAction.CHECK_ITEM,
        TeachAction.COMPLETION_ITEM,
        TeachAction.PRACTICE_ITEM,
        TeachAction.TRANSFER_ITEM,
        TeachAction.REVIEW_ITEM,
    }
)


class PracticeSupport(StrEnum):
    """How much help an item gets, from the node's mastery band (blueprint DI-8)."""

    EXPLAIN_FIRST = "EXPLAIN_FIRST"  # M < 40: micro explanation, guided example
    GUIDED = "GUIDED"  # 40-59: Socratic questions, early hints
    ASK_WHY = "ASK_WHY"  # 60-74: independent practice and "vì sao"
    TRANSFER = "TRANSFER"  # 75-89: new forms
    CHALLENGE = "CHALLENGE"  # >= 90


class ItemResolution(StrEnum):
    """How an item ended, used to weight the evidence it produces."""

    INDEPENDENT = "INDEPENDENT"  # solved at H0
    SUPPORTED = "SUPPORTED"  # solved after H1–H5
    WORKED = "WORKED"  # solved only with H6/H7
    UNRESOLVED = "UNRESOLVED"  # closed without a correct answer


def resolution_for(level: HintLevel) -> ItemResolution:
    if level == HintLevel.H0:
        return ItemResolution.INDEPENDENT
    if level <= HintLevel.H5:
        return ItemResolution.SUPPORTED
    return ItemResolution.WORKED
