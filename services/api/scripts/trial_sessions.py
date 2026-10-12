"""Trial sessions on the published teaching plans (``make trial``): scripted learners, offline, read-only.

Reads the plans published in the database of services/api/.env (it writes nothing there: the sessions run
in memory) and lets four scripted learners study each chapter with the template tutor (no model call):

- ``gioi``: answers right, retells with the key ideas;
- ``hay-sai``: answers wrong first, asks for a hint, then answers right;
- ``sai-dang``: answers in the wrong form first (0,475 for "viết phân số thập phân", one value of a list,
  a measure with its unit), wanders off topic once per period;
- ``bi``: says "con không biết" to every first question of an item, then answers right.

For each run it reports whether the chapter ends, how many periods pass, the outcomes of the checker, the
hints given, and any hint the review rejected that still reached the child (must be none).
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from cavat import db
from cavat.config import get_settings
from cavat.core.pedagogy import Outcome
from cavat.modules.assessment.math_checker import check_answer, parse_literal
from cavat.modules.ingest.repository import TeachingPlanRepository
from cavat.modules.session.chapter_service import build_chapter
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.teaching.loop import Awaiting, MessageKind, TeachingLoop
from cavat.modules.tutor.item_loop import Phase

T0 = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
EXPLAINING = (Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON)
LIMIT = 4000


def right_answer(chapter, item_id: str) -> str:
    item = chapter.item(item_id)
    ans = item.answer
    if ans.type == "compare":
        left, right = parse_literal(ans.left).value, parse_literal(ans.right).value
        sign = "<" if left < right else ">" if left > right else "="
        larger, smaller = (ans.left, ans.right) if left > right else (ans.right, ans.left)
        return {"sign": sign, "larger": larger, "smaller": smaller}[ans.ask]
    if ans.type == "order":
        key = lambda n: Fraction(parse_literal(n).value)  # noqa: E731
        return "; ".join(sorted(ans.numbers, key=key, reverse=ans.direction == "desc"))
    if ans.type == "numeric":
        return ans.value
    if ans.type == "choice":
        return next(o.id for o in ans.options if o.correct)
    if ans.type == "boolean":
        return "đúng" if ans.value else "sai"
    return ans.sample_answer


def wrong_form(chapter, item_id: str) -> str | None:
    """The same value in a form the question does not ask, or a part of the answer."""
    ans = chapter.item(item_id).answer
    if ans.type == "numeric" and ans.form == "fraction":
        return str(
            parse_literal(ans.value).value.numerator / parse_literal(ans.value).value.denominator
        ).replace(".", ",")
    if ans.type == "numeric" and ans.form == "decimal":
        value = parse_literal(ans.value).value
        return f"{value.numerator}/{value.denominator}"
    if ans.type == "open" and re.match(r"x = \d+ ;", ans.sample_answer):
        return ans.sample_answer.split(";")[0].strip()
    return None


@dataclass
class Learner:
    style: str
    chapter: object
    seen: set[str] = field(default_factory=set)
    off_topic: set[str] = field(default_factory=set)
    wants_hint: bool = False

    def reply(self, turn) -> str:
        chapter = self.chapter
        if turn.awaiting == Awaiting.THEORY_REPLY:
            node = turn.node_id or ""
            if self.style == "sai-dang" and node not in self.off_topic:
                self.off_topic.add(node)
                return "Cô ơi con thích đá bóng lắm."
            variant = next(
                (t for n in chapter.nodes for t in n.theory if t.ask and t.ask in (turn.prompt or "")), None
            )
            return variant.reply if variant and variant.reply else "Con nghĩ là được ạ."
        if turn.awaiting == Awaiting.RETELL:
            node_id = turn.node_id or next(
                m.node_id for m in reversed(turn.messages) if m.kind == MessageKind.RETELL_PROMPT
            )
            return ". ".join(ideas[0] for ideas in chapter.node(node_id).explain.key_ideas)
        item = chapter.item(turn.item_id)
        if turn.item_phase in EXPLAINING:
            return item.explanation or "Vì con làm theo quy tắc cô dạy."
        first = turn.item_id not in self.seen
        self.seen.add(turn.item_id)
        if first and self.style == "hay-sai":
            self.wants_hint = True
            return "123"
        if first and self.style == "bi":
            return "Con không biết ạ."
        if first and self.style == "sai-dang" and (other := wrong_form(chapter, turn.item_id)):
            return other
        return right_answer(chapter, turn.item_id)


def run(chapter, style: str, rejected: set[str]) -> dict:
    loop = TeachingLoop(chapter, f"trial-{style}")
    learner = Learner(style, chapter)
    turns = [loop.start(T0)]
    outcomes: Counter[str] = Counter()
    hints, leaked, wrong_form_accepted, stuck = 0, [], [], Counter()
    transcript: list[str] = []
    error = None
    try:
        for i in range(LIMIT):
            turn = turns[-1]
            for m in turn.messages:
                transcript.append(f"Gia sư [{m.kind}]: {m.text}")
                if m.kind == MessageKind.ITEM and any(r in m.text for r in rejected):
                    leaked.append(m.text)
            if turn.awaiting == Awaiting.NOTHING:
                break
            now = T0 + timedelta(seconds=15 * (i + 1))
            if learner.wants_hint and turn.awaiting == Awaiting.ANSWER:
                learner.wants_hint = False
                hinted = loop.on_hint_request(now, 10)
                hints += sum(1 for e in hinted.events if e.event_type == "HINT_DELIVERED")
                transcript.append("Bé: [Xin gợi ý]")
                turns.append(hinted)
                continue
            text = learner.reply(turn)
            transcript.append(f"Bé: {text}")
            if turn.awaiting == Awaiting.ANSWER and turn.item_phase not in EXPLAINING:
                result = check_answer(chapter.item(turn.item_id), text, chapter.lesson_of(turn.item_id))
                outcomes[result.outcome.value] += 1
                stuck[turn.item_id] += 1
                if text == wrong_form(chapter, turn.item_id) and result.outcome == Outcome.CORRECT:
                    wrong_form_accepted.append(turn.item_id)
            nxt = loop.on_student(text, now, 10)
            hints += sum(1 for e in nxt.events if e.event_type == "HINT_DELIVERED")
            turns.append(nxt)
    except Exception as exc:  # a trial reports what broke instead of stopping the others
        error = f"{type(exc).__name__}: {exc}"
    projection = loop.projection()
    passed = [n for n, s in projection.nodes.items() if s.passed_at is not None]
    return {
        "style": style,
        "finished": turns[-1].awaiting == Awaiting.NOTHING,
        "turns": len(turns),
        "periods": len(chapter.nodes),
        "passed": len(passed),
        "outcomes": dict(outcomes),
        "hints": hints,
        "rejected_hints_shown": leaked,
        "wrong_form_accepted": wrong_form_accepted,
        "most_tries": stuck.most_common(3),
        "error": error,
        "transcript": transcript,
    }


async def main() -> None:
    settings = get_settings()
    database = db.get_db(settings)
    plans = await TeachingPlanRepository(database, DEMO_SCHOOL_ID).list_published()
    await db.close_client()
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.storage_dir / "trials"
    out.mkdir(parents=True, exist_ok=True)
    print(f"Database (chỉ đọc): {settings.mongodb_db}")
    for plan in plans:
        snap = plan.published[plan.current]
        chapter = build_chapter(snap["package"], snap["lessons"])
        rejected = {
            m.group(1)
            for t, d in plan.decisions.items()
            if t.startswith("hint:") and d.get("action") == "reject"
            for m in [re.search(r"\[Nội dung: (.*)\]$", d.get("reason", ""))]
            if m
        }
        print(
            f"\n{plan.chapter_id} ({plan.current}): {len(chapter.nodes)} tiết, {len(rejected)} gợi ý bị loại"
        )
        for style in ("gioi", "hay-sai", "sai-dang", "bi"):
            result = run(chapter, style, rejected)
            path = out / f"{plan.chapter_id}-{style}.json"
            path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
            print(
                f"  {style:9} xong={result['finished']} lượt={result['turns']} tiết qua={result['passed']}/"
                f"{result['periods']} chấm={result['outcomes']} gợi ý={result['hints']} "
                f"gợi ý bị loại lọt={len(result['rejected_hints_shown'])} "
                f"sai dạng được chấm đúng={len(result['wrong_form_accepted'])} lỗi={result['error']}"
            )
            print(f"            câu phải trả lời nhiều lần nhất: {result['most_tries']}")


if __name__ == "__main__":
    asyncio.run(main())
