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
