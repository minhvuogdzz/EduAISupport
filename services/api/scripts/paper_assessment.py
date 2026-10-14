"""Numbers of the assessment section of the paper: output docs/paper/data/assessment.json.

How close the projection of understanding is to the framework it was specified from (RQ4), by four
experiments that need no model and write nothing:

1. conformance: random streams of resolved items go through ``project_chapter`` and through an oracle
   written from the formulas of the paper (closed form, not the fold); invariants of the specification
   (order, monotonicity, gates, determinism) are counted over the same streams;
2. response curves and gates: the score and the level the projection gives to hand-built learners
   (every hint level, every error class, the staircase of the gates of DI-6);
3. known groups: the four scripted learners of ``make trial`` learn both published chapters in memory;
   the projection should order them by what they were scripted to know and need;
4. sensitivity: the projection of the simulated learner S1 recomputed with each declared interpretation
   moved to a neighbouring value.

Read only (the database of services/api/.env is only read). The learner is the anonymised S1.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from statistics import mean

import paper_student  # noqa: E402  (same folder: scripts/)
import trial_sessions  # noqa: E402
from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.modules.assessment.projector import DEFAULT_POLICY, project_chapter
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.ingest.repository import TeachingPlanRepository
from cavat.modules.session import chapter_service
from cavat.modules.session.chapter_service import build_chapter
from cavat.modules.session.service import DEMO_SCHOOL_ID

OUT = REPO_ROOT / "docs/paper/data/assessment.json"
SAMPLE = REPO_ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml"
NODE = "KC-DEC-FRAC"  # a source node of the sample chapter: no prerequisite, so the prior is 0.5 (DI-16)
T0 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
SEED = 20261014
IND = DEFAULT_POLICY.independence
W = dict(DEFAULT_POLICY.weights)


class Ev:
    def __init__(self, event_type: str, payload: dict, session: str = "s1", at: datetime = T0):
        self.event_type, self.payload, self.session_id, self.occurred_at = event_type, payload, session, at


def resolved(
    item: str,
    *,
    level: str = "B",
    difficulty: float = 0.5,
    hint: int = 0,
    ok: bool = True,
    error: str | None = None,
    guessed: bool = False,
    explained: bool | None = None,
    transfer: str = "none",
    misconceptions: tuple[str, ...] = (),
    session: str = "s1",
    at: datetime = T0,
) -> Ev:
    resolution = (
        "UNRESOLVED" if not ok else "INDEPENDENT" if hint == 0 else "SUPPORTED" if hint <= 5 else "WORKED"
    )
    return Ev(
        "ITEM_RESOLVED",
        {
            "item_id": item,
            "purpose": "PRACTICE",
            "kc_ids": [NODE],
            "cognitive_level": level,
            "difficulty": difficulty,
            "transfer": transfer,
            "resolution": resolution,
            "max_hint_level": hint,
            "attempts": 1 + (hint > 0),
            "hints_count": hint,
            "misconception_ids": list(misconceptions),
            "final_error_class": error,
            "explained": explained,
            "guessed": guessed,
        },
        session,
        at,
    )


def explanation(item: str, quality: float = 1.0, session: str = "s1", at: datetime = T0) -> Ev:
    return Ev(
        "EXPLANATION_SUBMITTED",
        {
            "item_id": item,
            "text": "vì ...",
            "reasoning_quality": quality,
            "label_source": "RUBRIC_RULE",
            "label_confidence": 1.0,
        },
        session,
        at,
    )


def snapshot(chapter, events, policy=DEFAULT_POLICY) -> dict:
    s = project_chapter(events, chapter, policy).nodes[NODE]
    return {
        "mastery": s.mastery,
        "confidence": s.confidence,
        "level": s.level,
        "state": s.state,
        "items": s.items,
        "successes": s.successes,
        "levels": s.levels,
        "forms": s.forms,
        "has_explanation": s.has_explanation,
        "has_application": s.has_application,
        "understood": s.understood,
        "pass_now": s.pass_now,
        "missing": s.missing,
        "dims": {
            d: {"mean": round(v.mean * 100, 1), "n_eff": round(v.n_eff, 2)} for d, v in s.dimensions.items()
        },
    }


# ---------------------------------------------------------------------------------------- the oracle


def spec_state(rows: list[dict], completion: set[str], prior: float = 0.5) -> dict:
    """The state of the paper's equations (closed form, written from the formulas, not from the fold):
    Beta sums per dimension, DI-1 renormalisation, the confidence of DI-11, the level of §4-§8 with the
    gates of DI-6 and the provisional state of §53 without S."""
    acc = {d: [0.0, 0.0, 0.0] for d in "CRATISD"}
    scores: list[float] = []  # non-I evidence in order (the consistency factor)
    levels_seen: set[str] = set()
    sessions: dict[str, float] = {}
    application = False

    def add(d, score, weight):
        acc[d][0] += weight * score
        acc[d][1] += weight * (1 - score)
        acc[d][2] += weight
        if d != "I":
            scores.append(score)

    for r in rows:
        sessions.setdefault(r["session"], r["day"])
        sessions[r["session"]] = min(sessions[r["session"]], r["day"])
        if r.get("why") is not None:  # a "vì sao" reply judged by the rubric (DI-55)
            if r["why"] > 0.2:
                add("R", r["why"], 0.5)
            continue
        level, transfer = r["level"], r["transfer"]
        levels_seen.add(level)
        dim = (
            "D"
            if level == "DIAG"
            else "T"
            if level == "E"
            else "A"
            if level == "D"
            else "T"
            if transfer != "none"
            else "R"
            if level == "C"
            else "C"
        )
        support = IND[r["hint"]]
        scaffold = 0.5 if r["item"] in completion else 1.0
        if r["ok"]:
            w = (0.5 + r["difficulty"]) * max(support, 0.3) * scaffold * (0.5 if r["guessed"] else 1.0)
            add(dim, 1.0, w)
            add("I", support, scaffold)
        else:
            score = {"CALCULATION": 0.5, "FORMAT": 0.7}.get(r["error"] or "", 0.0)
            w = (1.5 - r["difficulty"]) * scaffold
            add(dim, score, w)
            if r["error"] == "CONCEPTUAL":
                add("R", 0.0, w)
        if r["explained"] is False:
            add("R", 0.0, 1.0)
        if r["guessed"]:
            add("R", 0.0, 1.0)
        if r["ok"] and r["hint"] <= 3 and not r["guessed"] and scaffold == 1.0:
            application = application or dim in ("A", "T")
    avail = [d for d in "CRATISD" if acc[d][2] >= 1.0]
    if not avail:
        return {"mastery": None, "confidence": 0.0, "level": 0}
    mu = {d: (2 * prior + acc[d][0]) / (2 + acc[d][2]) for d in "CRATISD"}
    mastery = 100 * sum(W[d] * mu[d] for d in avail) / sum(W[d] for d in avail)
    n_eff = sum(acc[d][2] for d in "CRATSD")
    f_n = 1 - math.exp(-n_eff / 6)
    f_div = 0.4 + 0.6 * min(1.0, len(levels_seen) / 4)
    days = [r["day"] for r in rows]
    if len(sessions) < 2:
        f_span = 0.7
    else:
        f_span = 1.0 if max(days) - min(days) >= 3 else 0.85
    recent = scores[-8:]
    f_cons = min(1.0, max(0.5, 1 - 2 * statistics.pstdev(recent))) if len(recent) > 1 else 1.0
    confidence = 100 * f_n * f_div * f_span * f_cons
    has_expl = acc["R"][2] >= 1.0 and mu["R"] >= 0.6
    level = sum(mastery >= b for b in DEFAULT_POLICY.bands)
    if level >= 3 and not has_expl:
        level = 2
    if level >= 4 and not application:
        level = 3
    if level == 5 and not (mastery >= 85 and confidence >= 75 and acc["A"][2] >= 1.0 and mu["A"] >= 0.8):
        level = 4
    return {
        "mastery": mastery,
        "confidence": confidence,
        "level": level,
        "has_explanation": has_expl,
        "has_application": application,
    }


ITEMS = [  # (item id, cognitive level, difficulty, transfer) of node KC-DEC-FRAC in the sample chapter
    ("TP-CC-01", "A", 0.2, "none"),
    ("TP-CP-01", "B", 0.35, "none"),  # a "cùng làm" item of the node: scaffolded, weight halved
    ("TP-PR-01", "B", 0.3, "none"),
    ("TP-PR-02", "B", 0.4, "none"),
    ("TP-TR-01", "D", 0.45, "near"),
    ("TP-TR-01", "E", 0.5, "far"),
    ("TP-PR-01", "C", 0.55, "none"),
]
ERRORS = ["CALCULATION", "FORMAT", "CONCEPTUAL", "PROCEDURAL", "REASONING", "UNKNOWN"]


def random_stream(rng: random.Random, family: str) -> list[dict]:
    """``mixed``: any learner; ``strong``: mostly independent and correct, two sessions several days apart,
    so that the upper gates (explanation, application, provisional mastery) are exercised too."""
    strong = family == "strong"
    rows: list[dict] = []
    second = rng.randint(1, 6) if strong else 0
    for i in range(rng.randint(4, 48 if strong else 40)):
        item, level, difficulty, transfer = rng.choice(ITEMS)
        session = "s2" if strong and i >= 10 else "s1"
        day = second if session == "s2" else 0
        if strong and rng.random() < 0.25:
            rows.append({"why": rng.choice([0.1, 0.5, 0.8, 1.0, 1.0]), "session": session, "day": day})
            continue
        ok = rng.random() < (0.93 if strong else 0.7)
        rows.append(
            {
                "item": item,
                "level": level,
                "difficulty": difficulty,
                "transfer": transfer,
                "hint": min(7, int(rng.expovariate(1.8 if strong else 0.55))),
                "ok": ok,
                "error": None if ok else rng.choice(ERRORS),
                "guessed": rng.random() < (0.03 if strong else 0.1),
                "explained": rng.choice([None, True, True])
                if strong
                else rng.choice([None, None, True, False]),
                "session": session,
                "day": day,
                "why": None,
            }
        )
    return rows


def events_of(rows: list[dict]) -> list[Ev]:
    out = []
    for r in rows:
        at = T0 + timedelta(days=r["day"])
        if r.get("why") is not None:
            out.append(explanation("TP-PR-01", r["why"], session=r["session"], at=at))
        else:
            out.append(
                resolved(
                    r["item"],
                    level=r["level"],
                    difficulty=r["difficulty"],
                    hint=r["hint"],
                    ok=r["ok"],
                    error=r["error"],
                    guessed=r["guessed"],
                    explained=r["explained"],
                    transfer=r["transfer"],
                    session=r["session"],
                    at=at,
                )
            )
    return out


def conformance(chapter) -> dict:
    rng = random.Random(SEED)
    completion = set(chapter.node(NODE).completion)
    out: dict = {"scaffolded_items": sorted(completion)}
    for family in ("mixed", "strong"):
        streams = [random_stream(rng, family) for _ in range(500)]
        dev_m, dev_c, level_bad, expl_bad, app_bad = [], [], 0, 0, 0
        order_bad = replay_bad = bounds_bad = gate_bad = 0
        help_n = help_bad = better_n = better_bad = 0
        help_jump = better_jump = 0.0
        level_hist: dict[int, int] = defaultdict(int)
        for rows in streams:
            state = project_chapter(events_of(rows), chapter).nodes[NODE]
            spec = spec_state(rows, completion)
            level_hist[state.level] += 1
            if (state.mastery is None) != (spec["mastery"] is None):
                dev_m.append(100.0)
            elif spec["mastery"] is not None:
                dev_m.append(abs(state.mastery - spec["mastery"]))
                dev_c.append(abs(state.confidence - spec["confidence"]))
                level_bad += state.level != spec["level"]
                expl_bad += state.has_explanation != spec["has_explanation"]
                app_bad += state.has_application != spec["has_application"]
                bounds_bad += not (0 <= state.mastery <= 100)
            # the Beta sums add up: the order of the events does not matter (one node, no prerequisite)
            shuffled = rows[:]
            rng.shuffle(shuffled)
            order_bad += project_chapter(events_of(shuffled), chapter).nodes[NODE].mastery != state.mastery
            # replay is the same computation
            replay_bad += (
                project_chapter(events_of(rows), chapter).nodes[NODE].model_dump() != state.model_dump()
            )
            # the gates of DI-6 and of the provisional state, read on the state itself
            gate_bad += state.level >= 3 and not state.has_explanation
            gate_bad += state.level >= 4 and not state.has_application
            gate_bad += state.level == 5 and not (
                state.mastery is not None and state.mastery >= 85 and state.confidence >= 75
            )
            # one more rung of help on a correct answer never raises M
            candidates = [i for i, r in enumerate(rows) if r.get("why") is None and r["ok"] and r["hint"] < 7]
            if candidates:
                k = rng.choice(candidates)
                more = [dict(r) for r in rows]
                more[k]["hint"] += 1
                a = project_chapter(events_of(more), chapter).nodes[NODE].mastery
                help_n += 1
                if a is not None and state.mastery is not None and a > state.mastery + 0.051:
                    help_bad += 1
                    help_jump = max(help_jump, a - state.mastery)
            # a wrong answer made a correct one at H0, not guessed: M never goes down (equal support)
            wrong = [i for i, r in enumerate(rows) if r.get("why") is None and not r["ok"]]
            if wrong:
                k = rng.choice(wrong)
                better = [dict(r) for r in rows]
                better[k].update(ok=True, error=None, hint=0, guessed=False)
                a = project_chapter(events_of(better), chapter).nodes[NODE].mastery
                better_n += 1
                if a is not None and state.mastery is not None and a < state.mastery - 0.051:
                    better_bad += 1
                    better_jump = max(better_jump, state.mastery - a)
        out[family] = {
            "streams": len(streams),
            "events": sum(len(s) for s in streams),
            "levels": {str(k): v for k, v in sorted(level_hist.items())},
            "max_dev_mastery": max(dev_m),
            "mean_dev_mastery": mean(dev_m),
            "max_dev_confidence": max(dev_c),
            "level_mismatch": level_bad,
            "explanation_mismatch": expl_bad,
            "application_mismatch": app_bad,
            "order_violations": order_bad,
            "replay_violations": replay_bad,
            "bounds_violations": bounds_bad,
            "gate_violations": int(gate_bad),
            "more_help_checked": help_n,
            "more_help_violations": int(help_bad),
            "more_help_max_jump": round(help_jump, 2),
            "better_outcome_checked": better_n,
            "better_outcome_violations": int(better_bad),
            "better_outcome_max_jump": round(better_jump, 2),
        }
    return out


# --------------------------------------------------------------------------------- response curves


def curves(chapter) -> dict:
    out: dict = {}
    n = 15
    out["independence"] = {
        str(h): [
            snapshot(chapter, [resolved("TP-PR-01", difficulty=0.35, hint=h) for _ in range(k)])["mastery"]
            for k in range(1, n + 1)
        ]
        for h in range(8)
    }
    out["independence_dims"] = {
        str(h): snapshot(chapter, [resolved("TP-PR-01", difficulty=0.35, hint=h) for _ in range(6)])["dims"]
        for h in range(8)
    }
    out["difficulty"] = {
        str(d): {
            "correct": [
                snapshot(chapter, [resolved("TP-PR-01", difficulty=d) for _ in range(k)])["mastery"]
                for k in range(1, 9)
            ],
            "wrong_after_4_correct": snapshot(
                chapter,
                [resolved("TP-PR-01", difficulty=0.5) for _ in range(4)]
                + [resolved("TP-PR-01", difficulty=d, ok=False, error="UNKNOWN")],
            )["mastery"],
        }
        for d in (0.2, 0.5, 0.8)
    }
    base = [resolved("TP-PR-01", difficulty=0.5) for _ in range(4)]
    before = snapshot(chapter, base)
    out["error_class"] = {"before": before["mastery"], "before_R": before["dims"]["R"]}
    for cls in ERRORS:
        s = snapshot(chapter, [*base, resolved("TP-PR-01", difficulty=0.5, ok=False, error=cls)])
        out["error_class"][cls] = {
            "mastery": s["mastery"],
            "C": s["dims"]["C"]["mean"],
            "R": s["dims"]["R"]["mean"],
        }
    out["scaffold"] = {
        "alone": snapshot(chapter, [resolved("TP-PR-01", difficulty=0.35) for _ in range(6)])["mastery"],
        "together": snapshot(chapter, [resolved("TP-CP-01", difficulty=0.35) for _ in range(6)])["mastery"],
    }
    out["guess"] = {
        "honest": snapshot(chapter, [resolved("TP-PR-01", difficulty=0.5) for _ in range(6)])["mastery"],
        "guessed": snapshot(chapter, [resolved("TP-PR-01", difficulty=0.5, guessed=True) for _ in range(6)])[
            "mastery"
        ],
    }
    patterns = {
        "đều, không gợi ý": [dict(hint=0, ok=True)] * 14,
        "sai rồi học dần": [
            dict(hint=0, ok=False, error="CONCEPTUAL"),
            dict(hint=0, ok=False, error="CONCEPTUAL"),
            dict(hint=5, ok=True),
            dict(hint=3, ok=True),
            dict(hint=2, ok=True),
            dict(hint=1, ok=True),
            *[dict(hint=0, ok=True)] * 8,
        ],
        "luôn cần gợi ý H6": [dict(hint=6, ok=True)] * 14,
        "đoán": [dict(hint=0, ok=True, guessed=True)] * 14,
        "đúng sai xen kẽ": [
            dict(hint=0, ok=i % 2 == 0, error=None if i % 2 == 0 else "UNKNOWN") for i in range(14)
        ],
        "toàn sai": [dict(hint=0, ok=False, error="CONCEPTUAL")] * 14,
    }
    out["patterns"] = {}
    for name, rows in patterns.items():
        trace = []
        for k in range(1, len(rows) + 1):
            evs = [resolved("TP-PR-01", difficulty=0.5, **r) for r in rows[:k]]
            trace.append(snapshot(chapter, evs)["mastery"])
        final = snapshot(chapter, [resolved("TP-PR-01", difficulty=0.5, **r) for r in rows])
        out["patterns"][name] = {"trace": trace, "final": final}
    return out


def gates(chapter) -> list[dict]:
    """The staircase of DI-6, the node pass rule (DI-15) and the provisional state (§53, without S)."""
    steps: list[tuple[str, list[Ev]]] = []
    ev: list[Ev] = []
    at = lambda d, h=0: T0 + timedelta(days=d, hours=h)  # noqa: E731
    hour = 0

    def tick() -> datetime:
        nonlocal hour
        hour += 1
        return at(0, hour)

    steps.append(("Chưa có bằng chứng", list(ev)))
    for item, level, d, _ in ITEMS[2:5]:
        ev.append(resolved(item, level=level if level != "D" else "B", difficulty=d, at=tick()))
    steps.append(("3 câu đúng, không gợi ý (mức B)", list(ev)))
    for k in range(9):
        ev.append(
            resolved(
                ("TP-PR-01", "TP-PR-02", "TP-CC-01")[k % 3],
                level=("B", "B", "A")[k % 3],
                difficulty=0.35,
                at=tick(),
            )
        )
    steps.append(("12 câu đúng (mức A–B), chưa hỏi “vì sao”", list(ev)))
    for _ in range(3):
        ev.append(explanation("TP-PR-01", 1.0, at=tick()))
    steps.append(("+ 3 lần giải thích đúng (chiều R)", list(ev)))
    for _ in range(4):
        ev.append(resolved("TP-TR-01", level="D", difficulty=0.45, transfer="near", at=tick()))
    steps.append(("+ 4 câu vận dụng đúng (mức D)", list(ev)))
    for _ in range(3):
        ev.append(resolved("TP-TR-01", level="E", difficulty=0.5, transfer="far", at=tick()))
    for _ in range(2):
        ev.append(resolved("TP-PR-01", level="C", difficulty=0.55, at=tick()))
    steps.append(("+ 3 câu chuyển giao (E) và 2 câu mức C, cùng buổi", list(ev)))
    for k in range(6):
        ev.append(
            resolved(
                ("TP-PR-01", "TP-PR-02", "TP-TR-01")[k % 3],
                level="B" if k % 3 < 2 else "D",
                difficulty=0.4,
                session="s2",
                at=at(4, k),
            )
        )
    for k in range(6):
        ev.append(explanation("TP-PR-01", 1.0, session="s2", at=at(4, 6 + k)))
    steps.append(("+ buổi 2 sau 4 ngày: 6 câu đúng, 6 lần giải thích đúng", list(ev)))
    for k in range(6):
        ev.append(
            resolved(
                ("TP-PR-01", "TP-TR-01", "TP-TR-01")[k % 3],
                level=("B", "D", "E")[k % 3],
                difficulty=0.5,
                transfer=("none", "near", "far")[k % 3],
                session="s3",
                at=at(8, k),
            )
        )
    for k in range(4):
        ev.append(explanation("TP-PR-01", 1.0, session="s3", at=at(8, 6 + k)))
    steps.append(("+ buổi 3 sau 8 ngày: 6 câu đúng (B, D, E), 4 lần giải thích đúng", list(ev)))
    ev.append(
        resolved(
            "TP-PR-01",
            difficulty=0.4,
            ok=False,
            error="CONCEPTUAL",
            misconceptions=("FRAC-M01",),
            session="s3",
            at=at(8, 11),
        )
    )
    steps.append(("+ phát hiện 1 lỗi quan niệm NGHIÊM TRỌNG", list(ev)))
    for k in range(2):
        ev.append(resolved("TP-PR-01", difficulty=0.3, session="s3", at=at(8, 12 + k)))
    steps.append(("+ 2 câu đúng nơi lỗi có thể lộ: lỗi được coi là đã giải quyết", list(ev)))
    for k in range(8):
        ev.append(resolved(("TP-PR-01", "TP-PR-02")[k % 2], difficulty=0.4, session="s3", at=at(8, 14 + k)))
    steps.append(("+ 8 câu đúng tiếp theo", list(ev)))
    rows = []
    for name, events in steps:
        s = snapshot(chapter, events)
        s["step"] = name
        s["events"] = len(events)
        rows.append(s)
    return rows


# ------------------------------------------------------------------------------------ known groups


@dataclass
class Dependent(trial_sessions.Learner):
    """The four scripted learners of ``make trial`` plus ``phu-thuoc``: says "con không biết" to the first
    four turns of every question (the ladder goes up one rung each time) and then answers right."""

    asked: dict = field(default_factory=dict)

    def reply(self, turn) -> str:
        item_turn = (
            turn.awaiting == trial_sessions.Awaiting.ANSWER
            and turn.item_phase not in trial_sessions.EXPLAINING
        )
        if self.style == "phu-thuoc" and item_turn:
            self.asked[turn.item_id] = self.asked.get(turn.item_id, 0) + 1
            if self.asked[turn.item_id] <= 4:
                return "Con không biết ạ."
            return trial_sessions.right_answer(self.chapter, turn.item_id)
        return super().reply(turn)


def known_groups(plans) -> dict:
    out: dict = {}
    captured: dict = {}

    class Recording(trial_sessions.TeachingLoop):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["loop"] = self

    original = trial_sessions.TeachingLoop, trial_sessions.Learner
    trial_sessions.TeachingLoop, trial_sessions.Learner = Recording, Dependent
    try:
        for plan in plans:
            snap = plan.published[plan.current]
            chapter = build_chapter(snap["package"], snap["lessons"])
            rows = {}
            for style in ("gioi", "sai-dang", "bi", "hay-sai", "phu-thuoc"):
                result = trial_sessions.run(chapter, style, set())
                proj = captured["loop"].projection()
                nodes = proj.nodes.values()
                ms = [n.mastery for n in nodes if n.mastery is not None]
                dims = defaultdict(list)
                for n in nodes:
                    for d, v in n.dimensions.items():
                        if v.in_mastery:
                            dims[d].append(v.mean * 100)
                rows[style] = {
                    "turns": result["turns"],
                    "passed": result["passed"],
                    "nodes": len(chapter.nodes),
                    "hints": result["hints"],
                    "outcomes": result["outcomes"],
                    "mastery_mean": round(mean(ms), 1) if ms else None,
                    "mastery_min": min(ms) if ms else None,
                    "mastery_max": max(ms) if ms else None,
                    "level_mean": round(mean(n.level for n in nodes), 2),
                    "confidence_mean": round(mean(n.confidence for n in nodes), 1),
                    "dims": {d: round(mean(v), 1) for d, v in dims.items()},
                    "per_node": [
                        {
                            "id": n.node_id,
                            "M": n.mastery,
                            "level": n.level,
                            "I": round(n.dimensions["I"].mean * 100, 1),
                        }
                        for n in nodes
                    ],
                }
            out[plan.chapter_id] = rows
    finally:
        trial_sessions.TeachingLoop, trial_sessions.Learner = original
    return out


# ----------------------------------------------------------------------------------- sensitivity

PERTURBATIONS: list[tuple[str, str, dict]] = [
    ("DI-2", "H3 0,60 → 0,50", {"independence": (1.0, 0.85, 0.70, 0.50, 0.50, 0.35, 0.20, 0.0)}),
    ("DI-2", "H3 0,60 → 0,70", {"independence": (1.0, 0.85, 0.70, 0.70, 0.50, 0.35, 0.20, 0.0)}),
    ("DI-2", "H5 0,35 → 0,25", {"independence": (1.0, 0.85, 0.70, 0.60, 0.50, 0.25, 0.20, 0.0)}),
    ("DI-2", "H5 0,35 → 0,45", {"independence": (1.0, 0.85, 0.70, 0.60, 0.50, 0.45, 0.20, 0.0)}),
    ("DI-5", "sàn hỗ trợ 0,3 → 0,1", {"min_support": 0.1}),
    ("DI-5", "sàn hỗ trợ 0,3 → 0,5", {"min_support": 0.5}),
    ("DI-12", "khối lượng tiên nghiệm 2 → 1", {"prior_mass": 1.0}),
    ("DI-12", "khối lượng tiên nghiệm 2 → 4", {"prior_mass": 4.0}),
    ("DI-3", "hệ số đoán 0,5 → 0,25", {"guess_factor": 0.25}),
    ("DI-3", "hệ số đoán 0,5 → 0,75", {"guess_factor": 0.75}),
    ("DI-6", "ngưỡng giải thích 0,6 → 0,5", {"explanation_gate": 0.5}),
    ("DI-6", "ngưỡng giải thích 0,6 → 0,7", {"explanation_gate": 0.7}),
    ("DI", "thành công khi gợi ý ≤ H3 → ≤ H2", {"success_max_hint": 2}),
    ("DI", "thành công khi gợi ý ≤ H3 → ≤ H4", {"success_max_hint": 4}),
    ("DI-55", "trọng số “vì sao” 0,5 → 0,3", {"rubric_explanation_weight": 0.3}),
    ("DI-55", "trọng số “vì sao” 0,5 → 0,8", {"rubric_explanation_weight": 0.8}),
    ("§4–§8", "các dải −5 điểm", {"bands": (15, 35, 55, 70, 85)}),
    ("§4–§8", "các dải +5 điểm", {"bands": (25, 45, 65, 80, 95)}),
    ("§20", "trọng số 7 chiều bằng nhau", {"weights": {d: 1 / 7 for d in "CRATISD"}}),
    ("DI-1", "ngưỡng bằng chứng tối thiểu 1,0 → 2,0", {"min_evidence": 2.0}),
]


def sensitivity(sessions_by_chapter: dict[str, list[dict]]) -> dict:
    out: dict = {}
    for chapter_id, sessions in sessions_by_chapter.items():
        chapter = chapter_service.chapters()[chapter_id]
        events = [paper_student.Ev(e, s["_id"]) for s in sessions for e in s["events"]]
        base = project_chapter(events, chapter)
        rows = []
        for di, label, change in PERTURBATIONS:
            policy = replace(DEFAULT_POLICY, **change)
            alt = project_chapter(events, chapter, policy)
            dm, lv, ps = [], 0, 0
            for node_id, b in base.nodes.items():
                a = alt.nodes[node_id]
                if a.mastery is not None and b.mastery is not None:
                    dm.append(abs(a.mastery - b.mastery))
                lv += a.level != b.level
                ps += (a.passed_at is not None) != (b.passed_at is not None)
            rows.append(
                {
                    "di": di,
                    "change": label,
                    "mean_abs_dM": round(mean(dm), 2) if dm else None,
                    "max_abs_dM": round(max(dm), 2) if dm else None,
                    "level_changes": lv,
                    "pass_changes": ps,
                    "nodes": len(base.nodes),
                }
            )
        out[chapter_id] = {
            "base": {
                n: {"M": s.mastery, "level": s.level, "passed": s.passed_at is not None}
                for n, s in base.nodes.items()
            },
            "rows": rows,
        }
    return out


async def fetch():
    settings = get_settings()
    database = db.get_db(settings)
    await chapter_service.load_published(database, DEMO_SCHOOL_ID)
    plans = await TeachingPlanRepository(database, DEMO_SCHOOL_ID).list_published()
    docs = await database["learning_sessions"].find({}).to_list(None)
    await db.close_client()
    by_chapter: dict[str, list[dict]] = defaultdict(list)
    for s in paper_student.select_sessions(docs):
        by_chapter[s["lesson_id"]].append(s)
    return plans, by_chapter


def main() -> None:
    sample = load_chapter(SAMPLE)
    plans, by_chapter = asyncio.run(fetch())
    if not by_chapter:
        sys.exit("no completed session of the simulated learner")
    out = {
        "policy": {
            "version": DEFAULT_POLICY.version,
            "weights": W,
            "independence": list(IND),
            "bands": list(DEFAULT_POLICY.bands),
        },
        "conformance": conformance(sample),
        "curves": curves(sample),
        "gates": gates(sample),
        "known_groups": known_groups(plans),
        "sensitivity": sensitivity(by_chapter),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for family, c in out["conformance"].items():
        if isinstance(c, dict):
            print(family, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()})
    for g in out["gates"]:
        print(
            f"{g['step']:62s} M={g['mastery']} conf={g['confidence']} level={g['level']} {g['state']} "
            f"pass={g['pass_now']} missing={g['missing']}"
        )
    for ch, rows in out["known_groups"].items():
        for style, r in rows.items():
            print(
                ch[-12:],
                style,
                r["passed"],
                "/",
                r["nodes"],
                "hints",
                r["hints"],
                "M",
                r["mastery_mean"],
                "level",
                r["level_mean"],
                "I",
                r["dims"].get("I"),
            )
    print("written", OUT.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
