"""INGEST-4: the teacher's decisions on the draft plan, kept across rebuilds, and the published plan the
tutor teaches. In-memory database, documents written for the tests, no model call (Qwen's drafts come from
the cache only)."""

from __future__ import annotations

import pytest
from cavat.config import get_settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.library.repository import DocumentRepository
from cavat.modules.session import chapter_service
from cavat.modules.session.api import get_database
from cavat.modules.session.service import DEMO_SCHOOL_ID
from fastapi.testclient import TestClient
from tests.test_ingest_plan import EXERCISES, KEY, MISTAKES, PLAN, THEORY, doc

SHEETS = """Phiếu 1 · Tiết 1 · So sánh
1. 8,3 …… 8,29
2. 0,45 …… 0,5
3. Số lớn nhất: 8,3 ; 8,29 ; 8,4
Phiếu 2 · Tiết 2 · Sắp xếp
1. Xếp từ bé đến lớn: 4,333 ; 4,37 ; 4,016
2. Xếp từ lớn đến bé: 4,9 ; 4,73 ; 4,121
3. Số bé nhất: 7,32 ; 7,215 ; 7,008
"""

SHEET_KEY = """Phiếu 1 · Tiết 1 · So sánh
1 | 8,3 > 8,29
2 | 0,45 < 0,5
3 | 8,4
Phiếu 2 · Tiết 2 · Sắp xếp
1 | 4,016 < 4,333 < 4,37
2 | 4,9 > 4,73 > 4,121
3 | 7,05
"""  # 7,05 is wrong (7,008): the key the teacher fixes

# The lesson plan of these tests: period 2 practises worksheet 2, the review period worksheet 3.
PLAN2 = PLAN.replace("Bài tập câu 2, 3.", "Bài tập câu 2, 3. Phiếu luyện tập số 2.").replace(
    "Ôn tập (5′) — Phiếu luyện tập số 2.", "Ôn tập (5′) — Phiếu luyện tập số 3."
)
assert PLAN2 != PLAN

TEACHER = {"X-Demo-Teacher": "1"}
URL = "/v1/teachers/teaching-plans/math-g5-decimals"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    database = InMemoryDatabase()
    await ensure_indexes(database)
    repo = DocumentRepository(database, DEMO_SCHOOL_ID)
    exercises, sheets = doc("BAI_TAP", EXERCISES), doc("PHIEU", SHEETS)
    for d in (
        doc("BAI_GIANG", THEORY),
        doc("GIAO_AN", PLAN2),
        doc("LOI_SAI", MISTAKES),
        exercises,
        doc("DAP_AN", KEY, answers_for=exercises.id),
        sheets,
        doc("DAP_AN", SHEET_KEY, answers_for=sheets.id),
    ):
        await repo.create(d.model_copy(update={"school_id": DEMO_SCHOOL_ID}))
    app.dependency_overrides[get_database] = lambda: database
    saved = (dict(chapter_service._published), dict(chapter_service._current), set(chapter_service._loaded))
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_database, None)
        chapter_service._published.clear()
        chapter_service._published.update(saved[0])
        chapter_service._current.clear()
        chapter_service._current.update(saved[1])
        chapter_service._loaded.clear()
        chapter_service._loaded.update(saved[2])
        get_settings.cache_clear()


def decide(client, target, action, value=None):
    response = client.post(
        f"{URL}/decisions", headers=TEACHER, json={"target": target, "action": action, "value": value}
    )
    assert response.status_code == 200, response.text
    return response.json()


def items_of(plan, node_id):
    node = next(n for n in plan["package"]["nodes"] if n["id"] == node_id)
    return node


def test_a_wrong_answer_key_is_fixed_by_the_teacher_and_then_taught(client):
    plan = client.post(f"{URL}/build", headers=TEACHER).json()
    plan = client.get(URL, headers=TEACHER).json()
    assert any(line.startswith("STP-PH02-3: CONFLICT") for line in plan["left_out"])
    plan = decide(client, "item:STP-PH02-3/answer", "edit", "7,008")
    assert not any(line.startswith("STP-PH02-3") for line in plan["left_out"])
    assert "STP-PH02-3" in items_of(plan, "STP-T02")["practice"]
    plan = client.post(f"{URL}/build", headers=TEACHER).json()  # a rebuild keeps the decision
    plan = client.get(URL, headers=TEACHER).json()
    assert "item:STP-PH02-3/answer" in plan["decisions"]
    assert "STP-PH02-3" in items_of(plan, "STP-T02")["practice"]


def test_hints_are_rejected_or_rewritten_by_the_teacher(client):
    client.post(f"{URL}/build", headers=TEACHER)
    plan = decide(client, "hint:STP-PH01-1:H2", "edit", "Con so sánh phần nguyên trước nhé?")
    item = next(i for i in plan["lessons"]["STP-Bài11"]["items"] if i["id"] == "STP-PH01-1")
    assert [h["text"] for h in item["hints"]] == ["Con so sánh phần nguyên trước nhé?"]
    plan = decide(client, "hint:STP-PH01-1:H2", "reject")
    item = next(i for i in plan["lessons"]["STP-Bài11"]["items"] if i["id"] == "STP-PH01-1")
    assert item["hints"] == []
    undone = client.delete(f"{URL}/decisions", headers=TEACHER, params={"target": "hint:STP-PH01-1:H2"})
    assert undone.status_code == 200 and "hint:STP-PH01-1:H2" not in undone.json()["decisions"]


def test_a_bad_decision_is_refused(client):
    client.post(f"{URL}/build", headers=TEACHER)
    for body in (
        {"target": "item:STP-BT-01a", "action": "edit", "value": "x"},
        {"target": "node:STP-T01/theory/T1/colour", "action": "edit", "value": "x"},
        {"target": "item:STP-BT-02/stage", "action": "edit", "value": "somewhere"},
        {"target": "lesson:x", "action": "approve"},
    ):
        assert client.post(f"{URL}/decisions", headers=TEACHER, json=body).status_code == 409


def test_publishing_waits_for_every_period_then_the_tutor_teaches_the_plan(client):
    client.post(f"{URL}/build", headers=TEACHER)
    refused = client.post(f"{URL}/publish", headers=TEACHER)
    assert refused.status_code == 409 and "chưa duyệt" in refused.json()["error"]["message"]
    # What the documents lack, the teacher writes: a second explanation, the retell's key ideas.
    decide(
        client,
        "node:STP-T02/theory/T2/text",
        "edit",
        "Viết các số cho cùng số chữ số ở phần thập phân rồi so sánh.",
    )
    decide(
        client, "node:STP-T02/theory/T2/ask", "edit", "Viết 4,37 thành mấy để có ba chữ số ở phần thập phân?"
    )
    decide(client, "node:STP-T02/theory/T2/representation", "edit", "viết cho dài bằng nhau")
    decide(client, "node:STP-T02/explain/key_ideas", "edit", "cùng số chữ số\nso từng hàng")
    decide(client, "item:STP-PH02-3/answer", "edit", "7,008")
    for node in ("STP-T01", "STP-T02"):
        plan = decide(client, f"node:{node}", "approve")
    assert plan["review"]["blockers"] == [], plan["review"]["blockers"]
    published = client.post(f"{URL}/publish", headers=TEACHER)
    assert published.status_code == 200, published.text
    version = published.json()["current"]
    assert version.startswith("tl-")
    student = {"X-Demo-Student": "s-1"}
    session = client.post("/v1/sessions", headers=student, json={"student_display_name": "An"}).json()
    state = client.get(f"/v1/sessions/{session['session_id']}/state", headers=student)
    assert state.status_code == 200
    assert chapter_service.chapters()["math-g5-decimals"].package.version == version


def test_the_review_view_shows_the_chapter_its_sources_and_what_waits(client):
    client.post(f"{URL}/build", headers=TEACHER)
    view = client.get(f"{URL}/view", headers=TEACHER).json()
    assert [n["node_id"] for n in view["content"]["nodes"]] == ["STP-T01", "STP-T02"]
    assert view["sources"]["STP-T01"][0] == "Giáo án, tiết 1, trang 1"
    wrong = next(i for i in view["left_out"] if i["item_id"] == "STP-PH02-3")
    assert wrong["status"] == "CONFLICT" and wrong["answer"] == "7,05" and wrong["findings"]
    assert view["items"]["STP-PH01-1"]["status"] == "VERIFIED"
    assert "STP-T01: chưa duyệt" in view["review"]["blockers"]
    assert client.get(f"{URL}/view", headers={"X-Demo-Student": "s"}).status_code in (401, 403)


def test_the_review_shows_the_verdict_on_the_teachers_answer_not_on_the_documents(client):
    """REFORM-3: a misread answer key is caught (the bank keeps that verdict), and once the teacher writes the
    answer the page stops saying "đáp án mâu thuẫn" over an answer that now holds."""
    client.post(f"{URL}/build", headers=TEACHER)
    before = client.get(f"{URL}/view", headers=TEACHER).json()
    assert next(i for i in before["left_out"] if i["item_id"] == "STP-PH02-3")["status"] == "CONFLICT"
    decide(client, "item:STP-PH02-3/answer", "edit", "7,008")
    note = client.get(f"{URL}/view", headers=TEACHER).json()["items"]["STP-PH02-3"]
    assert note["status"] == "TEACHER" and note["findings"] == []
    bank = client.get("/v1/teachers/item-banks/math-g5-decimals", headers=TEACHER).json()
    assert next(i for i in bank["items"] if i["item_id"] == "STP-PH02-3")["status"] == "CONFLICT"
    # An answer the teacher wrote that is still wrong shows what the checks found.
    decide(client, "item:STP-PH02-3/answer", "edit", "7,05")
    note = client.get(f"{URL}/view", headers=TEACHER).json()["items"]["STP-PH02-3"]
    assert note["status"] == "TEACHER" and note["findings"]


async def test_a_batch_of_decisions_is_checked_whole_then_written_once_with_its_reasons(
    tmp_path, monkeypatch
):
    from cavat.modules.ingest.review import ReviewError
    from cavat.modules.ingest.service import decide_many, rebuild

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    database = InMemoryDatabase()
    await ensure_indexes(database)
    repo = DocumentRepository(database, DEMO_SCHOOL_ID)
    exercises, sheets = doc("BAI_TAP", EXERCISES), doc("PHIEU", SHEETS)
    for d in (
        doc("BAI_GIANG", THEORY),
        doc("GIAO_AN", PLAN2),
        exercises,
        doc("DAP_AN", KEY, answers_for=exercises.id),
        sheets,
        doc("DAP_AN", SHEET_KEY, answers_for=sheets.id),
    ):
        await repo.create(d.model_copy(update={"school_id": DEMO_SCHOOL_ID}))
    await rebuild(database, DEMO_SCHOOL_ID, "math-g5-decimals")
    good = {"target": "item:STP-PH02-3/answer", "action": "edit", "value": "7,008", "reason": "đáp án in sai"}
    with pytest.raises(ReviewError):
        await decide_many(
            database, DEMO_SCHOOL_ID, "math-g5-decimals", [good, {"target": "x", "action": "approve"}], "gv"
        )
    plan = await decide_many(
        database,
        DEMO_SCHOOL_ID,
        "math-g5-decimals",
        [good, {"target": "node:STP-T01", "action": "approve"}],
        "gv",
    )
    assert plan.decisions["item:STP-PH02-3/answer"]["reason"] == "đáp án in sai"
    assert plan.decisions["node:STP-T01"]["by"] == "gv" and "reason" not in plan.decisions["node:STP-T01"]
    assert set(plan.decisions) == {"item:STP-PH02-3/answer", "node:STP-T01"}
    get_settings.cache_clear()


def test_the_teacher_may_lower_the_question_forms_a_period_asks():
    from cavat.modules.content.chapter_package import PassRule
    from cavat.modules.ingest.review import ReviewError, _edit_node, check_decision

    check_decision("node:STP-T08/pass_rule/min_forms", "edit", 1)
    with pytest.raises(ReviewError):
        check_decision("node:STP-T08/pass_rule/min_mastery", "edit", 0.1)

    class Node:  # the part of a period the edit touches
        pass_rule = PassRule()

        def model_copy(self, update):
            self.pass_rule = update["pass_rule"]
            return self

    assert _edit_node(Node(), ["pass_rule", "min_forms"], "1").pass_rule.min_forms == 1


def test_an_item_moved_to_another_stage_stays_there_once_it_is_approved(client):
    client.post(f"{URL}/build", headers=TEACHER)
    decide(client, "item:STP-PH02-3/answer", "edit", "7,008")
    decide(client, "item:STP-PH02-3/stage", "edit", "transfer")
    plan = decide(client, "item:STP-PH02-3", "approve")  # once crashed: the approval read as a stage
    node = items_of(plan, "STP-T02")
    assert "STP-PH02-3" in node["transfer"] and "STP-PH02-3" not in node["practice"]


def test_the_teacher_writes_what_a_right_open_answer_must_say(client):
    client.post(f"{URL}/build", headers=TEACHER)
    bad = {"target": "item:STP-PH02-1/facts", "action": "edit", "value": {"relations": ["≠"]}}
    assert client.post(f"{URL}/decisions", headers=TEACHER, json=bad).status_code == 409
    plan = decide(client, "item:STP-PH01-1/facts", "edit", {"numbers": [["0,7"]]})  # not an open item
    item = next(i for i in plan["lessons"]["STP-Bài11"]["items"] if i["id"] == "STP-PH01-1")
    assert item["answer"]["type"] != "open" or item["answer"]["facts"] == {"numbers": [["0,7"]]}


# --- REFORM-3b: an approval or a rejection of a hint counts for the text it was made on -----------------

SECOND = {  # what Qwen says the next time it drafts the same item
    "h1": "Trong đề, phần nguyên của hai số 8,3 và 8,29 là bao nhiêu?",
    "h2": "Theo quy tắc, khi phần nguyên bằng nhau, con so sánh hàng nào trước tiên?",
    "h3": "Con so sánh chữ số ở hàng phần mười của 8,3 và 8,29: chữ số nào lớn hơn?",
}
NO_NODE_DRAFTS = {"answers": [], "key_ideas": [], "missing_asks": []}
HINTS = "STP-PH01-1"


async def database_with_documents(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    database = InMemoryDatabase()
    await ensure_indexes(database)
    repo = DocumentRepository(database, DEMO_SCHOOL_ID)
    exercises, sheets = doc("BAI_TAP", EXERCISES), doc("PHIEU", SHEETS)
    for d in (
        doc("BAI_GIANG", THEORY),
        doc("GIAO_AN", PLAN2),
        doc("LOI_SAI", MISTAKES),
        exercises,
        doc("DAP_AN", KEY, answers_for=exercises.id),
        sheets,
        doc("DAP_AN", SHEET_KEY, answers_for=sheets.id),
    ):
        await repo.create(d.model_copy(update={"school_id": DEMO_SCHOOL_ID}))
    return database


def drafter_saying(texts, folder):
    from cavat.modules.ingest.drafting import Drafter
    from tests.test_ingest_drafting import ScriptedRouter

    return Drafter(ScriptedRouter({HINTS: texts}, NO_NODE_DRAFTS), folder)


def shown_hints(plan, item_id=HINTS):
    return {
        int(h["level"]): h["text"]
        for lesson in plan.lessons.values()
        for item in lesson["items"]
        if item["id"] == item_id
        for h in item["hints"]
    }


async def test_an_approval_or_a_rejection_counts_only_for_the_text_it_was_made_on(tmp_path, monkeypatch):
    """REFORM-3b: the decisions were keyed by item and level, so after Qwen drafted an item again a new hint
    showed "đã duyệt" before anyone read it and a new hint at a rejected level was dropped without a word."""
    from cavat.modules.ingest.review import effective_decisions
    from cavat.modules.ingest.service import decide_many, rebuild_plan
    from tests.test_ingest_drafting import GOOD

    database = await database_with_documents(tmp_path, monkeypatch)
    chapter, first = "math-g5-decimals", drafter_saying(GOOD, tmp_path / "first")
    try:
        await rebuild_plan(database, DEMO_SCHOOL_ID, chapter, first)
        plan = await decide_many(
            database,
            DEMO_SCHOOL_ID,
            chapter,
            [
                {"target": f"hint:{HINTS}:H1", "action": "approve"},
                {"target": f"hint:{HINTS}:H2", "action": "reject"},
            ],
            "gv",
        )
        assert plan.decisions[f"hint:{HINTS}:H1"]["text"] == GOOD["h1"]  # the text the teacher saw
        assert plan.decisions[f"hint:{HINTS}:H2"]["text"] == GOOD["h2"]
        assert shown_hints(plan) == {1: GOOD["h1"], 3: GOOD["h3"]}  # H2 is gone
        assert f"hint:{HINTS}:H1" in effective_decisions(plan.lessons, plan.decisions)

        plan = await rebuild_plan(
            database, DEMO_SCHOOL_ID, chapter, drafter_saying(SECOND, tmp_path / "second")
        )
        assert shown_hints(plan) == {1: SECOND["h1"], 2: SECOND["h2"], 3: SECOND["h3"]}
        assert (
            effective_decisions(plan.lessons, plan.decisions)
            .keys()
            .isdisjoint({f"hint:{HINTS}:H1", f"hint:{HINTS}:H2"})
        )  # nobody read these
        assert f"hint:{HINTS}:H1" in plan.decisions  # the record of what the teacher decided stays

        plan = await rebuild_plan(database, DEMO_SCHOOL_ID, chapter, first)  # the first text comes back
        assert shown_hints(plan) == {1: GOOD["h1"], 3: GOOD["h3"]}
        assert f"hint:{HINTS}:H1" in effective_decisions(plan.lessons, plan.decisions)
    finally:
        get_settings.cache_clear()


async def test_decisions_made_before_the_text_was_recorded_are_bound_at_the_next_rebuild(
    tmp_path, monkeypatch
):
    """The decisions already stored: an approval has the text read in "value", a rejection in its reason
    ("[Nội dung: …]"), and a few have neither: those mean the text the plan showed."""
    from cavat.modules.ingest.repository import TeachingPlanRepository
    from cavat.modules.ingest.service import rebuild_plan
    from tests.test_ingest_drafting import GOOD

    database = await database_with_documents(tmp_path, monkeypatch)
    chapter, first = "math-g5-decimals", drafter_saying(GOOD, tmp_path / "first")
    try:
        plan = await rebuild_plan(database, DEMO_SCHOOL_ID, chapter, first)
        who = {"by": "claude (ủy quyền chủ dự án 2026-10-12)", "at": "2026-10-12T13:56:45+00:00"}
        legacy = {
            f"hint:{HINTS}:H1": {"action": "approve", "value": GOOD["h1"], **who},
            f"hint:{HINTS}:H2": {
                "action": "reject",
                "value": None,
                "reason": f"Hỏi lạc. [Nội dung: {GOOD['h2']}]",
                **who,
            },
            f"hint:{HINTS}:H3": {"action": "approve", "value": None, **who},
        }
        await TeachingPlanRepository(database, DEMO_SCHOOL_ID).save(
            plan.model_copy(update={"decisions": legacy})
        )

        plan = await rebuild_plan(
            database, DEMO_SCHOOL_ID, chapter, first
        )  # same text: the decisions still count
        assert shown_hints(plan) == {1: GOOD["h1"], 3: GOOD["h3"]}
        assert [plan.decisions[f"hint:{HINTS}:H{n}"]["text"] for n in (1, 2, 3)] == [
            GOOD["h1"],
            GOOD["h2"],
            GOOD["h3"],
        ]

        second = drafter_saying(SECOND, tmp_path / "second")
        plan = await rebuild_plan(
            database, DEMO_SCHOOL_ID, chapter, second
        )  # another text: none of them counts
        assert shown_hints(plan) == {1: SECOND["h1"], 2: SECOND["h2"], 3: SECOND["h3"]}
    finally:
        get_settings.cache_clear()


async def test_the_pages_show_only_the_decisions_that_still_count(tmp_path, monkeypatch):
    from cavat.modules.ingest.api import _plan_view, review_view
    from cavat.modules.ingest.repository import ItemBankRepository
    from cavat.modules.ingest.service import decide_many, rebuild_plan
    from tests.test_ingest_drafting import GOOD

    database = await database_with_documents(tmp_path, monkeypatch)
    chapter = "math-g5-decimals"
    try:
        await rebuild_plan(database, DEMO_SCHOOL_ID, chapter, drafter_saying(GOOD, tmp_path / "first"))
        await decide_many(
            database, DEMO_SCHOOL_ID, chapter, [{"target": f"hint:{HINTS}:H1", "action": "approve"}], "gv"
        )
        plan = await rebuild_plan(
            database, DEMO_SCHOOL_ID, chapter, drafter_saying(SECOND, tmp_path / "second")
        )
        bank = await ItemBankRepository(database, DEMO_SCHOOL_ID).get(chapter)
        assert (
            f"hint:{HINTS}:H1" not in review_view(plan, bank)["decisions"]
        )  # the page shows "Duyệt", not "đã duyệt"
        assert f"hint:{HINTS}:H1" not in _plan_view(plan)["decisions"]
        assert f"hint:{HINTS}:H1" in plan.decisions
    finally:
        get_settings.cache_clear()


def test_what_a_decision_names_decides_whether_it_counts(tmp_path):
    from cavat.modules.ingest.review import apply_plan_decisions, effective_decisions
    from tests.test_ingest_drafting import GOOD, plan_and_bank

    def plan_with_hints(folder):
        plan = plan_and_bank()
        drafter_saying(GOOD, tmp_path / folder).draft(plan)
        return plan

    def levels(plan):
        return [int(h.level) for h in plan.lessons["STP-Bài11"].item(HINTS).hints]

    target = f"hint:{HINTS}:H2"
    plan = plan_with_hints("a")
    apply_plan_decisions(plan, {target: {"action": "reject", "text": "Một gợi ý khác hẳn."}})
    assert levels(plan) == [1, 2, 3]  # it names another text: the hint stays

    plan = plan_with_hints("b")
    spaced = "  " + GOOD["h2"].replace(" ", "  ") + " "
    apply_plan_decisions(plan, {target: {"action": "reject", "text": spaced}})
    assert levels(plan) == [1, 3]  # spaces do not make a different text

    plan = plan_with_hints("c")
    apply_plan_decisions(plan, {target: {"action": "reject"}})
    assert levels(plan) == [1, 3]  # a rejection that names no text rejects what is there, as it always did

    plan = plan_with_hints("d")
    edit = "Con so sánh phần nguyên trước nhé?"
    apply_plan_decisions(plan, {target: {"action": "edit", "value": edit}})
    assert plan.lessons["STP-Bài11"].item(HINTS).hints[1].text == edit  # the teacher's own words always stay

    lessons = {"STP-Bài11": plan.lessons["STP-Bài11"].model_dump()}
    approvals = {
        f"hint:{HINTS}:H1": {"action": "approve"},
        f"hint:{HINTS}:H3": {"action": "approve", "value": "x"},
    }
    assert (
        effective_decisions(lessons, approvals) == {}
    )  # an approval that names no text, or another one, counts for nothing
