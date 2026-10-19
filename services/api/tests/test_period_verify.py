"""FIX-3: the period's "vì sao" and the counterexamples, drafted and decided like the rest of the plan.

The plans built from the teacher's documents had no "vì sao" (51/444 tutor turns of a simulated session
were the generic one) and the teacher could not fix a counterexample that names an answer. Qwen now drafts
one "vì sao" per period (no number: it serves every item of the period), checked, for the teacher to edit
or reject; a counterexample is edited or removed by a decision. No call to Groq: a scripted router.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.ingest.drafting import VERIFY_LEAD, Drafter, verify_codes
from cavat.modules.ingest.review import ReviewError, apply_plan_decisions, check_decision
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
from cavat.modules.tutor.renderer import TemplateRenderer
from tests.test_ingest_drafting import plan_and_bank
from tests.test_ingest_review import client  # noqa: F401 - the documents of the review tests

WHY = "Vì sao con so sánh phần nguyên trước rồi mới so sánh phần thập phân?"


class Router:
    """Answers the "vì sao" request from a script and every other request with nothing."""

    def __init__(self, asks: dict[str, str]) -> None:
        self.asks, self.requests = asks, []

    def chat(self, model_class, request, *, calls_used=0):
        payload = json.loads(request.messages[1].content)
        self.requests.append(payload)
        if "TIẾT" in payload:
            data = {"items": [{"id": t["id"], "hoi": self.asks.get(t["id"], "")} for t in payload["TIẾT"]]}
        else:
            data = {}
        return SimpleNamespace(result=SimpleNamespace(data=data, model="qwen/qwen3.8-27b"), calls_made=1)


def period(plan, node_id):
    return next(n for n in plan.package.nodes if n.id == node_id)


def test_a_why_question_serves_every_item_of_its_period_or_is_refused():
    node = period(plan_and_bank(), "STP-T01")
    assert verify_codes(WHY, node) == []
    assert "HAS_NUMBER" in verify_codes("Vì sao 8,3 lớn hơn 8,29?", node)  # an item's numbers
    assert "NOT_ONE_QUESTION" in verify_codes("Vì sao con làm vậy? Con nói lại nhé?", node)
    assert "NOT_ONE_QUESTION" in verify_codes("Con giải thích cách so sánh nhé.", node)
    assert "STARTS_WITH_PRAISE" in verify_codes("Đúng rồi, vì sao con so sánh phần nguyên trước?", node)
    assert "WRONG_ADDRESS" in verify_codes("Vì sao em so sánh phần nguyên trước?", node)
    assert "NEW_MATH_TERM" in verify_codes("Vì sao con quy đồng mẫu số trước?", node)


def test_the_drafted_why_reaches_the_items_of_its_period_and_nothing_else_is_sent(tmp_path):
    plan = plan_and_bank()
    router = Router({"STP-T01": WHY, "STP-T02": "Vì sao 4,9 lớn hơn 4,73?"})
    drafts = Drafter(router, tmp_path).draft(plan)
    apply_plan_decisions(plan, {})
    kept = {d.target: d for d in drafts if d.kind == "VERIFY"}
    assert kept["STP-T01"].ok and not kept["STP-T02"].ok and "HAS_NUMBER" in kept["STP-T02"].codes
    assert period(plan, "STP-T01").verify_prompt == f"{VERIFY_LEAD} {WHY}"
    assert period(plan, "STP-T02").verify_prompt == ""  # refused: the generic "vì sao" stays
    item = plan.lessons["STP-Bài11"].item("STP-BT-01a")
    assert item.verify_prompt == f"{VERIFY_LEAD} {WHY}"
    [asked] = [r for r in router.requests if "TIẾT" in r]
    assert set(asked) == {"TIẾT"} and all(set(t) == {"id", "tên", "quy tắc"} for t in asked["TIẾT"])

    ctx = RenderContext(
        decision=PolicyDecision(move=Move.VERIFY, reason_codes=("CORRECT", "VERIFY_SAMPLED")),
        item=item,
        package=plan.lessons["STP-Bài11"],
        state=ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE),
    )
    msg = TemplateRenderer().render(ctx)
    assert msg.text == f"{VERIFY_LEAD} {WHY}" and msg.source == "TEMPLATE"


def test_the_teacher_rewrites_or_rejects_the_why_and_an_item_keeps_its_own(tmp_path):
    plan = plan_and_bank()
    Drafter(Router({"STP-T01": WHY}), tmp_path).draft(plan)
    own = "Đúng rồi! Vì sao con chọn số đó?"
    lesson = plan.lessons["STP-Bài11"]
    plan.lessons["STP-Bài11"] = lesson.model_copy(
        update={
            "items": [
                i.model_copy(update={"verify_prompt": own}) if i.id == "STP-BT-01b" else i
                for i in lesson.items
            ]
        }
    )
    mine = "Đúng rồi! Con nói cho cô nghe con so sánh phần nào trước nhé?"
    check_decision("node:STP-T01/verify/prompt", "edit", mine)
    apply_plan_decisions(plan, {"node:STP-T01/verify/prompt": {"action": "edit", "value": mine}})
    assert plan.lessons["STP-Bài11"].item("STP-BT-01a").verify_prompt == mine
    assert plan.lessons["STP-Bài11"].item("STP-BT-01b").verify_prompt == own

    again = plan_and_bank()
    Drafter(Router({"STP-T01": WHY}), tmp_path).draft(again)
    apply_plan_decisions(again, {"node:STP-T01/verify/prompt": {"action": "reject"}})
    assert period(again, "STP-T01").verify_prompt == ""
    assert again.lessons["STP-Bài11"].item("STP-BT-01a").verify_prompt is None


def test_the_teacher_edits_or_removes_a_counterexample():
    plan = plan_and_bank()
    [mistake] = [m for m in plan.lessons["STP-Bài11"].misconceptions if m.counter_examples]
    target = f"misconception:{mistake.id}/counter_examples"
    check_decision(target, "edit", "Con so sánh 0,7 và 0,65 xem số nào lớn hơn?")
    with pytest.raises(ReviewError):
        check_decision(f"misconception:{mistake.id}", "edit", "x")
    apply_plan_decisions(plan, {target: {"action": "edit", "value": "Một?\nHai?"}})
    edited = next(m for m in plan.lessons["STP-Bài11"].misconceptions if m.id == mistake.id)
    assert edited.counter_examples == ["Một?", "Hai?"]
    apply_plan_decisions(plan, {target: {"action": "reject"}})
    removed = next(m for m in plan.lessons["STP-Bài11"].misconceptions if m.id == mistake.id)
    assert removed.counter_examples == []


@pytest.mark.usefixtures("client")
async def test_a_rebuild_keeps_what_the_drafter_cannot_give_again(tmp_path):
    """The cache no longer meets a request (the answer is read differently since): the item keeps its hints
    and the period its "vì sao", unless the teacher changed the stem."""
    from cavat.main import app
    from cavat.modules.ingest.service import rebuild_plan
    from cavat.modules.session.api import get_database
    from cavat.modules.session.service import DEMO_SCHOOL_ID
    from tests.test_ingest_drafting import GOOD, ScriptedRouter

    database = app.dependency_overrides[get_database]()
    hints = ScriptedRouter({"STP-PH01-1": GOOD}, {"answers": [], "key_ideas": [], "missing_asks": []})

    class Both(Router):
        def chat(self, model_class, request, *, calls_used=0):
            if "TIẾT" in json.loads(request.messages[1].content):
                return super().chat(model_class, request, calls_used=calls_used)
            return hints.chat(model_class, request, calls_used=calls_used)

    first = await rebuild_plan(
        database, DEMO_SCHOOL_ID, "math-g5-decimals", Drafter(Both({"STP-T01": WHY}), tmp_path / "a")
    )

    def item(plan, item_id):
        return next(i for lesson in plan.lessons.values() for i in lesson["items"] if i["id"] == item_id)

    def period_of(plan, node_id):
        return next(n for n in plan.package["nodes"] if n["id"] == node_id)

    assert [h["text"] for h in item(first, "STP-PH01-1")["hints"]] == list(GOOD.values())
    assert period_of(first, "STP-T01")["verify_prompt"] == f"{VERIFY_LEAD} {WHY}"

    empty = Drafter(None, tmp_path / "empty")  # nothing cached: the drafter gives nothing again
    again = await rebuild_plan(database, DEMO_SCHOOL_ID, "math-g5-decimals", empty)
    assert [h["text"] for h in item(again, "STP-PH01-1")["hints"]] == list(GOOD.values())
    assert period_of(again, "STP-T01")["verify_prompt"] == f"{VERIFY_LEAD} {WHY}"
    assert {"STP-PH01-1:H1", "STP-T01"} <= {d["target"] for d in again.drafts if d["ok"]}  # still "AI soạn"

    from cavat.modules.ingest.service import decide

    await decide(
        database, DEMO_SCHOOL_ID, "math-g5-decimals", "item:STP-PH01-1/stem", "edit", "8,3 …… 8,4", "t"
    )
    changed = await rebuild_plan(database, DEMO_SCHOOL_ID, "math-g5-decimals", empty)
    assert item(changed, "STP-PH01-1")["hints"] == []  # a new stem: the old hints may not fit it
