"""INGEST-2: from the teacher's exercise documents and answer keys to a checked draft item bank.

The texts below are written for the tests in the layouts of the owner's documents (the documents themselves
stay out of the repository): a text-layer page puts a label alone on its line, a page read by Gemini writes
a table row "2 | a) … | b) …", worksheets print two columns, test keys add a score column.
"""

from __future__ import annotations

from fractions import Fraction

import pytest
from cavat.core.repository import new_id
from cavat.modules.assessment.vi_words import decimal_from_words
from cavat.modules.ingest.build import build_bank
from cavat.modules.ingest.parse import options_of, parse_blocks, split_parts
from cavat.modules.ingest.plan import parse_periods
from cavat.modules.ingest.verify import check_item, round_to
from cavat.modules.library.repository import PageReadRecord, TeacherDocument

EXERCISES = """[Trang 1]
TOÁN 5 · KẾT NỐI TRI THỨC
Bài tập · Số thập phân
36 câu · từ dễ đến khó
Phần 1 · Kiểm tra hiểu
★
1 Viết thành số thập phân:
a) 3/10 = ……
b) 45/100 = ……
2
Viết số đo dưới dạng số thập phân:
a) 4 m 6 dm = …… m
b) 2 kg 75 g = …… kg
Phần 2 · Cùng làm
★★
3
Điền dấu >, <, = thích hợp vào chỗ chấm:
a) 7,4 …… 7,39
b) 0,6 …… 0,60
4 Làm tròn đến hàng phần mười:
a) 5,36 ≈ ……
b) 2,94 ≈ ……
5
Tìm các số tự nhiên x biết 3,2 < x < 6,4.
CAVAT AI Tutor · Tài liệu soạn riêng
Trang 1
"""

KEY = """[Trang 1]
Đáp án bài tập · Số thập phân
Phần 1 · Kiểm tra hiểu
Câu | Đáp án và lời giải ngắn
1 | a) 0,3 | b) 0,45
2 | a) 4,6 m | b) 2,075 kg
[Trang 2]
Phần 2 · Cùng làm
 Câu
 3
a) 7,4 > 7,39    b) 0,6 = 0,60
a) 7,40 > 7,39; b) 0,6 = 0,6.
 4
a) 5,4    b) 2,9
 5
x = 4 ; 5 ; 6
DÀNH CHO NGƯỜI DẠY · Lưu ý chấm
Chấm theo kết quả.
"""

SHEETS = """Phiếu 1 · Tiết 1 · Phân số thập phân
1. 7/10 = ........
3. 1,4 = ........
2. 23/100 = ........
4. Gồm 6 đơn vị, 3 phần mười, 5 phần
trăm: ......
"""

SHEET_KEY = """Phiếu 1 . Tiết 1 - Phân số thập phân
1 | 0,7
3 | 14/10
2 | 0,23
4 | 6,35
"""

TEST = """Đề số 1 · Thời gian: 40 phút
Phần I. Trắc nghiệm
1
Số “mười hai phẩy không tám” viết là:
A. 12,8
B. 12,08
C. 12,008
D. 120,8
Phần II. Tự luận
B1
(1,0 điểm) Tính diện tích tam giác đáy 2,4 m, chiều cao 0,5 m.
"""

TEST_KEY = """Đề số 1
Phần I. Trắc nghiệm (3 điểm)
 1
B — 12,08
 0,5
Phần II. Tự luận (7 điểm)
 B1a
S = 2,4 × 0,5 : 2 = 0,6 m²
 1,0
DÀNH CHO NGƯỜI DẠY · Lưu ý chấm
Học sinh làm cách khác nhưng đúng vẫn cho đủ điểm.
"""

PLAN = """Tiết 1 · Bài 10: Từ phân số thập phân đến số thập phân
Thực hành (15′) — Bài tập câu 1, 2. Phiếu luyện tập số 1 (STP-phieuluyentap).
Tiết 2 · Bài 11: So sánh
Thực hành (15′) — Bài tập câu 3, 5 (tìm x). Phiếu luyện tập số 2
Tiết 3 (thêm) · Ôn tập và kiểm tra cuối chương
"""


def doc(kind: str, text: str, **fields) -> TeacherDocument:
    base = dict(
        id=new_id(),
        school_id="s1",
        title=kind,
        kind=kind,
        chapter_id="math-g5-decimals",
        filename=f"{kind}.pdf",
        content_type="application/pdf",
        size=1,
        sha256="x" * 64,
        stored_path="d",
        uploaded_by="t",
        text=text,
    )
    return TeacherDocument(**{**base, **fields})


def test_questions_and_answers_are_cut_in_every_layout():
    questions = parse_blocks(EXERCISES, "BAI_TAP")
    assert [(b.section, b.label, b.stage) for b in questions] == [
        ("Phần 1", "1", "KIEM_TRA_HIEU"),
        ("Phần 1", "2", "KIEM_TRA_HIEU"),
        ("Phần 2", "3", "CUNG_LAM"),
        ("Phần 2", "4", "CUNG_LAM"),
        ("Phần 2", "5", "CUNG_LAM"),
    ]
    answers = parse_blocks(KEY, "BAI_TAP", answers=True)
    assert [b.label for b in answers] == ["1", "2", "3", "4", "5"]
    assert "DÀNH CHO" not in answers[-1].text  # advice after the last answer is not an answer
    sheets = parse_blocks(SHEETS, "PHIEU")
    assert [b.label for b in sheets] == ["1", "2", "3", "4"]  # two columns put back in order
    assert sheets[3].text.endswith("phần\ntrăm: ......") and sheets[0].period == 1
    key = parse_blocks(TEST_KEY, "DE_KIEM_TRA", answers=True)
    assert [(b.section, b.label, b.text) for b in key] == [
        ("Đề 1 · I", "1", "B — 12,08"),
        ("Đề 1 · II", "B1a", "S = 2,4 × 0,5 : 2 = 0,6 m²"),
    ]  # the score column is gone


def test_sub_questions_options_and_a_repeated_explanation():
    stem, parts = split_parts("Điền dấu:\na) 7,4 …… 7,39\nb) 0,6 …… 0,60")
    assert stem == "Điền dấu:" and [p for p, _ in parts] == ["a", "b"]
    _, answer_parts = split_parts("a) 7,4 > 7,39    b) 0,6 = 0,60\na) 7,40 > 7,39; b) 0,6 = 0,6.")
    assert dict(answer_parts) == {"a": "7,4 > 7,39", "b": "0,6 = 0,60"}  # the explanation run is not a part
    stem, options = options_of("Số nào bằng 0,25?\nA. 0,205\nB. 0,250\nC. 2,50\nD. 0,0250")
    assert stem == "Số nào bằng 0,25?" and options["B"] == "0,250"


def test_periods_of_the_lesson_plan():
    periods = parse_periods(PLAN)
    assert [(p.number, p.lesson, p.exercises, p.sheet) for p in periods] == [
        (1, "Bài 10", [1, 2], 1),
        (2, "Bài 11", [3, 5], 2),
        (3, "", [], None),
    ]


@pytest.mark.parametrize(
    ("words", "value"),
    [
        ("năm phẩy bảy", "57/10"),
        ("không phẩy không tám", "8/100"),
        ("mười bốn phẩy hai trăm linh năm", "14205/1000"),
        ("ba mươi phẩy mười lăm", "3015/100"),
        ("hai mươi lăm phẩy bốn", "254/10"),
    ],
)
def test_decimals_in_words(words, value):
    assert decimal_from_words(words) == Fraction(value)


def test_rounding_is_half_up():
    assert round_to(Fraction("9.96"), 1) == 10 and round_to(Fraction("2.345"), 2) == Fraction("2.35")


@pytest.mark.parametrize(
    ("stem", "answer", "ok"),
    [
        ("0,9 = ……", "9/10", True),
        ("0,9 = ……", "7/10", False),  # seen live: a fraction image misread
        ("3 m 5 cm = …… m", "3,05 m", True),
        ("3 m 5 cm = …… m", "3,5 m", False),
        ("3,46 ≈ …… (hàng phần mười)", "3,5", True),
        ("8,3 …… 8,29", "8,3 > 8,29", True),
        ("8,3 …… 8,29", "8,3 < 8,29", False),
        ("Sắp xếp các số 5,08 ; 5,8 ; 4,99 theo thứ tự từ bé đến lớn.", "4,99 < 5,08 < 5,8", True),
        ("Số tự nhiên x: 1,8 < x < 5,4: x = ……", "x = 2 ; 3 ; 4 ; 5", True),
        ("Số 64,138: chữ số 4 ở hàng ……, giá trị ……", "hàng đơn vị; giá trị 4", True),
        ("Gồm 17 đơn vị, 1 phần mười, 8 phần trăm: ……", "17,18", True),
        ("Viết số: Mười hai phẩy ba trăm linh năm: ……", "12,305", True),
        ("Đọc số 0,08", "không phẩy không tám", True),
        ("Đáy 3,1 m, cao 56 cm: S = …… cm²", "8680 cm²", True),
        ("Đáy 11 cm và 5 cm, cao 6 cm: S = …… cm²", "48 cm²", True),
        ("S = 150 cm², cao 12 cm, đáy bé 7 cm: đáy lớn = …… cm", "18 cm", True),
        ("Tam giác vuông, hai cạnh góc vuông 18 cm và 15 cm: S = …… cm²", "135 cm²", True),
        ("Tìm chữ số x để 7,1 < 7,x2 < 7,35.", "x = 1, 2 hoặc 3", True),
        ("Tìm chữ số x để 7,1 < 7,x2 < 7,35.", "x = 1, 2, 3 hoặc 4", False),
        ("12,5 < 12,05 ……", "S (12,50 > 12,05)", True),
    ],
)
def test_each_answer_is_checked_against_its_question(stem, answer, ok):
    findings = check_item(stem, answer, context="Làm tròn đến hàng phần mười")
    assert findings, "no check applied"
    assert all(f.ok for f in findings) == ok, findings


def test_a_relation_written_in_an_answer_must_hold():
    assert not all(f.ok for f in check_item("Tính diện tích.", "S = 12 × 7 : 2 = 44 cm²"))
    assert all(f.ok for f in check_item("Tính diện tích.", "S = 120 × 80 : 2 = 4800 cm² = 0,48 m²"))


def test_a_made_up_number_in_a_true_comparison_is_seen():
    """ "12,01 < 12,7" holds, but 12,7 is not in the question: the teacher looks (REVIEW)."""
    stem = "Điền dấu >, <, = : 2,3 …… 2,30 12,01 …… 12,1"
    findings = check_item(stem, "2,3 = 2,30 ; 12,01 < 12,7")
    assert [f.check for f in findings if not f.ok] == ["GROUNDED"]


def test_a_multiple_choice_answer_names_a_right_option():
    options = {"A": "12,8", "B": "12,08", "C": "12,008", "D": "120,8"}
    assert all(
        f.ok for f in check_item("Số “mười hai phẩy không tám” viết là:", "B — 12,08", options=options)
    )
    assert not all(f.ok for f in check_item("Số “mười hai phẩy không tám” viết là:", "A", options=options))


def test_the_bank_pairs_documents_places_items_in_periods_and_marks_disputed_readings():
    exercises = doc("BAI_TAP", EXERCISES)
    sheets = doc("PHIEU", SHEETS)
    test = doc("DE_KIEM_TRA", TEST)
    disputed = [PageReadRecord(page=1, method="ocr-gemini", status="NEEDS_REVIEW", disputed=["14/10"])]
    documents = [
        exercises,
        doc("DAP_AN", KEY, answers_for=exercises.id),
        sheets,
        doc("DAP_AN", SHEET_KEY, answers_for=sheets.id, page_reads=disputed),
        test,
        doc("DAP_AN", TEST_KEY, answers_for=test.id),
        doc("GIAO_AN", PLAN),
    ]
    bank = {i.item_id: i for i in build_bank("math-g5-decimals", "STP", documents)}
    assert set(bank) == {
        "STP-BT-01a", "STP-BT-01b", "STP-BT-02a", "STP-BT-02b", "STP-BT-03a", "STP-BT-03b",
        "STP-BT-04a", "STP-BT-04b", "STP-BT-05",
        "STP-PH01-1", "STP-PH01-2", "STP-PH01-3", "STP-PH01-4", "STP-DE1-1", "STP-DE1-B1",
    }  # fmt: skip
    assert bank["STP-BT-02b"].answer == "2,075 kg" and bank["STP-BT-02b"].status == "VERIFIED"
    assert bank["STP-BT-03b"].answer == "0,6 = 0,60" and bank["STP-BT-03b"].periods == [2]
    assert bank["STP-PH01-3"].status == "DISPUTED"  # one of the two readings saw another fraction
    assert bank["STP-PH01-4"].status == "VERIFIED" and bank["STP-PH01-4"].periods == [1]
    assert bank["STP-DE1-1"].assessment and bank["STP-DE1-1"].options["B"] == "12,08"
    assert bank["STP-DE1-B1"].status == "VERIFIED" and bank["STP-DE1-B1"].periods == [3]
    assert all(i.status in ("VERIFIED", "DISPUTED") for i in bank.values()), {
        k: (i.status, i.findings) for k, i in bank.items() if i.status not in ("VERIFIED", "DISPUTED")
    }


async def test_the_teacher_builds_and_reads_the_bank_a_student_cannot():
    from cavat.core.memory_db import InMemoryDatabase
    from cavat.db import ensure_indexes
    from cavat.main import app
    from cavat.modules.library.repository import DocumentRepository
    from cavat.modules.session.api import get_database
    from cavat.modules.session.service import DEMO_SCHOOL_ID
    from fastapi.testclient import TestClient

    database = InMemoryDatabase()
    await ensure_indexes(database)
    repo = DocumentRepository(database, DEMO_SCHOOL_ID)
    exercises = doc("BAI_TAP", EXERCISES, school_id=DEMO_SCHOOL_ID)
    await repo.create(exercises)
    await repo.create(doc("DAP_AN", KEY, answers_for=exercises.id, school_id=DEMO_SCHOOL_ID))
    app.dependency_overrides[get_database] = lambda: database
    try:
        client = TestClient(app)
        teacher = {"X-Demo-Teacher": "1"}
        assert client.get("/v1/teachers/item-banks/math-g5-decimals", headers=teacher).status_code == 404
        built = client.post("/v1/teachers/item-banks/math-g5-decimals/build", headers=teacher).json()
        assert built["stats"]["items"] == 9 and built["stats"]["VERIFIED"] == 9
        bank = client.get("/v1/teachers/item-banks/math-g5-decimals", headers=teacher).json()
        assert [i["item_id"] for i in bank["items"]][:2] == ["STP-BT-01a", "STP-BT-01b"]
        again = client.post("/v1/teachers/item-banks/math-g5-decimals/build", headers=teacher)
        assert again.status_code == 200 and await database["item_banks"].count_documents({}) == 1  # replaced
        assert client.get(
            "/v1/teachers/item-banks/math-g5-decimals", headers={"X-Demo-Student": "s"}
        ).status_code in (
            401,
            403,
        )
        assert client.get("/v1/teachers/item-banks/other", headers=teacher).status_code == 404
    finally:
        app.dependency_overrides.pop(get_database, None)
