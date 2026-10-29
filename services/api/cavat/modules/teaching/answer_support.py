"""Meaning-based check for answers, separate from the old bridge's lexical contract (DI-86).

A second gateway call checks the entire answer against the source. Exact quotes prevent fabricated
citations; they do not themselves prove entailment. Arithmetic and the classroom boundaries stay in code.
"""

import json
from collections.abc import Sequence
from typing import Any

from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest
from cavat.modules.tutor.prompt_builder import _prompt_file, clean_text

SUPPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "quotes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["supported", "quotes"],
    "additionalProperties": False,
}


def support_request(message: str, sources: Sequence[str], question: str) -> ChatRequest:
    return ChatRequest(
        messages=(
            ChatMessage(
                "system",
                (_prompt_file("answer-support.v2.md")),
            ),
            ChatMessage(
                "user",
                json.dumps(
                    {
                        "nguon": [clean_text(s, 1200) for s in sources],
                        "cau_hoi": clean_text(question, 300),
                        "cau_tra_loi": clean_text(message, 600),
                    },
                    ensure_ascii=False,
                ),
            ),
        ),
        json_schema=SUPPORT_SCHEMA,
        schema_name="answer_support_v1",
        max_output_tokens=600,
        temperature=0.0,
    )


def supported(data: dict | None, sources: Sequence[str]) -> bool:
    if not data or data.get("supported") is not True:
        return False
    quotes = data.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return False
    # Whitespace alone may differ; spelling/words must be copied from an actual source.
    originals = [" ".join(s.split()) for s in sources]
    return all(
        isinstance(q, str) and len(q.split()) >= 4 and any(" ".join(q.split()) in s for s in originals)
        for q in quotes
    )
