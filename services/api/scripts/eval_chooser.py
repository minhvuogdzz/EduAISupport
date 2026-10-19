"""How Qwen picks among the moves the policy allows, on many turns at once (AUTO-3, ``make eval-chooser``).

AUTO-2 measured the chooser inside sessions and saw 4 picks only: the chooser may spend the first half of
the 15 calls of a session (DI-62), and every session spends them all. This script measures the chooser on
its own, outside the session cap:

1. **Collect.** The simulated child of ``simulate_learner.py`` ("Vương") studies each chapter on templates
   only, in an in-memory database (the plans are copied from the database of .env, read-only; nothing is
   written). A recording chooser keeps every turn where the policy offered a choice, and picks nothing, so
   the sessions run on the policy's own moves.
2. **Ask.** Qwen (``ModelChooser``, the prompt of the sessions) picks on each turn kept, one call per turn,
   paced for the Groq free tier. Answers are cached in ``var/storage/reports/eval-chooser-cache.json``,
   so a second run costs no quota.
3. **Count.** Per kind of menu (the policy's move and the moves allowed): how often Qwen kept the policy's
   move, how often it picked another, how often it gave nothing. The report goes to ``evals/reports``
   with counts only, and reasons only for the chapter whose content is in the repo (CLAUDE.md: never
   commit the text of the teacher's documents).

``--collect-only`` stops after step 1 and spends nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from cavat.modules.tutor.chooser import CHOOSER_VERSION, Choice, describe
from cavat.modules.tutor.contracts import PolicyDecision
from cavat.modules.tutor.policy import MoveOption

REPO_CHAPTER = "math-g5-decimals"  # its content is docs/pedagogy in the repo; the other is the teacher's
REPORTS = Path(__file__).resolve().parents[3] / "evals" / "reports"


@dataclass(frozen=True)
class Case:
    """One turn where the policy offered a choice, with what the chooser sees."""

    chapter: str
    item_id: str
    turn: int
    rules: tuple[str, ...]  # the rule ids of the policy's own move
    moves: tuple[str, ...]  # the moves offered, "A" first
    descriptions: tuple[str, ...]
    stem: str
    last_tutor: str
    said: str
    decisions: tuple[PolicyDecision, ...] = ()  # the moves themselves, for the model's menu

    @property
    def kind(self) -> str:
        """The menu: the policy's move, then the moves allowed instead ("PROBE → HINT")."""
        return f"{self.moves[0]} → {' / '.join(self.moves[1:])}"

    @property
    def key(self) -> str:
        raw = json.dumps([CHOOSER_VERSION, self.descriptions, self.stem, self.last_tutor, self.said])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def menu(self) -> list[MoveOption]:
        """The menu the session offered (ids A, B, C), as the model reads it."""
        return [MoveOption(chr(65 + i), d) for i, d in enumerate(self.decisions)]


@dataclass
class Recorder:
    """A chooser that keeps the turn and picks nothing: the session goes on with the policy's move."""

    chapter: str = ""
    cases: list[Case] = field(default_factory=list)

    def choose(self, *, menu: Sequence[MoveOption], stem: str, last_tutor: str, said: str, turn: int):
        a = menu[0].decision
        self.cases.append(
            Case(
                chapter=self.chapter,
                item_id="",
                turn=turn,
                rules=tuple(a.rule_ids),
                moves=tuple(o.decision.move.value for o in menu),
                descriptions=tuple(describe(o.decision) for o in menu),
                stem=stem,
                last_tutor=last_tutor,
                said=said,
                decisions=tuple(o.decision for o in menu),
            )
        )
        return None


def unique(cases: Iterable[Case]) -> list[Case]:
    """The same menu on the same words is asked once (a replay asks the recorder again)."""
    seen: dict[str, Case] = {}
    for c in cases:
        seen.setdefault(c.key, c)
    return list(seen.values())


def summarize(cases: Sequence[Case], picks: Mapping[str, Choice | None]) -> dict[str, Any]:
    """Per kind of menu: turns, kept (A), other (B/C), none (no answer or an id off the menu)."""
    rows: dict[str, Counter] = defaultdict(Counter)
    for c in cases:
        pick = picks.get(c.key)
        ids = [chr(65 + i) for i in range(len(c.moves))]
        if pick is None or pick.option_id not in ids:
            outcome = "none"
        elif pick.option_id == "A":
            outcome = "kept"
        else:
            outcome = "other"
        rows[c.kind][outcome] += 1
        rows[c.kind]["turns"] += 1
    total = Counter()
    for r in rows.values():
        total.update(r)
    return {
        "turns": total["turns"],
        "kept": total["kept"],
        "other": total["other"],
        "none": total["none"],
        "by_kind": {k: dict(v) for k, v in sorted(rows.items(), key=lambda kv: -kv[1]["turns"])},
    }


def report(cases: Sequence[Case], picks: Mapping[str, Choice | None], meta: Mapping[str, Any]) -> str:
    """The Markdown report: counts per menu, and reasons for the repo chapter only."""
    s = summarize(cases, picks)
    answered = s["kept"] + s["other"]
    share = f"{100 * s['other'] / answered:.0f}%" if answered else "–"
    lines = [
        f"# Bộ chọn nước đi (AUTO-3, `{CHOOSER_VERSION}`), {meta['date']}",
        "",
        f"- Lượt có lựa chọn thu được: {meta['collected']} (khác nhau: {s['turns']}), "
        f"từ {meta['sessions']} buổi học mô phỏng chạy bằng câu mẫu, trong bộ nhớ.",
        f"- Qwen trả lời {answered}/{s['turns']} lượt: giữ nước của chính sách {s['kept']}, "
        f"chọn nước khác {s['other']} ({share} số lượt trả lời), không trả lời được {s['none']}.",
        f"- Lượt gọi model đã tiêu: {meta['calls']} (lần chạy này), lấy từ bộ đệm: {meta['cached']}.",
        "",
        "| Thực đơn (nước của chính sách → nước được phép) | Lượt | Giữ | Khác | Không trả lời |",
        "|---|---|---|---|---|",
    ]
    for kind, r in s["by_kind"].items():
        counts = " | ".join(str(r.get(k, 0)) for k in ("turns", "kept", "other", "none"))
        lines.append(f"| {kind} | {counts} |")
    reasons = [
        (c.kind, c.moves[ord(p.option_id) - 65], p.reason)
        for c in cases
        if c.chapter == REPO_CHAPTER
        and (p := picks.get(c.key)) is not None
        and p.option_id in [chr(65 + i) for i in range(len(c.moves))]
        and p.reason
    ]
    if reasons:
        lines += ["", f"## Lý do Qwen nêu (chương {REPO_CHAPTER}, nội dung có trong repo)", ""]
        shown: Counter = Counter()
        for kind, move, reason in reasons:
            if shown[(kind, move)] >= 2:
                continue
            shown[(kind, move)] += 1
            lines.append(f"- {kind}, Qwen chọn {move}: {reason}")
    return "\n".join(lines) + "\n"


def ask(cases: Sequence[Case], router: Any, cache_file: Path, pause_s: float) -> tuple[dict, int, int]:
    """Qwen's pick on each case, cached by case; returns (picks, calls spent, cases from the cache)."""
    from cavat.modules.tutor.chooser import ModelChooser

    cache: dict[str, Any] = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    picks: dict[str, Choice | None] = {}
    spent = cached = 0
    for n, c in enumerate(cases, 1):
        if c.key in cache:
            hit = cache[c.key]
            picks[c.key] = Choice(hit["option_id"], hit["reason"]) if hit else None
            cached += 1
            continue
        chooser = ModelChooser(router, calls_used=0, max_calls=10**6)
        pick = chooser.choose(menu=c.menu(), stem=c.stem, last_tutor=c.last_tutor, said=c.said, turn=c.turn)
        spent += chooser.calls_made
        picks[c.key] = pick
        if pick is not None or chooser.calls_made:  # a quota refusal is not cached: ask again next run
            cache[c.key] = {"option_id": pick.option_id, "reason": pick.reason} if pick else None
            cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        print(f"  {n}/{len(cases)} {c.kind}: {pick.option_id if pick else '–'}", flush=True)
        time.sleep(pause_s)
    return picks, spent, cached


def collect(chapters: Sequence[str], sessions: int, turns: int) -> tuple[list[Case], int]:
    """Run the simulated child on templates with the recording chooser; returns (cases, sessions run)."""
    from functools import wraps

    import simulate_learner as sim
    from cavat.config import get_settings
    from cavat.main import app
    from cavat.modules.session import chapter_service
    from cavat.modules.session.api import account_name, student_identity
    from fastapi.testclient import TestClient

    recorder = Recorder()
    apply = chapter_service.apply_command

    @wraps(apply)
    def recorded(*args, **kwargs):
        kwargs["chooser"] = recorder  # the templates-only API passes no chooser; this one only records
        return apply(*args, **kwargs)

    chapter_service.apply_command = recorded
    sim._in_memory(get_settings())  # templates only: no model call while collecting
    app.dependency_overrides[student_identity] = lambda: "sim-auto3"
    app.dependency_overrides[account_name] = lambda: "Vuong"
    run = 0
    with TestClient(app) as client:
        for chapter_id in chapters:
            print(chapter_id)
            recorder.chapter = chapter_id
            run += len(sim.run(client, chapter_id, "sim-auto3", sessions, turns))
    chapter_service.apply_command = apply
    return recorder.cases, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sessions", type=int, default=2, help="simulated sessions per chapter")
    parser.add_argument("--turns", type=int, default=400, help="turns per session at most")
    parser.add_argument("--max-cases", type=int, default=80, help="turns asked to Qwen at most")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between two model calls")
    parser.add_argument("--collect-only", action="store_true", help="count the turns, call no model")
    args = parser.parse_args()

    import simulate_learner as sim
    from cavat.config import get_settings

    cases_all, run = collect(sim.CHAPTERS, args.sessions, args.turns)
    cases = unique(cases_all)
    kinds = Counter(c.kind for c in cases)
    print(f"{len(cases_all)} lượt có lựa chọn ({len(cases)} khác nhau) trong {run} buổi: {dict(kinds)}")
    if args.collect_only:
        return
    # Spread the turns asked over the kinds of menu, so a frequent kind does not take the whole budget.
    by_kind: dict[str, list[Case]] = defaultdict(list)
    for c in cases:
        by_kind[c.kind].append(c)
    asked: list[Case] = []
    while len(asked) < min(args.max_cases, len(cases)):
        for group in by_kind.values():
            if group and len(asked) < args.max_cases:
                asked.append(group.pop(0))
    from cavat.modules.ai_gateway.router import build_router

    settings = get_settings()
    out = settings.storage_dir / "reports"
    out.mkdir(parents=True, exist_ok=True)
    picks, spent, cached = ask(asked, build_router(), out / "eval-chooser-cache.json", args.pause)
    meta = {"date": date.today().isoformat(), "collected": len(cases_all), "sessions": run}
    text = report(asked, picks, {**meta, "calls": spent, "cached": cached})
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{meta['date']}-chooser.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"Báo cáo: {path}")


if __name__ == "__main__":
    sys.exit(main())
