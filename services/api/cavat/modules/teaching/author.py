"""Author ungraded teaching from learning goals, independently of item/assessment phrasing."""

import json
import re
from dataclasses import replace

from cavat.modules.ai_gateway.base import (
    MAX_PROMPT_TOKENS,
    ChatMessage,
    ChatRequest,
    ModelClass,
    estimate_prompt_tokens,
)
from cavat.modules.teaching.curriculum import CHECK_SCHEMA, verified
from cavat.modules.teaching.decimal_facts import fraction_facts, notation_facts
from cavat.modules.tutor import brain
from cavat.modules.tutor.prompt_builder import TUTOR_OUTPUT_SCHEMA, _prompt_file, clean_text
from cavat.modules.tutor.validator import (
    INTELLIGENCE_PRAISE_PATTERNS,
    PII_PATTERNS,
    foreign_text,
    wrong_address,
)


def _bounded_request(system, case, schema, name, *, temperature=0):
    """Keep the actual task, student words and complete proposed speech; shed old context first."""
    case = {
        **case,
        "lich_su": list(case.get("lich_su", [])),
        "kien_thuc_tham_khao": list(case.get("kien_thuc_tham_khao", [])),
    }
    while True:
        request = ChatRequest(
            messages=(
                ChatMessage("system", _prompt_file(system)),
                ChatMessage("user", json.dumps(case, ensure_ascii=False)),
            ),
            json_schema=schema,
            schema_name=name,
            max_output_tokens=600,
            temperature=temperature,
        )
        if estimate_prompt_tokens(request) <= MAX_PROMPT_TOKENS:
            return request
        if len(case["lich_su"]) > 2:
            case["lich_su"].pop(0)
        elif len(case["kien_thuc_tham_khao"]) > 1:
            case["kien_thuc_tham_khao"].pop()
        elif case["lich_su"]:
            case["lich_su"].pop(0)
        else:
            # Fixed fields are bounded by the caller; never truncate the speech being verified.
            return request


def write_lesson(router, pack, *, calls_used, questions, session_entry=False):
    """At most two drafts; a verified mentor draft is delivered without a weaker mandatory rewrite."""
    used, rejected, flagged = 0, [], False
    try:
        chain = getattr(router, "chain", None)
        mentor = bool(chain and chain(ModelClass.TUTOR_MENTOR))
    except KeyError:
        mentor = False
    role = ModelClass.TUTOR_MENTOR if mentor and pack.prefer_mentor else ModelClass.TUTOR_REASONING
    case = {
        "bai_dang_hoc": clean_text(pack.lesson, 300),
        "muc_tieu_va_viec_can_lam": clean_text(pack.task, 1300),
        "y_dang_trao_doi": clean_text(pack.question, 500),
        "kien_thuc_tham_khao": [clean_text(s, 650) for s in pack.grounds[:2]],
        "lich_su": [{"vai": t.role, "loi": clean_text(t.text, 600)} for t in pack.recent[-6:]],
        "con_vua_noi": clean_text(pack.student_text, 400),
        "cach_xung_ho": {"co": pack.tutor_self, "con": pack.student_address},
        "do_dai_toi_da": pack.max_words,
        "cau_hoi": questions,
        "can_quay_lai_bai": pack.return_to_lesson,
        "mo_buoi": session_entry,
    }
    schema = TUTOR_OUTPUT_SCHEMA
    review_schema = CHECK_SCHEMA
    if session_entry:
        schema = {
            **TUTOR_OUTPUT_SCHEMA,
            "properties": {
                **TUTOR_OUTPUT_SCHEMA["properties"],
                "knowledge_recall": {"type": "string"},
                "practice_plan": {"type": "string"},
            },
            "required": [*TUTOR_OUTPUT_SCHEMA["required"], "knowledge_recall", "practice_plan"],
        }
        review_schema = {
            **CHECK_SCHEMA,
            "properties": {
                **CHECK_SCHEMA["properties"],
                "recall_explains_knowledge": {"type": "boolean"},
                "plan_names_practice": {"type": "boolean"},
            },
            "required": [*CHECK_SCHEMA["required"], "recall_explains_knowledge", "plan_names_practice"],
        }
    drafts = 0
    while drafts < 2:
        request = _bounded_request(
            "lesson-teacher.v3.md",
            {**case, "can_sua": rejected[-1] if rejected else []},
            schema,
            "lesson_teacher_v1",
            temperature=0.5,
        )
        out = router.chat(role, request, calls_used=calls_used + used)
        used += out.calls_made
        if out.result is None:
            rejected.append((f"SERVICE_UNAVAILABLE:{out.fallback_reason}",))
            if role == ModelClass.TUTOR_MENTOR:
                role = ModelClass.TUTOR_REASONING
                continue
            break
        drafts += 1
        text, safety, feedback = brain.fields_of(out.result.data)
        recall = plan = ""
        if session_entry:
            data = out.result.data or {}
            recall = data.get("knowledge_recall", "")
            plan = data.get("practice_plan", "")
            recall = recall.strip() if isinstance(recall, str) else ""
            plan = plan.strip() if isinstance(plan, str) else ""
            text = " ".join(part for part in (recall, plan, text) if part)
        flagged |= safety
        # The conversational word target is stylistic, not an answer/intent gate.
        # Keep a hard ceiling, let the reviewer judge age-appropriate clarity and concision.
        checked_pack = replace(pack, max_words=max(120, pack.max_words * 2))
        codes = list(brain.speech_codes(text, checked_pack, flexible=True, rephrase=True, copy_run=14))
        if not text:
            codes.append("EMPTY")
        if session_entry and (not recall or not plan):
            codes.append(
                "MISSING_ORIENTATION: cần knowledge_recall là ý lý thuyết, practice_plan là nội dung ôn"
            )
        if safety:
            codes.append("SAFETY")
        if foreign_text(text) or wrong_address(text, pack.student_address):
            codes.append("WRONG_ADDRESS")
        if any(re.search(p, text, re.I) for p in PII_PATTERNS + INTELLIGENCE_PRAISE_PATTERNS):
            codes.append("UNSAFE_LANGUAGE")
        count = text.count("?")
        if (
            count > 1
            or (questions == "required" and (count != 1 or not text.endswith("?")))
            or (questions == "none" and count)
        ):
            codes.append("QUESTION_COUNT")
        if questions == "none" and re.search(r"con (?:hãy|thử)|hãy (?:thử|đếm|viết|tính)", text):
            codes.append("HAS_QUESTION")
        if not codes:
            review = _bounded_request(
                "lesson-review.v3.md",
                {
                    **case,
                    "loi_de_xuat": text,
                    "kiem_chung_so": notation_facts(text),
                    "kiem_chung_so_phan": fraction_facts(text),
                    "knowledge_recall": recall,
                    "practice_plan": plan,
                },
                review_schema,
                "lesson_review_v1",
            )
            checked = router.chat(ModelClass.EVAL_JUDGE, review, calls_used=calls_used + used)
            used += checked.calls_made
            if checked.result is None:
                rejected.append((f"SERVICE_UNAVAILABLE:{checked.fallback_reason}",))
                break  # Another draft cannot fix an unavailable reviewer; preserve quota.
            data = checked.result.data if checked.result else None
            if (
                verified(data)
                and data.get("needs_pedagogy_support") is not True
                and (
                    not session_entry
                    or (
                        data.get("recall_explains_knowledge") is True
                        and data.get("plan_names_practice") is True
                    )
                )
            ):
                return brain.BrainOutcome(
                    text, used, tuple(rejected), flagged, model=out.result.model, feedback=feedback
                )
            codes.append("REVIEW_FAILED")
            if data:
                codes.append(clean_text(str(data.get("reason", "")), 350))
        rejected.append(tuple(codes))
        role = ModelClass.TUTOR_REASONING
    return brain.BrainOutcome(None, used, tuple(rejected), flagged, "lesson_unavailable")
