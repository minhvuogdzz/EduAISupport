"""Evaluation of the Hybrid RAG (plan v1, 5.5.5): a labelled question set, the configurations of the
ablation (keywords only, semantics only, hybrid, hybrid + pedagogical re-ranking, and since RAG-5 one
component left out or added at a time), Hit@k, Recall@k and MRR, and how well
``grounded`` tells questions on the chapter from off-topic ones. Used by ``make eval-rag`` and by the
regression test that keeps the offline numbers from falling.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean

import yaml

from cavat.modules.rag.retrieve import RagIndex


def _config(keyword: bool, semantic: bool, rerank: bool, route: bool, define: bool) -> dict[str, bool]:
    return {"keyword": keyword, "semantic": semantic, "rerank": rerank, "route": route, "define": define}


# The first five keep the meaning they had before RAG-5 ("+rerank" = re-ranking, routing DI-57 and the
# definition boost DI-50 together), so the numbers reported until then can be read against them.
CONFIGS: dict[str, dict[str, bool]] = {
    "keyword": _config(True, False, False, False, False),
    "semantic": _config(False, True, False, False, False),
    "hybrid": _config(True, True, False, False, False),
    "keyword+rerank": _config(True, False, True, True, True),  # what runs without vectors
    "hybrid+rerank": _config(True, True, True, True, True),  # what runs with vectors
}
# RAG-5: one component at a time. Leave one out of the configuration that runs ("no-semantic" is
# "keyword+rerank" above; no graph scope is the flat RAG of scripts/paper_rag.py), and add one to "hybrid".
ABLATION: dict[str, dict[str, bool]] = {
    "no-keyword": _config(False, True, True, True, True),
    "no-rerank": _config(True, True, False, True, True),
    "no-route": _config(True, True, True, False, True),
    "no-define": _config(True, True, True, True, False),
    "hybrid+rerank-only": _config(True, True, True, False, False),
    "hybrid+route-only": _config(True, True, False, True, False),
    "hybrid+define-only": _config(True, True, False, False, True),
}
ALL_CONFIGS = {**CONFIGS, **ABLATION}


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    q: str
    relevant: tuple[str, ...]  # empty: off-topic, nothing may ground it
    node: str | None = None
    mode: str = "question"
    used: frozenset[str] = frozenset()
    misconception: str | None = None
    style: str = ""  # RAG-6: how the child typed it (co-dau, khong-dau, sai-chinh-ta, viet-tat)


@dataclass(frozen=True)
class CaseResult:
    case: Case
    ranking: list[str]  # chunk ids, final order
    first_relevant: int | None  # 1-based rank of the first relevant chunk
    grounded: bool
    best_cosine: float  # best cosine among the chunks handed to the tutor (top k)
    semantic: str  # the embedder the retrieval used, "off" when it ran without vectors


@dataclass(frozen=True)
class Metrics:
    n: int
    hit1: float
    hit3: float
    recall3: float
    recall5: float
    mrr: float


def load_cases(path: Path) -> list[Case]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Case(
            id=c["id"],
            group=c["group"],
            q=c["q"],
            relevant=tuple(c.get("relevant") or ()),
            node=c.get("node"),
            mode=c.get("mode", "question"),
            used=frozenset(c.get("used") or ()),
            misconception=c.get("misconception"),
            style=c.get("style", ""),
        )
        for c in data["cases"]
    ]


def expand(labels: Iterable[str], index: RagIndex) -> set[str]:
    """Labels as chunk ids: "STP-T02:*" stands for every passage of that node (its theory, method, worked
    examples, notes, and the teacher's document passages tied to it), whose ids are not stable."""
    out: set[str] = set()
    for label in labels:
        if label.endswith(":*"):
            node = label[:-2]
            out |= {c.chunk_id for c in index.chunks if c.node_id == node}
        else:
            out.add(label)
    return out


def run(index: RagIndex, cases: Iterable[Case], config: str, k: int = 3) -> list[CaseResult]:
    out = []
    for case in cases:
        found = index.retrieve(
            case.q,
            node_id=case.node,
            mode=case.mode,
            used=case.used,
            misconception_id=case.misconception,
            k=k,
            max_chars=100_000,
            **ALL_CONFIGS[config],
        )
        ranking = [s.chunk.chunk_id for s in found.ranked]
        relevant = expand(case.relevant, index)
        first = next((i for i, cid in enumerate(ranking, 1) if cid in relevant), None)
        best_cosine = max((s.cosine for s in found.results), default=0.0)
        if relevant != set(case.relevant):  # "STP-T02:*": recall over the passages the label stands for
            case = replace(case, relevant=tuple(sorted(relevant)))
        out.append(CaseResult(case, ranking, first, found.grounded, best_cosine, found.semantic))
    return out


def metrics(results: Iterable[CaseResult]) -> Metrics:
    scored = [r for r in results if r.case.relevant]
    if not scored:
        return Metrics(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    def recall(r: CaseResult, k: int) -> float:
        return len(set(r.ranking[:k]) & set(r.case.relevant)) / len(r.case.relevant)

    return Metrics(
        n=len(scored),
        hit1=mean(r.first_relevant == 1 for r in scored),
        hit3=mean(r.first_relevant is not None and r.first_relevant <= 3 for r in scored),
        recall3=mean(recall(r, 3) for r in scored),
        recall5=mean(recall(r, 5) for r in scored),
        mrr=mean(1 / r.first_relevant if r.first_relevant else 0.0 for r in scored),
    )


@dataclass(frozen=True)
class Grounding:
    on_topic: int
    on_topic_grounded: float  # share of questions on the chapter the tutor may answer (higher is better)
    off_topic: int
    off_topic_rejected: float  # share of off-topic questions left ungrounded (should be 1)


def grounding(results: Iterable[CaseResult]) -> Grounding:
    results = list(results)
    on = [r for r in results if r.case.relevant]
    off = [r for r in results if not r.case.relevant]
    return Grounding(
        len(on),
        mean(r.grounded for r in on) if on else 0.0,
        len(off),
        mean(not r.grounded for r in off) if off else 0.0,
    )


def cosine_threshold(results: Iterable[CaseResult]) -> tuple[float, float, float] | None:
    """Where a semantic model's grounding threshold falls (DI-17): halfway between the off-topic question
    that comes closest and the question on the chapter that comes least close, when the two do not overlap
    (else just above the closest off-topic one). Returns (off-topic max, on-topic min, threshold)."""
    results = list(results)
    off = [r.best_cosine for r in results if not r.case.relevant]
    on = [r.best_cosine for r in results if r.case.relevant]
    if not off or not on:
        return None
    off_max, on_min = max(off), min(on)
    threshold = (off_max + on_min) / 2 if off_max < on_min else off_max + 0.01
    return off_max, on_min, round(threshold, 2)


def without_vectors(by_config: dict[str, list[CaseResult]]) -> int:
    """Retrievals of a configuration that asks for vectors but ran without them (the model call failed)."""
    return sum(
        r.semantic == "off"
        for name, results in by_config.items()
        if ALL_CONFIGS[name]["semantic"]
        for r in results
    )


def markdown(by_config: dict[str, list[CaseResult]], embedder: str, production: str, semantic: bool) -> str:
    """The ablation table, Hit@3 by group, grounding, and the cases the configuration that runs misses.

    ``production``: the configuration a session runs with these vectors (``keyword+rerank`` without a model);
    ``semantic``: the vectors come from a model, so a cosine threshold can be calibrated.
    """
    lines = [
        f"Embedder: `{embedder}`",
        "",
        "| Cấu hình | n | Hit@1 | Hit@3 | Recall@3 | Recall@5 | MRR |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, results in by_config.items():
        m = metrics(results)
        lines.append(
            f"| {name} | {m.n} | {m.hit1:.2f} | {m.hit3:.2f} | {m.recall3:.2f} | {m.recall5:.2f} "
            f"| {m.mrr:.3f} |"
        )
    groups = sorted({r.case.group for r in next(iter(by_config.values())) if r.case.relevant})
    lines += ["", "Hit@3 theo nhóm câu hỏi:", "", "| Cấu hình | " + " | ".join(groups) + " |"]
    lines.append("|---|" + "---|" * len(groups))
    for name, results in by_config.items():
        cells = [f"{metrics(r for r in results if r.case.group == g).hit3:.2f}" for g in groups]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    name = production
    production_results = by_config.get(production, [])
    g = grounding(production_results)
    lines += [
        "",
        f"Có căn cứ ({name}): {g.on_topic_grounded:.0%} của {g.on_topic} câu trong chương được coi là có "
        f"căn cứ; {g.off_topic_rejected:.0%} của {g.off_topic} câu lạc đề bị từ chối.",
    ]
    calibration = cosine_threshold(production_results) if semantic else None
    if calibration:
        off_max, on_min, threshold = calibration
        lines.append(
            f"Hiệu chỉnh ngưỡng cosine: câu lạc đề gần nhất {off_max:.3f}, câu trong chương xa nhất "
            f"{on_min:.3f}, ngưỡng ở giữa {threshold:.2f}."
        )
    missed = [
        r
        for r in production_results
        if r.case.relevant and (r.first_relevant is None or r.first_relevant > 3)
    ]
    wrong = [r for r in production_results if not r.case.relevant and r.grounded]
    if missed or wrong:
        lines += ["", f"Câu chưa đạt ({name}):", ""]
        for r in missed:
            rank = r.first_relevant or "không có"
            lines.append(
                f"- {r.case.id} «{r.case.q}»: đoạn đúng đầu tiên ở hạng {rank}; top 3: {r.ranking[:3]}"
            )
        for r in wrong:
            lines.append(
                f"- {r.case.id} «{r.case.q}»: câu lạc đề mà vẫn coi là có căn cứ; top 1: {r.ranking[:1]}"
            )
    return "\n".join(lines)


# RAG-5: what each component brings, against the configuration that runs with vectors.
LEAVE_ONE_OUT = (
    ("bỏ từ khóa (BM25)", "no-keyword"),
    ("bỏ vector", "keyword+rerank"),
    ("bỏ xếp lại sư phạm", "no-rerank"),
    ("bỏ định tuyến DI-57", "no-route"),
    ("bỏ ưu tiên định nghĩa DI-50", "no-define"),
)
ADD_ONE = (
    ("hybrid (RRF, phạm vi đồ thị)", "hybrid"),
    ("hybrid + xếp lại sư phạm", "hybrid+rerank-only"),
    ("hybrid + định tuyến DI-57", "hybrid+route-only"),
    ("hybrid + ưu tiên định nghĩa DI-50", "hybrid+define-only"),
)


def ablation_markdown(by_config: dict[str, list[CaseResult]], full: str = "hybrid+rerank") -> str:
    """One row per component: the configuration without it (or with it alone on top of ``hybrid``), its
    metrics, the change of MRR against ``full``, and the questions whose Hit@3 it fixes or breaks."""
    base = {r.case.id: r for r in by_config[full] if r.case.relevant}

    def hit3(r: CaseResult) -> bool:
        return r.first_relevant is not None and r.first_relevant <= 3

    def row(label: str, name: str) -> str:
        m, f = metrics(by_config[name]), metrics(by_config[full])
        other = {r.case.id: r for r in by_config[name] if r.case.relevant}
        lost = sorted(i for i, r in base.items() if hit3(r) and not hit3(other[i]))
        won = sorted(i for i, r in base.items() if not hit3(r) and hit3(other[i]))
        change = ", ".join([*(f"−{i}" for i in lost), *(f"+{i}" for i in won)]) or "—"
        return (
            f"| {label} | `{name}` | {m.hit1:.2f} | {m.hit3:.2f} | {m.mrr:.3f} | {m.mrr - f.mrr:+.3f} "
            f"| {change} |"
        )

    f = metrics(by_config[full])
    lines = [
        "| Thành phần | Cấu hình | Hit@1 | Hit@3 | MRR | ΔMRR so với đủ | Hit@3 đổi (− mất, + được) |",
        "|---|---|---|---|---|---|---|",
        f"| đủ mọi thành phần | `{full}` | {f.hit1:.2f} | {f.hit3:.2f} | {f.mrr:.3f} | — | — |",
        *(row(label, name) for label, name in LEAVE_ONE_OUT),
        "| *thêm từng thành phần vào hybrid* | | | | | | |",
        *(row(label, name) for label, name in ADD_ONE),
    ]
    return "\n".join(lines)
