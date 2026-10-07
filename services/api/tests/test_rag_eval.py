"""Regression floor of the Hybrid RAG on its labelled questions (plan v1 5.5.5, CLAUDE.md rule 7), offline.

`make eval-rag` writes the full report (and `LIVE=1` the one with Gemini vectors); this test only keeps the
offline numbers from falling when the chunking, the tokens, the fusion or the re-ranking change. The floors
sit just under the numbers measured on 2026-10-07 (evals/reports/2026-10-07-rag-offline.md).
"""

import pytest
from cavat.config import REPO_ROOT
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.rag.embed import HashEmbedder
from cavat.modules.rag.evaluate import grounding, load_cases, metrics, run
from cavat.modules.rag.service import RagService
from cavat.modules.session import chapter_service, service

MAIN = REPO_ROOT / "evals/datasets/rag-decimals-v1.yaml"
HOLDOUT = REPO_ROOT / "evals/datasets/rag-decimals-holdout-v1.yaml"


@pytest.fixture(scope="module")
async def index():
    rag = RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: HashEmbedder())
    return await rag.current(InMemoryDatabase())


async def test_every_label_names_a_passage_of_the_chapter(index):
    known = {c.chunk_id for c in index.chunks}
    for path in (MAIN, HOLDOUT):
        for case in load_cases(path):
            assert set(case.relevant) <= known, (path.name, case.id)


async def test_without_vectors_the_ranking_holds_its_floor(index):
    main = run(index, load_cases(MAIN), "keyword+rerank")
    m = metrics(main)
    assert m.n == 57
    assert m.hit3 >= 0.93 and m.mrr >= 0.85  # measured 0.95 and 0.882
    assert metrics(run(index, load_cases(HOLDOUT), "keyword+rerank")).mrr >= 0.58  # measured 0.608


async def test_the_pedagogical_re_ranking_is_what_policy_questions_need(index):
    cases = [c for c in load_cases(MAIN) if c.group == "chinh-sach"]
    assert metrics(run(index, cases, "keyword+rerank")).hit1 > metrics(run(index, cases, "keyword")).hit1


async def test_off_topic_questions_find_no_grounding_on_keywords(index):
    for path in (MAIN, HOLDOUT):
        g = grounding(run(index, load_cases(path), "keyword+rerank"))
        assert g.off_topic_rejected >= 0.9, path.name  # measured 0.90 and 0.93


async def test_the_fusion_runs_with_offline_vectors(index):
    m = metrics(run(index, load_cases(MAIN), "hybrid+rerank"))
    assert m.hit3 >= 0.95 and m.mrr >= 0.85  # measured 1.00 and 0.895 with the trigram vectors
