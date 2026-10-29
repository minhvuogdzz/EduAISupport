"""The teacher's document library and lesson content (DOC-1). In-memory database, files in a temp dir."""

import io
import zipfile

import pytest
from cavat.config import get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.library import api as library_api
from cavat.modules.library.extract import extract
from cavat.modules.session.api import get_database
from fastapi.testclient import TestClient

TEACHER = {"X-Demo-Teacher": "1"}


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    # No call to Gemini from a test: a fake OCR reads scans and photos.
    monkeypatch.setattr(
        library_api, "_ocr", lambda: lambda data, mime, prompt: f"[Trang 1]\nChữ đọc bằng OCR ({mime})"
    )
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)
    get_settings.cache_clear()


def docx(*paragraphs: str, row: tuple[str, str] | None = None) -> bytes:
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    if row:
        cells = "".join(f"<w:tc><w:p><w:r><w:t>{c}</w:t></w:r></w:p></w:tc>" for c in row)
        body += f"<w:tbl><w:tr>{cells}</w:tr></w:tbl>"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        info = zipfile.ZipInfo("word/document.xml", date_time=(2026, 1, 1, 0, 0, 0))
        archive.writestr(info, f"<w:document {w}><w:body>{body}</w:body></w:document>")
    return out.getvalue()


def pdf(text: str) -> bytes:
    """A one-page PDF with a text layer (ASCII text)."""
    stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def upload(client, name: str, data: bytes, **form: str):
    return client.post(
        "/v1/teachers/documents",
        files={"file": (name, data)},
        data={
            "title": form.get("title", ""),
            "kind": form.get("kind", "KHAC"),
            "chapter_id": form.get("chapter", ""),
        },
        headers=TEACHER,
    )


def test_text_is_read_from_every_kind_of_file():
    assert extract(b"Bai 1. So thap phan", "a.txt", None).text == "Bai 1. So thap phan"
    word = extract(docx("Bài 1: Số thập phân", "Ví dụ 0,25", row=("Câu", "Đáp án")), "giao-an.docx", None)
    assert word.method == "docx" and word.text == "Bài 1: Số thập phân\nVí dụ 0,25\nCâu | Đáp án"
    page = extract(pdf("So sanh hai so thap phan: 0,25 va 0,3. " * 2), "sgk.pdf", None)
    assert page.method == "pdf-text" and page.pages == 1 and "[Trang 1]" in page.text and "0,25" in page.text
    photo = extract(b"\x89PNG...", "phieu.png", None)
    assert photo.needs_ocr and photo.text == ""


def test_the_teacher_uploads_reads_downloads_and_deletes_a_document(client, tmp_path):
    payload = docx("Câu 1. Viết 7/100 thành số thập phân.")
    made = upload(
        client,
        "Phiếu bài tập 1.docx",
        payload,
        title="Phiếu 1",
        kind="BAI_TAP",
        chapter="math-g5-decimals",
    )
    assert made.status_code == 201, made.text
    doc = made.json()
    assert (doc["title"], doc["kind"], doc["chapter_id"], doc["status"], doc["method"]) == (
        "Phiếu 1",
        "BAI_TAP",
        "math-g5-decimals",
        "READ",
        "docx",
    )
    assert (tmp_path / "documents" / doc["document_id"]).is_dir()  # the original is kept on disk

    listed = client.get("/v1/teachers/documents", headers=TEACHER).json()
    assert [d["document_id"] for d in listed] == [doc["document_id"]] and "text" not in listed[0]
    detail = client.get(f"/v1/teachers/documents/{doc['document_id']}", headers=TEACHER).json()
    assert detail["text"] == "Câu 1. Viết 7/100 thành số thập phân."
    original = client.get(f"/v1/teachers/documents/{doc['document_id']}/file", headers=TEACHER)
    assert original.status_code == 200 and original.content == payload

    assert client.delete(f"/v1/teachers/documents/{doc['document_id']}", headers=TEACHER).status_code == 204
    assert client.get("/v1/teachers/documents", headers=TEACHER).json() == []
    assert not (tmp_path / "documents" / doc["document_id"]).exists()


def test_photos_go_through_ocr_and_wrong_files_are_refused(client, monkeypatch):
    photo = upload(client, "trang-sgk.jpg", b"\xff\xd8 jpeg bytes").json()
    assert (photo["status"], photo["method"]) == ("READ", "ocr-gemini")
    assert upload(client, "virus.exe", b"MZ").status_code == 415
    assert upload(client, "trong.txt", b"").status_code == 422
    monkeypatch.setattr(library_api, "MAX_BYTES", 10)
    assert upload(client, "lon.txt", b"x" * 11).status_code == 413
    # Teachers only.
    assert client.get("/v1/teachers/documents").status_code == 401


def test_the_teacher_reads_the_chapter_with_its_answers(client):
    chapters = client.get("/v1/teachers/chapters", headers=TEACHER).json()
    decimals = next(c for c in chapters if c["chapter_id"] == "math-g5-decimals")
    assert decimals["nodes"] == 7 and decimals["items"] > 20
    content = client.get("/v1/teachers/chapters/math-g5-decimals", headers=TEACHER).json()
    assert content["source"].endswith("chuong-so-thap-phan/chapter.yaml")
    frac = content["nodes"][0]
    assert frac["name"] == "Phân số thập phân" and frac["theory"][0]["reply"]
    item = next(i for i in frac["items"] if i["item_id"] == "TP-PR-01")
    assert (item["answer"], item["stage"]) == ("0,9", "Luyện tập")
    assert item["hints"] and item["wrong_answers"] == {"0,09": "FRAC-M01"}
    assert any(m["id"] == "FRAC-M01" for m in content["misconceptions"])
    assert client.get("/v1/teachers/chapters/nope", headers=TEACHER).status_code == 404


def test_the_gemini_reader_keeps_readings_and_checks_with_another_model(tmp_path):
    """INGEST-1: readings are cached with their model; the check skips the first reading's model."""
    from cavat.modules.ai_gateway.base import QuotaExceeded, VisionResult

    class Router:
        vision_models = ("gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite")

        def __init__(self):
            self.calls = []

        def describe_image_with(self, model, data, prompt, *, mime_type):
            self.calls.append(model)
            if model == "gemini-3.8-flash" and len(self.calls) > 1:
                raise QuotaExceeded("rate limited", model=model, reset_at=None)
            return VisionResult(model=model, text=f"đọc bởi {model}")

    router = Router()
    reader = library_api.GeminiReader(router, tmp_path)
    assert reader(b"page", "application/pdf", "p") == "đọc bởi gemini-3.8-flash"
    assert reader.last_model == "gemini-3.8-flash"
    assert reader.check(b"page", "application/pdf", "p", other_than="gemini-3.8-flash") == (
        "đọc bởi gemini-3.5-flash-lite"
    )
    assert reader(b"page", "application/pdf", "p") == "đọc bởi gemini-3.8-flash"  # from the disk cache
    assert router.calls == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
