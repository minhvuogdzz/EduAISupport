"""CFG-3: what the model calls of real sessions cost, read back from their events (`make model-usage`).

The numbers come from ``MODEL_CALLED`` and ``MODEL_FALLBACK`` (ADR-032): the model that wrote, the tokens the
provider counted, which limit a 429 named (ITPM: input tokens per minute; TPD: per day; RPM, RPD) and what
the gateway estimated before sending. Nothing here writes; a session without these events (written before
CFG-2) counts as having made no call.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

# Tokens a day Groq gives the tutor model on the free plan (the Limits page of the console, 2026-10-25).
QWEN_TOKENS_PER_DAY = 200_000


def session_usage(doc: Mapping[str, Any]) -> dict[str, Any]:
    events = doc.get("events", [])
    calls = [e["payload"] for e in events if e["event_type"] == "MODEL_CALLED"]
    moved = [e["payload"] for e in events if e["event_type"] == "MODEL_FALLBACK"]
    answered = [c for c in calls if c.get("model")]
    attempts = [a for c in calls for a in c.get("attempts", [])]
    quota = [a for a in attempts if a.get("error") == "QuotaExceeded"]
    counted = [c for c in answered if c.get("prompt_tokens")]
    prompt = sum(c["prompt_tokens"] for c in answered)
    state = doc.get("state") or {}
    return {
        "session_id": doc.get("_id") or doc.get("id"),
        "student": doc.get("student_display_name"),
        "chapter": doc.get("lesson_id"),
        "lifecycle": state.get("lifecycle"),
        "created_at": doc.get("created_at"),
        "calls": len(calls),
        "answered": len(answered),
        "unanswered": dict(Counter(c.get("fallback_reason") for c in calls if not c.get("model"))),
        "by_model": dict(Counter(c["model"] for c in answered)),
        "by_purpose": dict(Counter(c["purpose"] for c in calls)),
        "prompt_tokens": prompt,
        "completion_tokens": sum(c["completion_tokens"] for c in answered),
        "tokens_by_model": _tokens_by_model(answered),
        "refused": dict(Counter(a.get("limit") or "?" for a in quota if a.get("sent"))),  # 429 Groq sent back
        "skipped": sum(1 for a in quota if not a.get("sent")),  # not sent: the model was known out of quota
        "fallbacks": dict(Counter(f"{m['from_model']} -> {m['to_model']} ({m['reason']})" for m in moved)),
        "longest_wait_s": max(
            (a["retry_after_s"] for a in quota if a.get("retry_after_s") is not None), default=None
        ),
        "chars_per_token": _ratio(
            sum(c["prompt_chars"] for c in counted), sum(c["prompt_tokens"] for c in counted)
        ),
        "estimate_over_real": _ratio(
            sum(c["estimated_tokens"] for c in counted), sum(c["prompt_tokens"] for c in counted)
        ),
    }


def _ratio(top: float, bottom: float) -> float | None:
    return round(top / bottom, 2) if bottom else None


def _tokens_by_model(answered: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    out: Counter[str] = Counter()
    for c in answered:
        out[c["model"]] += c["prompt_tokens"] + c["completion_tokens"]
    return dict(out)


def summarize(docs: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    sessions = sorted((session_usage(d) for d in docs), key=lambda s: str(s["created_at"]))
    total: dict[str, Any] = {"sessions": len(sessions)}
    for key in ("calls", "answered", "prompt_tokens", "completion_tokens", "skipped"):
        total[key] = sum(s[key] for s in sessions)
    for key in ("by_model", "tokens_by_model", "refused", "fallbacks", "unanswered"):
        merged: Counter[str] = Counter()
        for s in sessions:
            merged.update(s[key])
        total[key] = dict(merged)
    qwen_sessions = [s for s in sessions if any("qwen" in m for m in s["tokens_by_model"])]
    qwen_tokens = sum(t for s in qwen_sessions for m, t in s["tokens_by_model"].items() if "qwen" in m)
    total["qwen_tokens_per_session"] = round(qwen_tokens / len(qwen_sessions)) if qwen_sessions else None
    total["sessions_per_day"] = (
        round(QWEN_TOKENS_PER_DAY / total["qwen_tokens_per_session"])
        if total["qwen_tokens_per_session"]
        else None
    )
    return {"sessions": sessions, "total": total}


def render(summary: Mapping[str, Any]) -> str:
    lines: list[str] = []
    for s in summary["sessions"]:
        when = (
            s["created_at"].strftime("%d/%m %H:%M")
            if isinstance(s["created_at"], datetime)
            else s["created_at"]
        )
        lines.append(
            f"Buổi {s['session_id']} · {s['student'] or '?'} · {s['chapter']} · {s['lifecycle']} · {when}"
        )
        if not s["calls"]:
            lines.append("  không gọi model nào (câu mẫu, hoặc buổi học trước CFG-2)")
            continue
        lines.append(
            f"  {s['calls']} lần gọi, {s['answered']} được trả lời;"
            f" token {s['prompt_tokens']} + {s['completion_tokens']}"
            f" (vào + ra); model: {_pairs(s['by_model'])}"
        )
        lines.append(f"  mục đích: {_pairs(s['by_purpose'])}")
        if s["refused"] or s["skipped"] or s["unanswered"]:
            lines.append(
                f"  hạn mức: Groq trả 429 {sum(s['refused'].values())} lần ({_pairs(s['refused'])}),"
                f" bỏ qua {s['skipped']} lần gửi vì đã biết hết; {sum(s['unanswered'].values())} lần gọi"
                f" không model nào trả lời; chờ lâu nhất {s['longest_wait_s']}s"
            )
        if s["fallbacks"]:
            lines.append(f"  xuống chuỗi: {_pairs(s['fallbacks'])}")
        if s["chars_per_token"]:
            lines.append(
                f"  ký tự mỗi token thật {s['chars_per_token']}; ước lượng / thật {s['estimate_over_real']}"
            )
    t = summary["total"]
    lines += ["", f"Tổng {t['sessions']} buổi: {t['calls']} lần gọi, {t['answered']} được trả lời"]
    lines.append(
        f"  token vào {t['prompt_tokens']}, ra {t['completion_tokens']};"
        f" theo model: {_pairs(t['tokens_by_model'])}"
    )
    if t["refused"] or t["unanswered"]:
        lines.append(
            f"  429 của Groq: {_pairs(t['refused'])}; không model nào trả lời: {_pairs(t['unanswered'])}"
        )
    if t["fallbacks"]:
        lines.append(f"  xuống chuỗi: {_pairs(t['fallbacks'])}")
    if t["qwen_tokens_per_session"]:
        lines.append(
            f"  Qwen tốn trung bình {t['qwen_tokens_per_session']} token mỗi buổi:"
            f" {QWEN_TOKENS_PER_DAY} token mỗi ngày đủ cho khoảng {t['sessions_per_day']} buổi như vậy"
        )
    return "\n".join(lines)


def _pairs(counts: Mapping[str, Any]) -> str:
    return (
        ", ".join(
            f"{k} ×{v}" if isinstance(v, int) and not isinstance(v, bool) else f"{k}: {v}"
            for k, v in counts.items()
        )
        or "—"
    )


async def load(
    database: Any, school_id: str, *, since: datetime | None = None, session_id: str | None = None
) -> list[dict[str, Any]]:
    """The sessions to report on: one by id, or those updated since ``since``. Reads only."""
    flt: dict[str, Any] = {"school_id": school_id}
    if session_id:
        flt["_id"] = session_id
    elif since is not None:
        flt["updated_at"] = {"$gte": since}
    return await database["learning_sessions"].find(flt).to_list(None)
