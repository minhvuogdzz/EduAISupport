"""FIG-1: the figures of a PDF page are found from its vector drawing, with no model, and cut alone.

The PDF is written by the test (``figures_pdf``): no document of the teacher is used."""

from __future__ import annotations

import pytest
from cavat.modules.figures.finder import FigureDocument, Region, is_label, is_prose, merge_row
from figures_pdf import Page, build, sample_pdf


@pytest.fixture(scope="module")
def sample() -> bytes:
    return sample_pdf()


def test_a_page_gives_its_figures_and_nothing_of_its_chrome(sample):
    with FigureDocument(sample) as doc:
        assert doc.pages == 3
        first = doc.find(1)
    # The banner, its clipped decoration, the badge, the dotted answer line, the header and footer: none.
    assert len(first) == 1
    triangle = first[0]
    assert set(triangle.labels) >= {"A", "B", "C", "H", "h", "a"}
    assert triangle.dashed  # the height AH is drawn dashed
    assert triangle.box.top > 200, "the box starts below the banner and the question line"
    assert triangle.box.width < 200


def test_figures_come_in_reading_order(sample):
    with FigureDocument(sample) as doc:
        trapezoid, house = doc.find(2)
        row = doc.find(3)
    assert trapezoid.box.top < house.box.top
    assert {"8 cm", "6 cm", "14 cm"} <= set(trapezoid.labels)
    assert {"2 m", "4 m", "6 m"} <= set(house.labels)
    # Three triangles side by side, each with the caption printed under it.
    assert [r.caption for r in row] == ["Hình 1", "Hình 2", "Hình 3"]
    assert [r.box.left for r in row] == sorted(r.box.left for r in row)


def test_a_row_of_panels_can_be_joined_into_one_figure(sample):
    with FigureDocument(sample) as doc:
        row = doc.find(3)
    joined = merge_row(row, 0, 3)
    assert joined is not None and len(joined) == 1
    assert joined[0].panels == 3
    assert joined[0].box.width > 2 * row[0].box.width
    # Not a row: a figure over another one
    with FigureDocument(sample) as doc:
        stacked = doc.find(2)
    assert merge_row(stacked, 0, 2) is None
    assert merge_row(row, 0, 1) is None


def test_a_figure_is_cut_alone_on_white(sample):
    with FigureDocument(sample) as doc:
        trapezoid, house = doc.find(2)
        image = doc.render(trapezoid)
        other = doc.render(house)
    assert image.mode == "RGB"
    assert image.width == pytest.approx(trapezoid.box.width * 3, abs=2)
    assert image.height == pytest.approx(trapezoid.box.height * 3, abs=2)
    assert image.convert("L").getextrema()[0] < 200, "the drawing is there"
    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert image.tobytes() != other.tobytes()


def test_what_is_not_a_figure_is_left_out():
    """A box around a paragraph, a table of many short texts and a lone rule are not figures."""
    page = Page().chrome(1)
    page.rect(60, 100, 300, 70, fill="0.9 0.95 1", stroke="0.1 0.3 0.7")
    page.prose(120, "Ghi nho: dien tich tam giac bang day nhan chieu cao roi chia hai")
    page.line(60, 300, 500, 300)
    for i in range(14):
        page.text(70 + 25 * i, 500, str(i), 9)
    page.rect(60, 480, 400, 40)
    pdf = build([page, Page().chrome(2)])
    with FigureDocument(pdf) as doc:
        assert doc.find(1) == []


def test_labels_and_prose_are_told_apart():
    for label in ("A", "h", "12 cm", "3,5", "(a + b)", "BM", "8 m"):
        assert is_label(label), label
    for text in ("Tính diện tích hình tam giác", "nên làm tròn", ".", ""):
        assert not is_label(text), text
    assert is_prose("Tính diện tích hình tam giác")
    assert not is_prose("12 cm") and not is_prose("Hình 1")


def test_a_page_without_figures_gives_none():
    page = Page().chrome(1).prose(100, "Chi co chu, khong co hinh nao tren trang nay")
    with FigureDocument(build([page, Page().chrome(2)])) as doc:
        assert doc.find(1) == []


def test_a_region_keeps_the_numbers_it_writes():
    region = Region(page=1, box=None, members=(), labels=("A", "12 cm", "7,5 cm"))  # type: ignore[arg-type]
    assert region.numbers() == {"12", "7,5"}
    assert region.letters() == {"A"}
