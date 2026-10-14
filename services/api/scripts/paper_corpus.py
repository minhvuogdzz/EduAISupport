"""Numbers of the data sections of the paper: output docs/paper/data/corpus.json (read only).

The corpus the tutor teaches and retrieves from, as it was extracted from the teacher's documents:

- the documents and how each page was read (text layer, or read again by a model and checked);
- the item banks: questions cut from the exercise documents, answers checked exactly;
- the teaching plans: the graph, what each node holds, and what the review did with it;
- the drafts a model wrote for the plans and what the validator did with them.

Titles of documents are not written: only their kind, pages and sizes.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, defaultdict
from statistics import mean

from cavat import db
from cavat.config import REPO_ROOT, get_settings

OUT = REPO_ROOT / "docs/paper/data/corpus.json"
CHAPTERS = ("math-g5-decimals", "math-g5-area-triangle-trapezoid")


def depth_of(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Longest path from a source (a node with no prerequisite): the layer of the graph drawing."""
    parents: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        parents[b].append(a)
    depth: dict[str, int] = {}

    def of(n: str) -> int:
        if n not in depth:
            depth[n] = 1 + max((of(p) for p in parents[n]), default=-1)
        return depth[n]

    for n in nodes:
        of(n)
    return depth


async def main() -> None:
    database = db.get_db(get_settings())
    documents = await database["documents"].find({}).to_list(None)
    banks = await database["item_banks"].find({}).to_list(None)
    plans = await database["teaching_plans"].find({}).to_list(None)
    await db.close_client()

    out: dict = {"documents": {}, "banks": {}, "plans": {}}
    for chapter in CHAPTERS:
        docs = [d for d in documents if d.get("chapter_id") == chapter]
        reads = [p for d in docs for p in d.get("page_reads") or []]
        out["documents"][chapter] = {
            "n": len(docs),
            "by_kind": {
                k: {
                    "n": sum(1 for d in docs if d["kind"] == k),
                    "pages": sum(d["pages"] for d in docs if d["kind"] == k),
                    "syllables": sum(len((d.get("text") or "").split()) for d in docs if d["kind"] == k),
                }
                for k in sorted({d["kind"] for d in docs})
            },
            "pages": sum(d["pages"] for d in docs),
            "syllables": sum(len((d.get("text") or "").split()) for d in docs),
            "reads": {
                "pages": len(reads),
                "text_layer": sum(1 for p in reads if p["method"] == "pdf-text"),
                "ocr": sum(1 for p in reads if p["method"] == "ocr-gemini"),
                "reason": dict(Counter(p["reason"] or "NONE" for p in reads)),
                "needs_review": sum(1 for p in reads if p["status"] != "OK"),
                "numbers_added": sum(len(p.get("added") or []) for p in reads),
                "confirmed_pages": sum(1 for p in reads if p.get("note") == "CONFIRMED"),
                "disputed_numbers": sum(len(p.get("disputed") or []) for p in reads),
                "missing_numbers": sum(len(p.get("missing") or []) for p in reads),
            },
            "status": dict(Counter(d["status"] for d in docs)),
        }
    for bank in banks:
        items = bank["items"]
        checks = Counter()
        ok = Counter()
        for i in items:
            for f in i.get("findings") or []:
                checks[f["check"]] += 1
                ok[f["check"]] += bool(f["ok"])
        periods = Counter(p for i in items for p in (i.get("periods") or []))
        out["banks"][bank["chapter_id"]] = {
            "items": len(items),
            "status": dict(Counter(i["status"] for i in items)),
            "source": dict(Counter(i["source"] for i in items)),
            "stage": dict(Counter(i["stage"] for i in items)),
            "assessment": sum(bool(i["assessment"]) for i in items),
            "figure": sum(bool(i["figure"]) for i in items),
            "with_findings": sum(1 for i in items if i.get("findings")),
            "checks": {k: {"n": checks[k], "ok": ok[k]} for k in sorted(checks)},
            "unplaced": sum(1 for i in items if not i.get("periods") and not i["assessment"]),
            "per_period": dict(sorted(periods.items())),
            "sources": len(bank.get("sources") or []),
        }
    for plan in plans:
        pkg = plan["package"]
        lessons = plan["lessons"]
        nodes = pkg["nodes"]
        ids = [n["id"] for n in nodes]
        edges = [
            (r["source"], r["target"])
            for r in pkg["relations"]
            if r["type"] in ("PREREQUISITE", "APPLICATION")
        ]
        depth = depth_of(ids, edges)
        items = {i["id"]: i for lesson in lessons.values() for i in lesson["items"]}
        mis = [m for lesson in lessons.values() for m in lesson["misconceptions"]]
        decisions = list((plan.get("decisions") or {}).values())
        drafts = plan.get("drafts") or []
        by_kind: dict[str, dict] = {}
        for k in sorted({d["kind"] for d in drafts}):
            rows = [d for d in drafts if d["kind"] == k]
            by_kind[k] = {"n": len(rows), "ok": sum(bool(r["ok"]) for r in rows)}
        out["plans"][plan["chapter_id"]] = {
            "version": plan.get("current"),
            "nodes": len(nodes),
            "relations": dict(Counter(r["type"] for r in pkg["relations"])),
            "depth": max(depth.values()) + 1,
            "node_list": [
                {
                    "id": n["id"],
                    "name": n["name"],
                    "layer": n["layer"],
                    "depth": depth[n["id"]],
                    "theory": len(n["theory"]),
                    "examples": len(n["worked_examples"]),
                    "checks": len(n["checks"]),
                    "completion": len(n.get("completion") or []),
                    "practice": len(n["practice"]),
                    "transfer": len(n["transfer"]),
                    "key_ideas": len(n["explain"]["key_ideas"]),
                    "pass_rule": n["pass_rule"],
                    "prerequisites": [a for a, b in edges if b == n["id"]],
                }
                for n in nodes
            ],
            "edges": [
                {"source": r["source"], "target": r["target"], "type": r["type"]}
                for r in pkg["relations"]
                if r["type"] in ("PREREQUISITE", "APPLICATION")
            ],
            "items": {
                "n": len(items),
                "by_type": dict(Counter(i["answer"]["type"] for i in items.values())),
                "by_level": dict(sorted(Counter(i["cognitive_level"] for i in items.values()).items())),
                "by_purpose": dict(Counter(i["purpose"] for i in items.values())),
                "difficulty_mean": round(mean(i["difficulty"] for i in items.values()), 3),
                "with_hints": sum(1 for i in items.values() if i.get("hints")),
                "hints": sum(len(i.get("hints") or []) for i in items.values()),
                "wrong_answers_declared": sum(
                    len(i["answer"].get("wrong_answers") or {}) for i in items.values()
                ),
            },
            "assessment_items": len(plan.get("assessment") or []),
            "misconceptions": {
                "n": len(mis),
                "critical": sum(m["severity"] == "CRITICAL" for m in mis),
                "with_bug_rule": sum(bool(m.get("bug_rule")) for m in mis),
            },
            "drafts": {
                "n": len(drafts),
                "ok": sum(bool(d["ok"]) for d in drafts),
                "by_kind": by_kind,
                "by_model": dict(Counter(d["model"] for d in drafts)),
                "codes": dict(Counter(c for d in drafts for c in (d.get("codes") or [])).most_common()),
            },
            "decisions": {
                "n": len(decisions),
                "by_action": dict(Counter(d["action"] for d in decisions)),
                "by_target": dict(
                    Counter(
                        k.split(":")[0]
                        + ("/" + k.split("/")[1] if k.startswith("node:") and "/" in k else "")
                        for k in (plan.get("decisions") or {})
                    ).most_common()
                ),
                "by_reviewer": dict(
                    Counter("teacher" if not d["by"].startswith("claude") else "assistant" for d in decisions)
                ),
            },
            "left_out": len(plan.get("left_out") or []),
            "problems": len(plan.get("problems") or []),
            "published_versions": len(plan.get("published") or {}),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", OUT.relative_to(REPO_ROOT))


if __name__ == "__main__":
    asyncio.run(main())
