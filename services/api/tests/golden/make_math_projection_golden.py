"""Write the Mathematics projection golden (ENG-4, english-module-rules M3/E3): run once BEFORE a change.

Scripted learners study the decimals chapter through the real teaching loop, offline, with templates only
(no model, no database). Their event logs and the projection of each log under ``node-mastery/0.3.0`` are
written to ``math-projection-before-eng4.json``. ``test_math_projection_golden.py`` projects the stored
logs with the code of today and compares the JSON byte for byte.

Run from services/api: ``.venv/bin/python tests/golden/make_math_projection_golden.py``. It was run on the
commit before ENG-4 (6ac53b9); running it again after a change would hide a regression, not find one.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path

from cavat.core.events import ExplanationSubmitted, ItemResolved, QuestionShown, RetellJudged
from cavat.core.pedagogy import ErrorClass, ItemResolution
from cavat.modules.assessment.math_checker import parse_literal
from cavat.modules.assessment.projector import MASTERY_POLICY_VERSION, project_chapter
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.item_loop import Phase

ROOT = Path(__file__).resolve().parents[4]
CHAPTER_PATH = ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"
OUT = Path(__file__).with_name("math-projection-before-eng4.json")
T0 = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)
EXPLAINING = (Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON)
CHAPTER = load_chapter(CHAPTER_PATH)


def right(item_id: str) -> str:
    ans = CHAPTER.item(item_id).answer
    if ans.type == "compare":
        left, r = parse_literal(ans.left).value, parse_literal(ans.right).value
        sign = "<" if left < r else ">" if left > r else "="
        larger, smaller = (ans.left, ans.right) if left > r else (ans.right, ans.left)
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


class Learner:
    """Right with probability ``skill``; otherwise wrong, lost, or asking for help; vague "vì sao" too."""

    def __init__(self, seed: int, skill: float) -> None:
        self.rng, self.skill = random.Random(seed), skill

    def reply(self, turn) -> str:
        rng = self.rng
        if turn.awaiting == Awaiting.THEORY_REPLY:
            variant = next(t for t in CHAPTER.node(turn.node_id).theory if t.ask == turn.prompt)
            if rng.random() < self.skill and variant.accept:
                return variant.accept[0]
            return "Con không biết ạ."
        if turn.awaiting == Awaiting.RETELL:
            if rng.random() < self.skill:
                return ". ".join(ideas[0] for ideas in CHAPTER.node(turn.node_id).explain.key_ideas)
            return "Con không nhớ ạ."
        item = CHAPTER.item(turn.item_id)
        if turn.item_phase in EXPLAINING:
            if rng.random() < self.skill:
                return item.explanation or "Vì con làm theo quy tắc cô dạy."
            return "Vì con thấy vậy ạ."
        roll = rng.random()
        if roll < self.skill:
            return right(turn.item_id)
        if roll < self.skill + (1 - self.skill) / 2:
            return rng.choice(["123", "0,5", "sai", "A", "<"])
        return rng.choice(["con không biết", "gợi ý cho con với", "là sao ạ"])


def converse(learner: Learner, session_id: str, limit: int = 500):
    loop = TeachingLoop(CHAPTER, session_id)
    turns = [loop.start(T0)]
    for _ in range(limit):
        if turns[-1].awaiting == Awaiting.NOTHING:
            break
        now = T0 + timedelta(seconds=10 * len(turns))
        turns.append(loop.on_student(learner.reply(turns[-1]), now, seconds=10))
    return loop


READ = {"QUESTION_SHOWN", "ITEM_RESOLVED", "EXPLANATION_SUBMITTED", "RETELL_JUDGED"}


def event_json(e) -> dict:
    """An event as stored; the payload of an event the projector does not read is left out (it only
    counts for the index ``seq``), so the file stays small."""
    kind = str(e.event_type)
    payload = e.payload if isinstance(e.payload, dict) else e.payload.model_dump(mode="json")
    return {
        "event_type": kind,
        "payload": json.loads(json.dumps(payload, default=str)) if kind in READ else {},
        "session_id": e.session_id,
        "occurred_at": e.occurred_at.isoformat(),
    }


@dataclass(frozen=True)
class Ev:
    event_type: str
    payload: dict
    session_id: str
    occurred_at: datetime


def synthetic(seed: int, n: int = 120) -> list[Ev]:
    """Random evidence over every item of the chapter: every resolution, hint level, error class (with
    the ones Mathematics never writes, L1 excepted as it does not exist yet), misconceptions, guesses,
    judged and unjudged explanations, LLM labels below and above 0.6, voice answers with a low ASR
    confidence (Mathematics must ignore it, rule M4), several sessions over several days."""
    rng = random.Random(seed)
    items = sorted(CHAPTER._items)
    mis = sorted(m.id for lesson in CHAPTER.lessons.values() for m in lesson.misconceptions) + ["X-UNKNOWN"]
    nodes = [node.id for node in CHAPTER.nodes]
    out: list[Ev] = []
    for k in range(n):
        at = T0 + timedelta(days=k // 30, minutes=k)
        session = f"syn-{seed}-{k // 30}"
        item_id = rng.choice(items)
        it = CHAPTER.item(item_id)
        roll = rng.random()
        if roll < 0.1:
            out.append(
                Ev(
                    "QUESTION_SHOWN",
                    QuestionShown(
                        item_id=item_id,
                        activity_type="GUIDED_PRACTICE",
                        purpose=it.purpose,
                        kc_ids=list(it.kc_ids),
                        cognitive_level=it.cognitive_level,
                        difficulty=it.difficulty,
                        transfer=it.transfer,
                    ).model_dump(mode="json"),
                    session,
                    at,
                )
            )
            continue
        if roll < 0.25:
            source = rng.choice(["NONE", "RUBRIC_RULE", "LLM", "TEACHER"])
            payload = ExplanationSubmitted(
                item_id=item_id,
                text="vì ...",
                label_source=source,
                reasoning_quality=None if source == "NONE" else round(rng.random(), 2),
                label_confidence=round(rng.random(), 2),
            )
            out.append(Ev("EXPLANATION_SUBMITTED", payload.model_dump(mode="json"), session, at))
            continue
        if roll < 0.35:
            payload = RetellJudged(
                node_id=rng.choice(nodes + ["KC-NOT-IN-CHAPTER"]),
                text="...",
                ideas_total=3,
                score=round(rng.random(), 2),
                label_source=rng.choice(["RUBRIC_RULE", "LLM", "TEACHER"]),
                label_confidence=round(rng.random(), 2),
                purpose=rng.choice(["RETELL", "RECALL"]),
            )
            out.append(Ev("RETELL_JUDGED", payload.model_dump(mode="json"), session, at))
            continue
        if roll < 0.4:
            out.append(Ev("TUTOR_TURN", {}, session, at))
            continue
        hint = rng.choice([0, 0, 0, 1, 2, 3, 4, 5, 6, 7])
        resolution = rng.choice(list(ItemResolution))
        error = (
            rng.choice([None, *[c for c in ErrorClass]]) if resolution == ItemResolution.UNRESOLVED else None
        )
        voice = rng.random() < 0.3
        payload = ItemResolved(
            item_id=item_id,
            purpose=it.purpose,
            kc_ids=list(it.kc_ids),
            cognitive_level=it.cognitive_level,
            difficulty=it.difficulty,
            transfer=it.transfer,
            resolution=resolution,
            max_hint_level=hint,
            attempts=rng.randint(1, 3),
            hints_count=hint,
            misconception_ids=rng.sample(mis, k=rng.choice([0, 0, 1, 2])),
            final_error_class=error,
            explained=rng.choice([None, None, True, False]),
            guessed=rng.random() < 0.1,
            modality="VOICE" if voice else "TEXT",
            asr_confidence=round(rng.random(), 2) if voice else None,
        )
        out.append(Ev("ITEM_RESOLVED", payload.model_dump(mode="json"), session, at))
    return out


def digest(projection) -> str:
    canonical = json.dumps(projection.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def summary(projection) -> dict:
    return {
        n.node_id: [
            n.mastery,
            n.level,
            n.passed_at,
            len([e for e in projection.evidence if e.node_id == n.node_id]),
        ]
        for n in projection.nodes.values()
    }


PROFILES = [(1, 0.95), (2, 0.8), (3, 0.6), (4, 0.4), (5, 0.25), (6, 0.7), (7, 0.5)]
SYNTHETIC = [11, 12, 13, 14, 15]


def main() -> None:
    logs = []
    for seed, skill in PROFILES:
        loop = converse(Learner(seed, skill), f"golden-{seed}")
        events = [event_json(e) for e in loop.events]
        projection = project_chapter(loop.events, CHAPTER)
        logs.append(
            {
                "kind": "teaching-loop",
                "seed": seed,
                "skill": skill,
                "events": events,
                "sha256": digest(projection),
                "summary": summary(projection),
            }
        )
    for seed in SYNTHETIC:
        events = synthetic(seed)
        projection = project_chapter(events, CHAPTER)
        logs.append(
            {
                "kind": "synthetic",
                "seed": seed,
                "events": [event_json(e) for e in events],
                "sha256": digest(projection),
                "summary": summary(projection),
            }
        )
    doc = {
        "chapter": str(CHAPTER_PATH.relative_to(ROOT)),
        "policy_version": MASTERY_POLICY_VERSION,
        "logs": logs,
    }
    OUT.write_text(
        json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(OUT, sum(len(log["events"]) for log in logs), "events")


if __name__ == "__main__":
    main()
