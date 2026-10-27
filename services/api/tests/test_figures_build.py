"""FIG-1: figures are paired with the "[Hình: …]" of the questions, stored under their own keys, and served
with the teacher's say. In-memory database, PDF written by the test (``figures_pdf``)."""

from __future__ import annotations

import io

import pytest
from cavat.config import get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.figures import service
from cavat.modules.figures.build import plan_chapter, question_id_of, questions_of
from cavat.modules.figures.finder import Box, FigureDocument, Region
from cavat.modules.figures.matching import (
    alt_of,
    evidence,
    match_page,
    panels_of,
    split_pages,
    tags_of,
)
from cavat.modules.figures.repository import FigureRepository
from cavat.modules.library.repository import TeacherDocument
from cavat.modules.session.api import get_database
from cavat.modules.session.service import DEMO_SCHOOL_ID  # noqa: E402
from fastapi.testclient import TestClient
from figures_pdf import TAG_HOUSE, TAG_ROW, TAG_TRAPEZOID, TAG_TRIANGLE, TEXT, sample_pdf
from PIL import Image

SCHOOL = DEMO_SCHOOL_ID
CHAPTER = "math-g5-area-triangle-trapezoid"
TEACHER = {"X-Demo-Teacher": "1"}
STUDENT = {"X-Demo-Student": "s1"}


def region(*labels: str, left: float = 0, panels: int = 1) -> Region:
    return Region(page=1, box=Box(left, 0, left + 100, 80), members=(), labels=labels, panels=panels)


def item(item_id: str, question: str, part: str = "", page: int = 1) -> dict:
    return {
        "item_id": item_id,
        "part": part,
        "question": question,
        "document_id": "d1",
        "page": page,
        "label": "1",
    }


ITEMS = [
    item("DTTGHT-BT-01", f"Tính diện tích. {TAG_TRIANGLE}", page=1),
    item("DTTGHT-BT-02a", f"Hình thang. {TAG_TRAPEZOID}", "a", page=2),
    item("DTTGHT-BT-02b", f"Hình thang. {TAG_TRAPEZOID}", "b", page=2),
    item("DTTGHT-BT-03", f"Nhà. {TAG_HOUSE}", page=2),
    item("DTTGHT-BT-04", f"Ba tam giác. {TAG_ROW}", page=3),
    item("DTTGHT-BT-05", "Không có hình", page=3),
]


def document(path_name: str = "baitap.pdf", text: str = TEXT) -> TeacherDocument:
    return TeacherDocument(
        id="d1",
        school_id=SCHOOL,
        title="Bài tập",
        kind="BAI_TAP",
        chapter_id=CHAPTER,
        filename=path_name,
        content_type="application/pdf",
        size=1,
        sha256="x",
        stored_path=f"documents/d1/{path_name}",
        uploaded_by="t",
        text=text,
    )


# --- reading the words ----------------------------------------------------------------------------------


def test_tags_pages_and_panels_are_read_from_the_text():
    assert tags_of(TEXT) == [TAG_TRIANGLE, TAG_TRAPEZOID, TAG_HOUSE, TAG_ROW]
    assert sorted(split_pages(TEXT)) == [1, 2, 3]
    assert panels_of(TAG_ROW) == 3 and panels_of(TAG_HOUSE) == 1
    assert alt_of(TAG_HOUSE).startswith("mặt trước ngôi nhà")
    assert tags_of("[Hình: một dòng\n  tả hai dòng]") == ["[Hình: một dòng tả hai dòng]"]


def test_a_question_id_drops_the_sub_question_letter_and_groups_its_items():
    assert question_id_of({"item_id": "DTTGHT-BT-02b", "part": "b"}) == "DTTGHT-BT-02"
    assert question_id_of({"item_id": "DTTGHT-DE1-B4", "part": ""}) == "DTTGHT-DE1-B4"
    found = {q.question_id: q for q in questions_of(ITEMS)}
    assert sorted(found) == ["DTTGHT-BT-01", "DTTGHT-BT-02", "DTTGHT-BT-03", "DTTGHT-BT-04"]
    assert found["DTTGHT-BT-02"].item_ids == ["DTTGHT-BT-02a", "DTTGHT-BT-02b"]


# --- pairing --------------------------------------------------------------------------------------------


def test_the_order_and_the_content_pair_descriptions_with_drawings():
    tags = [TAG_TRAPEZOID, TAG_HOUSE]
    regions = [region("A", "B", "C", "D", "H", "8 cm", "6 cm", "14 cm"), region("2 m", "4 m", "6 m")]
    match = match_page(2, tags, regions)
    assert [p.tag for p in match.pairs] == tags
    assert all(p.confidence == "SURE" for p in match.pairs)
    assert match.spare == [] and match.unmatched_tags == []


def test_a_frame_the_finder_took_for_a_drawing_is_skipped():
    frame = region("•")
    match = match_page(2, [TAG_HOUSE], [frame, region("2 m", "4 m", "6 m", left=200)])
    assert [p.region.labels for p in match.pairs] == [("2 m", "4 m", "6 m")]
    assert match.spare == [frame]


def test_a_description_that_shares_nothing_gets_no_drawing_when_counts_differ():
    match = match_page(1, [TAG_HOUSE], [region("A", "B", "C"), region("X", "Y")])
    assert match.pairs == [] and match.unmatched_tags == [TAG_HOUSE]


def test_equal_counts_pair_by_order_and_wait_for_the_teacher():
    tag = "[Hình: 100 ô vuông, tô màu 3 cột đầu tiên]"
    match = match_page(1, [tag], [region("= 0,3")])
    assert len(match.pairs) == 1 and match.pairs[0].confidence == "REVIEW"


def test_a_description_of_panels_takes_a_row_of_drawings():
    row = [region("A", "B", "C", "h", "a", left=left) for left in (0, 130, 260)]
    match = match_page(3, [TAG_ROW], row)
    assert len(match.pairs) == 1 and match.pairs[0].region.panels == 3
    assert "pA" in evidence(TAG_ROW) and "lh" in evidence(TAG_ROW)


# --- from documents to figures ---------------------------------------------------------------------------


@pytest.fixture
def pdf_file(tmp_path):
    path = tmp_path / "documents" / "d1" / "baitap.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(sample_pdf())
    return path


def test_every_question_with_a_description_takes_its_drawing(pdf_file, tmp_path):
    built = plan_chapter(CHAPTER, [document()], ITEMS, service.storage_reader(tmp_path))
    assert built.questions == 4 and built.tags == 4
    assert [(m.question_id, m.order) for m in built.matches] == [
        ("DTTGHT-BT-01", 1),
        ("DTTGHT-BT-02", 1),
        ("DTTGHT-BT-03", 1),
        ("DTTGHT-BT-04", 1),
    ]
    assert built.unmatched == [] and built.matched_questions == 4
    row = built.matches[-1]
    assert row.panels == 3 and row.width > 2 * built.matches[0].height // 3
    assert Image.open(io.BytesIO(row.png)).size == (row.width, row.height)
    assert built.matches[1].item_ids == ["DTTGHT-BT-02a", "DTTGHT-BT-02b"]


def test_a_missing_file_or_a_description_off_the_page_is_reported_not_guessed(tmp_path):
    built = plan_chapter(CHAPTER, [document()], ITEMS, service.storage_reader(tmp_path))
    assert {u.reason for u in built.unmatched} == {"NO_FILE"}
    assert len(built.unmatched) == 4
    # a question whose description the page does not hold
    path = tmp_path / "documents" / "d1" / "baitap.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(sample_pdf())
    other = [item("DTTGHT-BT-09", "x [Hình: tam giác không có trên trang]", page=1)]
    built = plan_chapter(CHAPTER, [document()], other, service.storage_reader(tmp_path))
    assert [u.reason for u in built.unmatched] == ["NOT_ON_PAGE"]


async def test_store_keeps_the_teachers_decision_and_own_picture(pdf_file, tmp_path):
    database = InMemoryDatabase()
    await ensure_indexes(database)
    built = plan_chapter(CHAPTER, [document()], ITEMS, service.storage_reader(tmp_path))
    first = await service.store(database, SCHOOL, built, tmp_path)
    assert (first.created, first.updated, first.kept) == (4, 0, 0)
    repo = FigureRepository(database, SCHOOL)
    figures = await repo.list_chapter(CHAPTER)
    assert [f.status for f in figures] == ["AUTO"] * 4
    assert all((tmp_path / f.file).is_file() for f in figures)
    # rejected by the teacher: still rejected after the same drawing is built again
    await repo.decide(figures[0].id, "REJECTED", "t1")
    again = await service.store(database, SCHOOL, built, tmp_path)
    assert (again.created, again.updated, again.kept) == (0, 3, 1)
    after = {f.question_id: f for f in await repo.list_chapter(CHAPTER)}
    assert after["DTTGHT-BT-01"].status == "REJECTED" and after["DTTGHT-BT-01"].id == figures[0].id
    # the teacher's own picture is never replaced
    png = io.BytesIO()
    Image.new("RGB", (40, 30), "red").save(png, "PNG")
    own = await service.put_upload(
        database,
        SCHOOL,
        tmp_path,
        chapter_id=CHAPTER,
        question_id="DTTGHT-BT-03",
        order=1,
        tag="",
        alt="",
        data=png.getvalue(),
        by="t1",
    )
    assert own.method == "UPLOAD" and own.status == "APPROVED" and own.tag == TAG_HOUSE
    await service.store(database, SCHOOL, built, tmp_path)
    kept = await repo.get_slot(CHAPTER, "DTTGHT-BT-03", 1)
    assert kept is not None and kept.method == "UPLOAD" and kept.id == own.id


async def test_figures_of_one_school_are_invisible_to_another(pdf_file, tmp_path):
    database = InMemoryDatabase()
    await ensure_indexes(database)
    built = plan_chapter(CHAPTER, [document()], ITEMS, service.storage_reader(tmp_path))
    await service.store(database, SCHOOL, built, tmp_path)
    assert await FigureRepository(database, "other-school").list_chapter(CHAPTER) == []


def test_a_picture_that_is_not_an_image_is_refused():
    with pytest.raises(ValueError, match="NOT_AN_IMAGE"):
        service.normalise_upload(b"not an image")
    with pytest.raises(ValueError, match="TOO_BIG"):
        service.normalise_upload(b"x" * (service.MAX_UPLOAD_BYTES + 1))


def test_the_preview_names_questions_by_code_and_writes_every_picture(pdf_file, tmp_path):
    built = plan_chapter(CHAPTER, [document()], ITEMS, service.storage_reader(tmp_path))
    page = service.write_preview(built, tmp_path / "figures-preview" / CHAPTER)
    names = {p.name for p in page.parent.iterdir()}
    assert {"DTTGHT-BT-01-h1.png", "DTTGHT-BT-04-h1.png", "index.html"} <= names
    assert "DTTGHT-BT-02" in page.read_text(encoding="utf-8")


def test_the_sample_figures_exist_as_drawings(pdf_file):
    with FigureDocument(pdf_file.read_bytes()) as doc:
        assert [len(doc.find(p)) for p in (1, 2, 3)] == [1, 2, 3]


# --- the API --------------------------------------------------------------------------------------------


@pytest.fixture
async def client(tmp_path, pdf_file, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    database = InMemoryDatabase()
    await ensure_indexes(database)
    built = plan_chapter(CHAPTER, [document()], ITEMS, service.storage_reader(tmp_path))
    built.matches[3].confidence = "REVIEW"  # the row of panels waits for the teacher
    await service.store(database, DEMO_SCHOOL_ID, built, tmp_path)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)
    get_settings.cache_clear()


def test_a_child_sees_only_the_figures_shown_to_children(client):
    listed = client.get("/v1/figures", params={"chapter_id": CHAPTER}, headers=STUDENT).json()
    assert [f["question_id"] for f in listed] == ["DTTGHT-BT-01", "DTTGHT-BT-02", "DTTGHT-BT-03"]
    hidden = next(
        f for f in client.get("/v1/teachers/figures", params={"chapter_id": CHAPTER}, headers=TEACHER).json()
    )
    assert hidden["status"] in ("AUTO", "REVIEW")
    first = listed[0]
    image = client.get(f"/v1/figures/{first['figure_id']}/image", headers=STUDENT)
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(image.content)).width == first["width"]
    assert first["tag"] == TAG_TRIANGLE and first["alt"].startswith("tam giác ABC")


def test_no_identity_no_figure(client):
    assert client.get("/v1/figures", params={"chapter_id": CHAPTER}).status_code == 401


def test_the_teacher_approves_rejects_and_replaces(client):
    rows = client.get("/v1/teachers/figures", params={"chapter_id": CHAPTER}, headers=TEACHER).json()
    row = next(r for r in rows if r["question_id"] == "DTTGHT-BT-04")
    assert row["status"] == "REVIEW" and not row["shown"]
    assert client.get(f"/v1/figures/{row['figure_id']}/image", headers=STUDENT).status_code == 404
    assert client.get(f"/v1/figures/{row['figure_id']}/image", headers=TEACHER).status_code == 200
    ok = client.post(
        f"/v1/teachers/figures/{row['figure_id']}/decision", json={"action": "approve"}, headers=TEACHER
    )
    assert ok.json()["status"] == "APPROVED" and ok.json()["decided_by"] == "1"
    assert client.get(f"/v1/figures/{row['figure_id']}/image", headers=STUDENT).status_code == 200
    gone = client.post(
        f"/v1/teachers/figures/{row['figure_id']}/decision", json={"action": "reject"}, headers=TEACHER
    )
    assert gone.json()["status"] == "REJECTED"
    assert client.get(f"/v1/figures/{row['figure_id']}/image", headers=STUDENT).status_code == 404
    undone = client.post(
        f"/v1/teachers/figures/{row['figure_id']}/decision", json={"action": "undo"}, headers=TEACHER
    )
    assert undone.json()["status"] in ("AUTO", "REVIEW")
    # a student cannot decide
    assert (
        client.post(
            f"/v1/teachers/figures/{row['figure_id']}/decision", json={"action": "approve"}, headers=STUDENT
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/teachers/figures/nope/decision", json={"action": "approve"}, headers=TEACHER
        ).status_code
        == 404
    )

    png = io.BytesIO()
    Image.new("RGB", (60, 40), "blue").save(png, "PNG")
    files = {"file": ("hinh.png", png.getvalue(), "image/png")}
    form = {"chapter_id": CHAPTER, "question_id": "DTTGHT-BT-05", "order": "1", "tag": "[Hình: x]"}
    made = client.post("/v1/teachers/figures", data=form, files=files, headers=TEACHER)
    assert made.status_code == 201 and made.json()["method"] == "UPLOAD" and made.json()["shown"]
    bad = client.post(
        "/v1/teachers/figures", data=form, files={"file": ("a.txt", b"hi", "text/plain")}, headers=TEACHER
    )
    assert bad.status_code == 415
