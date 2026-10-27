"""A small PDF with vector figures for the FIG-1 tests: written by hand, no library, no document of the
teacher. Coordinates are in points from the top left of an A4 page (595 x 842), as in ``figures.finder``.

Each page carries what the teacher's documents carry around their figures: a header rule and a footer that
repeat on every page (the page's chrome), a number badge, a dotted answer line, and (page 1) a title banner
with a clipped decoration. The figures are what is left: a triangle with its dashed height and labels, a
trapezoid, a house, and a row of three triangles with their printed captions.
"""

from __future__ import annotations

import io

WIDTH, HEIGHT = 595, 842


def _y(top: float) -> float:
    return HEIGHT - top


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class Page:
    def __init__(self) -> None:
        self.ops: list[bytes] = []

    def raw(self, ops: str) -> Page:
        self.ops.append(ops.encode())
        return self

    def text(self, left: float, top: float, text: str, size: float = 10, bold: bool = False) -> Page:
        font = "F2" if bold else "F1"
        self.ops.append(
            f"BT /{font} {size} Tf {left} {_y(top + size)} Td (".encode() + _escape(text) + b") Tj ET"
        )
        return self

    def poly(
        self,
        points: list[tuple[float, float]],
        *,
        fill: str = "",
        stroke: str = "0.7 0.3 0.15",
        width: float = 1.5,
        dashed: bool = False,
        close: bool = True,
    ) -> Page:
        path = " ".join(f"{x} {_y(y)} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(points))
        paint = "B" if fill else "S"
        if close:
            path += " h"
        dash = "[4 3] 0 d" if dashed else "[] 0 d"
        fill_op = f"{fill} rg " if fill else ""
        self.ops.append(f"q {dash} {width} w {stroke} RG {fill_op}{path} {paint} Q".encode())
        return self

    def rect(self, left: float, top: float, w: float, h: float, **kwargs: object) -> Page:
        points = [(left, top), (left + w, top), (left + w, top + h), (left, top + h)]
        return self.poly(points, **kwargs)  # type: ignore[arg-type]

    def line(self, x1: float, y1: float, x2: float, y2: float, *, dashed: bool = False) -> Page:
        return self.poly([(x1, y1), (x2, y2)], dashed=dashed, close=False, stroke="0.1 0.3 0.7")

    def clipped(self, clip: tuple[float, float, float, float], inner: str) -> Page:
        left, top, width, height = clip
        self.ops.append(f"q {left} {_y(top + height)} {width} {height} re W n {inner} Q".encode())
        return self

    # --- what a document puts on every page --------------------------------------------------------

    def chrome(self, number: int) -> Page:
        self.rect(0, 0, WIDTH, 11, fill="0.85 0.4 0.15", stroke="0.85 0.4 0.15")
        self.line(50, 44, 545, 44)
        self.text(51, 30, "TOAN 5 · tai lieu mau", 8)
        self.line(50, 799, 545, 799)
        self.text(508, 806, f"Trang {number}", 8)
        return self

    def badge(self, top: float, number: int) -> Page:
        """The number of a question: a filled circle (22.7 pt) with its digit."""
        self.rect(51, top, 22.7, 22.7, fill="0.85 0.4 0.15", stroke="0.85 0.4 0.15")
        self.text(58, top + 7, str(number), 9, bold=True)
        return self

    def answer_line(self, top: float) -> Page:
        self.line(82, top, 545, top, dashed=True)
        return self

    def triangle(
        self, left: float, top: float, *, labels: tuple[str, ...] = ("A", "B", "C", "H", "h", "a")
    ) -> Page:
        """Triangle ABC (base 100, height 80) with its dashed height AH, the right-angle mark and labels."""
        a, b, c, h = (left + 40, top), (left, top + 80), (left + 100, top + 80), (left + 40, top + 80)
        self.poly([a, b, c], fill="0.99 0.93 0.88")
        self.line(*a, *h, dashed=True)
        self.rect(left + 40, top + 70, 10, 10, stroke="0.7 0.3 0.15", width=1)
        spots = {
            "A": (left + 37, top - 12),
            "B": (left - 10, top + 74),
            "C": (left + 103, top + 74),
            "H": (left + 37, top + 84),
            "h": (left + 28, top + 36),
            "a": (left + 47, top + 92),
        }
        for label in labels:
            self.text(*spots[label], label, 9)
        return self

    def trapezoid(self, left: float, top: float) -> Page:
        """Trapezoid ABCD, AB = 8 cm (top), DC = 14 cm (bottom), AH = 6 cm."""
        a, b, c, d = (left + 30, top), (left + 130, top), (left + 170, top + 70), (left, top + 70)
        self.poly([a, b, c, d], fill="0.99 0.93 0.88")
        self.line(left + 30, top, left + 30, top + 70, dashed=True)
        for label, (x, y) in {
            "A": (left + 24, top - 12),
            "B": (left + 132, top - 12),
            "C": (left + 173, top + 66),
            "D": (left - 10, top + 66),
            "H": (left + 27, top + 74),
        }.items():
            self.text(x, y, label, 9)
        self.text(left + 60, top - 14, "8 cm", 9)
        self.text(left + 12, top + 28, "6 cm", 9)
        self.text(left + 70, top + 88, "14 cm", 9)
        return self

    def house(self, left: float, top: float) -> Page:
        """A rectangle 6 m x 4 m with a roof triangle of base 6 m and height 2 m on it."""
        self.rect(left, top + 40, 120, 80, fill="0.99 0.93 0.88")
        self.poly([(left, top + 40), (left + 120, top + 40), (left + 60, top)], fill="1 0.88 0.7")
        self.line(left + 60, top, left + 60, top + 40, dashed=True)
        self.text(left + 64, top + 16, "2 m", 9)
        self.text(left + 125, top + 76, "4 m", 9)
        self.text(left + 50, top + 126, "6 m", 9)
        return self

    def banner(self) -> Page:
        """A title banner: a box around a line of prose, a decoration clipped by it."""
        self.rect(51, 68, 493, 102, fill="0.85 0.4 0.15", stroke="0.85 0.4 0.15")
        self.clipped(
            (51, 68, 493, 102),
            "0.3 0.4 0.7 rg 480 40 m 590 40 l 590 150 l 480 150 l h f",
        )
        self.text(75, 120, "Bai tap chuong Dien tich hinh tam giac, hinh thang", 14, bold=True)
        return self

    def prose(self, top: float, text: str) -> Page:
        return self.text(82, top, text, 10.5)

    def content(self) -> bytes:
        return b"\n".join(self.ops)


def build(pages: list[Page]) -> bytes:
    """The PDF of these pages: Helvetica and Helvetica-Bold, one content stream per page."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # patched below, object numbers must be known first
    pages_obj = add(b"")
    font1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    kids = []
    for page in pages:
        stream = page.content()
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        resources = f"<< /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >>".encode()
        kids.append(
            add(
                (
                    f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {WIDTH} {HEIGHT}] "
                    f"/Contents {content} 0 R /Resources "
                ).encode()
                + resources
                + b" >>"
            )
        )
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()
    refs = " ".join(f"{k} 0 R" for k in kids)
    objects[pages_obj - 1] = f"<< /Type /Pages /Kids [{refs}] /Count {len(kids)} >>".encode()
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer << /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


def sample_pdf() -> bytes:
    """Three pages: a triangle with a banner, a trapezoid and a house, a row of three triangles."""
    one = Page().chrome(1).banner()
    one.badge(190, 1).prose(194, "Tinh dien tich tam giac ABC co day BC = 12 cm.")
    one.triangle(120, 260)
    one.answer_line(400)
    two = Page().chrome(2)
    two.badge(80, 2).prose(84, "Tinh dien tich hinh thang ABCD.")
    two.trapezoid(100, 150)
    two.badge(300, 3).prose(304, "Tinh dien tich mat truoc ngoi nha.")
    two.house(100, 360)
    three = Page().chrome(3)
    three.badge(80, 4).prose(84, "Quan sat ba tam giac, ghi ten loai tam giac.")
    for number, left in enumerate((80, 250, 420), 1):
        three.triangle(left, 160, labels=("A", "B", "C", "h", "a"))
        three.text(left + 30, 268, f"Hình {number}", 10, bold=True)
    return build([one, two, three])


# What the document's text says of its figures (the reading of the model, "[Trang n]" marks).
TEXT = (
    "[Trang 1]\n"
    "Bai tap chuong\n"
    "1 Tinh dien tich tam giac ABC co day BC = 12 cm. "
    "[Hình: tam giác ABC, đáy BC = a, đường cao AH = h vuông góc với BC tại H]\n"
    "[Trang 2]\n"
    "2 Tinh dien tich hinh thang ABCD. "
    "[Hình: hình thang ABCD có đáy bé AB = 8 cm, đáy lớn CD = 14 cm, đường cao AH = 6 cm]\n"
    "3 Tinh dien tich mat truoc ngoi nha. "
    "[Hình: mặt trước ngôi nhà, hình chữ nhật 6 m x 4 m, trên là hình tam giác đáy 6 m, cao 2 m]\n"
    "[Trang 3]\n"
    "4 Quan sat ba tam giac. "
    "[Hình: Hình 1: Tam giác ABC nhọn, AH = h. Hình 2: Tam giác ABC vuông tại B. "
    "Hình 3: Tam giác ABC tù, đáy a.]\n"
)

TAG_TRIANGLE = "[Hình: tam giác ABC, đáy BC = a, đường cao AH = h vuông góc với BC tại H]"
TAG_TRAPEZOID = "[Hình: hình thang ABCD có đáy bé AB = 8 cm, đáy lớn CD = 14 cm, đường cao AH = 6 cm]"
TAG_HOUSE = "[Hình: mặt trước ngôi nhà, hình chữ nhật 6 m x 4 m, trên là hình tam giác đáy 6 m, cao 2 m]"
TAG_ROW = (
    "[Hình: Hình 1: Tam giác ABC nhọn, AH = h. Hình 2: Tam giác ABC vuông tại B. "
    "Hình 3: Tam giác ABC tù, đáy a.]"
)
