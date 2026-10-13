"""Hybrid RAG (RAG-1): corpus, two-form BM25, coverage, fusion and re-ranking, the offline and the cached
gateway embedders, the service that rebuilds when the corpus changes, and the teacher's API. Offline: the
trigram embedder stands in for Gemini, and a fake batch function for the gateway."""

import io
import zipfile
from dataclasses import replace
from datetime import timedelta

import numpy as np
import pytest
from cavat.config import get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.library.repository import DocumentRepository, TeacherDocument
from cavat.modules.rag import retrieve as retrieve_module
from cavat.modules.rag.bm25 import TwoFormBM25, content_words, tokens
from cavat.modules.rag.chunks import MAX_SYLLABLES, Chunk, chapter_chunks, document_chunks, syllables
from cavat.modules.rag.embed import GatewayEmbedder, HashEmbedder
from cavat.modules.rag.retrieve import RRF_K, RagIndex
from cavat.modules.rag.service import SEMANTIC_RETRY, RagService, tag_passages
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, service
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient

TEACHER = {"X-Demo-Teacher": "1"}
DECIMALS = "math-g5-decimals"


def decimals():
    return chapter_service.chapters()[DECIMALS]


def offline_service() -> RagService:
    return RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: HashEmbedder())


async def decimals_index() -> RagIndex:
    return await offline_service().current(InMemoryDatabase())


def chunk(
    chunk_id, text, *, node=None, kind="theory", approved=True, misconception=None, chapter="c"
) -> Chunk:
    return Chunk(
        chunk_id, text, kind, chapter, node, "chapter", chunk_id, approved, misconception_id=misconception
    )


# --- corpus -------------------------------------------------------------------------------------------


def test_chapter_chunks_follow_teaching_units():
    chunks = chapter_chunks(decimals())
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    kinds = {c.kind for c in chunks}
    assert kinds == {"theory", "method", "worked_example", "misconception_note"}
    nodes = decimals().package.nodes
    assert sum(c.kind == "method" for c in chunks) == len(nodes)  # one method per node
    assert sum(c.kind == "theory" for c in chunks) == sum(len(n.theory) for n in nodes)
    # The {left}/{right} counter-examples are session templates, never retrieved text.
    assert not any("{" in c.text for c in chunks)
    t1 = next(c for c in chunks if c.chunk_id == "KC-DEC-EQ:theory:T1")
    assert t1.node_id == "KC-DEC-EQ" and t1.source == "chapter"
    assert t1.extra["reply"] in t1.text  # kept apart so RAG-2 can leave it out of a prompt
    assert not t1.approved  # the chapter is still a draft


def test_document_passages_keep_lines_pages_and_one_sentence_of_overlap():
    def paragraph(tag: str, n: int) -> str:
        return " ".join(f"{tag}{i}" for i in range(n - 1)) + " hết."

    text = "\n".join(
        [
            "[Trang 1]",
            "Bài 8. Số thập phân. " + paragraph("a", 120),
            "",
            "Câu đầu. " + paragraph("b", 100),
            "[Trang 2]",
            "| 0,5 | không phẩy năm |",
            paragraph("c", 90),
            "",
            "Câu ngắn. " + paragraph("d", 400),
        ]
    )
    passages = document_chunks("d1", "SGK", DECIMALS, text)
    assert [p.chunk_id for p in passages][:2] == ["doc:d1:1", "doc:d1:2"]
    assert passages[0].page == 1 and passages[1].page == 2
    assert all(p.kind == "source_passage" and p.document_id == "d1" and p.node_id is None for p in passages)
    assert passages[0].title == "SGK, trang 1"
    # Cut between lines only: the table row stays whole, and a passage holds at most 300 syllables...
    assert any("| 0,5 | không phẩy năm |" in p.text.splitlines() for p in passages)
    assert all(syllables(p.text) <= MAX_SYLLABLES for p in passages[:-1])
    # ...except one sentence longer than that, which is never cut.
    assert syllables(passages[-1].text) == 400
    # The next passage starts with the last sentence of the previous one.
    last_sentence = passages[0].text.splitlines()[-1].split(". ")[-1]
    assert passages[1].text.startswith(last_sentence)


def test_a_passage_is_tied_to_the_node_it_clearly_talks_about():
    about_comparing = chunk(
        "p1",
        "Muốn so sánh hai số thập phân, ta so sánh phần nguyên trước, rồi so sánh hàng phần mười, "
        "hàng phần trăm. Số nào có chữ số lớn hơn thì số đó lớn hơn.",
        kind="source_passage",
        chapter=DECIMALS,
    )
    homework = chunk(
        "p2", "Bài tập về nhà: làm bài 1, 2, 3 vào vở ô li.", kind="source_passage", chapter=DECIMALS
    )
    tagged = {c.chunk_id: c for c in tag_passages([about_comparing, homework], chapter_chunks(decimals()))}
    assert tagged["p1"].node_id == "KC-DEC-CMP"
    assert tagged["p2"].node_id is None  # no node stands out: one step from every node


# --- keywords -----------------------------------------------------------------------------------------


def test_folded_query_finds_the_passage_with_diacritics():
    index = TwoFormBM25(["Phần nguyên đứng bên trái dấu phẩy.", "Hàng phần mười đứng ngay sau dấu phẩy."])
    scores = index.scores("phan nguyen")
    assert scores[0] > scores[1]
    assert index.scores("phần nguyên")[0] > 0


def test_a_number_has_one_form():
    assert "0,25" in tokens("0.25", folded=False)
    assert "3,5" in tokens("được 3.5 m", folded=False)
    assert "1.000" in tokens("1.000 mm", folded=False)  # a thousands dot stays
    assert "phần_mười" in tokens("hàng phần mười", folded=False)  # adjacent pairs keep phrases


def test_coverage_separates_questions_on_the_chapter_from_off_topic_ones():
    index = TwoFormBM25([c.text for c in chapter_chunks(decimals())])
    assert max(index.coverage("phan nguyen la gi")) == 1.0
    assert max(index.coverage("con mèo nhà con tên là Mướp")) < 0.5
    assert content_words("là sao ạ") == [] and max(index.coverage("là sao ạ")) == 0.0
    assert content_words("so sánh 0,9 và 0,87") == ["so", "sánh"]  # numbers and fillers carry no content
    # Typed with diacritics, a word keeps them: "thủ đô Việt Nam" is not "thứ độ viết năm".
    assert max(index.coverage("thủ đô của Việt Nam là gì")) < 0.5


# --- fusion, graph, re-ranking, grounding -------------------------------------------------------------


def graph_index(embedder=None) -> RagIndex:
    chunks = [
        chunk("a", "so sánh phần nguyên trước", node="A"),
        chunk("b", "so sánh hàng phần mười", node="B"),
        chunk("c", "so sánh hàng phần trăm", node="C"),
        chunk("d", "so sánh hàng phần nghìn", node="D"),
        chunk("doc", "so sánh hai số đo", node=None, kind="source_passage"),
    ]
    return RagIndex(chunks, embedder, {"A": ["B"], "B": ["A", "C"], "C": ["B"]})


def test_rrf_weighs_every_passage_by_its_distance_on_the_graph():
    found = graph_index().retrieve("so sánh", node_id="A", k=5, rerank=False)
    by_id = {s.chunk.chunk_id: s for s in found.ranked}
    assert "d" not in by_id  # not linked to A: out of scope
    assert {cid: s.distance for cid, s in by_id.items()} == {"a": 0, "b": 1, "c": 2, "doc": 1}
    for s in found.ranked:  # keywords only (no embedder): one list
        assert s.fused == pytest.approx(1 / (RRF_K + s.bm25_rank) / (1 + s.distance))
    assert found.results[0].chunk.chunk_id == "a" and found.semantic == "off"


async def test_a_node_reaches_what_it_builds_on_never_what_comes_after_it():
    index = await decimals_index()
    # CMP applies PLACE and EQ, which build on CONCEPT; ORDER and APPLY come after CMP.
    assert index.distances("KC-DEC-CMP") == {
        "KC-DEC-CMP": 0,
        "KC-DEC-PLACE": 1,
        "KC-DEC-EQ": 1,
        "KC-DEC-CONCEPT": 2,
    }
    nodes = {s.chunk.node_id for s in index.retrieve("so sánh", node_id="KC-DEC-CMP", k=50).ranked}
    assert "KC-DEC-ORDER" not in nodes and "KC-DEC-APPLY" not in nodes


def test_hybrid_fuses_the_keyword_and_the_vector_ranks():
    found = graph_index(HashEmbedder()).retrieve("so sánh phần nguyên", k=5, rerank=False)
    top = found.results[0]
    assert top.chunk.chunk_id == "a" and top.bm25_rank == 1 and top.cosine_rank == 1
    assert top.fused == pytest.approx(2 / (RRF_K + 1))
    assert found.semantic == "hash-trigram-512"


async def test_re_ranking_teaches_another_way_and_answers_the_mistake_just_made():
    index = await decimals_index()
    first = index.retrieve("So sánh hai số thập phân", node_id="KC-DEC-CMP", mode="teach")
    assert first.results[0].chunk.chunk_id == "KC-DEC-CMP:theory:T1"
    again = index.retrieve(
        "So sánh hai số thập phân",
        node_id="KC-DEC-CMP",
        mode="teach",
        used=frozenset({"KC-DEC-CMP:theory:T1"}),
    )
    assert again.results[0].chunk.kind == "theory"
    assert again.results[0].chunk.chunk_id != "KC-DEC-CMP:theory:T1"
    used = next(s for s in again.ranked if s.chunk.chunk_id == "KC-DEC-CMP:theory:T1")
    assert "đã dùng trong buổi" in used.reasons

    hint = index.retrieve("0,4 > 0,45", node_id="KC-DEC-CMP", mode="hint", misconception_id="DEC-M02")
    assert hint.results[0].chunk.misconception_id == "DEC-M02"
    assert "đúng lỗi sai vừa gặp" in hint.results[0].reasons


async def test_an_off_topic_question_is_not_grounded():
    index = await decimals_index()
    assert index.retrieve("tai sao phai them so 0").grounded
    assert index.retrieve("sao thêm số 0 vào cuối mà số không đổi").results[0].chunk.node_id == "KC-DEC-EQ"
    for question in ("con mèo nhà con tên là Mướp", "hôm nay trời mưa to quá cô ạ", "là sao ạ"):
        assert not index.retrieve(question).grounded, question


def test_a_calibrated_semantic_model_can_ground_a_paraphrase(monkeypatch):
    class Fixed:
        name, semantic = "fake-model", True

        def embed(self, texts, task):
            vectors = np.zeros((len(texts), 2), dtype=np.float32)
            vectors[:, 0] = 1.0  # every text points the same way: cosine 1
            return vectors

    index = RagIndex([chunk("a", "viết thêm chữ số 0 vào tận cùng bên phải")], Fixed(), {})
    assert not index.retrieve("đằng sau mọc thêm số không").grounded  # no threshold for this model
    monkeypatch.setitem(retrieve_module.GROUNDED_COSINE, "fake-model", 0.9)
    assert index.retrieve("đằng sau mọc thêm số không").grounded


def test_keywords_do_not_overrule_a_calibrated_model(monkeypatch):
    class Orthogonal:
        name, semantic = "fake-model", True

        def embed(self, texts, task):
            vectors = np.zeros((len(texts), 2), dtype=np.float32)
            vectors[:, 0 if task == "RETRIEVAL_DOCUMENT" else 1] = 1.0  # question and passages: cosine 0
            return vectors

    index = RagIndex([chunk("a", "cộng hai phân số khác mẫu số")], Orthogonal(), {})
    keywords = index.retrieve("cộng hai phân số khác mẫu số")
    # no threshold for this model: keywords decide
    assert keywords.grounded and keywords.grounding.startswith("độ phủ từ khóa 1.00")
    monkeypatch.setitem(retrieve_module.GROUNDED_COSINE, "fake-model", 0.65)
    meaning = index.retrieve("cộng hai phân số khác mẫu số")
    assert not meaning.grounded and meaning.grounding == "cosine 0.00 < 0.65"


def test_the_size_budget_keeps_the_prompt_small():
    long = "so sánh " + "rất dài " * 400
    index = RagIndex([chunk("long1", long), chunk("long2", long), chunk("short", "so sánh ngắn")], None, {})
    found = index.retrieve("so sánh", k=3, max_chars=1000)
    assert sum(len(s.chunk.text) for s in found.results[1:]) <= 1000
    assert "short" in [s.chunk.chunk_id for s in found.results]


# --- embedders ----------------------------------------------------------------------------------------


def test_the_gateway_embedder_spends_the_quota_once_per_text(tmp_path):
    calls: list[list[str]] = []

    def batch(texts, task):
        calls.append(list(texts))
        return [[float(len(t)), 1.0] for t in texts]

    cache = tmp_path / "rag" / "embeddings-test.jsonl"
    embedder = GatewayEmbedder(batch, "test-model", cache, batch=2)
    first = embedder.embed(["a", "bb", "ccc", "dddd", "eeeee"], "RETRIEVAL_DOCUMENT")
    assert [len(c) for c in calls] == [2, 2, 1]
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0)
    embedder.embed(["bb", "ccc"], "RETRIEVAL_DOCUMENT")
    assert len(calls) == 3  # cached in memory
    again = GatewayEmbedder(batch, "test-model", cache, batch=2)
    assert np.allclose(again.embed(["a", "eeeee"], "RETRIEVAL_DOCUMENT"), first[[0, 4]])
    assert len(calls) == 3  # cached on disk
    again.embed(["a"], "RETRIEVAL_QUERY")
    assert len(calls) == 4  # the task is part of the key
    assert "eeeee" not in cache.read_text()  # only hashes and vectors are written


def test_keywords_and_structure_keep_working_when_the_embedding_model_fails():
    class Down:
        name, semantic = "down", True

        def embed(self, texts, task):
            raise RuntimeError("429 quota")

    index = RagIndex([chunk("a", "phần nguyên"), chunk("b", "phần mười")], Down(), {})
    assert index.embedder is None and "quota" in (index.semantic_error or "")
    found = index.retrieve("phan nguyen")
    assert found.semantic == "off" and found.results[0].chunk.chunk_id == "a"


def test_a_failing_query_vector_falls_back_to_keywords():
    class QueriesDown:
        name, semantic = "half", True

        def embed(self, texts, task):
            if task == "RETRIEVAL_QUERY":
                raise RuntimeError("network")
            return HashEmbedder().embed(texts, task)

    index = RagIndex([chunk("a", "phần nguyên"), chunk("b", "phần mười")], QueriesDown(), {})
    found = index.retrieve("phan nguyen")
    assert found.semantic == "off" and found.results[0].chunk.chunk_id == "a"


# --- service ------------------------------------------------------------------------------------------


def document(text: str, **fields) -> TeacherDocument:
    base = {
        "school_id": service.DEMO_SCHOOL_ID,
        "title": "Phiếu so sánh",
        "kind": "BAI_TAP",
        "chapter_id": DECIMALS,
        "filename": "phieu.docx",
        "content_type": "application/octet-stream",
        "size": len(text),
        "sha256": "x" * 64,
        "stored_path": "library/phieu.docx",
        "uploaded_by": "teacher",
        "text": text,
    }
    return TeacherDocument(**{**base, **fields})


async def test_the_service_rebuilds_only_when_the_corpus_changes():
    database = InMemoryDatabase()
    await ensure_indexes(database)
    rag = offline_service()
    first = await rag.current(database)
    assert await rag.current(database) is first
    await DocumentRepository(database, service.DEMO_SCHOOL_ID).create(
        document("[Trang 1]\nMuốn so sánh hai số thập phân, so sánh phần nguyên trước.")
    )
    second = await rag.current(database)
    assert second is not first
    passage = next(c for c in second.chunks if c.source == "document")
    assert passage.title == "Phiếu so sánh, trang 1" and passage.node_id == "KC-DEC-CMP"
    assert await rag.current(database, force=True) is not second


@pytest.mark.parametrize("kind", ["DAP_AN", "DE_KIEM_TRA"])
async def test_answer_keys_and_tests_never_reach_the_rag(kind):
    """INGEST-1, CLAUDE.md rule 2: a passage of the RAG can reach a prompt, an answer never may."""
    database = InMemoryDatabase()
    await ensure_indexes(database)
    repo = DocumentRepository(database, service.DEMO_SCHOOL_ID)
    await repo.create(document("[Trang 1]\nCâu 5: 2 m 7 cm = 2,07 m. Đáp án B.", kind=kind, title="Đáp án"))
    await repo.create(document("[Trang 1]\nMuốn so sánh hai số thập phân, so sánh phần nguyên trước."))
    index = await offline_service().current(database)
    titles = {c.title for c in index.chunks if c.source == "document"}
    assert titles == {"Phiếu so sánh, trang 1"}


async def test_the_service_tries_the_embedding_model_again_after_a_failure():
    class Flaky:
        name, semantic = "flaky", True
        down = True

        def embed(self, texts, task):
            if Flaky.down:
                raise RuntimeError("429")
            return HashEmbedder().embed(texts, task)

    rag = RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=Flaky)
    database = InMemoryDatabase()
    failed = await rag.current(database)
    assert failed.semantic_error and await rag.current(database) is failed  # not before the delay
    Flaky.down = False
    rag.built_at -= SEMANTIC_RETRY + timedelta(seconds=1)
    recovered = await rag.current(database)
    assert recovered.semantic_error is None and recovered.embedder is not None


# --- teacher API --------------------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(session_api, "_rag_service", offline_service())
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)
    get_settings.cache_clear()


def docx(*paragraphs: str) -> bytes:
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document {w}><w:body>{body}</w:body></w:document>")
    return out.getvalue()


def test_the_teacher_sees_where_the_rag_takes_its_passages_from(client):
    status = client.get("/v1/teachers/rag/status", headers=TEACHER).json()
    assert status["by_source"] == {"chapter": status["chunks"]}
    assert status["by_kind"]["theory"] > 0 and status["documents"] == []
    assert status["semantic"] == "hash-trigram-512" and status["semantic_is_model"] is False
    cmp = next(n for n in status["nodes"] if n["node_id"] == "KC-DEC-CMP")
    assert cmp["name"] == "So sánh hai số thập phân" and cmp["chunks"] > 0

    upload = client.post(
        "/v1/teachers/documents",
        headers=TEACHER,
        files={
            "file": (
                "phieu.docx",
                docx("Muốn so sánh hai số thập phân, so sánh phần nguyên trước."),
                "application/x",
            )
        },
        data={"title": "Phiếu bài tập 1", "kind": "BAI_TAP", "chapter_id": DECIMALS},
    )
    assert upload.status_code == 201, upload.text
    status = client.get("/v1/teachers/rag/status", headers=TEACHER).json()
    assert status["by_source"]["document"] == 1
    [doc] = status["documents"]
    assert doc["title"] == "Phiếu bài tập 1" and doc["passages"] == 1 and doc["tied_to_node"] == 1

    found = client.get(
        "/v1/teachers/rag/search", params={"q": "so sanh phan nguyen truoc"}, headers=TEACHER
    ).json()
    top = found["results"][0]
    assert top["source"] == "document" and top["title"] == "Phiếu bài tập 1"
    assert found["grounded"] is True
    for key in (
        "bm25",
        "bm25_rank",
        "cosine",
        "cosine_rank",
        "distance",
        "fused",
        "final",
        "coverage",
        "reasons",
    ):
        assert key in top

    rebuilt = client.post("/v1/teachers/rag/rebuild", headers=TEACHER).json()
    assert rebuilt["chunks"] == status["chunks"]


def test_a_search_inside_a_node_and_a_mode(client):
    found = client.get(
        "/v1/teachers/rag/search",
        params={"q": "Số thập phân bằng nhau", "node": "KC-DEC-EQ", "mode": "teach", "k": 2},
        headers=TEACHER,
    ).json()
    assert len(found["results"]) == 2 and found["mode"] == "teach"
    assert found["results"][0]["node_name"] == "Số thập phân bằng nhau"
    assert found["results"][0]["kind"] == "theory"


def test_only_the_teacher_reads_the_rag(client):
    assert client.get("/v1/teachers/rag/status").status_code in (401, 403)
    assert client.get(
        "/v1/teachers/rag/search", params={"q": "x"}, headers={"X-Demo-Student": "s1"}
    ).status_code in (
        401,
        403,
    )
    assert client.get("/v1/teachers/rag/search", params={"q": ""}, headers=TEACHER).status_code == 422


# --- scope of a published chapter (DI-50) -------------------------------------------------------------

CHAIN = {"B": ["A"], "C": ["B"], "D": ["C"], "E": ["D"]}  # each node builds on the one before (order edges)


def test_a_definition_question_reaches_every_period_the_node_builds_on():
    chunks = [
        chunk("A:theory", "Phần thập phân là các chữ số bên phải dấu phẩy.", node="A"),
        chunk("D:theory", "Sắp xếp các số thập phân từ bé đến lớn.", node="D"),
    ]
    index = RagIndex(chunks, None, CHAIN)
    found = index.retrieve("phần thập phân là gì vậy cô", node_id="D", k=3)
    assert found.mode == "definition" and found.results[0].chunk.chunk_id == "A:theory"
    assert "định nghĩa «phan thap phan»" in found.results[0].reasons
    assert (
        not index.retrieve("phần thập phân có mấy chữ số", node_id="D", k=3).results[0].chunk.node_id == "A"
    )
    assert "E" not in index.ancestors("D") and index.ancestors("D") == {"A", "B", "C"}


def test_a_passage_of_several_periods_never_reaches_an_earlier_one():
    overview = replace(
        chunk("doc:overview", "Diện tích hình thang bằng tổng hai đáy nhân chiều cao chia 2."),
        candidates=("A", "B"),
    )
    index = RagIndex([overview], None, CHAIN)
    early = [s.chunk.chunk_id for s in index.retrieve("diện tích hình thang", node_id="A", k=3).ranked]
    late = [s.chunk.chunk_id for s in index.retrieve("diện tích hình thang", node_id="B", k=3).ranked]
    assert early == [] and late == ["doc:overview"]  # at A it names B, a period still to come


def test_passages_tied_to_several_nodes_stay_untied():
    reference = [chunk(f"{n}:t", f"tam giác hình thang diện tích {n}", node=n) for n in "ABC"]
    passage = Chunk(
        "doc:1", "tam giác hình thang diện tích", "source_passage", "c", None, "document", "d", True
    )
    (tagged,) = tag_passages([passage], reference)
    assert tagged.node_id is None and set(tagged.candidates) == {"A", "B", "C"}


def test_a_passage_longer_than_the_budget_does_not_crowd_out_the_others():
    index = RagIndex(
        [
            chunk("page", "đường cao " + "rất dài " * 300),
            chunk("def", "Đường cao của tam giác là đoạn thẳng."),
        ],
        None,
        {},
    )
    found = index.retrieve("đường cao là gì", k=3, max_chars=1200)
    assert [s.chunk.chunk_id for s in found.results] == ["def"]


@pytest.mark.parametrize(
    ("text", "term", "defines_it"),
    [
        ("Đường cao của tam giác là đoạn thẳng kẻ từ một đỉnh", "duong cao", True),
        ("Cạnh đối diện đó gọi là đáy tương ứng", "day", True),
        ("Tam giác vuông: đáy và đường cao là những cạnh nào?", "duong cao", False),  # a question
        ("Số 7,25 có phần nguyên là 7", "phan nguyen", False),  # a value
        ("phần nguyên đều là 0", "phan nguyen", False),
    ],
)
def test_a_definition_is_told_from_a_question_and_a_value(text, term, defines_it):
    from cavat.modules.rag.retrieve import defines

    assert defines(text, term) is defines_it


def test_a_later_period_wins_only_when_it_is_clearly_closer():
    from cavat.modules.rag.retrieve import defined_term

    assert defined_term("đường cao là gì vậy cô") == "duong cao"
    assert defined_term("so sánh 7,25 và 7,3") is None
    chunks = [
        chunk("A:theory", "Diện tích tam giác bằng đáy nhân chiều cao chia 2.", node="A"),
        chunk("E:theory", "Làm tròn số thập phân đến hàng phần trăm.", node="E"),
    ]
    index = RagIndex(chunks, None, CHAIN)
    order = ["A", "B", "C", "D", "E"]
    later, found = index.question("vì sao diện tích tam giác chia 2", "A", order)
    assert later is None and found.results[0].chunk.chunk_id == "A:theory"
    later, _ = index.question("làm tròn số thập phân đến hàng phần trăm thế nào", "A", order)
    assert later == "E"
