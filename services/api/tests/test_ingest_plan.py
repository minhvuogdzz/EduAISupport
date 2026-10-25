"""INGEST-3a: the draft teaching plan of a chapter from its theory, lesson plan, mistakes and item bank.

The documents are written for the tests in the layouts of the owner's documents (theirs stay out of git).
"""

from __future__ import annotations

import pytest
from cavat.core.repository import new_id
from cavat.modules.ingest.build import ItemDraft, build_bank
from cavat.modules.ingest.teaching import answer_spec, assign_sections, build_plan
from cavat.modules.ingest.theory import parse_lesson_plan, parse_mistakes, parse_theory
from cavat.modules.library.repository import TeacherDocument

THEORY = """[Trang 1]
Lý thuyết · Số thập phân
Bài 11 · So sánh các số thập phân
GHI NHỚ · Cách so sánh hai số thập phân
Bước 1. So sánh phần nguyên: số nào có phần nguyên lớn hơn thì lớn hơn.
Bước 2. Phần nguyên bằng nhau thì so sánh lần lượt từng hàng của phần thập phân:
hàng phần mười, hàng phần trăm; viết thêm chữ số 0 cho đủ.
VÍ DỤ · So sánh 7,25 và 7,3
Phần nguyên cùng là 7. Viết 7,3 = 7,30. Hàng phần mười: 2 < 3 nên 7,25 < 7,3.
LƯU Ý · Đừng nhầm
Số có phần thập phân dài hơn chưa chắc lớn hơn: 0,5 > 0,125.
Sắp xếp thứ tự
VÍ DỤ · Xếp 6,08 ; 6,8 ; 5,99 từ bé đến lớn
Viết cùng 2 chữ số: 6,08 ; 6,80 ; 5,99. Phần nguyên 5 bé nhất.
Đáp số: 5,99 < 6,08 < 6,8.
[Hình: tia số từ 5 đến 7]
"""

PLAN = """Tiết 1 · Bài 11: So sánh hai số thập phân
35–40′
Mục tiêu
\x7f Bé so sánh được hai số thập phân.
Chuẩn bị
\x7f Bảng hàng in khổ lớn.
Tiến trình
Khởi động (5′) — Ôn so sánh số tự nhiên.
Khám phá (12′) — Đặt 7,25 và 7,3 vào bảng hàng. So từng hàng từ trái sang phải.
Thực hành (15′) — Bài tập câu 1. Phiếu luyện tập số 1.
Củng cố (5′) — Bé tự nói quy tắc: “so phần nguyên trước → bằng nhau thì so từng hàng”.
Câu hỏi gợi
mở
\x7f Hai số có cùng phần nguyên thì so sánh hàng nào trước?
\x7f Vì sao 0,5 lớn hơn 0,125?
Khi bé sai
\x7f Bé cho rằng số dài hơn thì lớn hơn: thêm số 0 cho dài bằng nhau.
Tiết 2 · Bài 11: Sắp xếp thứ tự các số thập phân
Mục tiêu
\x7f Bé sắp xếp được các số thập phân từ bé đến lớn.
Tiến trình
Khám phá (12′) — Viết các số cho cùng số chữ số rồi xếp thứ tự.
Thực hành (15′) — Bài tập câu 2, 3.
Câu hỏi gợi
mở
\x7f Muốn xếp thứ tự, việc đầu tiên là gì?
Tiết 3 · Ôn tập và kiểm tra cuối chương
Ôn tập (5′) — Phiếu luyện tập số 2.
"""

MISTAKES = """Lỗi 1 · Cho rằng “dài hơn thì lớn hơn”
Biểu hiện
Chọn 0,125 > 0,5 “vì 125 lớn hơn 5”.
Vì sao bé hay
sai
Bé so sánh phần thập phân như số tự nhiên.
Cho bé tự
thấy
(phản ví dụ)
Viết thêm số 0: 0,500 và 0,125.
Cách sửa
1. So phần nguyên trước.
"""

EXERCISES = """Phần 1 · Kiểm tra hiểu
1
Điền dấu >, <, = thích hợp vào chỗ chấm:
a) 7,4 …… 7,39
b) 0,6 …… 0,60
Phần 2 · Cùng làm
2
Sắp xếp các số 5,08 ; 5,8 ; 4,99 theo thứ tự từ bé đến lớn.
Phần 4 · Vận dụng
3
Ba bạn chạy: Nam 14,28 giây; Hà 14,3 giây; Lan 14,09 giây. Xếp từ bé đến lớn các thời gian.
"""

KEY = """Phần 1 · Kiểm tra hiểu
1 | a) 7,4 > 7,39 | b) 0,6 = 0,60
Phần 2 · Cùng làm
2 | 4,99 < 5,08 < 5,8
Phần 4 · Vận dụng
3 | 14,09 < 14,28 < 14,3
"""

SHEETS = """Phiếu 1 · Tiết 1 · So sánh
1. 8,3 …… 8,29
2. 0,45 …… 0,5
Phiếu 2 · Tiết 3 · Ôn tập
1. 2,6 …… 2,60
"""

SHEET_KEY = """Phiếu 1 · Tiết 1 · So sánh
1 | 8,3 > 8,29
2 | 0,45 < 0,5
Phiếu 2 · Tiết 3 · Ôn tập
1 | 2,6 = 2,60
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


def documents() -> list[TeacherDocument]:
    exercises, sheets = doc("BAI_TAP", EXERCISES), doc("PHIEU", SHEETS)
    return [
        doc("BAI_GIANG", THEORY),
        doc("GIAO_AN", PLAN),
        doc("LOI_SAI", MISTAKES),
        exercises,
        doc("DAP_AN", KEY, answers_for=exercises.id),
        sheets,
        doc("DAP_AN", SHEET_KEY, answers_for=sheets.id),
    ]


def test_the_theory_plan_and_mistakes_are_read_in_parts():
    sections = parse_theory(THEORY)
    assert [(s.lesson, s.title, [b.kind for b in s.boxes]) for s in sections] == [
        ("Bài 11", "", ["RULE", "EXAMPLE", "NOTE"]),
        ("Bài 11", "Sắp xếp thứ tự", ["EXAMPLE", "FIGURE"]),
    ]
    first, second, review = parse_lesson_plan(PLAN)
    assert (first.lesson, first.title, review.lesson) == ("Bài 11", "So sánh hai số thập phân", "")
    assert first.questions == [
        "Hai số có cùng phần nguyên thì so sánh hàng nào trước?",
        "Vì sao 0,5 lớn hơn 0,125?",
    ]
    assert first.mistakes == ["Bé cho rằng số dài hơn thì lớn hơn: thêm số 0 cho dài bằng nhau."]
    assert first.steps["Củng cố"].startswith("Bé tự nói quy tắc")
    (mistake,) = parse_mistakes(MISTAKES)
    assert mistake.counter_example == "Viết thêm số 0: 0,500 và 0,125." and mistake.cause.startswith(
        "Bé so sánh"
    )


def test_each_section_and_example_goes_to_the_period_it_is_about():
    sections = parse_theory(THEORY)
    periods = [p for p in parse_lesson_plan(PLAN) if p.lesson]
    placed = assign_sections(periods, sections)
    titles = {
        n: [b.title for s in mine for b in s.boxes if b.kind == "EXAMPLE"] for n, mine in placed.items()
    }
    assert titles == {1: ["So sánh 7,25 và 7,3"], 2: ["Xếp 6,08 ; 6,8 ; 5,99 từ bé đến lớn"]}


# A rule and four worked examples on two pages: each example box is a section of its own for the assignment.
THEORY_EXAMPLES = """[Trang 1]
Lý thuyết · Số thập phân
Bài 11 · So sánh các số thập phân
GHI NHỚ · Cách so sánh hai số thập phân
Bước 1. So sánh phần nguyên: số nào có phần nguyên lớn hơn thì lớn hơn.
Bước 2. Phần nguyên bằng nhau thì so sánh lần lượt từng hàng của phần thập phân.
VÍ DỤ · So sánh 7,25 và 7,3
Phần nguyên cùng là 7. Viết 7,3 = 7,30. Hàng phần mười: 2 < 3 nên 7,25 < 7,3.
VÍ DỤ · So sánh 4,5 và 4,05
Phần nguyên cùng là 4. Hàng phần mười: 5 > 0 nên 4,5 > 4,05.
VÍ DỤ · So sánh 9,1 và 9,10
Viết 9,1 = 9,10 nên hai số bằng nhau.
[Trang 2]
Lý thuyết · Số thập phân
VÍ DỤ · So sánh 6,2 và 6,19
Hàng phần mười: 2 > 1 nên 6,2 > 6,19.
"""


def test_a_period_names_each_source_once_however_many_examples_it_has():
    """REFORM-3: the review page listed one line per example box, the same page eleven times in a row."""
    docs = [doc("BAI_GIANG", THEORY_EXAMPLES) if d.kind == "BAI_GIANG" else d for d in documents()]
    plan = build_plan(
        "math-g5-decimals", "Số thập phân", "STP", docs, build_bank("math-g5-decimals", "STP", docs)
    )
    first = plan.package.nodes[0]
    assert len(first.worked_examples) == 4  # nothing is dropped: only the list of sources is short
    assert plan.sources[first.id] == [
        "Giáo án, tiết 1, trang 1",
        "Lý thuyết, Bài 11 · So sánh các số thập phân, trang 1",
        "Lý thuyết, Bài 11 · So sánh các số thập phân, trang 2",
    ]
    for node_id, lines in plan.sources.items():
        assert len(lines) == len(set(lines)), node_id


def test_the_plan_has_a_node_per_period_with_the_teachers_text_and_its_items():
    docs = documents()
    plan = build_plan(
        "math-g5-decimals", "Số thập phân", "STP", docs, build_bank("math-g5-decimals", "STP", docs)
    )
    first, second = plan.package.nodes
    assert (first.id, first.layer, second.layer) == ("STP-T01", "BASIC", "BASIC")
    assert first.method.steps[0].startswith("Bước 1. So sánh phần nguyên")
    assert [t.representation for t in first.theory] == [
        "Bảng hàng in khổ lớn.",
        "khung GHI NHỚ · Cách so sánh hai số thập phân",
    ]
    assert first.theory[0].ask == "Hai số có cùng phần nguyên thì so sánh hàng nào trước?"
    assert first.explain.key_ideas == [["so phần nguyên trước"], ["bằng nhau thì so từng hàng"]]
    assert second.worked_examples[0].answer == "5,99 < 6,08 < 6,8"
    assert (first.checks, first.practice) == (["STP-BT-01a", "STP-BT-01b"], ["STP-PH01-1", "STP-PH01-2"])
    assert (second.completion, second.transfer) == (["STP-BT-02"], ["STP-BT-03"])
    assert second.checks == []  # no question of "Kiểm tra hiểu" and no worksheet: listed as a gap
    lesson = plan.lessons["STP-Bài11"]
    assert lesson.item("STP-BT-01a").answer.type == "compare"
    assert lesson.item("STP-BT-02").answer.type == "order"
    assert {m.id for m in lesson.misconceptions} == {"STP-T01-M1", "STP-L1"}
    review = plan.lessons["STP-KT"].item("STP-PH02-1")  # the review period's worksheet
    assert review.purpose == "REVIEW"
    assert any("STP-T02: needs at least 1 checks item" in p for p in plan.problems)
    assert plan.sources["STP-T01"][0] == "Giáo án, tiết 1, trang 1"


def test_an_item_in_conflict_is_never_taught():
    docs = documents()
    bank = build_bank("math-g5-decimals", "STP", docs)
    wrong = next(i for i in bank if i.item_id == "STP-PH01-1")
    wrong.status = "CONFLICT"
    plan = build_plan("math-g5-decimals", "Số thập phân", "STP", docs, bank)
    assert "STP-PH01-1" not in plan.package.nodes[0].practice
    assert "STP-PH01-1: CONFLICT" in plan.left_out


async def test_the_teacher_builds_and_reads_the_plan():
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
    for d in documents():
        await repo.create(d.model_copy(update={"school_id": DEMO_SCHOOL_ID}))
    app.dependency_overrides[get_database] = lambda: database
    try:
        client = TestClient(app)
        teacher = {"X-Demo-Teacher": "1"}
        built = client.post("/v1/teachers/teaching-plans/math-g5-decimals/build", headers=teacher).json()
        assert built["nodes"] == 2 and built["problems"] > 0
        plan = client.get("/v1/teachers/teaching-plans/math-g5-decimals", headers=teacher).json()
        assert plan["status"] == "DRAFT" and [n["id"] for n in plan["package"]["nodes"]] == [
            "STP-T01",
            "STP-T02",
        ]
        assert client.get("/v1/teachers/item-banks/math-g5-decimals", headers=teacher).status_code == 200
    finally:
        app.dependency_overrides.pop(get_database, None)


def test_a_basic_period_asks_no_application_evidence():
    """DI-6, owner 2026-10-12: application is asked of the practice periods and the chapter test."""
    docs = documents()
    plan = build_plan(
        "math-g5-decimals", "Số thập phân", "STP", docs, build_bank("math-g5-decimals", "STP", docs)
    )
    first = plan.package.nodes[0]
    assert first.layer == "BASIC" and not first.pass_rule.require_application and first.transfer == []
    assert not any(p.startswith("STP-T01: needs at least 1 transfer") for p in plan.problems)


def _draft(stem: str, answer: str) -> ItemDraft:
    """A bank item as the builder leaves it: the checks read the sub-question (the last line)."""
    return ItemDraft(
        item_id="DTTGHT-BT-01",
        chapter_id="c",
        source="BAI_TAP",
        document_id="d",
        answer_document_id="a",
        page=1,
        section="Phần 2",
        label="1",
        part="",
        stage="LUYEN_TAP",
        stem=stem,
        answer=answer,
        check_stem=stem.split("\n")[-1],
    )


def test_an_area_answer_is_a_number_not_true_or_false():
    spec = answer_spec(_draft("Tam giác có đáy 6 m, chiều cao 2 m. Tính diện tích.", "S = 6 × 2 : 2 = 6 m²."))
    assert spec.type == "numeric" and spec.value == "6"
    assert answer_spec(_draft("7,5 > 7,49 …", "Đ")).type == "boolean"


def test_a_word_problem_is_checked_on_the_number_its_answer_ends_on():
    spec = answer_spec(
        _draft(
            "Hình thang có diện tích 150 cm², đáy lớn 18 cm, đáy bé 12 cm.\nb) Tăng chiều cao thêm 2 cm thì"
            " diện tích tăng thêm bao nhiêu?",
            "Chiều cao mới 12 cm: S = 30 × 12 : 2 = 180 cm².\nTăng thêm 30 cm².",
        )
    )
    assert spec.type == "numeric" and spec.value == "30"


def test_a_question_asking_several_things_is_left_to_the_rubric():
    for stem, answer in (
        (
            "Tam giác đáy 10 cm, cao 6 cm và hình thang hai đáy 7 cm, 5 cm, cao 6 cm."
            " Hình nào lớn hơn và lớn hơn bao nhiêu?",
            "Tam giác 30 cm². Hình thang 36 cm². Hình thang lớn hơn 6 cm².",
        ),
        (
            "BM = 4 cm, MC = 6 cm, cao 5 cm. Tính diện tích các tam giác ABM, ACM và ABC.",
            "SABM = 10 cm²; SACM = 15 cm²; SABC = 25 cm².",
        ),
        (
            "Đáy 6 cm, cao 4 cm. Tính diện tích. Nếu gấp đôi đáy thì diện tích gấp mấy lần?",
            "S = 12 cm². Đáy 12 cm: S = 24 cm² (gấp 2).",
        ),
    ):
        assert answer_spec(_draft(stem, answer)).type == "open"


def test_a_measure_in_tonnes_is_a_number_and_a_list_of_values_is_not():
    spec = answer_spec(_draft("17 tấn 2 kg = …… tấn", "17,002 tấn"))
    assert spec.type == "numeric" and spec.value == "17,002"
    assert answer_spec(_draft("Số tự nhiên x: 1,8 < x < 5,4: x = ……", "x = 2 ; 3 ; 4 ; 5")).type == "open"


def test_a_key_that_restates_the_question_is_read_on_its_right_side():
    spec = answer_spec(
        _draft("Viết thành số thập phân hoặc phân số thập phân:\nc) 0,29 = ……", "0,29 = 29/100")
    )
    assert (spec.type, spec.value, spec.form) == ("numeric", "29/100", "fraction")
    spec = answer_spec(_draft("Làm tròn:\na) 8,49 đến hàng đơn vị", "8,49 ≈ 8"))
    assert (spec.type, spec.value) == ("numeric", "8")


def test_several_comparisons_or_free_units_are_left_to_the_rubric():
    line = "a) Điền dấu >, <, = : 7,35 …… 7,4    0,60 …… 0,6"
    assert answer_spec(_draft(line, "7,35 < 7,4; 0,60 = 0,6")).type == "open"
    stem = "Tính diện tích hình tam giác (đổi về cùng đơn vị trước):\na) đáy 3 dm, chiều cao 25 cm"
    assert answer_spec(_draft(stem, "3 dm = 30 cm; S = 30 × 25 : 2 = 375 cm².")).type == "open"


@pytest.mark.parametrize(
    ("stem", "answer", "facts"),
    [
        ("Đọc các số thập phân sau:\nc) 14,205", "mười bốn phẩy hai trăm linh năm", {"reading": "14,205"}),
        (
            "Số 13,975: chữ số 7 ở hàng ......, giá trị ......",
            "hàng phần trăm; giá trị 0,07",
            {"phrases": [["phần trăm"]], "numbers": [["0,07"]]},
        ),
        (
            "Số tự nhiên x: 1,8 < x < 5,4: x = ……",
            "x = 2 ; 3 ; 4 ; 5",
            {"numbers": [["2"], ["3"], ["4"], ["5"]], "only_numbers": True},
        ),
        ("So sánh (điền >, <, =):\nb) 0,8 kg …… 750 g", "0,8 kg > 750 g", {"relations": [">"]}),
        (
            "An cao 1 m 38 cm, Bình cao 1,4 m, Chi cao 135 cm. Ai cao nhất? Xếp tên ba bạn từ thấp đến cao.",
            "Chi (1,35 m) < An (1,38 m) < Bình (1,40 m). Bình cao nhất.",
            {"order": ["Chi", "An", "Bình"]},
        ),
        (
            "Bao nào nhẹ nhất, bao nào nặng nhất?",
            "A = 4,50 kg; C = 4,05 kg. Nhẹ nhất: bao C. Nặng nhất: bao A.",
            {"pairs": [("nhẹ", "C"), ("nặng", "A")]},
        ),
        (
            "Cho tam giác ABC, BM = 4 cm, MC = 6 cm, cao 5 cm. Tính diện tích các tam giác ABM, ACM và ABC.",
            "SABM = 10 cm²; SACM = 15 cm²; SABC = 25 cm² (= 10 + 15).",
            {"numbers": [["10"], ["15"], ["25"]]},
        ),
        (
            "Một tam giác đáy 12 cm. Tính chiều cao và diện tích tam giác ban đầu.",
            "Chiều cao: 13,5 × 2 : 3 = 9 cm\nS ban đầu = 12 × 9 : 2 = 54 cm²",
            {"numbers": [["9"], ["54"]]},
        ),
    ],
)
def test_the_facts_of_an_open_key_are_read_from_the_teachers_answer(stem, answer, facts):
    spec = answer_spec(_draft(stem, answer))
    assert spec.type == "open" and spec.facts.model_dump(exclude_defaults=True) == facts


def test_a_choice_between_two_named_shapes_and_a_largest_number_are_typed():
    stem = "Tam giác (đáy 16, cao 7) hay hình thang (đáy 7 và 4, cao 8) có diện tích lớn hơn? (cm)"
    spec = answer_spec(_draft(stem, "Tam giác 56 cm²; hình thang 44 cm²: tam\ngiác lớn hơn 12 cm²"))
    assert spec.type == "choice" and [o.correct for o in spec.options] == [True, False]
    spec = answer_spec(_draft("Số lớn nhất: 11,3 ; 11,90 ; 11,17 ; 11,8", "11,90"))
    assert (spec.type, spec.value) == ("numeric", "11,90")
    assert (
        answer_spec(
            _draft("Viết ba số thập phân lớn hơn 1,2 nhưng bé hơn 1,3.", "Đáp án mở, ví dụ 1,21")
        ).facts
        is None
    )
