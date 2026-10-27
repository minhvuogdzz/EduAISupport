"""Find the figures of a PDF page from its vector structure (FIG-1, ADR-037). No model is called.

The teacher's documents draw every figure with PDF path operators (lines, polygons, dashes) and write its
labels ("A", "h", "12 cm") as short text runs. A figure is therefore a group of path objects that touch one
another, plus the short text runs around them. What is not a figure is recognised without reading the
text of the page:

- the page's chrome: an object that sits at the same place on most pages (header, footer, top band);
- a decoration clipped by its container (the circles of the title banner, drawn through a clip path);
- a container: a box that encloses a line of prose (the callouts "GHI NHỚ", "VÍ DỤ");
- a rule (the dotted answer lines) and a badge (the number of a question): a group with a single path that
  is thin or small.

Groups are then joined by distance, short labels and the printed caption "Hình 1" are added, and the
result is a list of rectangles. ``FigureDocument.render`` draws one rectangle alone (every other object of
the page removed first, so no line of text can cross the picture). A group that is not sure is still
returned: ``matching`` decides what a question may take, and a figure no question takes is reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw

# Distances in PDF points (1/72 inch), measured on the teacher's documents.
JOIN_GAP = 4.0  # two paths closer than this belong to one figure (a figure's lines touch)
LABEL_GAP = 20.0  # a short text run this close to a figure is its label ("a" under the base)
CAPTION_GAP = 28.0  # the printed caption "Hình 1" under a figure
ROW_GAP = 150.0  # panels of one row ("Hình 1", "Hình 2", "Hình 3") are this far apart at most
PADDING = 6.0  # white border kept around the picture
MIN_SIZE = (36.0, 10.0)  # a figure is at least this long and this high: smaller is a badge or a mark
MAX_WIDTH_SHARE = 0.8  # wider than this share of the page: a table, a callout, a rule across the page
MAX_LABELS = 10  # a table has far more short texts than a figure
REPEAT_SHARE = 0.4  # an object on this share of the pages (and at least two) is the page's chrome
RENDER_SCALE = 3.0  # 216 dpi: a figure of 100 pt is 300 px wide

PATH, TEXT, IMAGE, FORM = 2, 1, 3, 5
_UNITS = {"mm", "cm", "dm", "m", "km", "hm", "dam"}
_CAPTION = re.compile(r"^Hình\s*(\d+)$")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class Box:
    """A rectangle with the origin at the top left of the page (PDF points)."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    def union(self, other: Box) -> Box:
        return Box(
            min(self.left, other.left),
            min(self.top, other.top),
            max(self.right, other.right),
            max(self.bottom, other.bottom),
        )

    def grow(self, by: float) -> Box:
        return Box(self.left - by, self.top - by, self.right + by, self.bottom + by)

    def inter(self, other: Box) -> float:
        """Area of the overlap with another box."""
        width = min(self.right, other.right) - max(self.left, other.left)
        height = min(self.bottom, other.bottom) - max(self.top, other.top)
        return max(width, 0.0) * max(height, 0.0)

    def touches(self, other: Box, gap: float) -> bool:
        return self.grow(gap / 2).inter(other.grow(gap / 2)) > 0 or self._near(other, gap)

    def _near(self, other: Box, gap: float) -> bool:
        dx = max(other.left - self.right, self.left - other.right, 0.0)
        dy = max(other.top - self.bottom, self.top - other.bottom, 0.0)
        return dx <= gap and dy <= gap

    def contains_center(self, other: Box) -> bool:
        cx, cy = (other.left + other.right) / 2, (other.top + other.bottom) / 2
        return self.left <= cx <= self.right and self.top <= cy <= self.bottom

    def as_list(self) -> list[float]:
        return [round(v, 1) for v in (self.left, self.top, self.right, self.bottom)]


@dataclass
class PageObject:
    index: int  # position in the page's object list: stable between two readings of the same page
    kind: int
    box: Box
    text: str = ""
    clipped: bool = False
    dashed: bool = False


@dataclass
class Region:
    """One figure found on a page: the rectangle to cut and what is written in it."""

    page: int  # 1-based
    box: Box  # the picture, with its padding
    members: tuple[int, ...]  # indices of the page objects that belong to it
    labels: tuple[str, ...] = ()  # its short texts, in reading order ("A", "B", "12 cm")
    caption: str = ""  # the printed "Hình 1" under it ("" when there is none)
    paths: int = 0
    dashed: bool = False  # it has a dashed line (an altitude, a hidden edge)
    panels: int = 1  # how many panels were joined into it ("Hình 1" … "Hình 3")

    def numbers(self) -> set[str]:
        return {m for label in self.labels for m in re.findall(r"\d+(?:,\d+)?", label)}

    def letters(self) -> set[str]:
        return {label for label in self.labels if re.fullmatch(r"[A-Z]", label)}


@dataclass
class _Group:
    box: Box
    members: list[int] = field(default_factory=list)
    paths: int = 0
    dashed: bool = False
    labels: list[PageObject] = field(default_factory=list)
    caption: PageObject | None = None


def is_label(text: str) -> bool:
    """A short text that can be written on a figure: a point ("A"), a letter ("h"), a measure ("12 cm")."""
    text = text.strip()
    if not text or len(text) > 14 or not any(c.isalnum() for c in text):
        return False
    return all(len(w) < 3 or w.lower() in _UNITS for w in _WORD.findall(text))


def is_prose(text: str) -> bool:
    """A line of a paragraph: two words of three letters or more."""
    return sum(len(w) >= 3 for w in _WORD.findall(text)) >= 2


class FigureDocument:
    """A PDF opened for finding and drawing its figures."""

    def __init__(self, data: bytes) -> None:
        self._pdf = pdfium.PdfDocument(data)
        self.pages = len(self._pdf)
        self._chrome: set[tuple[int, int, int, int, int]] | None = None

    def close(self) -> None:
        self._pdf.close()

    def __enter__(self) -> FigureDocument:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # --- reading a page -----------------------------------------------------------------------

    def objects(self, number: int) -> tuple[list[PageObject], Box]:
        """The objects of page ``number`` (1-based) and the page's box."""
        page = self._pdf[number - 1]
        width, height = page.get_size()
        textpage = page.get_textpage()
        out: list[PageObject] = []
        for index, obj in enumerate(page.get_objects(max_depth=1)):
            left, bottom, right, top = obj.get_bounds()
            box = Box(left, height - top, right, height - bottom)
            text, clipped, dashed = "", False, False
            if obj.type == TEXT:
                text = textpage.get_text_bounded(left, bottom, right, top).strip()
            elif obj.type == PATH:
                clip = pdfium_raw.FPDFPageObj_GetClipPath(obj.raw)
                clipped = bool(clip) and pdfium_raw.FPDFClipPath_CountPaths(clip) > 0
                dashed = pdfium_raw.FPDFPageObj_GetDashCount(obj.raw) > 0
            out.append(PageObject(index, obj.type, box, text, clipped, dashed))
        textpage.close()
        page.close()
        return out, Box(0.0, 0.0, width, height)

    def _chrome_signatures(self) -> set[tuple[int, int, int, int, int]]:
        """Objects at the same place (to 2 pt) on at least two pages and REPEAT_SHARE of them."""
        if self._chrome is not None:
            return self._chrome
        counts: dict[tuple[int, int, int, int, int], int] = {}
        for number in range(1, self.pages + 1):
            seen: set[tuple[int, int, int, int, int]] = set()
            for obj in self.objects(number)[0]:
                seen.add(_signature(obj))
            for sig in seen:
                counts[sig] = counts.get(sig, 0) + 1
        needed = max(2, round(REPEAT_SHARE * self.pages + 0.4999))
        self._chrome = {sig for sig, n in counts.items() if n >= needed}
        return self._chrome

    # --- finding ------------------------------------------------------------------------------

    def find(self, number: int) -> list[Region]:
        """The figures of page ``number``, in reading order."""
        objects, page_box = self.objects(number)
        chrome = self._chrome_signatures() if self.pages >= 2 else set()
        texts = [o for o in objects if o.kind == TEXT and o.text and _signature(o) not in chrome]
        prose = [o for o in texts if is_prose(o.text)]
        parts = [o for o in objects if o.kind in (PATH, FORM) and _is_part(o, chrome, page_box)]
        groups = [g for g in _join(parts) if not _is_mark(g)]
        labels = [o for o in texts if is_label(o.text) and not _in_prose_line(o, prose)]
        captions = [o for o in texts if _CAPTION.match(o.text)]
        pictures = [o for o in objects if o.kind == IMAGE and _signature(o) not in chrome]
        groups = _merge_overlapping(groups)
        for group in groups:
            _add_labels(group, labels, captions, pictures)
        groups = _merge_overlapping(groups)  # a label may have joined two drawings
        groups = [g for g in groups if _is_figure(g, prose, page_box)]
        return _reading_order([self._region(number, g) for g in groups])

    def _region(self, number: int, group: _Group) -> Region:
        box = group.box
        members = list(group.members)
        labels = sorted(group.labels, key=lambda o: (round(o.box.top / 4), o.box.left))
        if group.caption is not None:
            box = box.union(group.caption.box)
            members.append(group.caption.index)
        members += [o.index for o in group.labels]
        caption = group.caption.text.strip() if group.caption is not None else ""
        return Region(
            page=number,
            box=box.grow(PADDING),
            members=tuple(sorted(set(members))),
            labels=tuple(o.text.strip() for o in labels),
            caption=caption,
            paths=group.paths,
            dashed=group.dashed,
        )

    # --- drawing ------------------------------------------------------------------------------

    def render(self, region: Region, scale: float = RENDER_SCALE) -> Any:
        """The region as a PIL image: its own objects only, on white."""
        page = self._pdf[region.page - 1]
        keep = set(region.members)
        stale = [o for i, o in enumerate(page.get_objects(max_depth=1)) if i not in keep]
        for obj in stale:
            page.remove_obj(obj)
        width, height = page.get_size()
        box = region.box
        crop = (
            max(box.left, 0.0),
            max(height - box.bottom, 0.0),
            max(width - box.right, 0.0),
            max(box.top, 0.0),
        )
        image = page.render(scale=scale, crop=crop).to_pil().convert("RGB")
        page.close()
        return image


# --- the steps of ``find`` --------------------------------------------------------------------------


def _signature(obj: PageObject) -> tuple[int, int, int, int, int]:
    box = obj.box
    return (obj.kind, round(box.left / 2), round(box.top / 2), round(box.width / 2), round(box.height / 2))


def _is_part(obj: PageObject, chrome: set[Any], page: Box) -> bool:
    """Can this path, form or image be a part of a figure?"""
    if _signature(obj) in chrome or obj.clipped:
        return False
    return obj.box.width < MAX_WIDTH_SHARE * page.width and obj.box.area < 0.5 * page.area


def _join(parts: list[PageObject]) -> list[_Group]:
    """Union-find on distance: parts closer than ``JOIN_GAP`` are one group."""
    parent = list(range(len(parts)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(parts):
        for j in range(i + 1, len(parts)):
            if a.box.touches(parts[j].box, JOIN_GAP):
                parent[root(j)] = root(i)
    groups: dict[int, _Group] = {}
    for i, part in enumerate(parts):
        group = groups.setdefault(root(i), _Group(part.box))
        group.box = group.box.union(part.box)
        group.members.append(part.index)
        group.paths += 1
        group.dashed = group.dashed or part.dashed
    return list(groups.values())


def _is_mark(group: _Group) -> bool:
    """A lone thin rule (the dotted answer line) or a lone small shape (a badge): not a figure."""
    if group.paths > 1:
        return False
    box = group.box
    return min(box.width, box.height) <= 4.0 or max(box.width, box.height) < MIN_SIZE[0]


def _add_labels(
    group: _Group, labels: list[PageObject], captions: list[PageObject], pictures: list[PageObject]
) -> None:
    """Short texts near the drawing join it and the box grows to hold them; then the picture of a fraction
    written under it (the hundred squares of the decimals chapter) and its printed caption."""
    drawing = group.box
    for text in labels:
        if drawing.grow(LABEL_GAP).inter(text.box) > 0:
            group.labels.append(text)
            group.box = group.box.union(text.box)
    for text in labels:  # a label next to a label: "(a + b)" is two runs
        if text not in group.labels and group.box.grow(2.0).inter(text.box) > 0:
            group.labels.append(text)
            group.box = group.box.union(text.box)
    for picture in pictures:
        if picture.box.height < 40 and group.box.grow(LABEL_GAP).inter(picture.box) > 0:
            group.box = group.box.union(picture.box)
            group.members.append(picture.index)
    for text in captions:
        below = 0 <= text.box.top - group.box.bottom <= CAPTION_GAP
        across = min(group.box.right, text.box.right) - max(group.box.left, text.box.left) > 0
        if below and across and group.caption is None:
            group.caption = text


def _in_prose_line(text: PageObject, prose: list[PageObject]) -> bool:
    """A short run that belongs to a line of a paragraph: a bold digit or a full stop at its end."""
    for line in prose:
        shared = min(text.box.bottom, line.box.bottom) - max(text.box.top, line.box.top)
        gap = max(text.box.left - line.box.right, line.box.left - text.box.right, 0.0)
        if shared >= 0.5 * min(text.box.height, line.box.height) and gap <= 6.0:
            return True
    return False


def _merge_overlapping(groups: list[_Group]) -> list[_Group]:
    """Two drawings whose boxes overlap are one figure (a dashed line inside a trapezoid)."""
    groups = list(groups)
    merged = True
    while merged:
        merged = False
        for i, a in enumerate(groups):
            for j in range(i + 1, len(groups)):
                b = groups[j]
                if a.box.inter(b.box) > 0:
                    a.box = a.box.union(b.box)
                    a.members += b.members
                    a.paths += b.paths
                    a.dashed = a.dashed or b.dashed
                    a.labels += [t for t in b.labels if t not in a.labels]
                    a.caption = a.caption or b.caption
                    del groups[j]
                    merged = True
                    break
            if merged:
                break
    return groups


def _is_figure(group: _Group, prose: list[PageObject], page: Box) -> bool:
    """Size, and what it is not: a box around a paragraph, a table (full width, many short texts)."""
    box = group.box
    if max(box.width, box.height) < MIN_SIZE[0] or min(box.width, box.height) < MIN_SIZE[1]:
        return False
    if box.width >= MAX_WIDTH_SHARE * page.width or len(group.labels) > MAX_LABELS:
        return False
    return not any(box.contains_center(t.box) for t in prose)


def _reading_order(regions: list[Region]) -> list[Region]:
    """Top to bottom, rows left to right: two regions are in one row when they share half their height."""
    ordered = sorted(regions, key=lambda r: (r.box.top, r.box.left))
    rows: list[list[Region]] = []
    for region in ordered:
        for row in rows:
            ref = row[0].box
            overlap = min(ref.bottom, region.box.bottom) - max(ref.top, region.box.top)
            if overlap >= 0.5 * min(ref.height, region.box.height):
                row.append(region)
                break
        else:
            rows.append([region])
    return [r for row in rows for r in sorted(row, key=lambda r: r.box.left)]


def merge_row(regions: list[Region], start: int, count: int) -> list[Region] | None:
    """Join ``count`` consecutive regions of one row into a single figure of panels ("Hình 1" … "Hình 3").

    None when they are not on one row or are further apart than ``ROW_GAP``."""
    chosen = regions[start : start + count]
    if len(chosen) < count or count < 2:
        return None
    first = chosen[0].box
    for prev, nxt in zip(chosen, chosen[1:], strict=False):
        overlap = min(prev.box.bottom, nxt.box.bottom) - max(prev.box.top, nxt.box.top)
        gap = nxt.box.left - prev.box.right
        if overlap < 0.5 * min(prev.box.height, nxt.box.height) or gap > ROW_GAP:
            return None
        first = first.union(nxt.box)
    merged = Region(
        page=chosen[0].page,
        box=first,
        members=tuple(sorted({m for r in chosen for m in r.members})),
        labels=tuple(label for r in chosen for label in r.labels),
        caption=" ".join(r.caption for r in chosen if r.caption),
        paths=sum(r.paths for r in chosen),
        dashed=any(r.dashed for r in chosen),
        panels=sum(r.panels for r in chosen),
    )
    return [*regions[:start], merged, *regions[start + count :]]
