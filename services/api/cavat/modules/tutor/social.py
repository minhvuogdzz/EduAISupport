"""BRAIN-2: pure social turns are conversation, never an assessment attempt (DI-87)."""

import re

from cavat.core.vi_text import fold, normalize


def social_reply(text: str, tutor: str = "cô", student: str = "con") -> str | None:
    # Full matches only: a greeting followed by a maths question must reach the maths path.
    said = re.sub(r"[^\w\s]", " ", fold(normalize(text)))
    said = " ".join(said.split())
    if re.fullmatch(r"(?:(?:con|em) )?(?:hi|hello|chao)(?: (?:co|thay))?(?: (?:oi|a|nhe))?", said):
        return f"{tutor.capitalize()} chào {student}! {tutor.capitalize()} đang nghe đây."
    if re.fullmatch(r"(?:(?:con|em) )?(?:cam on|thank you|thanks)(?: (?:co|thay))?(?: a)?", said):
        return f"Không có gì, {student} nhé."
    if re.fullmatch(
        r"(?:sao|tai sao) (?:lai |co lai )?(?:noi )?(?:con|em) chao (?:co|thay)(?: (?:vay|a))?",
        said,
    ) or re.fullmatch(r"co (?:phai |nen )?chao con chu", said):
        return f"À, {tutor} nói nhầm. {tutor.capitalize()} chào {student} nhé!"
    return None


def reversed_greeting(text: str) -> bool:
    """Refuse the tutor speaking as the child, without rejecting 'Con viết…' instructions."""
    return bool(re.search(r"(?:^|[.!?;:]\s*)(?:con|em)\s+(?:chào|cảm ơn)\s+(?:cô|thầy)\b", text.lower()))
