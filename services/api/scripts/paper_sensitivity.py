"""Sensitivity of the pedagogical re-ranking factors (kappa_m and gamma of the paper) on frozen sets.

Read only: the database of services/api/.env is read, nothing is written there; the vectors come from
the cache in var/storage/rag (no quota is spent). Output: docs/paper/data/sensitivity.json.

The factors are declared interpretations (DI-17, DI-50), chosen by hand from what each teaching mode needs and
never fitted on a question set. This script moves each one on its own, the others at their production value:

- kappa_m (``KIND_FACTOR``): every factor raised to a power s (s = 0: all 1, no kind preference; s = 1:
  production; s = 2: the preference doubled in log scale);
- gamma (``MISCONCEPTION_FACTOR``, ``DEFINES_FACTOR``): values around the production ones, 1.0 being "off".

For each setting: Hit@3 and MRR on the in-scope questions of v2, v3 and v4 (production configuration,
routing on).
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paper_rag as pr  # noqa: E402
from cavat.config import REPO_ROOT  # noqa: E402
from cavat.modules.rag import retrieve as rt  # noqa: E402
from cavat.modules.rag.evaluate import load_cases  # noqa: E402
from cavat.modules.session import chapter_service  # noqa: E402

OUT = REPO_ROOT / "docs/paper/data/sensitivity.json"
SETS = ("published_holdout_v2", "published_holdout_v3", "published_holdout_v4")
KAPPA_POWERS = (0.0, 0.5, 1.0, 1.5, 2.0)
MISCONCEPTION = (1.0, 1.25, 1.5, 2.0)
DEFINES = (1.0, 1.3, 1.6, 2.0)


PREFERRED: dict[str, str] = {}  # the kind each mode asks for first, from the production factors


def run(index, cases, orders) -> dict:
    """Hit@3 and MRR (the rank of the first relevant passage: any passage of the period counts, so the kind of
    passage does not move it) and what the factors are for: the share of questions whose first passage is of
    the kind the mode asks for (``kind1``), and, for the questions with a detected misconception, the share
    whose first passage is its note (``note1``)."""
    out = {}
    for name in SETS:
        pairs = [
            (
                c,
                pr.detail(
                    index, c, pr.PRODUCTION, order=next((o for o in orders.values() if c.node in o), None)
                ),
            )
            for c in cases[name]
        ]
        rows = [r for _, r in pairs]
        m = pr.metrics(rows)
        scoped = [(c, r) for c, r in pairs if r["relevant"] and r["top"]]
        kind = [r["top"][0]["kind"] == PREFERRED[r["mode"]] for c, r in scoped if r["mode"] in PREFERRED]
        note = [r["top"][0]["kind"] == "misconception_note" for c, r in scoped if c.misconception]
        out[name] = {
            "n": m["n"],
            "hit3": round(m["hit3"], 3),
            "mrr": round(m["mrr"], 3),
            "kind1": round(sum(kind) / len(kind), 3) if kind else None,
            "n_kind": len(kind),
            "note1": round(sum(note) / len(note), 3) if note else None,
            "n_note": len(note),
        }
    return out


def main() -> None:
    indexes, embedder = asyncio.run(pr.build_indexes())
    index = indexes["published"]
    cases = {name: load_cases(pr.SETS[name][1]) for name in SETS}
    for name in SETS:
        embedder.embed(sorted({c.q for c in cases[name]}), "RETRIEVAL_QUERY")
    orders = {cid: c.topological_order() for cid, c in chapter_service.chapters().items()}
    base_kind = copy.deepcopy(rt.KIND_FACTOR)
    base = (rt.MISCONCEPTION_FACTOR, rt.DEFINES_FACTOR)
    PREFERRED.update({mode: max(kinds, key=kinds.get) for mode, kinds in base_kind.items() if kinds})
    result: dict = {
        "production": run(index, cases, orders),
        "kappa_power": {},
        "misconception": {},
        "defines": {},
    }
    try:
        for s in KAPPA_POWERS:
            for mode, kinds in base_kind.items():
                rt.KIND_FACTOR[mode] = {k: v**s for k, v in kinds.items()}
            result["kappa_power"][str(s)] = run(index, cases, orders)
        for mode, kinds in base_kind.items():
            rt.KIND_FACTOR[mode] = dict(kinds)
        for v in MISCONCEPTION:
            rt.MISCONCEPTION_FACTOR = v
            result["misconception"][str(v)] = run(index, cases, orders)
        rt.MISCONCEPTION_FACTOR = base[0]
        for v in DEFINES:
            rt.DEFINES_FACTOR = v
            result["defines"][str(v)] = run(index, cases, orders)
    finally:
        rt.KIND_FACTOR.clear()
        rt.KIND_FACTOR.update(base_kind)
        rt.MISCONCEPTION_FACTOR, rt.DEFINES_FACTOR = base
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for group in ("production", "kappa_power", "misconception", "defines"):
        print(group)
        data = result[group] if group != "production" else {"-": result[group]}
        for key, row in data.items():
            print(
                " ",
                key,
                {k.split("_")[-1]: (v["hit3"], v["mrr"], v["kind1"], v["note1"]) for k, v in row.items()},
            )


if __name__ == "__main__":
    main()
