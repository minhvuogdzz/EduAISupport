"""Numbers of the RAG sections of the paper (docs/paper): `make paper-data` runs this and the two scripts
next to it. Read only: the database of services/api/.env is read, nothing is written there; the vectors come
from the cache in var/storage/rag (the quota is not spent again). Output: docs/paper/data/rag.json.

What it measures, per question set and configuration (keywords, semantics, hybrid, each with and without the
pedagogical re-ranking), with and without the topic routing of DI-57:

- the rank of the first relevant passage (Hit@k for k = 1..10, Recall@3/5, MRR), per question;
- what the tutor does with the question (answer, say "bài sau", keep it for the teacher), per question;
- the best cosine of the passages handed to the tutor, for the grounding threshold;
- the corpus: passages by kind, length, tagging to nodes;
- the sensitivity of Hit@3 and of the false-answer rate to the routing margin;
- the ablation of one component at a time (RAG-5): leave one out of the configuration that runs, or add one
  to the plain hybrid, paired by question against the configuration that runs;
- 95% intervals (Wilson for proportions, paired bootstrap for differences) and exact McNemar tests.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date
from statistics import mean, median

from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.rag import retrieve as retrieve_module
from cavat.modules.rag.chunks import syllables
from cavat.modules.rag.evaluate import ABLATION, ALL_CONFIGS, CONFIGS, Case, expand, load_cases
from cavat.modules.rag.service import RagService, default_embedder
from cavat.modules.session import chapter_service
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.teaching.grounded import ANSWER_CHARS, ANSWER_PASSAGES

OUT = REPO_ROOT / "docs/paper/data/rag.json"
DATA = REPO_ROOT / "evals/datasets"
SEED = 20261013
BOOTSTRAP = 10_000
SWEEP = (0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 9.0)  # 9.0: routing off
PRODUCTION = "hybrid+rerank"
SETS = {
    "published_tune": ("published", DATA / "rag-published-v1.yaml"),
    "published_holdout_v1": ("published", DATA / "rag-published-holdout-v1.yaml"),
    "published_holdout_v2": ("published", DATA / "rag-published-holdout-v2.yaml"),
    # RAG-6: written as children type, frozen (tag eval-freeze-rag-v3) before the DI-50 fix
    "published_holdout_v3": ("published", DATA / "rag-published-holdout-v3.yaml"),
    "sample_tune": ("sample", DATA / "rag-decimals-v1.yaml"),
    "sample_holdout": ("sample", DATA / "rag-decimals-holdout-v1.yaml"),
}


# --------------------------------------------------------------------------- statistics


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values: list[float], rng: random.Random, b: int = BOOTSTRAP) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    n = len(values)
    means = sorted(mean(values[rng.randrange(n)] for _ in range(n)) for _ in range(b))
    return (means[int(0.025 * b)], means[int(0.975 * b) - 1])


def paired_bootstrap(a: list[float], c: list[float], rng: random.Random, b: int = BOOTSTRAP):
    """Mean of (c - a) and its 95% interval, resampling questions (pairs)."""
    n = len(a)
    if n == 0:
        return (0.0, 0.0, 0.0)
    diff = [y - x for x, y in zip(a, c, strict=True)]
    means = sorted(mean(diff[rng.randrange(n)] for _ in range(n)) for _ in range(b))
    return (mean(diff), means[int(0.025 * b)], means[int(0.975 * b) - 1])


def mcnemar_exact(wrong_to_right: int, right_to_wrong: int) -> float:
    """Two-sided exact p-value of the discordant pairs (the binomial test with p = 1/2)."""
    n = wrong_to_right + right_to_wrong
    if n == 0:
        return 1.0
    k = min(wrong_to_right, right_to_wrong)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


# --------------------------------------------------------------------------- indexes


async def build_indexes():
    settings = get_settings()
    embedder = default_embedder()
    if embedder is None:
        sys.exit("GEMINI_API_KEY is not set: the vectors of the paper come from the cache of a live run")
    database = db.get_db(settings)
    await chapter_service.load_published(database, DEMO_SCHOOL_ID)
    published = await RagService(DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: embedder).current(
        database
    )
    await db.close_client()
    sample_chapters = {cid: c for cid, (c, _) in chapter_service.chapter_sources().items()}
    sample = await RagService(DEMO_SCHOOL_ID, lambda: sample_chapters, embedder=lambda: embedder).current(
        InMemoryDatabase()
    )
    for name, index in (("published", published), ("sample", sample)):
        if index.semantic_error:
            sys.exit(f"{name}: the embedding model failed: {index.semantic_error}")
    return {"published": published, "sample": sample}, embedder


def corpus_stats(index) -> dict:
    chunks = index.chunks
    by_kind: dict[str, list[int]] = defaultdict(list)
    for c in chunks:
        by_kind[c.kind].append(syllables(c.text))

    def describe(values: list[int]) -> dict:
        ordered = sorted(values)
        at = lambda q: ordered[int(q * (len(ordered) - 1))]  # noqa: E731
        return {
            "n": len(values),
            "mean": round(mean(values), 1),
            "median": median(values),
            "p10": at(0.1),
            "q1": at(0.25),
            "q3": at(0.75),
            "p90": at(0.9),
            "max": max(values),
            "total": sum(values),
            "lengths": ordered,
        }

    passages = [c for c in chunks if c.kind == "source_passage"]
    per_node: Counter[str] = Counter()
    for c in chunks:
        if c.node_id:
            per_node[(c.node_id, c.kind)] += 1
    nodes = sorted({c.node_id for c in chunks if c.node_id})
    return {
        "chunks": len(chunks),
        "by_kind": {k: describe(v) for k, v in sorted(by_kind.items())},
        "by_chapter": dict(Counter(c.chapter_id for c in chunks)),
        "passages": {
            "n": len(passages),
            "tied": sum(1 for c in passages if c.node_id),
            "spread": sum(1 for c in passages if not c.node_id and c.candidates),
            "unassigned": sum(1 for c in passages if not c.node_id and not c.candidates),
            "by_chapter": dict(Counter(c.chapter_id for c in passages)),
            "by_document": len({c.document_id for c in passages}),
            "with_page": sum(1 for c in passages if c.page),
        },
        "per_node": {n: {kind: per_node.get((n, kind), 0) for kind in sorted(by_kind)} for n in nodes},
        "vectors": {
            "model": index.embedder.name if index.embedder else None,
            "dims": int(index.vectors.shape[1]),
        }
        if index.vectors is not None
        else None,
        "graph": {
            "nodes": len(index.graph),
            "edges": sum(len(v) for v in index.graph.values()),
        },
    }


# --------------------------------------------------------------------------- retrieval runs


# A conventional RAG over the whole chapter: no period of the graph given (no scope, no distance weight, no
# routing, no "later period" check). The comparison that says what the graph adds.
FLAT = {
    "flat-hybrid": {"keyword": True, "semantic": True, "rerank": False, "route": False, "define": False},
    "flat-hybrid+rerank": {"keyword": True, "semantic": True, "rerank": True, "route": True, "define": True},
}


def detail(index, case: Case, config: str, k: int = 3, order: list[str] | None = None) -> dict:
    flat = config in FLAT
    found = index.retrieve(
        case.q,
        node_id=None if flat else case.node,
        mode=case.mode,
        used=case.used,
        misconception_id=case.misconception,
        k=k,
        max_chars=100_000,
        **(FLAT[config] if flat else ALL_CONFIGS[config]),
    )
    ahead = None
    if order and case.node in order:
        # a chosen passage of a period after the one being learnt: what the tutor would teach ahead
        ahead = any(
            s.chunk.node_id in order and order.index(s.chunk.node_id) > order.index(case.node)
            for s in found.results
            if s.chunk.node_id
        )
    ranking = [s.chunk.chunk_id for s in found.ranked]
    relevant = expand(case.relevant, index)
    first = next((i for i, cid in enumerate(ranking, 1) if cid in relevant), None)
    top = [
        {"id": s.chunk.chunk_id, "kind": s.chunk.kind, "node": s.chunk.node_id, "cosine": round(s.cosine, 3)}
        for s in found.ranked[:3]
    ]
    return {
        "id": case.id,
        "group": case.group,
        "style": case.style,
        "q": case.q,
        "node": case.node,
        "mode": found.mode,
        "relevant": len(relevant),
        "first": first,
        "grounded": found.grounded,
        "best_cosine": round(max((s.cosine for s in found.results), default=0.0), 4),
        "best_coverage": round(max((s.coverage for s in found.results), default=0.0), 4),
        "ahead": ahead,
        "top": top,
        "reasons": [list(s.reasons) for s in found.ranked[:3]],
    }


def decide(index, case: Case, order_of: dict[str, list[str]]) -> dict:
    """What the tutor does with a question (``GroundedSpeaker.answer`` before the model is called)."""
    order = next((o for o in order_of.values() if case.node in o), [])
    later, scoped = index.question(case.q, case.node, order, k=ANSWER_PASSAGES, max_chars=ANSWER_CHARS)
    outcome = "LATER" if later else ("ANSWER" if scoped.grounded else "PARKED")
    return {"id": case.id, "group": case.group, "outcome": outcome, "later_node": later, "node": case.node}


def metrics(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["relevant"]]
    n = len(scored)
    if not n:
        return {"n": 0}

    def hit(r: dict, k: int) -> bool:
        return r["first"] is not None and r["first"] <= k

    return {
        "n": n,
        "hit1": mean(hit(r, 1) for r in scored),
        "hit3": mean(hit(r, 3) for r in scored),
        "hit5": mean(hit(r, 5) for r in scored),
        "mrr": mean(1 / r["first"] if r["first"] else 0.0 for r in scored),
        "hit_k": {k: sum(hit(r, k) for r in scored) / n for k in range(1, 11)},
    }


def with_routing(margin: float):
    """Context: the routing margins of retrieve.py set for a block (cosine and keyword-coverage together)."""

    class _Margin:
        def __enter__(self):
            self.saved = (retrieve_module.ROUTE_MARGIN_COSINE, retrieve_module.ROUTE_MARGIN_COVERAGE)
            retrieve_module.ROUTE_MARGIN_COSINE = margin
            retrieve_module.ROUTE_MARGIN_COVERAGE = margin if margin > 1 else margin * 7.5
            return self

        def __exit__(self, *exc):
            retrieve_module.ROUTE_MARGIN_COSINE, retrieve_module.ROUTE_MARGIN_COVERAGE = self.saved

    return _Margin()


def main() -> None:
    indexes, embedder = asyncio.run(build_indexes())
    rng = random.Random(SEED)
    cases = {name: load_cases(path) for name, (_, path) in SETS.items()}
    # every question vector in the cache already (batched, cached): a miss would call the model once
    for name in SETS:
        embedder.embed(sorted({c.q for c in cases[name]}), "RETRIEVAL_QUERY")
    orders = {cid: c.topological_order() for cid, c in chapter_service.chapters().items()}
    sample_orders = {cid: c.topological_order() for cid, (c, _) in chapter_service.chapter_sources().items()}
    result: dict = {
        "meta": {
            "date": date.today().isoformat(),
            "seed": SEED,
            "bootstrap": BOOTSTRAP,
            "embedder": embedder.name,
            "production": PRODUCTION,
            "route_margin": retrieve_module.ROUTE_MARGIN_COSINE,
        },
        "corpus": {k: corpus_stats(v) for k, v in indexes.items()},
        "sets": {},
    }
    production_margin = retrieve_module.ROUTE_MARGIN_COSINE

    for name, (which, _) in SETS.items():
        index = indexes[which]
        entry: dict = {
            "n": len(cases[name]),
            "in_scope": sum(1 for c in cases[name] if c.relevant),
            "groups": dict(Counter(c.group for c in cases[name])),
            "configs": {},
        }
        order_of = orders if which == "published" else sample_orders
        for config in (*ALL_CONFIGS, *FLAT):
            for routing, margin in (("on", production_margin), ("off", 9.0)):
                if routing == "off" and (which != "published" or config in FLAT or config in ABLATION):
                    continue  # the routing is not part of the sample-chapter run of `make eval-rag`
                with with_routing(margin):
                    rows = [
                        detail(
                            index,
                            c,
                            config,
                            order=next((o for o in order_of.values() if c.node in o), None),
                        )
                        for c in cases[name]
                    ]
                entry["configs"].setdefault(config, {})[routing] = {"rows": rows, "metrics": metrics(rows)}
        # What the tutor does, with and without routing (production configuration).
        for routing, margin in (("on", production_margin), ("off", 9.0)):
            if routing == "off" and which != "published":
                continue
            with with_routing(margin):
                entry.setdefault("decisions", {})[routing] = [decide(index, c, order_of) for c in cases[name]]
        result["sets"][name] = entry

    # Retrieval traces of a few questions, with and without the routing: every signal of the top passages.
    def trace(index, case: Case, margin: float) -> list[dict]:
        with with_routing(margin):
            found = index.retrieve(
                case.q,
                node_id=case.node,
                mode=case.mode,
                used=case.used,
                misconception_id=case.misconception,
                k=3,
                max_chars=100_000,
                **CONFIGS[PRODUCTION],
            )
        relevant = expand(case.relevant, index)
        return [
            {
                "rank": r,
                "kind": sc.chunk.kind,
                "node": sc.chunk.node_id,
                "relevant": sc.chunk.chunk_id in relevant,
                "bm25_rank": sc.bm25_rank,
                "cos_rank": sc.cosine_rank,
                "cosine": round(sc.cosine, 3),
                "distance": sc.distance,
                "fused": round(sc.fused, 5),
                "final": round(sc.final, 5),
                "reasons": list(sc.reasons),
            }
            for r, sc in enumerate(found.ranked[:5], 1)
        ]

    traces = {}
    by_id = {c.id: c for c in cases["published_holdout_v2"]}
    for qid in ("V05", "V13", "V12"):
        case = by_id[qid]
        traces[qid] = {
            "q": case.q,
            "node": case.node,
            "group": case.group,
            "relevant_nodes": [lab.removesuffix(":*") for lab in case.relevant],
            "off": trace(indexes["published"], case, 9.0),
            "on": trace(indexes["published"], case, production_margin),
        }
    result["traces"] = traces

    # Sensitivity of the routing margin: in-scope Hit@3 and out-of-scope false answers.
    sweep = []
    for margin in SWEEP:
        row: dict = {"margin": margin}
        for name in (
            "published_tune",
            "published_holdout_v1",
            "published_holdout_v2",
            "published_holdout_v3",
        ):
            index = indexes["published"]
            with with_routing(margin):
                rows = [detail(index, c, PRODUCTION) for c in cases[name]]
                dec = [decide(index, c, orders) for c in cases[name]]
            m = metrics(rows)
            out_of_scope = [d for d, c in zip(dec, cases[name], strict=True) if not c.relevant]
            row[name] = {
                "hit3": m["hit3"],
                "mrr": m["mrr"],
                "false_answers": sum(d["outcome"] == "ANSWER" for d in out_of_scope),
                "out_of_scope": len(out_of_scope),
                "answered": sum(
                    d["outcome"] == "ANSWER" for d, c in zip(dec, cases[name], strict=True) if c.relevant
                ),
                "in_scope": m["n"],
            }
        sweep.append(row)
    result["sweep"] = sweep

    # Statistics of the paired comparisons that the paper reports.
    stats: dict = {}
    for name in ("published_tune", "published_holdout_v1", "published_holdout_v2", "published_holdout_v3"):
        before = result["sets"][name]["configs"][PRODUCTION]["off"]["rows"]
        after = result["sets"][name]["configs"][PRODUCTION]["on"]["rows"]
        pairs = [(b, a) for b, a in zip(before, after, strict=True) if b["relevant"]]

        def hit3(r: dict) -> float:
            return 1.0 if r["first"] is not None and r["first"] <= 3 else 0.0

        def rr(r: dict) -> float:
            return 1 / r["first"] if r["first"] else 0.0

        fixed = sum(1 for b, a in pairs if not hit3(b) and hit3(a))
        broken = sum(1 for b, a in pairs if hit3(b) and not hit3(a))
        stats[name] = {
            "n": len(pairs),
            "hit3_before": mean(hit3(b) for b, _ in pairs),
            "hit3_after": mean(hit3(a) for _, a in pairs),
            "hit3_before_ci": wilson(sum(hit3(b) for b, _ in pairs), len(pairs)),
            "hit3_after_ci": wilson(sum(hit3(a) for _, a in pairs), len(pairs)),
            "delta_hit3": paired_bootstrap([hit3(b) for b, _ in pairs], [hit3(a) for _, a in pairs], rng),
            "delta_mrr": paired_bootstrap([rr(b) for b, _ in pairs], [rr(a) for _, a in pairs], rng),
            "mcnemar": {"fixed": fixed, "broken": broken, "p": mcnemar_exact(fixed, broken)},
            "mrr_before_ci": bootstrap_ci([rr(b) for b, _ in pairs], rng),
            "mrr_after_ci": bootstrap_ci([rr(a) for _, a in pairs], rng),
        }
    # Configuration contrasts on the frozen holdout (after routing).
    rows_of = {c: result["sets"]["published_holdout_v2"]["configs"][c]["on"]["rows"] for c in CONFIGS}
    contrasts = {}
    for a_name, b_name in (
        ("keyword", "hybrid"),
        ("hybrid", "hybrid+rerank"),
        ("keyword+rerank", "hybrid+rerank"),
        ("semantic", "hybrid+rerank"),
    ):
        a = [r for r in rows_of[a_name] if r["relevant"]]
        b = [r for r in rows_of[b_name] if r["relevant"]]
        ra = [1 / r["first"] if r["first"] else 0.0 for r in a]
        rb = [1 / r["first"] if r["first"] else 0.0 for r in b]
        ha = [1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in a]
        hb = [1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in b]
        contrasts[f"{a_name}->{b_name}"] = {
            "delta_mrr": paired_bootstrap(ra, rb, rng),
            "delta_hit3": paired_bootstrap(ha, hb, rng),
            "mcnemar_p": mcnemar_exact(
                sum(1 for x, y in zip(ha, hb, strict=True) if not x and y),
                sum(1 for x, y in zip(ha, hb, strict=True) if x and not y),
            ),
        }
    stats["contrasts_v2"] = contrasts
    # What the graph adds to a conventional RAG: in-scope retrieval, teaching ahead, answering a later period.
    flat_stats = {}
    for name in ("published_tune", "published_holdout_v1", "published_holdout_v2", "published_holdout_v3"):
        entry = {}
        for config in (PRODUCTION, *FLAT):
            rows = result["sets"][name]["configs"][config]["on"]["rows"]
            on = [r for r in rows if r["relevant"]]
            later = [r for r in rows if r["group"] == "bai-sau"]
            off = [r for r in rows if r["group"] in ("lac-de-toan", "lac-de")]
            m = metrics(rows)
            entry[config] = {
                "n": m["n"],
                "hit3": m["hit3"],
                "mrr": m["mrr"],
                "ahead": sum(bool(r["ahead"]) for r in rows if r["ahead"] is not None),
                "ahead_n": sum(r["ahead"] is not None for r in rows),
                "ahead_in_scope": sum(bool(r["ahead"]) for r in on if r["ahead"] is not None),
                "in_scope_n": len(on),
                "later_n": len(later),
                "later_answered": sum(r["grounded"] for r in later),
                "off_n": len(off),
                "off_answered": sum(r["grounded"] for r in off),
            }
        flat_stats[name] = entry
    stats["flat"] = flat_stats
    # Production against the conventional RAG, paired by question, on each published set and on all of them.
    versus: dict = {}
    for flat_name in FLAT:
        groups = {
            name: [name]
            for name in (
                "published_tune",
                "published_holdout_v1",
                "published_holdout_v2",
                "published_holdout_v3",
            )
        }
        groups["all_published"] = list(groups)
        groups["heldout_only"] = ["published_holdout_v2"]
        for label, names in groups.items():
            a_rows, b_rows = [], []
            for n in names:
                a = result["sets"][n]["configs"][flat_name]["on"]["rows"]
                b = result["sets"][n]["configs"][PRODUCTION]["on"]["rows"]
                a_rows += [r for r in a if r["relevant"]]
                b_rows += [r for r in b if r["relevant"]]
            ha = [1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in a_rows]
            hb = [1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in b_rows]
            ra = [1 / r["first"] if r["first"] else 0.0 for r in a_rows]
            rb = [1 / r["first"] if r["first"] else 0.0 for r in b_rows]
            fixed = sum(1 for x, y in zip(ha, hb, strict=True) if not x and y)
            broken = sum(1 for x, y in zip(ha, hb, strict=True) if x and not y)
            versus.setdefault(flat_name, {})[label] = {
                "n": len(ha),
                "hit3_flat": mean(ha),
                "hit3_prod": mean(hb),
                "mrr_flat": mean(ra),
                "mrr_prod": mean(rb),
                "delta_mrr": paired_bootstrap(ra, rb, rng),
                "mcnemar": {"fixed": fixed, "broken": broken, "p": mcnemar_exact(fixed, broken)},
            }
    stats["flat_vs_production"] = versus
    # RAG-5: each component apart, paired by question against the configuration that runs. Leaving out the
    # vectors is "keyword+rerank"; leaving out the graph scope is the flat RAG.
    leave_one_out = {
        "keyword": "no-keyword",
        "semantic": "keyword+rerank",
        "scope": "flat-hybrid+rerank",
        "rerank": "no-rerank",
        "route": "no-route",
        "define": "no-define",
    }
    add_one = {
        "none": "hybrid",
        "rerank": "hybrid+rerank-only",
        "route": "hybrid+route-only",
        "define": "hybrid+define-only",
    }
    pools = {
        name: [name]
        for name in ("published_tune", "published_holdout_v1", "published_holdout_v2", "published_holdout_v3")
    }
    pools["heldout"] = ["published_holdout_v1", "published_holdout_v2"]

    def against_production(config: str, names: list[str]) -> dict:
        a_rows, b_rows = [], []
        for n in names:
            a_rows += [r for r in result["sets"][n]["configs"][config]["on"]["rows"] if r["relevant"]]
            b_rows += [r for r in result["sets"][n]["configs"][PRODUCTION]["on"]["rows"] if r["relevant"]]
        ha = [1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in a_rows]
        hb = [1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in b_rows]
        ra = [1 / r["first"] if r["first"] else 0.0 for r in a_rows]
        rb = [1 / r["first"] if r["first"] else 0.0 for r in b_rows]
        lost = [r["id"] for r, x, y in zip(a_rows, ha, hb, strict=True) if y and not x]
        won = [r["id"] for r, x, y in zip(a_rows, ha, hb, strict=True) if x and not y]
        return {
            "config": config,
            "n": len(ha),
            "hit1": mean(1.0 if r["first"] == 1 else 0.0 for r in a_rows),
            "hit3": mean(ha),
            "mrr": mean(ra),
            # the change when the component is taken out (or the plain hybrid against the full one)
            "delta_mrr": paired_bootstrap(rb, ra, rng),
            "delta_hit3": paired_bootstrap(hb, ha, rng),
            "lost": lost,
            "won": won,
            "mcnemar_p": mcnemar_exact(len(won), len(lost)),
        }

    # RAG-6: the frozen v3 set by how the child typed the question (in-chapter questions only).
    styles: dict = {}
    for config in (PRODUCTION, "keyword+rerank"):
        rows = [
            r
            for r in result["sets"]["published_holdout_v3"]["configs"][config]["on"]["rows"]
            if r["relevant"]
        ]
        for style in sorted({r["style"] for r in rows}):
            got = [r for r in rows if r["style"] == style]
            styles.setdefault(style, {})[config] = {
                "n": len(got),
                "hit3": mean(1.0 if r["first"] and r["first"] <= 3 else 0.0 for r in got),
                "mrr": mean(1 / r["first"] if r["first"] else 0.0 for r in got),
            }
    stats["styles_v3"] = styles
    stats["components"] = {
        label: {
            "production": {
                "n": len(
                    [
                        r
                        for n in names
                        for r in result["sets"][n]["configs"][PRODUCTION]["on"]["rows"]
                        if r["relevant"]
                    ]
                ),
                "mrr": mean(
                    (1 / r["first"] if r["first"] else 0.0)
                    for n in names
                    for r in result["sets"][n]["configs"][PRODUCTION]["on"]["rows"]
                    if r["relevant"]
                ),
            },
            "leave_one_out": {k: against_production(c, names) for k, c in leave_one_out.items()},
            "add_one": {k: against_production(c, names) for k, c in add_one.items()},
        }
        for label, names in pools.items()
    }
    # Grounding: the confusion of the threshold on every set (production configuration, routing on).
    grounding = {}
    for name in SETS:
        which = SETS[name][0]
        rows = result["sets"][name]["configs"][PRODUCTION]["on"]["rows"]
        on = [r for r in rows if r["relevant"]]
        off = [r for r in rows if not r["relevant"]]
        grounding[name] = {
            "on_topic": len(on),
            "on_grounded": sum(r["grounded"] for r in on),
            "on_ci": wilson(sum(r["grounded"] for r in on), len(on)),
            "off_topic": len(off),
            "off_rejected": sum(not r["grounded"] for r in off),
            "off_ci": wilson(sum(not r["grounded"] for r in off), len(off)),
            "best_cosine_on": sorted(r["best_cosine"] for r in on),
            "best_cosine_off": sorted(r["best_cosine"] for r in off),
            "index": which,
        }
    stats["grounding"] = grounding
    result["stats"] = stats

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=list), encoding="utf-8"
    )
    print(f"written {OUT.relative_to(REPO_ROOT)}")
    for name, s in stats.items():
        if name in ("contrasts_v2", "grounding", "flat", "flat_vs_production", "components", "styles_v3"):
            continue
        print(
            f"{name}: n={s['n']} Hit@3 {s['hit3_before']:.2f} -> {s['hit3_after']:.2f}, "
            f"MRR CI after {s['mrr_after_ci'][0]:.3f}-{s['mrr_after_ci'][1]:.3f}, "
            f"McNemar +{s['mcnemar']['fixed']}/-{s['mcnemar']['broken']} p={s['mcnemar']['p']:.4f}"
        )
    for label, block in stats["components"].items():
        parts = [
            f"-{k} {v['delta_mrr'][0]:+.3f} [{v['delta_mrr'][1]:+.3f}, {v['delta_mrr'][2]:+.3f}]"
            for k, v in block["leave_one_out"].items()
        ]
        print(f"components {label} (MRR {block['production']['mrr']:.3f}): " + "; ".join(parts))
    _ = replace  # keeps the import for readers of the module


if __name__ == "__main__":
    main()
