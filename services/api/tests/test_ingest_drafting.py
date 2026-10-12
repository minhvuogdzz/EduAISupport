"""INGEST-3b: Qwen drafts what the documents leave out; only what passes the checks enters the plan.

No call to Groq: a scripted router answers like the model would, good and bad drafts alike.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from cavat.modules.ingest.build import build_bank
from cavat.modules.ingest.drafting import Drafter, summary
from cavat.modules.ingest.teaching import build_plan
from tests.test_ingest_plan import documents


class ScriptedRouter:
    """Answers the hint prompt and the period prompt from scripts; remembers every request."""

    def __init__(self, hints: dict[str, dict[str, str]], node: dict):
        self.hints, self.node, self.requests = hints, node, []

    def chat(self, model_class, request, *, calls_used=0):
        payload = json.loads(request.messages[1].content)
        self.requests.append(payload)
        if "CÂU" in payload:
            data = {"items": [{"id": row["id"], **self.hints.get(row["id"], {})} for row in payload["CÂU"]]}
        else:
            data = self.node
        result = SimpleNamespace(data=data, model="qwen/qwen3.8-27b")
        return SimpleNamespace(result=result, calls_made=1)


GOOD = {
    "h1": "Câu này hỏi mình so sánh hai số nào?",
    "h2": "Mình so sánh phần nguyên trước, rồi mới so từng hàng. Hai số này có phần nguyên bằng nhau không?",
    "h3": "Con thử viết cho hai số có cùng số chữ số ở phần thập phân nhé?",
}


def plan_and_bank():
    docs = documents()
    bank = build_bank("math-g5-decimals", "STP", docs)
    return build_plan("math-g5-decimals", "Số thập phân", "STP", docs, bank)


def test_checked_hints_enter_the_plan_and_a_leaking_one_does_not(tmp_path):
    hints = {
        "STP-PH01-1": GOOD,
        "STP-PH01-2": {**GOOD, "h3": "Đáp án là 0,45 < 0,5 đó con, con chép lại nhé?"},  # leaks the answer
        "STP-BT-02": {**GOOD, "h2": "Con dùng phép nhân phân số để xếp nhé?", "h1": GOOD["h1"]},  # a new term
    }
    router = ScriptedRouter(hints, {"answers": [], "key_ideas": [], "missing_asks": []})
    plan = plan_and_bank()
    drafts = Drafter(router, tmp_path).draft(plan)
    lesson = plan.lessons["STP-Bài11"]
    assert [h.text for h in lesson.item("STP-PH01-1").hints] == list(GOOD.values())
    assert [int(h.level) for h in lesson.item("STP-PH01-2").hints] == [1, 2]  # H3 refused, never replaced
    refused = {d.target: d.codes for d in drafts if not d.ok}
    assert "ANSWER_LEAK" in refused["STP-PH01-2:H3"]
    assert "NEW_MATH_TERM" in refused["STP-BT-02:H2"]
    assert all(
        "STP-PH02" not in json.dumps(r, ensure_ascii=False) for r in router.requests
    )  # the review sheet
    assert not any("KT" in r.get("CÂU", [{}])[0].get("id", "") for r in router.requests if "CÂU" in r)


def test_answers_and_key_ideas_of_a_period_are_kept_only_in_its_words(tmp_path):
    node = {
        "answers": [
            {
                "ask": "Hai số có cùng phần nguyên thì so sánh hàng nào trước?",
                "reply": "So sánh hàng phần mười trước, rồi đến hàng phần trăm.",
                "accept": ["hàng phần mười", "phần mười trước", "hàng phần nghìn"],
            }
        ],
        "key_ideas": [["so phần nguyên trước"], ["so từng hàng"], ["nhân chéo hai phân số"]],
        "missing_asks": [],
    }
    router = ScriptedRouter({}, node)
    plan = plan_and_bank()
    drafts = Drafter(router, tmp_path).draft(plan)
    first = plan.package.nodes[0]
    assert first.theory[0].reply.startswith("So sánh hàng phần mười trước")
    assert first.theory[0].accept == [
        "hàng phần mười",
        "phần mười trước",
    ]  # "phần nghìn" is not in the period
    second = plan.package.nodes[1]
    assert ["nhân chéo hai phân số"] not in second.explain.key_ideas
    assert summary(drafts)["KEY_IDEA"]["refused"] >= 1


def test_a_second_build_costs_no_request(tmp_path):
    router = ScriptedRouter({"STP-PH01-1": GOOD}, {"answers": [], "key_ideas": [], "missing_asks": []})
    first = Drafter(router, tmp_path)
    first.draft(plan_and_bank())
    asked = len(router.requests)
    again = Drafter(router, tmp_path)
    again.draft(plan_and_bank())
    assert asked > 0 and len(router.requests) == asked and again.calls == 0
