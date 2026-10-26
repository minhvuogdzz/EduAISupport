"""Build the figures of a chapter from the documents of the database and keep them (FIG-1, ADR-034):
``make figures`` and the teacher's page share this.

``plan`` only reads (the documents, the item bank, the original PDFs) and returns what would be stored.
``store`` writes the pictures under ``var/storage/figures/`` and the figures into their own collection. It
never touches the item bank or the teaching plan: the words of a question do not change.
"""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cavat.modules.figures.build import ChapterFigures, FigureMatch, plan_chapter
from cavat.modules.figures.repository import FIGURE_VERSION, Figure, FigureRepository
from cavat.modules.ingest.repository import ItemBankRepository
from cavat.modules.library.repository import DocumentRepository, TeacherDocument

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SIDE = 1600  # px: a picture is shown inside a card, never wider


class FigureBuildError(Exception):
    pass


def storage_reader(storage_dir: Path):
    """The original file of a document, or None when it is not on this disk."""

    def read(doc: Any) -> bytes | None:
        path = storage_dir / doc.stored_path
        return path.read_bytes() if path.is_file() else None

    return read


async def plan(database: Any, school_id: str, chapter_id: str, storage_dir: Path) -> ChapterFigures:
    """The figures of the chapter as the documents of now give them. Reads only."""
    bank = await ItemBankRepository(database, school_id).get(chapter_id)
    if bank is None:
        raise FigureBuildError(f"{chapter_id}: the item bank is not built yet (make item-bank)")
    documents: list[TeacherDocument] = [
        d for d in await DocumentRepository(database, school_id).list_all() if d.chapter_id == chapter_id
    ]
    return plan_chapter(chapter_id, documents, bank.items, storage_reader(storage_dir))


@dataclass
class Stored:
    created: int = 0
    updated: int = 0
    kept: int = 0  # the teacher's own picture, or the teacher's decision on the same drawing
    stale: int = 0  # stored figures whose slot the documents no longer give


async def store(database: Any, school_id: str, built: ChapterFigures, storage_dir: Path) -> Stored:
    """Write a plan. A picture the teacher uploaded is never replaced; a decision (approved, rejected)
    stays while the drawing is the same one (same bytes)."""
    repo = FigureRepository(database, school_id)
    result = Stored()
    slots: set[tuple[str, int]] = set()
    for match in built.matches:
        slots.add((match.question_id, match.order))
        before = await repo.get_slot(built.chapter_id, match.question_id, match.order)
        if before is not None and before.method == "UPLOAD":
            result.kept += 1
            continue
        status = "AUTO" if match.confidence == "SURE" else "REVIEW"
        decided_by, decided_at = None, None
        if before is not None and before.sha256 == match.sha256 and before.status in ("APPROVED", "REJECTED"):
            status, decided_by, decided_at = before.status, before.decided_by, before.decided_at
            result.kept += 1
        elif before is None:
            result.created += 1
        else:
            result.updated += 1
        figure = _figure_of(school_id, built.chapter_id, match, status, before)
        figure.decided_by, figure.decided_at = decided_by, decided_at
        _write(storage_dir, figure.file, match.png)
        await repo.save(figure)
    for old in await repo.list_chapter(built.chapter_id):
        if (old.question_id, old.order) not in slots and old.method == "VECTOR":
            result.stale += 1
    return result


def _figure_of(
    school_id: str, chapter_id: str, match: FigureMatch, status: str, before: Figure | None
) -> Figure:
    figure = Figure(
        school_id=school_id,
        chapter_id=chapter_id,
        question_id=match.question_id,
        order=match.order,
        tag=match.tag,
        alt=match.alt,
        document_id=match.document_id,
        page=match.page,
        box=match.box,
        score=match.score,
        status=status,  # type: ignore[arg-type]
        method="VECTOR",
        sha256=match.sha256,
        width=match.width,
        height=match.height,
        version=FIGURE_VERSION,
    )
    if before is not None:
        figure.id = before.id
    figure.file = f"figures/{figure.id}.png"
    return figure


def _write(storage_dir: Path, relative: str, data: bytes) -> None:
    target = storage_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def normalise_upload(data: bytes) -> tuple[bytes, int, int]:
    """The teacher's own picture as a PNG (metadata dropped, no side over ``MAX_SIDE``). ValueError when it
    is not an image the page can show."""
    from PIL import Image, UnidentifiedImageError

    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("TOO_BIG")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("NOT_AN_IMAGE")
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("NOT_AN_IMAGE") from exc
    image = image.convert("RGBA")
    background = Image.new("RGBA", image.size, "white")  # a transparent picture on a white card
    image = Image.alpha_composite(background, image).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue(), image.width, image.height


async def put_upload(
    database: Any,
    school_id: str,
    storage_dir: Path,
    *,
    chapter_id: str,
    question_id: str,
    order: int,
    tag: str,
    alt: str,
    data: bytes,
    by: str,
) -> Figure:
    """ "Thay hình": the teacher's own picture takes the slot of a question's figure, approved."""
    import hashlib

    png, width, height = normalise_upload(data)
    repo = FigureRepository(database, school_id)
    before = await repo.get_slot(chapter_id, question_id, order)
    figure = Figure(
        school_id=school_id,
        chapter_id=chapter_id,
        question_id=question_id,
        order=order,
        tag=tag or (before.tag if before else ""),
        alt=alt or (before.alt if before else ""),
        document_id="",
        page=0,
        box=[],
        score=1.0,
        status="APPROVED",
        method="UPLOAD",
        sha256=hashlib.sha256(png).hexdigest(),
        width=width,
        height=height,
    )
    if before is not None:
        figure.id = before.id
    figure.file = f"figures/{figure.id}.png"
    from cavat.core.repository import utc_now

    figure.decided_by, figure.decided_at = by, utc_now()
    _write(storage_dir, figure.file, png)
    return await repo.save(figure)


# --- the preview the owner looks at before the real run -------------------------------------------------


def write_preview(built: ChapterFigures, out_dir: Path) -> Path:
    """The pictures and a page of them beside the descriptions, under ``var/storage/figures-preview/``.

    The page names a question by its code only; the description is the model's reading of the teacher's
    figure and stays in this folder, which is not versioned."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    rows: list[str] = []
    for m in built.matches:
        name = f"{m.question_id}-h{m.order}.png"
        (out_dir / name).write_bytes(m.png)
        status = "chắc" if m.confidence == "SURE" else "chờ giáo viên duyệt"
        rows.append(
            f"<tr><td><b>{html.escape(m.question_id)}</b> · hình {m.order}<br>"
            f"{html.escape(m.filename)}, trang {m.page}<br>khớp {m.score:.2f} ({status})</td>"
            f'<td><img src="{html.escape(name)}" width="{min(m.width // 2, 420)}"></td>'
            f"<td>{html.escape(m.alt)}</td></tr>"
        )
    for n, s in enumerate(built.spare, 1):
        name = f"thua-{re.sub(r'[^A-Za-z0-9]+', '-', s.filename)}-t{s.page}-{n}.png"
        (out_dir / name).write_bytes(s.png)
        labels = html.escape(" ".join(s.labels))
        rows.append(
            f'<tr class="spare"><td><b>hình không câu nào nhận</b><br>{html.escape(s.filename)}, '
            f'trang {s.page}</td><td><img src="{html.escape(name)}" width="300"></td><td>{labels}</td></tr>'
        )
    miss = "".join(
        f"<li>{html.escape(u.question_id)} · hình {u.order} ({html.escape(u.reason)})</li>"
        for u in built.unmatched
    )
    page = (
        '<!doctype html><meta charset="utf-8"><title>Hình xem thử</title>'
        "<style>body{font:15px system-ui;margin:24px}td{border-top:1px solid #ccc;padding:8px;"
        "vertical-align:top}.spare{background:#fff6e0}img{border:1px solid #ddd}</style>"
        f"<h1>{html.escape(built.chapter_id)}</h1>"
        f"<p>{len(built.matches)} hình khớp / {built.questions} câu có chữ tả hình. "
        f"Không khớp: {len(built.unmatched)}.</p>"
        + (f"<ul>{miss}</ul>" if miss else "")
        + "<table>"
        + "".join(rows)
        + "</table>"
    )
    path = out_dir / "index.html"
    path.write_text(page, encoding="utf-8")
    return path
