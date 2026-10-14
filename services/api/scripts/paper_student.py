"""Numbers of the student and Socratic sections of the paper: output docs/paper/data/student.json.

Read only. It takes the completed sessions of the simulated learner on the two published chapters (the
database of services/api/.env), and measures, from their event logs and from the teacher's view of them:

- the Socratic behaviour of every tutor message (questions per turn, length, the answer said before it may
  be: ``leak``), by move and by source (template, model, extract);
- the hint ladder: levels and targets delivered, the resolution of every item by the highest level used,
  the rules (R-* of the item loop, N-* of the node policy) that took the decisions;
- the learner model as the teacher sees it: for every node M, the seven dimensions, the level, the gates
  and the trajectory of M over the evidence;
- one node as a worked example of the evidence that moved it.

The learner is anonymised (S1): nothing here is a real child's data (it is a scripted learner).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from statistics import mean, median

from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.main import app
from cavat.modules.assessment.projector import project_chapter
from cavat.modules.assessment.vi_numbers import extract_numbers, parse_literal
from cavat.modules.session import chapter_service
from cavat.modules.session.api import teacher_identity
from cavat.modules.session.service import DEMO_SCHOOL_ID
from fastapi.testclient import TestClient

OUT = REPO_ROOT / "docs/paper/data/student.json"
CHAPTERS = ("math-g5-decimals", "math-g5-area-triangle-trapezoid")
KEEP_SESSIONS_AFTER = "2026-10-13T09:00"  # the sessions of the final run (earlier ones were archived)


class Ev:
    """What the projector reads from a stored event."""

    def __init__(self, raw: dict, session_id: str):
        self.event_type = raw["event_type"]
        self.payload = raw["payload"]
        self.session_id = session_id
        self.occurred_at = raw.get("occurred_at")
        self.sequence_no = raw.get("sequence_no", 0)


def says_key(item, text: str, known_text: str) -> bool:
    """The key of a numeric item said, in the form asked, when neither the stem nor the child said it."""
    ans = item.answer
    if ans.type != "numeric":
        return False
    try:
        key = parse_literal(ans.value)
    except ValueError:
        return False
    same = lambda n: n.value == key.value and n.form == key.form  # noqa: E731
    known = any(same(n) for n in [*extract_numbers(item.stem), *extract_numbers(known_text)])
    return not known and any(same(n) for n in extract_numbers(text))


def words(text: str) -> int:
    return len(text.split())


def select_sessions(docs: list[dict]) -> list[dict]:
    """The completed sessions of the final run of the simulated learner: the student with the most completed
    sessions created after ``KEEP_SESSIONS_AFTER`` (earlier ones were archived)."""
    recent = [
        d
        for d in docs
        if d["state"]["lifecycle"] == "COMPLETED"
        and str(d["created_at"]) >= KEEP_SESSIONS_AFTER.replace("T", " ")
    ]
    if not recent:
        return []
    student, _ = Counter(d["student_id"] for d in recent).most_common(1)[0]
    return sorted((d for d in recent if d["student_id"] == student), key=lambda d: d["created_at"])


async def load():
    settings = get_settings()
    database = db.get_db(settings)
    await chapter_service.load_published(database, DEMO_SCHOOL_ID)
    docs = await database["learning_sessions"].find({}).to_list(None)
    await db.close_client()
    return select_sessions(docs)


def teacher_view(student_id: str) -> dict:
    app.dependency_overrides[teacher_identity] = lambda: "teacher"
    out = {}
    with TestClient(app) as client:
        for chapter in CHAPTERS:
            out[chapter] = client.get(
                f"/v1/teachers/students/{student_id}", params={"chapter": chapter}
            ).json()
    return out


def analyse(chapter_id: str, sessions: list[dict]) -> dict:
    chapter = chapter_service.chapters()[chapter_id]
    events: list[Ev] = []
    for s in sessions:
        events += [Ev(e, s["_id"]) for e in s["events"]]
    projection = project_chapter(events, chapter)

    # ---- Socratic behaviour of the tutor's messages
    said_by_item: dict[str, list[str]] = defaultdict(list)
    msgs = []
    for e in events:
        p = e.payload
        if e.event_type == "STUDENT_MESSAGE":
            said_by_item[p.get("item_id", "")].append(p.get("text", ""))
        elif e.event_type == "QUESTION_SHOWN":
            said_by_item[p["item_id"]] = []  # a new attempt at the item
        elif e.event_type == "TUTOR_MESSAGE_SENT":
            item_id = p.get("item_id")
            text = p.get("text", "")
            item = None
            try:
                item = chapter.item(item_id)
            except Exception:  # noqa: BLE001 - an event of another lesson kind
                item = None
            leak = bool(item and says_key(item, text, " ".join(said_by_item.get(item_id, []))))
            msgs.append(
                {
                    "move": p.get("move"),
                    "source": p.get("source"),
                    "words": words(text),
                    "questions": text.count("?"),
                    "leak": leak,
                    "attempts": p.get("attempts_to_pass_validator", 1),
                    "numeric": bool(item and item.answer.type == "numeric"),
                }
            )
    by_move: dict[str, dict] = {}
    for move in sorted({m["move"] for m in msgs}):
        rows = [m for m in msgs if m["move"] == move]
        by_move[move] = {
            "n": len(rows),
            "mean_words": round(mean(r["words"] for r in rows), 1),
            "one_question": sum(r["questions"] == 1 for r in rows),
            "no_question": sum(r["questions"] == 0 for r in rows),
            "many_questions": sum(r["questions"] > 1 for r in rows),
            "leaks": sum(r["leak"] for r in rows),
            "numeric": sum(r["numeric"] for r in rows),
        }
    # a tutor message said again word for word within the same item (the ladder had nothing new to say)
    seen_text: dict[tuple[str, str], list[str]] = defaultdict(list)
    repeats_by_move: Counter[str] = Counter()
    considered_by_move: Counter[str] = Counter()
    items_considered, items_repeating = set(), set()
    for s in sessions:
        for raw in s["events"]:
            if raw["event_type"] != "TUTOR_MESSAGE_SENT" or raw["payload"].get("move") == "PRESENT":
                continue
            key = (s["_id"], raw["payload"].get("item_id") or "")
            text = raw["payload"].get("text", "").strip()
            move = raw["payload"].get("move") or ""
            items_considered.add(key)
            considered_by_move[move] += 1
            if text in seen_text[key]:
                repeats_by_move[move] += 1
                items_repeating.add(key)
            seen_text[key].append(text)
    rejected = Counter(
        code for e in events if e.event_type == "OUTPUT_REJECTED" for code in e.payload.get("issue_codes", [])
    )
    socratic = {
        "tutor_messages": len(msgs),
        "by_source": dict(Counter(m["source"] for m in msgs)),
        "source_by_move": {
            src: dict(Counter(m["move"] for m in msgs if m["source"] == src))
            for src in sorted({m["source"] for m in msgs})
        },
        "rejected_codes": dict(rejected),
        "by_move": by_move,
        "leaks": sum(m["leak"] for m in msgs),
        "leak_checked": sum(m["numeric"] for m in msgs),
        "more_than_one_question": sum(m["questions"] > 1 for m in msgs),
        "words": {
            "mean": round(mean(m["words"] for m in msgs), 1),
            "median": median(m["words"] for m in msgs),
            "max": max(m["words"] for m in msgs),
            "over_60": sum(m["words"] > 60 for m in msgs),
        },
        "retried_by_validator": sum(m["attempts"] > 1 for m in msgs),
        "repeats": {
            "considered": sum(considered_by_move.values()),
            "repeated": sum(repeats_by_move.values()),
            "items": len(items_considered),
            "items_repeating": len(items_repeating),
            "by_move": {m: [repeats_by_move[m], considered_by_move[m]] for m in considered_by_move},
        },
    }

    # ---- Hint ladder and resolution
    hints = [e.payload for e in events if e.event_type == "HINT_DELIVERED"]
    resolved = [e.payload for e in events if e.event_type == "ITEM_RESOLVED"]
    ladder = {
        "delivered": len(hints),
        "by_level": dict(sorted(Counter(h["hint_level"] for h in hints).items())),
        "by_target": dict(Counter(h["hint_target"] for h in hints)),
        "by_source": dict(Counter(h["source"] for h in hints)),
        "items": len(resolved),
        "resolution": dict(Counter(r["resolution"] for r in resolved)),
        "by_max_level": {
            str(lv): dict(Counter(r["resolution"] for r in resolved if r["max_hint_level"] == lv))
            for lv in range(0, 8)
            if any(r["max_hint_level"] == lv for r in resolved)
        },
        "attempts": dict(sorted(Counter(r["attempts"] for r in resolved).items())),
        "explained": dict(Counter(str(r.get("explained")) for r in resolved)),
        "misconceptions": dict(
            Counter(e.payload["misconception_id"] for e in events if e.event_type == "MISCONCEPTION_DETECTED")
        ),
    }

    # ---- Rules
    policy_rules = Counter(
        r for e in events if e.event_type == "POLICY_DECISION" for r in e.payload["rule_ids"]
    )
    policy_moves = Counter(e.payload["move"] for e in events if e.event_type == "POLICY_DECISION")
    node_rules = Counter(r for e in events if e.event_type == "NODE_DECISION" for r in e.payload["rule_ids"])
    node_actions = Counter(e.payload["action"] for e in events if e.event_type == "NODE_DECISION")
    rules = {
        "item_rules": dict(policy_rules.most_common()),
        "item_moves": dict(policy_moves.most_common()),
        "node_rules": dict(node_rules.most_common()),
        "node_actions": dict(node_actions.most_common()),
    }

    # ---- Learner model per node
    nodes = []
    order = chapter.topological_order()
    for node_id in order:
        st = projection.nodes[node_id]
        node = chapter.node(node_id)
        nodes.append(
            {
                "id": node_id,
                "name": node.name,
                "layer": node.layer,
                "mastery": st.mastery,
                "confidence": st.confidence,
                "level": st.level,
                "state": st.state,
                "passed": st.passed_at is not None,
                "passed_at": st.passed_at,
                "items": st.items,
                "successes": st.successes,
                "levels": list(st.levels),
                "forms": list(st.forms),
                "prior": st.prior,
                "missing": list(st.missing),
                "dims": {
                    d: {
                        "mean": round(v.mean * 100, 1),
                        "n_eff": round(v.n_eff, 2),
                        "in_mastery": v.in_mastery,
                    }
                    for d, v in st.dimensions.items()
                },
                "misconceptions": [
                    {"id": m.id, "severity": m.severity, "count": m.count, "status": m.status}
                    for m in st.misconceptions
                ],
                "rule": {
                    "min_mastery": node.pass_rule.min_mastery,
                    "min_successes": node.pass_rule.min_successes,
                    "min_levels": node.pass_rule.min_levels,
                    "min_forms": node.pass_rule.min_forms,
                    "require_explanation": node.pass_rule.require_explanation,
                    "require_application": node.pass_rule.require_application,
                    "max_items": node.pass_rule.max_items,
                },
            }
        )
    trace = [{"seq": t.seq, "node": t.node_id, "mastery": t.mastery} for t in projection.trace]
    evidence = [
        {
            "seq": ev.seq,
            "node": ev.node_id,
            "dim": ev.dimension,
            "score": round(ev.score, 3),
            "weight": round(ev.weight, 3),
            "reason": ev.reason,
            "item": ev.item_id,
        }
        for ev in projection.evidence
    ]
    return {
        "events": len(events),
        "sessions": [
            {
                "id": s["_id"][-8:],
                "events": len(s["events"]),
                "created": str(s["created_at"])[:19],
                "ended": str(s.get("ended_at"))[:19],
            }
            for s in sessions
        ],
        "student_messages": sum(e.event_type == "STUDENT_MESSAGE" for e in events),
        "socratic": socratic,
        "ladder": ladder,
        "rules": rules,
        "nodes": nodes,
        "trace": trace,
        "evidence": evidence,
        "relations": [
            {"source": r.source, "target": r.target, "type": r.type} for r in chapter.package.relations
        ],
    }


def main() -> None:
    sessions = asyncio.run(load())
    if not sessions:
        sys.exit("no completed session of the simulated learner after " + KEEP_SESSIONS_AFTER)
    by_chapter = defaultdict(list)
    for s in sessions:
        by_chapter[s["lesson_id"]].append(s)
    view = teacher_view(sessions[0]["student_id"])
    out = {"learner": "S1", "chapters": {}}
    for chapter_id in CHAPTERS:
        a = analyse(chapter_id, by_chapter[chapter_id])
        v = view[chapter_id]
        a["teacher_view"] = {
            "overall": v["overall"],
            "dimensions": v["dimensions"],
            "curve": v["curve"],
            "journey": v["journey"],
            "conversation": v["conversation"],
            "attention": v["attention"],
        }
        out["chapters"][chapter_id] = a
        print(
            chapter_id,
            "events",
            a["events"],
            "tutor messages",
            a["socratic"]["tutor_messages"],
            "leaks",
            a["socratic"]["leaks"],
            "/",
            a["socratic"]["leak_checked"],
            "numeric",
            "items",
            a["ladder"]["items"],
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("written", OUT.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
