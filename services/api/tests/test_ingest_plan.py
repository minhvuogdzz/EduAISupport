"""INGEST-3a: the draft teaching plan of a chapter from its theory, lesson plan, mistakes and item bank.

The documents are written for the tests in the layouts of the owner's documents (theirs stay out of git).
"""

from __future__ import annotations

from cavat.core.repository import new_id
from cavat.modules.ingest.build import build_bank
from cavat.modules.ingest.teaching import assign_sections, build_plan
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
