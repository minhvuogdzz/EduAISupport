"""INGEST-1: a PDF is read page by page, and what its text layer loses is read again and checked (DI-43).

The owner's documents showed both losses: fractions printed as small images vanish from the text layer, and
a geometry figure leaves only its labels ("H A B C 7 cm 12 cm"). No call to Gemini here: a fake OCR reads.
"""

from __future__ import annotations

import io

from cavat.modules.library.extract import (
    OCR_PAGE_PROMPT,
    clean_reading,
    compare_numbers,
    extract,
    why_read_again,
)
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def _pdf(*pages: tuple[str, bool]) -> bytes:
    """A PDF whose pages hold these lines of ASCII text, and an image when asked."""
    writer = PdfWriter()
    for text, with_image in pages:
        page = writer.add_blank_page(width=595, height=842)
        escaped = (line.replace("(", "\\(").replace(")", "\\)") for line in text.splitlines())
        lines = " ".join(f"({line}) Tj 0 -14 Td" for line in escaped)
        ops = f"BT /F1 11 Tf 40 800 Td {lines} ET"
        resources = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): writer._add_object(
                            DictionaryObject(
                                {
                                    NameObject("/Type"): NameObject("/Font"),
                                    NameObject("/Subtype"): NameObject("/Type1"),
                                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                                }
                            )
                        )
                    }
                )
            }
        )
        if with_image:
            image = DecodedStreamObject()
            image.set_data(b"\x00")
            image.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(1),
                    NameObject("/Height"): NumberObject(1),
                    NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            resources[NameObject("/XObject")] = DictionaryObject(
                {NameObject("/Im1"): writer._add_object(image)}
            )
            ops += " q 10 0 0 10 40 400 cm /Im1 Do Q"
        content = DecodedStreamObject()
        content.set_data(ops.encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(content)
        page[NameObject("/Resources")] = resources
        page[NameObject("/MediaBox")] = ArrayObject(
            [NumberObject(0), NumberObject(0), NumberObject(595), NumberObject(842)]
        )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


LONG = "Bai tap so thap phan, viet dung dau phay va ghi don vi khi bai co don vi."
FRACTIONS = f"{LONG}\nCau 1. Viet thanh so thap phan: a) = ...... b) = ......\nDap so 0,35 va 12,305"
FIGURE = f"{LONG}\nCau 4. Tinh dien tich hinh tam giac trong hinh ve.\nH A B C\n7 cm\n12 cm"


class FakeOcr:
    def __init__(self, reply: str | Exception) -> None:
        self.reply, self.prompts = reply, []

    def __call__(self, data: bytes, mime: str, prompt: str) -> str:
        self.prompts.append((mime, prompt))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_what_the_text_layer_loses_is_found():
    assert why_read_again(None, "short") == "SCAN"  # type: ignore[arg-type]  (text checks need no page)
    assert why_read_again(None, FIGURE) == "FIGURE"  # type: ignore[arg-type]
    house = f"{LONG}\n4. Hinh ghep\n5 m\n3 m\n2 m\nVI DU"
    assert why_read_again(None, house) == "FIGURE"  # type: ignore[arg-type]
    number_line = f"{LONG}\n30 Diem M tren tia so\n3\n4\n3,5\nM"
    assert why_read_again(None, number_line) == "FIGURE"  # type: ignore[arg-type]
    options = f"{LONG}\nA. 12,5 B. 12,05 C. 12,005 D. 120,5"
    assert why_read_again(PdfWriter().add_blank_page(10, 10), options) == ""


def test_a_page_with_images_is_read_again_and_the_reading_kept_when_it_holds_every_number():
    ocr = FakeOcr(
        "Cau 1. Viet thanh so thap phan: a) 7/10 = ...... b) 35/100 = ......\nDap so 0,35 va 12,305"
    )
    found = extract(_pdf((FRACTIONS, True), (LONG, False)), "baitap.pdf", ocr)
    first, second = found.page_reads
    assert (first.method, first.reason, first.status) == ("ocr-gemini", "IMAGES", "OK")
    # What only Gemini read is listed for the teacher; 35/100 is not new, its value 0,35 is on the page.
    assert first.added == ("7/10",)
    assert (second.method, second.reason) == ("pdf-text", "")
    assert "7/10" in found.text and found.text.startswith("[Trang 1]\n")
    assert found.method == "pdf-text+ocr" and not found.needs_review
    assert ocr.prompts == [("application/pdf", OCR_PAGE_PROMPT)]  # one page, the page prompt


def test_a_reading_that_drops_a_number_of_the_text_layer_is_not_trusted():
    ocr = FakeOcr("Cau 1. a) 7/10 b) 35/100\nDap so 0,35")  # 12,305 is lost
    found = extract(_pdf((FRACTIONS, True)), "baitap.pdf", ocr)
    (read,) = found.page_reads
    assert (read.method, read.status, read.missing) == ("pdf-text", "NEEDS_REVIEW", ("12,305",))
    assert "12,305" in found.text and "7/10" not in found.text  # the text layer stays
    assert found.needs_review


def test_a_failed_reading_or_no_gemini_leaves_the_page_for_the_teacher():
    failed = extract(_pdf((FIGURE, False)), "hinh.pdf", FakeOcr(RuntimeError("429")))
    assert failed.page_reads[0].status == "NEEDS_REVIEW" and "12 cm" in failed.text
    offline = extract(_pdf((FIGURE, False)), "hinh.pdf", None)
    assert offline.page_reads[0].status == "NEEDS_REVIEW" and not offline.needs_ocr


def test_numbers_are_compared_by_writing_or_value_and_lone_digits_are_left_out():
    missing, added = compare_numbers(
        "3\n0\n5\n,\n4 so 305,478 va 9.600.000 dong", "So 305,478 va 9600000 dong; 3/10"
    )
    assert missing == () and added == ("3/10",)
    assert compare_numbers("Dap so 12,05", "Dap so 12,5") == (("12,05",), ("12,5",))


def test_the_import_reads_what_a_file_is_from_its_name():
    from pathlib import Path

    from cavat.library_import import describe

    assert describe(Path("STP-lythuyet.pdf")) == (
        "math-g5-decimals",
        "BAI_GIANG",
        "Lý thuyết · Số thập phân",
        "",
    )
    assert describe(Path("DTTGHT-baitap-dapan.pdf")) == (
        "math-g5-area-triangle-trapezoid",
        "DAP_AN",
        "Đáp án bài tập · Diện tích hình tam giác, hình thang",
        "DTTGHT-baitap",
    )
    assert describe(Path("STP-dekiemtra.pdf"))[1] == "DE_KIEM_TRA"  # type: ignore[index]
    assert describe(Path("ghichu.pdf")) is None and describe(Path("STP-baitap-cu.pdf")) is None


def test_latex_in_a_reading_becomes_the_plain_form():
    assert clean_reading(r"Cứ 10 $\text{m}^2$ trồng 4 cây") == "Cứ 10 m² trồng 4 cây"  # seen live
    assert clean_reading(r"$\frac{7}{10}$ = 0,7 và $12 \times 7$") == "7/10 = 0,7 và 12 × 7"
