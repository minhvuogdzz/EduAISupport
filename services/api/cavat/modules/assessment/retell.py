"""Deterministic rubric for the node retell ("con nói lại", plan v1 step 3).

A key idea counts when the student's text contains one of its phrasings, as whole words, with or without
diacritics. The score is the share of key ideas found (DI: keyword rubric until the LLM label of milestone
2, which will only be a proposal with a confidence, PART 26.5).
"""

from __future__ import annotations

from cavat.core.events import RetellJudged
from cavat.core.vi_text import contains_phrase
from cavat.modules.content.chapter_package import ExplainSpec


def judge_retell(node_id: str, text: str, spec: ExplainSpec) -> RetellJudged:
    found = [
        i for i, phrasings in enumerate(spec.key_ideas) if any(contains_phrase(text, p) for p in phrasings)
    ]
    total = len(spec.key_ideas)
    return RetellJudged(
        node_id=node_id, text=text, ideas_found=found, ideas_total=total, score=len(found) / total
    )


def with_meaning(
    judged: RetellJudged, ideas: list[int], quotes: list[str], confidence: float
) -> RetellJudged:
    """REFORM-6 (4.1): the keyword judgement plus the ideas a model found with a checked quote. It only adds:
    the keywords' ideas stay, so the score never goes down."""
    if not ideas:
        return judged
    found = sorted({*judged.ideas_found, *ideas})
    return judged.model_copy(
        update={
            "ideas_found": found,
            "score": len(found) / judged.ideas_total,
            "label_source": "LLM",
            "label_confidence": confidence,
            "model_ideas": ideas,
            "quotes": quotes,
        }
    )
