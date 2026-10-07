"""Hybrid RAG evaluation (RAG-1, plan v1 5.5.5): `make eval-rag`.

Runs the labelled questions of evals/datasets/rag-decimals-v1.yaml through the four configurations of the
plan (keywords, semantics, hybrid, hybrid + re-ranking) and the one that runs without vectors (keywords +
re-ranking), on the chapter content only: the database is in memory, no teacher document is read.

- `make eval-rag`: offline and free; hashed trigrams stand in for the semantic signal.
- `make eval-rag LIVE=1`: Gemini embeddings through the gateway (GEMINI_API_KEY in services/api/.env). Every
  vector is cached in var/storage/rag/, so the quota is spent once (about 50 passages and 70 questions, in
  a few batched requests), and nothing on the next runs.

The report goes to evals/reports/<date>-rag-<offline|gemini>.md.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import date

from cavat.config import REPO_ROOT
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.rag.embed import Embedder, GatewayEmbedder, HashEmbedder
from cavat.modules.rag.evaluate import CONFIGS, load_cases, markdown, run, without_vectors
from cavat.modules.rag.service import RagService, default_embedder
from cavat.modules.session import chapter_service
from cavat.modules.session.service import DEMO_SCHOOL_ID

DATASET = REPO_ROOT / "evals/datasets/rag-decimals-v1.yaml"  # tunes the parameters (DI-17)
HOLDOUT = REPO_ROOT / "evals/datasets/rag-decimals-holdout-v1.yaml"  # never tunes anything: unseen questions


RETRIES, PAUSE_S = 4, 20  # the free tier answers 429 to bursts of requests: wait and try again


class Metered:
    """Counts the requests and texts an embedder sends to the model (the quota this run spends), and tries
    a failed request again after a pause, so that no question of the evaluation runs without its vector."""

    def __init__(self, inner: GatewayEmbedder) -> None:
        self.requests, self.texts = 0, 0
        original = inner._embed_batch

        def batch(texts: list[str], task: str) -> list[list[float]]:
            for attempt in range(1, RETRIES + 1):
                self.requests += 1
                self.texts += len(texts)
                try:
                    return original(texts, task)
                except Exception as exc:  # noqa: BLE001 - quota or network; the last failure is raised
                    if attempt == RETRIES:
                        raise
                    print(f"embedding request failed ({type(exc).__name__}), retry in {PAUSE_S} s")
                    time.sleep(PAUSE_S)
            raise AssertionError("unreachable")

        inner._embed_batch = batch


async def main(live: bool) -> int:
    metered: Metered | None = None
    embedder: Embedder
    if live:
        made = default_embedder()
        if not isinstance(made, GatewayEmbedder):
            print(
                "GEMINI_API_KEY is not set in services/api/.env: run without LIVE=1 for the offline report."
            )
            return 1
        metered, embedder = Metered(made), made
    else:
        embedder = HashEmbedder()
    started = time.perf_counter()
    index = await RagService(DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: embedder).current(
        InMemoryDatabase()
    )
    if index.semantic_error:
        print(f"The embedding model failed: {index.semantic_error}")
        return 1
    cases, holdout = load_cases(DATASET), load_cases(HOLDOUT)
    known = {c.chunk_id for c in index.chunks}
    unknown = sorted({cid for case in cases + holdout for cid in case.relevant} - known)
    if unknown:
        print(f"Labels that name no passage of the chapter: {unknown}")
        return 1
    # Every question vector in a few batched requests first (cached), not one request per retrieval.
    embedder.embed(sorted({c.q for c in cases + holdout}), "RETRIEVAL_QUERY")
    by_config = {name: run(index, cases, name) for name in CONFIGS}
    by_config_holdout = {name: run(index, holdout, name) for name in CONFIGS}
    elapsed = time.perf_counter() - started
    missing = without_vectors(by_config) + without_vectors(by_config_holdout)
    if missing:
        print(f"{missing} retrievals ran without their vector: the numbers would not be clean, no report.")
        return 1
    production = "hybrid+rerank" if live else "keyword+rerank"
    embedder_name = index.embedder.name if index.embedder else "off"

    kind = "gemini" if live else "offline"
    on_topic = sum(1 for c in cases if c.relevant)
    lines = [
        f"# Đánh giá Hybrid RAG ({kind}), {date.today().isoformat()}",
        "",
        f"Bộ câu hỏi: `{DATASET.relative_to(REPO_ROOT)}`, {len(cases)} câu ({on_topic} câu trong chương, "
        f"{len(cases) - on_topic} câu lạc đề); kho đoạn: {len(index.chunks)} đoạn của chương Số thập phân "
        "(chưa có tài liệu giáo viên). Lệnh: `make eval-rag" + (" LIVE=1" if live else "") + "`.",
        "",
        "Hit@k: có ít nhất một đoạn đúng trong k đoạn đầu. Recall@k: tỉ lệ đoạn đúng nằm trong k đoạn đầu. "
        "MRR: trung bình 1/hạng của đoạn đúng đầu tiên. `keyword+rerank` là cấu hình chạy khi không có "
        "vector (không có khóa Gemini, hết hạn mức); `hybrid+rerank` là cấu hình chạy thật khi có vector.",
        "",
        "## Bộ câu chính (dùng để chỉnh tham số DI-17)",
        "",
        markdown(by_config, embedder_name, production=production, semantic=live),
        "",
        "## Bộ câu kiểm tra riêng (không dùng để chỉnh gì)",
        "",
        f"`{HOLDOUT.relative_to(REPO_ROOT)}`, {len(holdout)} câu viết sau khi chỉnh tham số, một nửa câu "
        "lạc đề là Toán ngoài chương. Đây là con số gần với câu học sinh thật hơn.",
        "",
        markdown(by_config_holdout, embedder_name, production=production, semantic=False),
        "",
        f"Thời gian: {elapsed:.1f} s cho {(len(cases) + len(holdout)) * len(CONFIGS)} lần truy xuất.",
    ]
    if metered is not None:
        lines.append(
            f"Gọi model embedding trong lần chạy này: {metered.requests} request, {metered.texts} văn bản; "
            "mọi lần truy xuất đều có vector. Vector được lưu đệm ở `var/storage/rag/`, các lần chạy sau "
            "không gọi lại model."
        )
    report = "\n".join(lines) + "\n"
    print(report)
    out = REPO_ROOT / "evals/reports" / f"{date.today().isoformat()}-rag-{kind}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Report: {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="Gemini embeddings through the gateway")
    sys.exit(asyncio.run(main(parser.parse_args().live)))
