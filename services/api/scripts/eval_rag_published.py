"""Hybrid RAG evaluation on the chapters published from the teacher's documents: `make eval-rag-published`.

Unlike `make eval-rag` (the built-in chapter, its content only), the index here is the one a session uses: the
published teaching plans and the teacher's document passages, read from the database of services/api/.env
(read only: nothing is written there). Questions: evals/datasets/rag-published-v1.yaml (tunes DI-50) and
rag-published-holdout-v1.yaml (never tunes anything).

- `make eval-rag-published`: offline, hashed trigrams stand in for the semantic signal.
- `make eval-rag-published LIVE=1`: Gemini embeddings, cached in var/storage/rag/ (the quota is spent once).

The report goes to evals/reports/<date>-rag-published-<offline|gemini>.md, with the grounding of every
group: a question on an earlier period must ground, one on a later period or off the chapter must not.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean

from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.modules.rag.embed import Embedder, GatewayEmbedder, HashEmbedder
from cavat.modules.rag.evaluate import CONFIGS, expand, load_cases, markdown, run, without_vectors
from cavat.modules.rag.service import RagService, default_embedder
from cavat.modules.session import chapter_service
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.teaching.grounded import ANSWER_CHARS, ANSWER_PASSAGES
from eval_rag import Metered

DATASET = REPO_ROOT / "evals/datasets/rag-published-v1.yaml"
HOLDOUT = REPO_ROOT / "evals/datasets/rag-published-holdout-v1.yaml"


def decisions(index, results) -> dict[str, str]:
    """What the tutor does with each question: ANSWER (grounded in its scope), LATER (it names the later
    period, plan 5.5.3) or PARKED (kept for the teacher), as ``GroundedSpeaker.answer`` decides."""
    orders = {cid: c.topological_order() for cid, c in chapter_service.chapters().items()}
    out = {}
    for r in results:
        order = next((o for o in orders.values() if r.case.node in o), [])
        later, scoped = index.question(
            r.case.q, r.case.node, order, k=ANSWER_PASSAGES, max_chars=ANSWER_CHARS
        )
        out[r.case.id] = "LATER" if later else ("ANSWER" if scoped.grounded else "PARKED")
    return out


def by_group(results, decided: dict[str, str]) -> list[str]:
    """Hit@3 and what the tutor does, per group of questions."""
    groups = defaultdict(list)
    for r in results:
        groups[r.case.group].append(r)
    lines = [
        "| Nhóm | n | Hit@3 | Trả lời | Báo bài sau | Gác cho cô | Mong muốn |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, rs in groups.items():
        on = bool(rs[0].case.relevant)
        hit = mean(r.first_relevant is not None and r.first_relevant <= 3 for r in rs) if on else None
        share = {d: mean(decided[r.case.id] == d for r in rs) for d in ("ANSWER", "LATER", "PARKED")}
        want = "trả lời, đúng đoạn" if on else ("báo bài sau hoặc gác" if name == "bai-sau" else "gác")
        lines.append(
            f"| {name} | {len(rs)} | {'—' if hit is None else f'{hit:.2f}'} | {share['ANSWER']:.2f} | "
            f"{share['LATER']:.2f} | {share['PARKED']:.2f} | {want} |"
        )
    return lines


def misses(results, decided: dict[str, str]) -> list[str]:
    out = []
    for r in results:
        on = bool(r.case.relevant)
        d = decided[r.case.id]
        wrong = (on and (r.first_relevant is None or r.first_relevant > 3 or d != "ANSWER")) or (
            not on and d == "ANSWER"
        )
        if wrong:
            out.append(
                f"- {r.case.id} ({r.case.group}, ở {r.case.node}): «{r.case.q}»: hạng đoạn đúng đầu tiên "
                f"{r.first_relevant or '—'}, gia sư: {d}, cosine tốt nhất {r.best_cosine:.2f}; "
                f"3 đoạn đầu: {', '.join(r.ranking[:3])}"
            )
    return out or ["- (không có)"]


async def main(live: bool, holdout_path=HOLDOUT, tag: str = "") -> int:
    settings = get_settings()
    metered: Metered | None = None
    embedder: Embedder
    if live:
        made = default_embedder()
        if not isinstance(made, GatewayEmbedder):
            print("GEMINI_API_KEY is not set in services/api/.env: run without LIVE=1.")
            return 1
        metered, embedder = Metered(made), made
    else:
        embedder = HashEmbedder()
    database = db.get_db(settings)
    await chapter_service.load_published(database, DEMO_SCHOOL_ID)
    index = await RagService(DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: embedder).current(
        database
    )
    await db.close_client()
    if index.semantic_error:
        print(f"The embedding model failed: {index.semantic_error}")
        return 1
    cases, holdout = load_cases(DATASET), load_cases(holdout_path)
    empty = [c.id for c in cases + holdout if c.relevant and not expand(c.relevant, index)]
    if empty:
        print(f"Labels that name no passage: {empty}")
        return 1
    embedder.embed(sorted({c.q for c in cases + holdout}), "RETRIEVAL_QUERY")
    production = "hybrid+rerank" if live else "keyword+rerank"
    by_config = {name: run(index, cases, name) for name in CONFIGS}
    by_config_holdout = {name: run(index, holdout, name) for name in CONFIGS}
    if without_vectors(by_config) + without_vectors(by_config_holdout):
        print("Some retrievals ran without their vector: no report.")
        return 1
    dev_decided = decisions(index, by_config[production])
    holdout_decided = decisions(index, by_config_holdout[production])
    kind = "gemini" if live else "offline"
    name = index.embedder.name if index.embedder else "off"
    docs = sum(1 for c in index.chunks if c.kind == "source_passage")
    lines = [
        f"# Đánh giá Hybrid RAG trên hai chương đã phát hành ({kind}), {date.today().isoformat()}",
        "",
        f"Kho đoạn: {len(index.chunks)} đoạn (trong đó {docs} đoạn tài liệu của giáo viên) của "
        f"{', '.join(sorted(chapter_service.chapters()))}, database `{settings.mongodb_db}` (chỉ đọc). "
        f"Lệnh: `make eval-rag-published{' LIVE=1' if live else ''}`. Cấu hình chạy thật: `{production}`.",
        "",
        "## Bộ câu chính (dùng để chỉnh DI-50)",
        "",
        markdown(by_config, name, production=production, semantic=live),
        "",
        *by_group(by_config[production], dev_decided),
        "",
        "Câu cấu hình chạy thật làm sai:",
        "",
        *misses(by_config[production], dev_decided),
        "",
        f"## Bộ câu giữ riêng `{holdout_path.name}` (không dùng để chỉnh gì)",
        "",
        markdown(by_config_holdout, name, production=production, semantic=False),
        "",
        *by_group(by_config_holdout[production], holdout_decided),
        "",
        "Câu cấu hình chạy thật làm sai:",
        "",
        *misses(by_config_holdout[production], holdout_decided),
    ]
    if metered is not None:
        lines += ["", f"Gọi model embedding: {metered.requests} request, {metered.texts} văn bản (lưu đệm)."]
    report = "\n".join(lines) + "\n"
    print(report)
    out = REPO_ROOT / "evals/reports" / f"{date.today().isoformat()}-rag-published-{kind}{tag}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Report: {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--holdout", default=str(HOLDOUT), help="the held-out questions (default: v1)")
    parser.add_argument("--tag", default="", help="suffix of the report name")
    args = parser.parse_args()
    holdout = args.holdout if args.holdout.startswith("/") else str(REPO_ROOT / args.holdout)
    sys.exit(asyncio.run(main(args.live, Path(holdout), args.tag)))
