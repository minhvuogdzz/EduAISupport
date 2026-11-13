"""ENG-2 (ADR-061): the Hybrid RAG keeps every subject apart, and Mathematics retrieves as before.

- Cross-subject leaks, both ways: an index holds one subject's chunks, filtered when it is built; a
  question of the other subject finds none of them, also a passage with no chapter or no node.
- A subject is required on new data; data stored before ENG-2 (no subject) is Mathematics (DI-120).
- Each subject reads its texts with its own analyzer (DI-121); the English one writes contractions out.
- Regression: every retrieval of the Mathematics eval questions is the same as before subjects existed
  (golden digests made at commit 565b6a0, before this change).

The English unit here is a small fake made for these tests in the style of Unit 11 "Family time" (Tiếng Anh 5
Global Success, tập hai), not teaching content.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from cavat.config import REPO_ROOT, get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.core.subjects import LEGACY_SUBJECT, check_subject, with_legacy_subject
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.content.chapter_package import Chapter, ChapterPackage
from cavat.modules.library.repository import DocumentRepository, TeacherDocument
from cavat.modules.observability.trace import _result
from cavat.modules.rag.analyzers import ENGLISH, MATH, analyzer_for, english_normalize
from cavat.modules.rag.bm25 import TwoFormBM25, tokens
from cavat.modules.rag.chunks import Chunk, chapter_chunks
from cavat.modules.rag.embed import HashEmbedder
from cavat.modules.rag.evaluate import ALL_CONFIGS, load_cases
from cavat.modules.rag.retrieve import RagIndex
from cavat.modules.rag.service import RagService, tag_passages
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, service
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient
from pydantic import ValidationError

SCHOOL = service.DEMO_SCHOOL_ID
DECIMALS = "math-g5-decimals"
FAMILY = "eng-g5-u11-family-time-test"  # the fake English unit of these tests (Unit 11 "Family time")
TEACHER = {"X-Demo-Teacher": "1"}
GOLDEN = Path(__file__).parent / "golden" / "rag-math-before-eng2.json"


def _node(node_id: str, name: str, theory: str, rule: str, example: str) -> dict:
    return {
        "id": node_id,
        "name": name,
        "layer": "BASIC",
        "description": name,
        "lesson_id": "eng-g5-u11-family-time-test-l1",
        "theory": [{"id": "T1", "representation": "picture", "text": theory, "ask": "What did you do?"}],
        "method": {"rule": rule, "steps": ["Look at the picture.", "Say the word."]},
        "worked_examples": [
            {"id": "W1", "problem": example, "steps": ["Point.", "Say."], "answer": "Yes, I did."}
        ],
        "explain": {"prompt": "Tell me about your family time.", "key_ideas": [["did"]]},
        "checks": [],
        "practice": [],
        "transfer": [],
    }


def english_unit() -> Chapter:
    package = ChapterPackage.model_validate(
        {
            "chapter_id": FAMILY,
            "version": "0.0.1-test",
            "status": "DRAFT",
            "subject": "english",
            "grade": 5,
            "title": "Unit 11. Family time (test)",
            "lessons": [],
            "nodes": [
                _node(
                    "EN-FT-ACTIVITIES",
                    "Family activities",
                    "Last summer my family went to the beach. We collected seashells and had a picnic.",
                    "An activity is a verb and what it is about: collect seashells, have a picnic.",
                    "What did your family do at the beach? We collected seashells.",
                ),
                _node(
                    "EN-FT-DID",
                    "Did you…? Yes, I did.",
                    "Did you collect seashells? Yes, I did. Did you swim? No, I didn't.",
                    "Ask with Did you and the base verb; answer Yes, I did or No, I didn't.",
                    "Did you visit your grandparents? Yes, I did.",
                ),
            ],
            "relations": [{"source": "EN-FT-ACTIVITIES", "target": "EN-FT-DID", "type": "PREREQUISITE"}],
        }
    )
    return Chapter(package=package, lessons={})


def both_subjects() -> dict[str, Chapter]:
    return {**chapter_service.chapters(), FAMILY: english_unit()}


def raw_document(doc_id: str, text: str, *, chapter_id, subject=None, kind="BAI_GIANG") -> dict:
    """A document as stored; ``subject`` None leaves the field out (written before ENG-2)."""
    doc = {
        "_id": doc_id,
        "school_id": SCHOOL,
        "title": doc_id,
        "kind": kind,
        "chapter_id": chapter_id,
        "filename": f"{doc_id}.txt",
        "content_type": "text/plain",
        "size": len(text),
        "sha256": doc_id,
        "stored_path": f"documents/{doc_id}/x.txt",
        "uploaded_by": "t",
        "status": "READ",
        "text": text,
    }
    if subject is not None:
        doc["subject"] = subject
    return doc


MATH_TEXT = (
    "Muốn so sánh hai số thập phân, ta so sánh phần nguyên trước, rồi so sánh hàng phần mười. "
    "Phần nguyên là phần bên trái dấu phẩy. Seashells picnic beach. "
)
ENGLISH_TEXT = (
    "Did you go to the beach? Yes, I did. We collected seashells. So sánh hai số thập phân, phần nguyên, "
    "dấu phẩy, hàng phần mười: words a child may type in a lesson of English. "
)


async def mixed_database() -> InMemoryDatabase:
    """Documents of both subjects, with and without a chapter; the Mathematics ones in the legacy form."""
    database = InMemoryDatabase()
    await ensure_indexes(database)
    documents = database["documents"]
    await documents.insert_one(raw_document("m-chapter", MATH_TEXT * 4, chapter_id=DECIMALS))
    await documents.insert_one(raw_document("m-none", MATH_TEXT * 4, chapter_id=None))
    await documents.insert_one(raw_document("m-empty", MATH_TEXT * 4, chapter_id=""))
    await documents.insert_one(raw_document("e-unit", ENGLISH_TEXT * 4, chapter_id=FAMILY, subject="english"))
    await documents.insert_one(raw_document("e-none", ENGLISH_TEXT * 4, chapter_id=None, subject="english"))
    await documents.insert_one(raw_document("e-empty", ENGLISH_TEXT * 4, chapter_id="", subject="english"))
    return database


def service_of_both() -> RagService:
    return RagService(SCHOOL, both_subjects, embedder=lambda: HashEmbedder())


MATH_QUESTIONS = (
    "so sánh hai số thập phân thế nào",
    "phần nguyên là gì vậy cô",
    "0,5 và 0,50 cái nào lớn hơn",
    "so sanh phan nguyen truoc",
)
ENGLISH_QUESTIONS = (
    "seashells nghĩa là gì hả cô",
    "Did you collect seashells?",
    "We didn't swim, we had a picnic.",
)
NODES = {"math": (None, "KC-DEC-CMP", "KC-DEC-EQ"), "english": (None, "EN-FT-ACTIVITIES", "EN-FT-DID")}


# --- cross-subject leaks, both ways ---------------------------------------------------------------------


async def test_each_index_is_built_from_its_own_subject_only():
    database = await mixed_database()
    rag = service_of_both()
    math, english = await rag.current(database, "math"), await rag.current(database, "english")
    assert {c.subject for c in math.chunks} == {"math"} and {c.subject for c in english.chunks} == {"english"}
    math_docs = {c.document_id for c in math.chunks if c.document_id}
    english_docs = {c.document_id for c in english.chunks if c.document_id}
    assert math_docs == {"m-chapter", "m-none", "m-empty"}
    assert english_docs == {"e-unit", "e-none", "e-empty"}
    assert not any(c.chapter_id == FAMILY or (c.node_id or "").startswith("EN-") for c in math.chunks)
    assert not any(c.chapter_id == DECIMALS or (c.node_id or "").startswith("KC-") for c in english.chunks)
    # The graph of each index is its own subject's (no edge reaches the other subject's nodes).
    assert not any(n.startswith("EN-") for n in math.graph) and set(english.graph) <= {
        "EN-FT-ACTIVITIES",
        "EN-FT-DID",
    }
    assert set(rag.chapters("english")) == {FAMILY} and FAMILY not in rag.chapters("math")
    assert {d.id for d in rag.state("english").documents} == english_docs


@pytest.mark.parametrize("mode", ["question", "teach", "hint"])
async def test_a_math_question_in_an_english_session_finds_no_math_chunk(mode):
    database = await mixed_database()
    english = await service_of_both().current(database, "english")
    for question in MATH_QUESTIONS:
        for node in NODES["english"]:
            found = english.retrieve(question, node_id=node, mode=mode, k=10, max_chars=100_000)
            assert found.subject == "english"
            assert all(s.chunk.subject == "english" for s in found.ranked), (question, node)
            # the English documents with no chapter and no node are the passages that would have matched
            assert all(not (s.chunk.document_id or "").startswith("m-") for s in found.ranked)
        later, found = english.question(question, "EN-FT-DID", ["EN-FT-ACTIVITIES", "EN-FT-DID"])
        assert later in (None, "EN-FT-ACTIVITIES", "EN-FT-DID")
        assert all(s.chunk.subject == "english" for s in found.results)


@pytest.mark.parametrize("mode", ["question", "teach", "hint"])
async def test_an_english_question_in_a_math_session_finds_no_english_chunk(mode):
    database = await mixed_database()
    math = await service_of_both().current(database, "math")
    for question in ENGLISH_QUESTIONS:
        for node in NODES["math"]:
            found = math.retrieve(question, node_id=node, mode=mode, k=10, max_chars=100_000)
            assert found.subject == "math"
            assert all(s.chunk.subject == "math" for s in found.ranked), (question, node)
            assert all(not (s.chunk.document_id or "").startswith("e-") for s in found.ranked)


async def test_the_unassigned_passages_of_the_other_subject_are_what_isolation_keeps_out():
    """The English passages with no chapter share the math words of the question: one index of both
    subjects, filtered only by chapter at retrieval, would have handed them to a Mathematics session."""
    database = await mixed_database()
    rag = service_of_both()
    english = await rag.current(database, "english")
    near = english.retrieve(MATH_QUESTIONS[0], k=10)
    assert any(s.chunk.document_id in ("e-none", "e-empty") for s in near.ranked)  # they do match...
    math = await rag.current(database, "math")
    far = math.retrieve(MATH_QUESTIONS[0], chapter_id=DECIMALS, node_id="KC-DEC-CMP", k=50)
    assert all(s.chunk.subject == "math" for s in far.ranked)  # ...and never reach a math session


def test_an_index_refuses_chunks_of_another_subject():
    math = chapter_chunks(chapter_service.chapters()[DECIMALS])
    english = chapter_chunks(english_unit())
    with pytest.raises(ValueError, match="another subject"):
        RagIndex(math + english, None, {}, subject="math")
    with pytest.raises(ValueError, match="another subject"):
        RagIndex(math, None, {}, subject="english")
    assert len(RagIndex(english, None, {}, subject="english").chunks) == len(english)


def test_a_passage_is_only_tied_to_a_node_of_its_own_subject():
    reference = chapter_chunks(chapter_service.chapters()[DECIMALS]) + chapter_chunks(english_unit())

    def passage(subject: str, text: str) -> Chunk:
        return Chunk("p", text, "source_passage", "", None, "document", "d", True, subject=subject)

    # An English passage full of mathematics words, with no chapter: never tied to a math node.
    (en,) = tag_passages([passage("english", MATH_TEXT * 3)], reference)
    assert not (en.node_id or "").startswith("KC-") and not any(n.startswith("KC-") for n in en.candidates)
    # A Mathematics passage full of English family words: never tied to an English node.
    (ma,) = tag_passages([passage("math", ENGLISH_TEXT * 3 + "collect seashells have a picnic")], reference)
    assert not (ma.node_id or "").startswith("EN-") and not any(n.startswith("EN-") for n in ma.candidates)
    # Within its own subject it is tied as before.
    (fam,) = tag_passages([passage("english", "Did you swim? No, I didn't. Did you? Yes, I did.")], reference)
    assert fam.node_id == "EN-FT-DID" and fam.chapter_id == FAMILY


# --- a subject is required on new data; old data is Mathematics (DI-120) --------------------------------


def test_new_data_without_a_subject_is_an_error():
    with pytest.raises(TypeError):
        Chunk("a", "t", "theory", "c", None, "chapter", "x", True)  # type: ignore[call-arg]
    for wrong in ("", None, "history"):
        with pytest.raises(ValueError):
            Chunk("a", "t", "theory", "c", None, "chapter", "x", True, subject=wrong)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            check_subject(wrong)
        with pytest.raises(ValueError):
            analyzer_for(wrong)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RagIndex([], None, {})  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        RagIndex([], None, {}, subject="")
    base = raw_document("x", "t", chapter_id=None)
    with pytest.raises(ValidationError):
        TeacherDocument.from_doc(base)  # a new document: no legacy rule outside the repository
    package = english_unit().package.model_dump()
    package.pop("subject")
    with pytest.raises(ValidationError):
        ChapterPackage.model_validate(package)


async def test_every_read_names_its_subject():
    database = InMemoryDatabase()
    rag = service_of_both()
    with pytest.raises(TypeError):
        await rag.current(database)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        await rag.current(database, "history")
    with pytest.raises(TypeError):
        await DocumentRepository(database, SCHOOL).list_all()  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        rag.chapters("")


async def test_a_document_stored_before_subjects_is_read_as_mathematics():
    database = InMemoryDatabase()
    await ensure_indexes(database)
    await database["documents"].insert_one(raw_document("old", "Phần nguyên.", chapter_id=DECIMALS))
    await database["documents"].insert_one(
        raw_document("new", "We had a picnic.", chapter_id=None, subject="english")
    )
    await database["documents"].insert_one({**raw_document("bad", "x", chapter_id=None), "subject": None})
    repo = DocumentRepository(database, SCHOOL)
    assert LEGACY_SUBJECT == "math" and with_legacy_subject({"a": 1}) == {"a": 1, "subject": "math"}
    old = await repo.get("old")
    assert old is not None and old.subject == "math"
    with pytest.raises(ValidationError):  # present but empty: an error, not Mathematics
        await repo.get("bad")
    await database["documents"].delete_one({"_id": "bad"})
    assert [d.id for d in await repo.list_all("math")] == ["old"]
    assert [d.id for d in await repo.list_all("english")] == ["new"]
    assert {d.id: d.subject for d in await repo.list_recent()} == {"old": "math", "new": "english"}
    # read only: the stored document keeps no "subject" field (no migration, DI-120)
    stored = await database["documents"].find_one({"_id": "old"})
    assert "subject" not in stored


# --- analyzers (DI-121) ---------------------------------------------------------------------------------


def test_the_math_analyzer_is_the_one_bm25_always_used():
    assert MATH.tokens("Phần nguyên là gì? 0.25", folded=False) == tokens("Phần nguyên là gì? 0.25", False)
    assert TwoFormBM25(["a b"]).analyzer is MATH


def test_the_english_analyzer_writes_contractions_out_and_drops_punctuation():
    assert english_normalize("I'm Mai!") == "i am mai"
    assert english_normalize("I’m Mai.") == "i am mai"  # a typographic apostrophe too
    assert english_normalize("Who's he? He's my father's brother.") == "who is he he is my father brother"
    assert english_normalize("Did you collect seashells? No, I didn't.") == (
        "did you collect seashells no i did not"
    )
    assert english_normalize("I don't have a sister, I can't swim; we won't go.") == (
        "i do not have a sister i can not swim we will not go"
    )
    assert english_normalize("They're here, we've got it, you'll see, I'd like") == (
        "they are here we have got it you will see i would like"
    )
    assert ENGLISH.tokens("I'm", folded=False) == ENGLISH.tokens("I am", folded=False)
    index = TwoFormBM25(["I am Mai. I have a brother.", "My mother is a teacher."], ENGLISH)
    first, second = index.scores("I'm Mai")
    assert first > 0 and second == 0


def test_the_english_analyzer_meets_a_past_verb_with_its_base_form():
    """A child asks with the base form ("collect") about a text in the past ("collected"), or the other way
    round; an irregular past ("went", "had", "did") meets its base too."""
    from cavat.modules.rag.analyzers import lemma

    pairs = {
        "collected": "collect", "visited": "visit", "played": "play", "studied": "study", "stopped": "stop",
        "baked": "bake", "agreed": "agree", "went": "go", "had": "have", "did": "do", "swam": "swim",
        "bought": "buy",
    }  # fmt: skip
    for past, base in pairs.items():
        assert lemma(past) == lemma(base), (past, base)
    assert lemma("called") == "call" and lemma("added") == "add" and lemma("need") == "need"
    assert lemma("seashells") == "seashells" and lemma("nghe") == "ngh" and lemma("nghé") == "nghé"
    index = TwoFormBM25(
        ["Last summer we collected seashells and went to the beach.", "We have a cat."], ENGLISH
    )
    for question in ("Did you collect seashells?", "Do you go to the beach?"):
        first, second = index.scores(question)
        assert first > second, question
    assert index.coverage("collect seashells")[0] == 1.0
    assert TwoFormBM25(["Did you collect seashells?"], ENGLISH).coverage("collected seashells")[0] == 1.0
    # "didn't" is "did not": a question with "did" meets an answer that says "didn't".
    assert TwoFormBM25(["No, I didn't."], ENGLISH).coverage("did")[0] == 1.0


def test_the_english_analyzer_reads_vietnamese_with_english_words_in_it():
    # The child's Vietnamese is filler ("nghĩa là gì hả cô"); the English word is the content.
    assert ENGLISH.content_words("seashells nghĩa là gì hả cô") == ["seashells"]
    assert ENGLISH.content_words("Seashells nghia la gi ha co") == ["seashells"]
    # English words that fold like Vietnamese fillers stay English; with diacritics they are fillers.
    assert "the" in ENGLISH.content_words("the beach")
    assert "thế" not in ENGLISH.content_words("thế beach")
    index = TwoFormBM25(["We collected seashells.", "Phần nguyên của số thập phân."], ENGLISH)
    assert index.coverage("seashells nghĩa là gì hả cô")[0] == 1.0
    assert index.coverage("phan nguyen la gi")[1] == 1.0  # folded Vietnamese still matches


def test_the_math_only_rules_do_not_run_in_another_subject():
    """DI-122: the definition question (DI-50) and the terms outside the chapters (DI-79) read Vietnamese
    mathematics; in an English index a question stays a question and names no foreign term."""
    english = RagIndex(chapter_chunks(english_unit()), None, {}, subject="english")
    assert english.foreign_terms("dien tich hinh tron tinh the nao") == []
    assert english.retrieve("seashells là gì vậy cô").mode == "question"
    math = RagIndex(chapter_chunks(chapter_service.chapters()[DECIMALS]), None, {}, subject="math")
    assert "hinh tron" in math.foreign_terms("dien tich hinh tron tinh the nao")
    assert math.retrieve("phần nguyên là gì vậy cô").mode == "definition"


# --- API and trace --------------------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(session_api, "_rag_service", service_of_both())
    database = await mixed_database()
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)
    get_settings.cache_clear()


def test_the_teacher_reads_the_index_of_one_subject_and_sees_it(client):
    math = client.get("/v1/teachers/rag/status", headers=TEACHER).json()  # DI-123: Mathematics by default
    english = client.get("/v1/teachers/rag/status", params={"subject": "english"}, headers=TEACHER).json()
    assert (math["subject"], english["subject"]) == ("math", "english")
    assert {d["document_id"] for d in english["documents"]} == {"e-unit", "e-none", "e-empty"}
    assert {n["node_id"] for n in english["nodes"]} == {"EN-FT-ACTIVITIES", "EN-FT-DID"}
    assert not any(n["node_id"].startswith("EN-") for n in math["nodes"])
    found = client.get(
        "/v1/teachers/rag/search",
        params={"q": MATH_QUESTIONS[0], "subject": "english", "k": 10},
        headers=TEACHER,
    ).json()
    assert found["subject"] == "english" and found["results"]
    assert {r["subject"] for r in found["results"]} == {"english"}
    found = client.get(
        "/v1/teachers/rag/search", params={"q": "Did you collect seashells?"}, headers=TEACHER
    ).json()
    assert {r["subject"] for r in found["results"]} <= {"math"}
    rebuilt = client.post("/v1/teachers/rag/rebuild", params={"subject": "english"}, headers=TEACHER).json()
    assert rebuilt["subject"] == "english"
    wrong = client.get("/v1/teachers/rag/status", params={"subject": "history"}, headers=TEACHER)
    assert wrong.status_code == 422


def test_the_trace_records_the_subject_of_the_index_and_of_every_chunk():
    index = RagIndex(chapter_chunks(english_unit()), None, {}, subject="english")
    found = index.retrieve("Did you collect seashells?")
    details = _result("rag", "retrieve", found, (), {})["details"]
    assert details["subject"] == "english" and details["chunks"]
    assert {c["subject"] for c in details["chunks"]} == {"english"}


# --- regression: Mathematics retrieves exactly as before subjects existed --------------------------------

_PARA = (
    "Muốn so sánh hai số thập phân, ta so sánh phần nguyên trước, rồi so sánh hàng phần mười, hàng phần "
    "trăm. Số nào có chữ số lớn hơn thì số đó lớn hơn. "
)
_TRI = (
    "Muốn tính diện tích hình tam giác ta lấy độ dài đáy nhân với chiều cao (cùng đơn vị đo) rồi chia cho 2. "
    "Đường cao là đoạn thẳng kẻ từ đỉnh vuông góc với cạnh đáy. "
)
_MIX = "Bài tập về nhà: làm bài 1, 2, 3 vào vở ô li. Chương này có số thập phân và diện tích hình thang. "
# Stored before ENG-2 (no subject field): the documents of the snapshot the golden digests were made from.
_LEGACY_DOCS = (
    ("d-cmp", "SGK so sánh", "SGK", DECIMALS, "[Trang 1]\n" + (_PARA * 12) + "\n\n" + (_PARA * 8)),
    ("d-tri", "Bài giảng tam giác", "BAI_GIANG", None, "[Trang 3]\n" + (_TRI * 14)),
    ("d-mix", "Phiếu ôn", "PHIEU", "", _MIX * 20),
    ("d-key", "Đáp án", "DAP_AN", DECIMALS, _PARA * 10),
    ("d-off", "Thông báo", "KHAC", None, "qzx wvk jjq. " * 120),  # tied to no node, no candidate
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _row(s) -> list:
    return [
        s.chunk.chunk_id,
        s.chunk.node_id,
        s.chunk.chapter_id,
        round(s.bm25, 9),
        s.bm25_rank,
        round(s.cosine, 6),
        s.cosine_rank,
        s.distance,
        round(s.fused, 12),
        round(s.final, 12),
        round(s.coverage, 9),
        list(s.reasons),
    ]


async def test_mathematics_retrieves_exactly_as_before_subjects():
    """Every eval question of the RAG (seven datasets), in each of the 12 configurations, the routing of a
    child's question and the foreign terms: ranks and scores the same as at commit 565b6a0. Offline, without
    vectors (pure Python, the same on every machine); the documents are stored without a subject."""
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    database = InMemoryDatabase()
    for doc_id, title, kind, chapter_id, text in _LEGACY_DOCS:
        stored = raw_document(doc_id, text, chapter_id=chapter_id, kind=kind)
        await database["documents"].insert_one({**stored, "title": title, "sha256": doc_id})
    chapters = {cid: c for cid, (c, _) in chapter_service.chapter_sources().items()}
    index = await RagService(SCHOOL, lambda: chapters, embedder=lambda: None).current(database, "math")
    chunks = [[c.chunk_id, c.node_id, c.chapter_id, c.kind, list(c.candidates), c.text] for c in index.chunks]
    assert _digest(chunks) == golden["chunks"]
    orders = {n.id: c.topological_order() for c in chapters.values() for n in c.package.nodes}
    seen: dict[str, str] = {}
    for dataset in sorted((REPO_ROOT / "evals/datasets").glob("rag-*.yaml")):
        for case in load_cases(dataset):
            entries = {}
            for config, flags in ALL_CONFIGS.items():
                f = index.retrieve(
                    case.q,
                    node_id=case.node,
                    mode=case.mode,
                    used=case.used,
                    misconception_id=case.misconception,
                    k=3,
                    max_chars=1800,
                    **flags,
                )
                entries[config] = {
                    "mode": f.mode,
                    "grounded": f.grounded,
                    "grounding": f.grounding,
                    "cand": f.candidates,
                    "sem": f.semantic,
                    "results": [s.chunk.chunk_id for s in f.results],
                    "ranked": [_row(s) for s in f.ranked],
                }
            later, f = index.question(case.q, case.node, orders.get(case.node, []))
            entries["question"] = [later, [_row(s) for s in f.results], f.grounded]
            entries["foreign"] = index.foreign_terms(case.q)
            seen[f"{dataset.stem}:{case.id}"] = _digest(entries)
    assert seen.keys() == golden["cases"].keys()
    changed = sorted(k for k in seen if seen[k] != golden["cases"][k])
    assert changed == [], f"Mathematics retrieval changed for {len(changed)} questions: {changed[:10]}"
