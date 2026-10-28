"""Semantic listening before lossful intent expansion; it never grades or solves a task (DI-91)."""

from __future__ import annotations

import json
from collections.abc import Sequence

from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ModelClass
from cavat.modules.tutor.prompt_builder import Turn, _prompt_file, clean_text

DIALOGUE_LABELS = ("AMBIGUOUS_REPLY", "REPAIR", "DECLINE", "CONTINUE", "PASS")
SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": list(DIALOGUE_LABELS)},
        "focus": {"type": "string"},
        "answer": {"type": "string"},
    },
    "required": ["label", "focus", "answer"],
    "additionalProperties": False,
}


def listen(model, *, stem: str, last_tutor: str, said: str, recent: Sequence[Turn], phase: str):
    """A reading of raw language, no expected answer or grading authority is supplied."""
    from cavat.modules.tutor.reader import Reading

    request = ChatRequest(
        messages=(
            ChatMessage("system", _prompt_file("listener.v4.md")),
            ChatMessage(
                "user",
                json.dumps(
                    {
                        "de_bai": clean_text(stem, 600),
                        "co_vua_noi": clean_text(last_tutor, 700),
                        "dang_cho": phase,
                        "hoi_thoai": [{"vai": t.role, "loi": clean_text(t.text, 400)} for t in recent[-6:]],
                        "con_vua_noi": clean_text(said, 500),
                    },
                    ensure_ascii=False,
                ),
            ),
        ),
        json_schema=SCHEMA,
        schema_name="dialogue_listen_v4",
        max_output_tokens=400,
        temperature=0,
    )
    out = model.router.chat(
        ModelClass.TUTOR_REASONING, request, calls_used=model.calls_used + model.calls_made
    )
    model.calls_made += out.calls_made
    data = out.result.data if out.result is not None else None
    if not data or data.get("label") not in DIALOGUE_LABELS:
        return None
    return Reading(
        data["label"],
        focus=clean_text(str(data.get("focus", "")), 300),
        answer=clean_text(str(data.get("answer", "")), 80),
        source="LLM",
    )


def conversation_signal(said: str, last_tutor: str):
    """Unambiguous discourse acts, never mathematical evidence or a proposed answer."""
    from cavat.core.vi_text import fold, normalize
    from cavat.modules.tutor.reader import Reading

    normalized = normalize(said)
    words = fold(normalized)
    previous = fold(normalize(last_tutor))
    if words in {"ha", "chua hieu", "con chua hieu"} or said.strip() == "?":
        return Reading("REPAIR", focus="giải thích lại ý cô vừa nói bằng một bước đơn giản hơn")
    if (
        words in {"phai", "dung", "dung roi", "vang", "u"}
        and any(phrase in previous for phrase in ("chua hieu", "chua ro"))
        and previous.endswith(("phai khong", "dung khong"))
        and "?" in last_tutor
    ):
        return Reading("REPAIR", focus="con xác nhận chưa hiểu; giảng ngay chỗ vừa hỏi, không hỏi lại")
    if normalized in {"à", "ừ"} or words in {
        "ok",
        "okok",
        "okay",
        "uh",
        "vang",
        "a ok",
        "a okok",
        "roi",
        "lam tiep",
        "tiep tuc",
        "hieu roi",
        "con hieu roi",
        "ra la vay a",
        "vay a",
    }:
        return Reading("CONTINUE", focus="tiếp nhận lời cô; trở lại câu đang chờ, chưa là bằng chứng hiểu")
    return None
