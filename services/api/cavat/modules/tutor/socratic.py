"""Small deterministic checks supplement, never replace, semantic Socratic review."""

import re

from cavat.core.vi_text import fold
from cavat.modules.assessment.vi_numbers import extract_numbers
from cavat.modules.tutor.dialogue import question_tail


def acknowledges_correction(text: str) -> bool:
    """Explicit repair language; truth and whether the correction helps are checked separately."""
    return bool(
        re.search(
            r"\bco\b.{0,30}\b(?:nham|sua|dinh chinh|noi sai|tinh sai|dien dat sai|"
            r"chua dung|chua chinh xac)\b|"
            r"\b(?:luot truoc|vua roi)\b.{0,25}\b(?:nham|sai)\b|"
            r"\bkhong (?:phai|chia ca|chia them|nhan them)\b",
            fold(text.lower()),
        )
    )


def readiness_only(message: str) -> bool:
    """A generic request for readiness is not the next mathematical learning step."""
    question = fold(question_tail(message).lower()).strip(" ?.!")
    if re.search(r"\b(?:viet|chep|nhac) (?:lai |ra )?(?:ket qua|dap an) (?:nay|do)\b", question):
        return True
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


def is_decimal_conversion(pending: str) -> bool:
    return bool(re.search(r"(?:thành|sang|viết|đổi).{0,45}số thập phân", pending.lower())) and any(
        "/" in n.text for n in extract_numbers(pending)
    )


def conversion_answer_leaked(message: str, pending: str) -> bool:
    """A decimal conversion's final answer must stay out of the explanation before its question.

    Only explicit numeric conversions are decided here. Conceptual questions and written-out
    numbers remain the semantic reviewer's responsibility; no assessment key enters a prompt.
    """
    if not is_decimal_conversion(pending):
        return False
    fractions = [n for n in extract_numbers(pending) if "/" in n.text]
    if not fractions:
        return False
    return any(
        n.value == fraction.value and re.fullmatch(r"\d+[,.]\d+", n.text.strip())
        for n in extract_numbers(message)
        for fraction in fractions
    )
