"""Which checker reads an answer, by the answer type of the item (ENG-4, ADR-063).

``phrase`` and ``word_order`` are English (``english_checker``); every other type goes to the
``MathChecker`` exactly as before (english-module-rules M1: ``math_checker.py`` is not changed). An English
choice or true/false item keeps the shared reading of ``math_checker`` for those types.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from cavat.modules.assessment import math_checker
from cavat.modules.assessment.english_checker import (
    ENGLISH_ANSWER_TYPES,
    check_english_item,
    correction_order,
)
from cavat.modules.assessment.math_checker import CheckResult


def is_english_answer(answer: Any) -> bool:
    return getattr(answer, "type", None) in ENGLISH_ANSWER_TYPES


def check_answer(item: Any, text: str, pkg: Any) -> CheckResult:
    """Check one student message against ``item``. Never calls an LLM."""
    if is_english_answer(item.answer):
        return check_english_item(item, text, pkg)
    result = math_checker.check_answer(item, text, pkg)
    if (
        getattr(pkg, "subject", None) == "english"
        and getattr(item.answer, "type", None) == "boolean"
        and result.outcome.value == "CORRECT"
        and (right := correction_order(item, text))
    ):
        # ENG-5h (DI-167): the judgment is right, the sentence that corrects it is in a wrong word order
        result = replace(result, detail={**(result.detail or {}), "word_order": right})
    return result
