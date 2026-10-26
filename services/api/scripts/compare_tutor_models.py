"""Compare the models that can write the tutor's words, on real hard turns (BRAIN-1, ADR-034, `make
compare-models`).

The owner allowed models other than Qwen to speak (2026-10-26). Before the default order is set,
this puts the SAME prompt to each model and writes the answers side by side with the automatic
checks of the net (leak, one question, length, address, wrong arithmetic, praise of a wrong answer,
a question that does not name the child's answer, a ground read out as it stands...), so the owner
can read them and choose.

The cases are real: the sessions of ``cavat_dev`` (read only, nothing is written there) are replayed
through the item loop with the template renderer to get the exact context of each tutor turn (the
child's words, the checker's verdict, the move the policy chose); the hardest turns are picked (the
first "vì sao", the child who cannot say why, "là sao", a wrong answer...), and the turns of the
teaching loop where a child did not get a theory question are added. A report holds the ids of items
and nodes, never the text of the teacher's documents; it holds the children's own words, so it stays
in ``evals/reports/`` (gitignored).

Free quota: each model is asked once per case (no retry), a few seconds apart for Groq (8.000 token
a minute); a model that answers 429 is noted as out of quota and skipped, never waited for.

    PYTHONPATH=. python scripts/compare_tutor_models.py --cases 16 \
        --models qwen/qwen3.8-27b openai/gpt-oss-120b ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from cavat import db
from cavat.config import get_settings
from cavat.core.pedagogy import ActivityType, Move
from cavat.core.repository import utc_now
from cavat.modules.ai_gateway.base import AIGatewayError, ModelClass
from cavat.modules.ai_gateway.gemini import GeminiChat
from cavat.modules.ai_gateway.groq import GroqClient
from cavat.modules.ai_gateway.router import AIRouter, ChatDispatcher
from cavat.modules.session import chapter_service, model_usage
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.tutor import brain
from cavat.modules.tutor.brain import BrainPack, estimate_prompt_tokens  # noqa: F401
from cavat.modules.tutor.contracts import RenderContext
from cavat.modules.tutor.item_loop import HINT_REQUEST_TEXT, ItemTutor
from cavat.modules.tutor.llm_renderer import LLMRenderer, _template_only
from cavat.modules.tutor.prompt_builder import Turn
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

REPORT = Path(__file__).resolve().parents[3] / "evals" / "reports"
THEORY_CUES = re.compile(r"là sao|như nào|là gì|hả|ko|không biết|chưa hiểu|khó", re.I)
PACE_S = {"groq": 20.0, "gemini": 6.0}  # Groq: 8.000 token a minute, a pack is about 2.500


@dataclass
class Case:
    label: str
    kind: str  # "item" | "teach"
    ref: str  # item id or node:variant, never the teacher's text
    move: str
    said: str
    pack: BrainPack
    check: object  # str -> tuple[str, ...]
    context: str = ""


@dataclass
class Answer:
    text: str = ""
    codes: tuple[str, ...] = ()
    words: int = 0
    seconds: float = 0.0
    tokens: int = 0
    error: str = ""


@dataclass
class Capture:
    """The renderer of the replay: says the template and keeps the context of each turn."""

    template: TemplateRenderer = field(default_factory=TemplateRenderer)
    seen: list[tuple[RenderContext, list[Turn], str]] = field(default_factory=list)
    history: list[Turn] = field(default_factory=list)

    def render(self, ctx: RenderContext):
        message = self.template.render(ctx)
        self.seen.append((ctx, list(self.history), message.text))
        if ctx.student_text:
            self.history.append(Turn("student", ctx.student_text))
        self.history.append(Turn("tutor", message.text))
        return message


def load_docs(days: float) -> list[dict]:
    async def read() -> list[dict]:
        database = db.get_db(get_settings())
        try:
            await chapter_service.load_published(database, DEMO_SCHOOL_ID)  # the plans the sessions ran on
            return await model_usage.load(database, DEMO_SCHOOL_ID, since=utc_now() - timedelta(days=days))
        finally:
            await db.close_client()

    return asyncio.run(read())


def item_runs(doc: dict) -> list[tuple[str, str, list[str]]]:
    """(item id, activity, the child's messages) for each item of a session, in order."""
    runs: list[tuple[str, str, list[str]]] = []
    for e in doc.get("events", []):
        p = e.get("payload") or {}
        if e["event_type"] == "QUESTION_SHOWN":
            runs.append((p["item_id"], p.get("activity_type", "GUIDED_PRACTICE"), []))
        elif e["event_type"] == "STUDENT_MESSAGE" and runs and p.get("item_id") == runs[-1][0]:
            runs[-1][2].append(p.get("text", ""))
        elif e["event_type"] == "HINT_REQUESTED" and runs:
            runs[-1][2].append(HINT_REQUEST_TEXT)
    return runs


PRIORITY = {
    Move.VERIFY: 0,
    Move.CLOSE_ITEM: 0,
    Move.CONFIRM_ADVANCE: 1,
    Move.EXPLAIN: 1,
    Move.HINT: 2,
    Move.COGNITIVE_CONFLICT: 2,
    Move.WORKED_GUIDANCE: 2,
    Move.PROBE: 3,
    Move.OFFER_CHOICE: 3,
}


def item_cases(docs: list[dict], limit: int, pin: tuple[str, ...] = ()) -> list[Case]:
    found: list[tuple[int, Case]] = []
    for doc in docs:
        chapter = chapter_service.chapter_for(doc.get("lesson_id"), doc.get("lesson_version"))
        if chapter is None:
            continue
        for item_id, activity, texts in item_runs(doc):
            try:
                item = chapter.item(item_id)
            except Exception:
                continue
            if item.is_assessment or not texts:
                continue
            cap = Capture()
            tutor = ItemTutor(
                item,
                chapter.lesson_of(item_id),
                ActivityType(activity),
                cap,
                validate_message,
                first_on_kc=True,
            )
            tutor.start()
            for text in texts:
                if tutor.phase.name == "RESOLVED":
                    break
                tutor.on_student(text)
            for ctx, history, _ in cap.seen:
                if _template_only(ctx) or ctx.decision.move not in PRIORITY:
                    continue
                renderer = LLMRenderer(None, TemplateRenderer(), validate_message)  # type: ignore[arg-type]
                renderer._history, renderer._history_item = list(history), item_id
                fallback = TemplateRenderer().render(ctx)
                pack = renderer._pack(ctx, fallback)
                said = ctx.student_text or ""
                score = PRIORITY[ctx.decision.move] * 10 + (0 if said else 5)
                if pin and doc["_id"].startswith(tuple(pin)):
                    score = -100  # the session of the owner's three faults comes first
                found.append(
                    (
                        score,
                        Case(
                            label=f"{doc['_id'][:8]}/{item_id}/{ctx.decision.move.value}",
                            kind="item",
                            ref=item_id,
                            move=ctx.decision.move.value,
                            said=said,
                            pack=pack,
                            check=lambda t, r=renderer, c=ctx, p=pack: r._codes(t, c, p),
                            context=", ".join(ctx.decision.reason_codes),
                        ),
                    )
                )
    found.sort(key=lambda x: x[0])
    out: list[Case] = []
    per_move: Counter[str] = Counter()
    for _, case in found:
        if per_move[case.move] >= max(2, limit // 5) and not case.label.startswith(tuple(pin) or ("\0",)):
            continue
        per_move[case.move] += 1
        out.append(case)
        if len(out) >= limit:
            break
    return out


OLD_LLM_MOVES = frozenset(
    {
        Move.PROBE, Move.HINT, Move.COGNITIVE_CONFLICT, Move.NUDGE, Move.REDIRECT, Move.EXPLAIN,
        Move.ASK_CONFIRM, Move.WORKED_GUIDANCE, Move.TEACH_BACK, Move.VERIFY, Move.CONFIRM_ADVANCE,
        Move.OFFER_CHOICE,
    }
)  # fmt: skip


def old_template_only(ctx: RenderContext) -> bool:
    """llm-renderer.v8: which turns of an item were the model's to word (see its ``_template_only``)."""
    move = ctx.decision.move
    if ctx.item.is_assessment or move not in OLD_LLM_MOVES:
        return True
    if move == Move.ASK_CONFIRM and {"TYPO", "GIBBERISH"}.intersection(ctx.decision.reason_codes):
        return True
    if move == Move.CONFIRM_ADVANCE and not (ctx.student_text or "").strip():
        return True
    return move == Move.VERIFY and "ASK_AGAIN" not in ctx.decision.reason_codes


def coverage(docs: list[dict]) -> str:
    """Of the item turns of the real sessions replayed, how many the model may write: before and after."""
    total = old = new = 0
    for doc in docs:
        chapter = chapter_service.chapter_for(doc.get("lesson_id"), doc.get("lesson_version"))
        if chapter is None:
            continue
        for item_id, activity, texts in item_runs(doc):
            try:
                item = chapter.item(item_id)
            except Exception:
                continue
            cap = Capture()
            tutor = ItemTutor(
                item,
                chapter.lesson_of(item_id),
                ActivityType(activity),
                cap,
                validate_message,
                first_on_kc=True,
            )
            tutor.start()
            for text in texts:
                if tutor.phase.name == "RESOLVED":
                    break
                tutor.on_student(text)
            for ctx, _, _ in cap.seen:
                total += 1
                old += not old_template_only(ctx)
                new += not _template_only(ctx)
    stored = Counter(
        (e.get("payload") or {}).get("source")
        for d in docs
        for e in d.get("events", [])
        if e["event_type"] == "TUTOR_MESSAGE_SENT"
    )
    return (
        f"{total} lượt gia sư của các câu, dựng lại từ lời con: model được phép viết "
        f"{old} ({old / max(total, 1):.0%}) với v8, {new} ({new / max(total, 1):.0%}) với v9. "
        f"Nguồn đã lưu của {sum(stored.values())} lượt thật (v8): {dict(stored)}."
    )


def teach_cases(docs: list[dict], limit: int, pin: tuple[str, ...] = ()) -> list[Case]:
    """Turns of the teaching loop: what the child says in a wait (not understood, off topic, another
    question), and the tutor's own theory and invitation to say it back, each with the net of ``grounded``."""
    from cavat.core.pedagogy import Outcome
    from cavat.modules.assessment.math_checker import classify_intent
    from cavat.modules.assessment.student_intent import wants_other_question
    from cavat.modules.teaching import grounded as g

    docs = sorted(docs, key=lambda d: not d["_id"].startswith(pin or ("\0",)))
    out: list[Case] = []
    seen: set[str] = set()
    for doc in docs:
        chapter = chapter_service.chapter_for(doc.get("lesson_id"), doc.get("lesson_version"))
        if chapter is None:
            continue
        events = doc.get("events", [])
        for i, e in enumerate(events):
            p = e.get("payload") or {}
            if e["event_type"] == "TEACH_MESSAGE_SENT":
                node_id, ref = p.get("node_id") or "", p.get("ref") or ""
                node_ref = f"{node_id}:{ref}"
            else:
                node_ref = p.get("item_id", "")
                if ":" not in node_ref:
                    continue
                node_id, ref = node_ref.split(":", 1)
            try:
                node = chapter.node(node_id)
            except Exception:
                continue
            recent = [
                (
                    "tutor" if x["event_type"] == "TEACH_MESSAGE_SENT" else "student",
                    (x.get("payload") or {}).get("text", ""),
                )
                for x in events[max(0, i - 6) : i]
                if x["event_type"] in ("TEACH_MESSAGE_SENT", "STUDENT_MESSAGE")
            ][-4:]
            who = {"tutor_self": "cô", "student_address": "con", "name": doc.get("student_display_name")}
            label = f"{doc['_id'][:8]}/{node_ref}"
            if e["event_type"] == "STUDENT_MESSAGE" and p.get("kind") in ("MESSAGE", "EXPLANATION"):
                text = p.get("text", "")
                variant = next((t for t in node.theory if t.id == ref), None)
                asked = variant.ask if variant else node.explain.prompt
                if wants_other_question(text):
                    kind, (pack, check) = (
                        "another",
                        g.another_request(text, asked=asked, node_name=node.name, recent=recent, **who),
                    )
                elif classify_intent(text) == Outcome.OFF_TOPIC:
                    kind, (pack, check) = "chat", g.chat_request(text, asked=asked, recent=recent, **who)
                elif THEORY_CUES.search(text) or ref == "RETELL":
                    ground = variant.reply if variant else node.method.rule
                    pack = g.teach_pack(
                        text,
                        asked=asked,
                        ground=ground,
                        judged="chưa rõ",
                        recent=recent,
                        rule=node.method.rule,
                        name=who["name"],
                    )
                    check = lambda t, pk=pack: g.teach_codes(t, pk, "chưa rõ")  # noqa: E731
                    kind = "teach"
                else:
                    continue
                key = f"{kind}/{text[:20]}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(Case(f"{label}/{kind}", "teach", node_ref, kind.upper(), text, pack, check))
            elif (
                e["event_type"] == "TEACH_MESSAGE_SENT"
                and p.get("kind") in ("THEORY", "RETELL_PROMPT")
                and doc["_id"].startswith(pin or ("\0",))
            ):
                kind = "lecture" if p["kind"] == "THEORY" else "invite"
                if f"{kind}/{node_id}" in seen:
                    continue
                seen.add(f"{kind}/{node_id}")
                if kind == "lecture":
                    variant = next((t for t in node.theory if t.id == p.get("ref")), None)
                    if variant is None:
                        continue
                    pack, check = g.lecture_request(
                        variant.text,
                        ask=variant.ask,
                        node_name=node.name,
                        rule=node.method.rule,
                        recent=recent,
                        **who,
                    )
                else:
                    pack, check = g.invite_request(node, prompt=node.explain.prompt, recent=recent, **who)
                out.append(Case(f"{label}/{kind}", "teach", node_ref, kind.upper(), "", pack, check))
        if len(out) >= limit:
            break
    return out[:limit]


def router_for(model: str, settings) -> AIRouter:
    groq = GroqClient(settings.groq_api_key) if settings.groq_api_key else None
    gemini = GeminiChat(settings.gemini_api_key) if settings.gemini_api_key else None
    return AIRouter(
        chat_provider=ChatDispatcher(groq, gemini),
        chains={ModelClass.TUTOR_REASONING: (model,)},
        max_calls_per_session=10_000,
    )


def flush(model: str, answers: list[Answer]) -> None:
    """Keep what a model has answered so far: a run that is stopped loses nothing."""
    name = re.sub(r"[^\w.-]", "_", model)
    (REPORT / f"BRAIN-1-partial-{name}.json").write_text(
        json.dumps([a.__dict__ for a in answers], ensure_ascii=False, indent=1), encoding="utf-8"
    )


def run_model(model: str, cases: list[Case], settings) -> list[Answer]:
    router = router_for(model, settings)
    vendor = "gemini" if model.startswith("gemini") else "groq"
    answers: list[Answer] = []
    dead = ""
    for case in cases:
        if dead:
            answers.append(Answer(error=dead))
            continue
        started = time.monotonic()
        try:
            outcome = router.chat(ModelClass.TUTOR_REASONING, brain.build_request(case.pack), calls_used=0)
        except AIGatewayError as exc:
            outcome, dead = None, f"lỗi: {type(exc).__name__}"
        if outcome is None or outcome.result is None:
            reason = dead or (outcome.fallback_reason.value if outcome and outcome.fallback_reason else "?")
            if outcome is not None and outcome.attempts:
                last = outcome.attempts[-1]
                reason = f"{last.error} {last.limit or ''} {last.detail[:80]}".strip()
            if "Quota" in reason:
                dead = f"hết hạn mức ({reason})"
            answers.append(Answer(error=reason, seconds=time.monotonic() - started))
        else:
            text, _, _ = brain.fields_of(outcome.result.data)
            codes = tuple(case.check(text)) if text else ("EMPTY",)
            usage = outcome.result.usage
            answers.append(
                Answer(
                    text,
                    codes,
                    len(text.split()),
                    time.monotonic() - started,
                    usage.prompt_tokens + usage.completion_tokens,
                )
            )
        flush(model, answers)
        time.sleep(PACE_S[vendor])
    return answers


def render_report(models: list[str], cases: list[Case], results: dict[str, list[Answer]], days: float) -> str:
    lines = [
        "# BRAIN-1: so sánh model viết lời gia sư",
        "",
        f"{len(cases)} lượt thật (đọc từ `cavat_dev`, {days:g} ngày gần nhất, chỉ đọc), cùng một prompt "
        "(`constitution.v6` + gói ngữ cảnh), mỗi model một lần, không thử lại. Kiểm tự động: "
        "`ANSWER_LEAK` lộ đáp án, `MULTIPLE_QUESTIONS`/`MISSING_QUESTION` số câu hỏi, `TOO_LONG` dài, "
        "`WRONG_ADDRESS` xưng hô, `WRONG_MATH` phép tính sai, `WRONG_PRAISE` khen khi chưa đúng, "
        "`OFF_TARGET` câu hỏi không nhắc đáp án của con, `COPIES_GROUND` đọc nguyên văn căn cứ, "
        "`REPEATS_PREVIOUS` lặp lời cô.",
        "",
        "## Tổng hợp",
        "",
        "| Model | Có lời | Qua bộ kiểm | Số từ TB | Token TB | Giây TB | Mã bác nhiều nhất | Ghi chú |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for model in models:
        answered = [a for a in results[model] if a.text]
        passed = [a for a in answered if not a.codes]
        codes = Counter(c for a in answered for c in a.codes)
        notes = {a.error for a in results[model] if a.error}
        avg = lambda xs: f"{sum(xs) / len(xs):.0f}" if xs else "-"  # noqa: E731
        lines.append(
            f"| `{model}` | {len(answered)}/{len(cases)} | {len(passed)}/{len(cases)} | "
            f"{avg([a.words for a in answered])} | {avg([a.tokens for a in answered])} | "
            f"{avg([a.seconds for a in answered])} | "
            f"{', '.join(f'{c}×{n}' for c, n in codes.most_common(3)) or '-'} | "
            f"{'; '.join(sorted(notes))[:90]} |"
        )
    lines += ["", "## Từng lượt", ""]
    for i, case in enumerate(cases):
        lines += [
            f"### {i + 1}. `{case.label}` ({case.kind}, nước đi {case.move})",
            "",
            f"Con nói: {case.said!r}" + (f" · lý do chính sách: {case.context}" if case.context else ""),
            "",
        ]
        for model in models:
            a = results[model][i]
            flag = "✅" if a.text and not a.codes else ("⚠️ " + ", ".join(a.codes) if a.text else "—")
            body = a.text or f"(không có lời: {a.error})"
            lines.append(f"- **{model}** {flag} ({a.words} từ): {body}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=int, default=24)
    parser.add_argument("--teach", type=int, default=9, help="how many of the cases are teaching-loop turns")
    parser.add_argument("--days", type=float, default=30)
    parser.add_argument(
        "--pin",
        nargs="*",
        default=["01a17468", "01a177d0"],
        help="session id prefixes whose turns come first",
    )
    parser.add_argument("--models", nargs="+", default=[])
    parser.add_argument("--dry", action="store_true", help="only list the cases, call no model")
    parser.add_argument("--out", default=str(REPORT / "BRAIN-1-models.md"))
    args = parser.parse_args()
    settings = get_settings()
    print(f"Database: {settings.mongodb_db} (chỉ đọc)")
    docs = load_docs(args.days)
    cases = item_cases(docs, args.cases - args.teach, tuple(args.pin)) + teach_cases(
        docs, args.teach, tuple(args.pin)
    )
    print(f"{len(docs)} buổi, {len(cases)} lượt:", Counter(c.move for c in cases))
    if not cases:
        sys.exit("Không có lượt nào để so sánh.")
    print(coverage(docs))
    if args.dry or not args.models:
        for c in cases:
            tokens = brain.estimate_prompt_tokens(brain.build_request(c.pack))
            print(f"{c.label:<50} ~{tokens} token | con: {c.said[:50]!r}")
        return
    with ThreadPoolExecutor(max_workers=len(args.models)) as pool:
        futures = {m: pool.submit(run_model, m, cases, settings) for m in args.models}
        results = {m: f.result() for m, f in futures.items()}
    report = (
        render_report(args.models, cases, results, args.days) + "\n## Phạm vi\n\n" + coverage(docs) + "\n"
    )
    Path(args.out).write_text(report, encoding="utf-8")
    Path(args.out).with_suffix(".json").write_text(
        json.dumps({m: [a.__dict__ for a in r] for m, r in results.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"Đã ghi {args.out}")


if __name__ == "__main__":
    main()
