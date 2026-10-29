"""Small deterministic checks supplement, never replace, semantic Socratic review."""

import re

from cavat.core.vi_text import fold
from cavat.modules.assessment.vi_numbers import extract_numbers
from cavat.modules.tutor.dialogue import question_tail


def readiness_only(message: str) -> bool:
    """A generic request for readiness is not the next mathematical learning step."""
    question = fold(question_tail(message).lower()).strip(" ?.!")
    if re.search(r"\bcon (?:co |con |da )?(?:nho|hieu|nam|san sang)\b.*\b(?:chua|khong)$", question):
        return True
    return bool(
        re.fullmatch(
            r"(?:(?:vay|the|bay gio) )?con (?:da |co |co the |muon |san sang )?"
            r"(?:hieu|hieu ro|nam duoc|thu|lam thu|viet ra|thu viet|tra loi|lam tiep)"
            r"(?: (?:viet|ra|lai|duoc|roi|them|thu|tiep))* (?:chua|khong|nhi)",
            question,
        )
    )


def conversion_answer_leaked(message: str, pending: str) -> bool:
    """A decimal conversion's final answer must stay out of the explanation before its question.

    Only explicit numeric conversions are decided here. Conceptual questions and written-out
    numbers remain the semantic reviewer's responsibility; no assessment key enters a prompt.
    """
    if not re.search(r"(?:thành|sang|viết|đổi).{0,45}số thập phân", pending.lower()):
        return False
    fractions = [n for n in extract_numbers(pending) if "/" in n.text]
    if not fractions:
        return False
    tail = question_tail(message)
    body = message[: message.rfind(tail)] if tail else message
    return any(
        n.value == fraction.value and re.fullmatch(r"\d+[,.]\d+", n.text.strip())
        for n in extract_numbers(body)
        for fraction in fractions
    )
