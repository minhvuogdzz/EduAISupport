"""Cut the figures of the two demo chapters out of the teacher's documents (FIG-1, ADR-037):
``make figures`` (``make figures DRY=1`` first).

Reads the documents and the item banks of the database of services/api/.env and their original PDFs under
``var/storage/documents/``. For each question whose text holds "[Hình: …]" it finds the drawing on the
page (from the PDF's vector structure, no model is called), cuts it to a PNG and keeps it in its own
collection ``figures``. The words of the questions, the item banks and the teaching plans are not touched.

``--dry`` writes nothing to the database or to ``var/storage/figures/``: it prints how many figures it
found, how many questions they serve and which questions got none, and puts the pictures beside their
descriptions in ``var/storage/figures-preview/<chapter>/index.html`` to be looked at. Nothing runs this at
startup or in a test.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from cavat import db
from cavat.config import get_settings
from cavat.modules.figures import service
from cavat.modules.figures.build import ChapterFigures
from cavat.modules.figures.repository import FigureRepository
from cavat.modules.ingest.service import PREFIXES
from cavat.modules.session.service import DEMO_SCHOOL_ID


def describe(built: ChapterFigures) -> list[str]:
    sure = sum(m.confidence == "SURE" for m in built.matches)
    lines = [
        f'  câu có chữ "[Hình …]": {built.questions} câu, {built.tags} hình được tả',
        f"  hình vẽ tìm thấy trên các trang đó: {built.drawings}",
        f"  khớp: {len(built.matches)} hình, cho {built.matched_questions}/{built.questions} câu "
        f"({sure} chắc, {len(built.matches) - sure} chờ giáo viên duyệt)",
    ]
    if built.unmatched:
        lines.append(f"  KHÔNG khớp ({len(built.unmatched)} hình, {len(built.unmatched_questions)} câu):")
        lines += [
            f"    - {u.question_id} · hình {u.order}: {u.reason} ({u.filename}, trang {u.page})"
            for u in built.unmatched
        ]
    else:
        lines.append("  không có câu nào thiếu hình")
    if built.spare:
        lines.append(f"  hình vẽ không câu nào nhận: {len(built.spare)}")
        lines += [f"    - {s.filename}, trang {s.page}" for s in built.spare]
    for other in built.others:
        if other.tags or other.kind in ("BAI_GIANG",):
            lines.append(
                f"  bài giảng {other.filename}: {other.tags} hình được tả, {other.drawings} hình vẽ, "
                f"{other.paired} ghép được (chưa gắn vào câu nào)"
            )
    return lines


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry", action="store_true", help="read and preview only: write nothing")
    parser.add_argument("--chapter", action="append", help="one chapter id (default: both demo chapters)")
    args = parser.parse_args()
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    database = db.get_db(settings)
    storage = settings.storage_dir
    mode = "CHẠY KHÔ: chỉ đọc, không ghi" if args.dry else "ghi vào bộ sưu tập figures"
    print(f"Database: {settings.mongodb_db} · {mode} · tài liệu gốc: {storage / 'documents'}")
    if not args.dry:
        await FigureRepository.ensure_indexes(database)
    for chapter_id in args.chapter or PREFIXES:
        print(chapter_id)
        try:
            built = await service.plan(database, DEMO_SCHOOL_ID, chapter_id, storage)
        except service.FigureBuildError as exc:
            print(f"  bỏ qua: {exc}")
            continue
        print("\n".join(describe(built)))
        preview = service.write_preview(built, storage / "figures-preview" / chapter_id)
        print(f"  ảnh xem thử: {preview}")
        if not args.dry:
            stored = await service.store(database, DEMO_SCHOOL_ID, built, storage)
            print(
                f"  đã ghi: {stored.created} mới, {stored.updated} cập nhật, {stored.kept} giữ nguyên "
                f"(quyết định hoặc hình giáo viên tự đưa), {stored.stale} hình cũ không còn khớp"
            )
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
