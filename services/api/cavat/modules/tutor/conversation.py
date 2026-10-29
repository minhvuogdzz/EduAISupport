"""Semantic listening before lossful intent expansion; it never grades or solves a task (DI-91)."""

from __future__ import annotations

import json
from collections.abc import Sequence

from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ModelClass
from cavat.modules.tutor.prompt_builder import Turn, _prompt_file, clean_text

DIALOGUE_LABELS = ("AMBIGUOUS_REPLY", "REPAIR", "DECLINE", "CONTINUE", "REACTION", "PASS")
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
    from cavat.modules.assessment.student_intent import expand_short_forms
    from cavat.modules.teaching.conductor import clean
    from cavat.modules.tutor.reader import Reading

    interpreted = expand_short_forms(clean(said).text)
    request = ChatRequest(
        messages=(
            ChatMessage("system", _prompt_file("listener.v6.md")),
            ChatMessage(
                "user",
                json.dumps(
                    {
                        "de_bai": clean_text(stem, 600),
                        "co_vua_noi": clean_text(last_tutor, 700),
                        "dang_cho": phase,
                        "hoi_thoai": [{"vai": t.role, "loi": clean_text(t.text, 400)} for t in recent[-6:]],
                        "con_vua_noi": clean_text(said, 500),
                        "ban_ho_tro_doc_teencode": clean_text(interpreted, 500),
                    },
                    ensure_ascii=False,
                ),
            ),
        ),
        json_schema=SCHEMA,
        schema_name="dialogue_listen_v6",
        max_output_tokens=400,
        temperature=0,
    )
    out = model.router.chat(ModelClass.INTENT_AGENT, request, calls_used=model.calls_used + model.calls_made)
    model.calls_made += out.calls_made
    data = out.result.data if out.result is not None else None
    if out.result is None:
        from cavat.modules.assessment.vi_numbers import extract_numbers

        # A missing listener cannot infer misunderstanding, a refusal, or a failed answer.
        if not extract_numbers(said):
            return Reading(
                "AMBIGUOUS_REPLY",
                focus="chưa đọc chắc ý con; hỏi con nói thêm, không đoán tâm trạng",
                source="RULE",
            )
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
    import re

    from cavat.core.vi_text import fold, normalize
    from cavat.modules.tutor.brain import explanation_only
    from cavat.modules.tutor.reader import Reading

    if re.fullmatch(r"(?:(?:ha|hi|he|hì|hí|hê){2,}|[😂🤣😆😅🙂🙃]+)[! .]*", said.strip().lower()):
        return Reading("REACTION", focus="phản ứng cảm xúc/đùa vui; chưa là đồng ý, chưa có bằng chứng hiểu")
    word_question = re.fullmatch(r"(?:cô ơi )?(\w+) là \1[?!. ]*", said.strip().lower())
    if word_question:
        return Reading(
            "REPAIR", focus=f"giải thích từ «{word_question[1]}» trong câu cô vừa hỏi bằng ví dụ cụ thể"
        )
    if explanation_only(said):
        return Reading(
            "REPAIR",
            focus="giải thích bằng cách khác hoặc làm mẫu một bước, rồi hỏi một bước nhỏ để con thử",
        )
    normalized = normalize(said)
    words = fold(normalized)
    previous = fold(normalize(last_tutor))
    if re.search(r"\b(?:quay lai|tro lai|tap trung)\b.{0,25}\b(?:bai|hoc)\b", words) or (
        "dang hoc" in words and any(cue in words for cue in ("chia se", "chuyen", "noi gi"))
    ):
        return Reading(
            "CONTINUE", focus="con nhắc cô quay lại bài; nhận lỗi lạc đề ngắn rồi đưa về việc học ngay"
        )
    if (
        words
        in {
            "ha",
            "chua hieu",
            "con chua hieu",
            "con van chua hieu",
            "em chua hieu",
            "con khong hieu",
            "em khong hieu",
            "khong hieu",
            "chua hieu lam",
        }
        or said.strip() == "?"
    ):
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
