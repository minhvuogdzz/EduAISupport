"""Bounded live BRAIN-2 regression; synthetic questions, in-memory index, no database access.

python scripts/eval_brain2.py --live [--env-file /path/to/private/.env]
Writes JSON under ignored var/storage/reports; never prints keys or learner records.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import monotonic

from cavat.config import REPO_ROOT, Settings
from cavat.modules.ai_gateway.router import RecordingRouter, build_router
from cavat.modules.rag.chunks import Chunk, chapter_chunks
from cavat.modules.rag.retrieve import RagIndex
from cavat.modules.session.chapter_service import chapters
from cavat.modules.teaching.grounded import GROUNDED_VERSION, GroundedSpeaker
from cavat.modules.teaching.official_web import OfficialEducation
from cavat.modules.tutor.brain import BRAIN_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    router = RecordingRouter(build_router(settings, for_eval=True))
    chapter = chapters()["math-g5-decimals"]
    index = RagIndex(
        chapter_chunks(chapter), None, {n.id: chapter.prerequisites(n.id) for n in chapter.nodes}
    )
    gap = RagIndex(
        [
            Chunk(
                "scope",
                "Ý bài đang học.",
                "theory",
                "math-g5-decimals",
                "frac",
                "chapter",
                "Phân số thập phân",
                True,
            )
        ],
        None,
        {"frac": set()},
    )
    web = OfficialEducation(cache_dir=settings.storage_dir / "web")
    cases = [
        ("denominator", "mẫu số là gì cô", "KC-DEC-FRAC", index, ("LLM", "WEB")),
        ("same_value", "Sao 0,30 và 0,3 lại bằng nhau?", "KC-DEC-EQ", index, ("LLM",)),
        ("fresh_example", "Cho con một ví dụ khác về số thập phân bằng nhau", "KC-DEC-EQ", index, ("LLM",)),
        ("official_gap", "phân số thập phân là gì", "frac", gap, ("WEB",)),
    ]
    rows = []
    for label, question, node, corpus, expected in cases:
        speaker = GroundedSpeaker(corpus, router, web=web, order=chapter.topological_order())
        started = monotonic()
        turn = speaker.answer(question, node_id=node, pending=None)
        spoken = turn.spoken
        row = {
            "case": label,
            "question": question,
            "kind": turn.kind,
            "source": spoken.source if spoken else None,
            "text": spoken.text if spoken else "",
            "rejected": spoken.rejected if spoken else (),
            "calls": speaker.calls_made,
            "seconds": round(monotonic() - started, 2),
            "url": turn.web.url if turn.web else None,
            "expected_sources": expected,
            "ok": spoken is not None and spoken.source in expected,
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = {
        "brain": BRAIN_VERSION,
        "grounded": GROUNDED_VERSION,
        "cases": rows,
        "models": [
            c.outcome.result.model if c.outcome.result else str(c.outcome.fallback_reason)
            for c in router.calls
        ],
    }
    path = REPO_ROOT / "var/storage/reports/brain2-live.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report: {path}")
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
