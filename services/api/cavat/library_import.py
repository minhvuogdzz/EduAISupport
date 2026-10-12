"""Import a folder of the teacher's documents into the library (INGEST-1): ``make library-import DIR=...``.

The owner keeps the documents of the two demo chapters in one folder, named ``<chương>-<loại>[-dapan].pdf``:
``STP-lythuyet.pdf``, ``STP-baitap.pdf``, ``STP-baitap-dapan.pdf``... Each file goes through the same path
as the upload button of the teacher's "Tài liệu" tab (``library.api.read_document``): kept on disk, read
page by page, the pages that lose fractions or figures read again by Gemini and checked (DI-43). An answer
key is linked to the document of its questions and, like a test, never reaches the RAG (CLAUDE.md rule 2).

It writes to the database of services/api/.env (cavat_dev): these are the teacher's own documents, not demo
data, so they carry no ``is_demo`` (CLAUDE.md rules 16-17). Nothing runs it at startup or in a test.
A file already imported is skipped; ``--again`` reads every file again (Gemini's readings come from the
disk cache, so this costs no quota for pages already read).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

from cavat import db
from cavat.config import REPO_ROOT, get_settings
from cavat.modules.identity.repository import UserRepository
from cavat.modules.library import api as library_api
from cavat.modules.library.extract import KINDS as FILE_KINDS
from cavat.modules.library.extract import extension_of
from cavat.modules.library.repository import RAG_KINDS, DocumentRepository, TeacherDocument
from cavat.modules.session.service import DEMO_SCHOOL_ID

CHAPTERS = {
    "STP": ("math-g5-decimals", "Số thập phân"),
    "DTTGHT": ("math-g5-area-triangle-trapezoid", "Diện tích hình tam giác, hình thang"),
}
KINDS = {
    "lythuyet": ("BAI_GIANG", "Lý thuyết"),
    "giaoan": ("GIAO_AN", "Giáo án"),
    "baitap": ("BAI_TAP", "Bài tập"),
    "phieuluyentap": ("PHIEU", "Phiếu luyện tập"),
    "dekiemtra": ("DE_KIEM_TRA", "Đề kiểm tra"),
    "loisai": ("LOI_SAI", "Lỗi sai hay gặp"),
}


def describe(path: Path) -> tuple[str, str, str, str] | None:
    """(chapter id, kind, title, the stem of the questions for an answer key) from the file name."""
    parts = path.stem.split("-")
    if len(parts) not in (2, 3) or parts[0] not in CHAPTERS or parts[1] not in KINDS:
        return None
    if len(parts) == 3 and parts[2] != "dapan":
        return None
    chapter_id, chapter_title = CHAPTERS[parts[0]]
    kind, kind_title = KINDS[parts[1]]
    if len(parts) == 3:
        return (
            chapter_id,
            "DAP_AN",
            f"Đáp án {kind_title.lower()} · {chapter_title}",
            f"{parts[0]}-{parts[1]}",
        )
    return chapter_id, kind, f"{kind_title} · {chapter_title}", ""


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--again", action="store_true", help="read every file again (cached readings)")
    args = parser.parse_args()
    folder = args.folder if args.folder.is_absolute() else REPO_ROOT / args.folder
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    database = db.get_db(settings)
    repo = DocumentRepository(database, DEMO_SCHOOL_ID)
    teachers = await UserRepository(database, DEMO_SCHOOL_ID).list_by_kind("TEACHER")
    uploaded_by = teachers[0].id if teachers else "import"
    ocr = library_api._ocr()
    if ocr is None:
        print("Chưa có GEMINI_API_KEY: trang có ảnh hoặc hình vẽ được đánh dấu để giáo viên xem.")
    known = {d.sha256: d for d in await repo.list_all()}
    files = sorted(
        (p for p in folder.iterdir() if extension_of(p.name) in FILE_KINDS),
        key=lambda p: (p.stem.endswith("-dapan"), p.name),  # questions before their answer keys
    )
    ids_by_stem: dict[str, str] = {}
    print(f"Database: {settings.mongodb_db} · thư mục: {folder}")
    for path in files:
        about = describe(path)
        if about is None:
            print(f"  bỏ qua {path.name}: tên file không theo mẫu <STP|DTTGHT>-<loại>[-dapan]")
            continue
        chapter_id, kind, title, questions_of = about
        data = path.read_bytes()
        old = known.get(hashlib.sha256(data).hexdigest())
        if old is not None and not args.again:
            ids_by_stem[path.stem] = old.id
            print(f"  đã có  {path.name}")
            continue
        document: TeacherDocument = await asyncio.to_thread(
            library_api.read_document,
            data,
            path.name,
            school_id=DEMO_SCHOOL_ID,
            title=title,
            kind=kind,
            chapter_id=chapter_id,
            answers_for=ids_by_stem.get(questions_of, ""),
            uploaded_by=uploaded_by,
            ocr=ocr,
            document_id=old.id if old else None,
        )
        if old is not None:
            await repo.delete(old.id)
        await repo.create(document)
        ids_by_stem[path.stem] = document.id
        again = [r.page for r in document.page_reads if r.reason]
        review = [r.page for r in document.page_reads if r.status != "OK"]
        print(
            f"  nhập   {path.name}: {kind}, {document.pages} trang, đọc lại {len(again)} trang"
            + (f", cần xem trang {review}" if review else "")
            + ("" if kind in RAG_KINDS else ", không vào RAG")
        )
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
