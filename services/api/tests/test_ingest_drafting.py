"""INGEST-3b: Qwen drafts what the documents leave out; only what passes the checks enters the plan.

No call to Groq: a scripted router answers like the model would, good and bad drafts alike.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from cavat.core.pedagogy import HintLevel, HintTarget
from cavat.modules.ai_gateway.base import Usage
from cavat.modules.content.lesson_package import BooleanAnswer, NumericAnswer
from cavat.modules.ingest.build import build_bank
from cavat.modules.ingest.drafting import (
    HINT_PROMPT,
    MAX_HINT_WORDS,
    RETRY_NOTES,
    Drafter,
    _hint_codes,
    generic_hint,
    prompt_text,
    summary,
)
from cavat.modules.ingest.teaching import build_plan
from tests.test_ingest_plan import documents


class ScriptedRouter:
    """Answers the hint prompt and the period prompt from scripts; remembers every request."""

    def __init__(self, hints: dict[str, dict[str, str]], node: dict):
        self.hints, self.node, self.requests, self.prompts = hints, node, [], []

    def chat(self, model_class, request, *, calls_used=0):
        payload = json.loads(request.messages[1].content)
        self.requests.append(payload)
        self.prompts.append(request.messages[0].content)
        if "CÂU" in payload:
            data = {"items": [{"id": row["id"], **self.hints.get(row["id"], {})} for row in payload["CÂU"]]}
        else:
            data = self.node
        result = SimpleNamespace(data=data, model="qwen/qwen3.8-27b", usage=Usage(prompt_tokens=900))
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
    # CFG-2: each kept draft carries the tokens the provider counted for it
    kept = [json.loads(p.read_text(encoding="utf-8")) for p in tmp_path.glob("*.json")]
    assert kept and all(k["usage"]["prompt_tokens"] == 900 for k in kept)


# --- REFORM-3: hints that ask about the data, and checks that stop refusing the words of the grade ---------

TARGETS = {HintLevel.H1: HintTarget.TASK, HintLevel.H2: HintTarget.CONCEPT, HintLevel.H3: HintTarget.STRATEGY}
CONVERSION = "Viết thành số thập phân:\n7/10 = ……"


def codes_of(text, level=HintLevel.H2, *, stem=None, answer=None, item_id="STP-PH01-1", **update):
    """Why the checks refuse a hint written for an item of the test plan (empty: it is kept)."""
    plan = plan_and_bank()
    lesson = plan.lessons["STP-Bài11"]
    item = lesson.item(item_id)
    if stem:
        update["stem"] = stem
    if answer:  # (value, form) of a numeric answer, or the answer itself
        update["answer"] = (
            NumericAnswer(type="numeric", value=answer[0], form=answer[1])
            if isinstance(answer, tuple)
            else answer
        )
    item = item.model_copy(update=update)
    node = next(n for n in plan.package.nodes if n.id == item.kc_ids[0])
    return _hint_codes(text, item, lesson, node, level, TARGETS[level])


@pytest.mark.parametrize(
    ("text", "level", "item", "codes"),
    [
        # The names the grade uses for what is on the page are not new ideas ("dấu phẩy" is no step).
        (
            "Dấu phẩy ngăn cách phần nguyên và phần thập phân. Hai số này có phần nguyên bằng nhau không?",
            HintLevel.H2,
            {},
            [],
        ),
        # 10, 100, 1000 are the places of a decimal, whatever the question prints.
        (
            "Mẫu số là 10, vậy phần thập phân có mấy chữ số?",
            HintLevel.H2,
            {"stem": CONVERSION, "answer": ("0,7", "decimal")},
            [],
        ),
        # The two terms of the fraction the child reads are printed in the item, though the validator reads
        # "7/10" as one number.
        (
            "Con nhìn vào tử số 7 và mẫu số 10 của phân số: mẫu số cho biết điều gì?",
            HintLevel.H2,
            {"stem": CONVERSION, "answer": ("0,7", "decimal")},
            [],
        ),
        # What stays refused: a number that is nowhere, the answer, a method the period does not teach.
        ("Con thử so sánh với 35 xem sao?", HintLevel.H3, {}, ["UNGROUNDED_NUMBER"]),
        ("Đáp án là 8,3 > 8,29 đó con, con chép lại nhé?", HintLevel.H3, {}, ["ANSWER_LEAK"]),
        ("Con nhân hai số với 10 rồi so sánh nhé?", HintLevel.H3, {}, ["NEW_MATH_TERM"]),
        # The denominator of the answer is part of the answer: no free pass for it.
        (
            "Mẫu số của phân số này là 10, đúng không?",
            HintLevel.H2,
            {"stem": "Viết thành phân số thập phân:\n0,9 = ……", "answer": ("9/10", "fraction")},
            ["ANSWER_LEAK"],
        ),
    ],
)
def test_the_checks_let_the_words_and_places_of_the_grade_through_and_nothing_more(text, level, item, codes):
    assert codes_of(text, level, **item) == codes


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("Con đã đọc đề và nhận ra cần so sánh hai số, đúng không?", HintLevel.H1),
        ("Con hiểu đề yêu cầu so sánh hai số thập phân, phải không?", HintLevel.H1),
        ("Đề bài yêu cầu con làm gì?", HintLevel.H1),
        ("Cô muốn con so sánh hai số này, con biết đề hỏi gì không?", HintLevel.H1),
        ("Hai số cần so sánh, con đã hiểu yêu cầu chưa?", HintLevel.H2),
    ],
)
def test_a_hint_that_asks_about_the_exercise_and_not_about_its_data_is_refused(text, level):
    assert codes_of(text, level) == ["GENERIC"]


def test_a_hint_that_tells_part_of_the_answer_is_a_leak_wherever_the_lesson_prints_the_number():
    """REFORM-3 pilot: "…thành phân số có mẫu số là 100. Tử số là bao nhiêu?" for 1,02 tells half of 102/100,
    and passed because another text of the lesson prints 100."""
    item = {
        "stem": "Viết thành phân số thập phân:\n1,02 = ……",
        "answer": ("102/100", "fraction"),
        "explanation": "Mẫu số 100 có hai chữ số 0.",  # the number is printed in the lesson, not in the item
    }
    leak = "Con viết 1,02 thành phân số có mẫu số là 100. Tử số là bao nhiêu?"
    assert codes_of(leak, HintLevel.H3, **item) == ["ANSWER_LEAK"]
    ask = "Con viết 1,02 thành phân số thập phân. Mẫu số là bao nhiêu?"
    assert codes_of(ask, HintLevel.H3, **item) == []
    printed = {"stem": "Viết thành số thập phân:\n49/100 = ……", "answer": ("0,49", "decimal")}
    same_words = "Mẫu số là 100, vậy phần thập phân gồm mấy chữ số khi con viết tử số vào?"
    assert codes_of(same_words, HintLevel.H3, **printed) == []  # 100 is on the page the child reads


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("Con ghi “Đ” cho câu này vì hai đáy song song, đúng không?", ["ANSWER_LEAK"]),
        ("Con chọn S vì hai đáy không song song nhé?", ["ANSWER_LEAK"]),
        ("Khẳng định này đúng vì hai đáy song song, con thấy sao?", ["ANSWER_LEAK"]),
        ("Câu này đúng hay sai khi con nhớ quy tắc về hai đáy?", []),
        ("Quy tắc nói gì về hai đáy của hình thang?", []),
    ],
)
def test_a_hint_on_a_true_false_statement_does_not_say_which_it_is(text, codes):
    stem, answer = "Hình thang có hai đáy song song. ……", BooleanAnswer(type="boolean", value=True)
    assert codes_of(text, HintLevel.H3, stem=stem, answer=answer) == codes


def test_a_hint_that_names_a_datum_and_asks_for_it_is_kept():
    for text in (
        "Con nhìn vào hai số 8,3 và 8,29: phần nguyên của mỗi số là mấy?",
        "Trong đề, hai số cần so sánh là những số nào?",
        "Phần nguyên bằng nhau thì con so sánh hàng nào trước?",
    ):
        assert codes_of(text, HintLevel.H1) == [], text
    # a tag question on a rule is an H2 like any other; it is H1 that must ask for something
    assert codes_of("Con nhớ rằng phần nguyên lớn hơn thì số lớn hơn, đúng không?", HintLevel.H2) == []


def test_the_hint_prompt_is_the_second_version_and_forbids_the_empty_questions():
    assert HINT_PROMPT == "draft-hints.v2.md"
    text = prompt_text(HINT_PROMPT)
    assert "<!--" not in text  # the comment block is for the people who edit it
    for part in (
        "H1 (TASK)",
        "H2 (CONCEPT)",
        "H3 (STRATEGY)",
        "KHÔNG nêu đáp án",
        "Đề bài yêu cầu con làm gì?",
    ):
        assert part in text
    # the gateway counts 3 characters a token: six items and a rule of 900 characters must still fit in 3 000
    assert len(text) / 3 + (900 + 6 * 600) / 3 < 3000


def test_the_examples_of_the_prompt_are_hints_the_checks_would_keep():
    """The model imitates the examples: each must be one question of at most 35 words, about the data."""
    examples = [
        json.loads(line) for line in prompt_text(HINT_PROMPT).splitlines() if line.startswith('{"h1"')
    ]
    assert len(examples) == 2
    for example in examples:
        for key, level in (("h1", HintLevel.H1), ("h2", HintLevel.H2), ("h3", HintLevel.H3)):
            hint = example[key]
            assert hint.count("?") == 1 and hint.endswith("?"), hint
            assert len(hint.split()) <= MAX_HINT_WORDS and not generic_hint(hint, level), hint


def test_a_drafter_can_still_send_the_first_prompt_for_the_comparison(tmp_path):
    router = ScriptedRouter({"STP-PH01-1": GOOD}, {"answers": [], "key_ideas": [], "missing_asks": []})
    Drafter(router, tmp_path).draft(plan_and_bank())
    Drafter(router, tmp_path / "v1", hint_prompt="draft-hints.v1.md").draft(plan_and_bank())
    sent = {p[:40] for p in router.prompts}
    assert prompt_text("draft-hints.v2.md")[:40] in sent and prompt_text("draft-hints.v1.md")[:40] in sent


class RewritingRouter(ScriptedRouter):
    """An empty question for H1 at first; to the request that follows (it has "SỬA LẠI"), a good one."""

    def chat(self, model_class, request, *, calls_used=0):
        payload = json.loads(request.messages[1].content)
        if "SỬA LẠI" not in payload:
            return super().chat(model_class, request, calls_used=calls_used)
        self.requests.append(payload)
        rows = [{"id": n["id"], "h1": GOOD["h1"], "h2": "", "h3": ""} for n in payload["SỬA LẠI"]]
        result = SimpleNamespace(
            data={"items": rows}, model="qwen/qwen3.8-27b", usage=Usage(prompt_tokens=900)
        )
        return SimpleNamespace(result=result, calls_made=1)


def test_an_empty_question_is_asked_again_with_its_reason_and_the_rewrite_is_kept(tmp_path):
    router = RewritingRouter(
        {"STP-PH01-1": {**GOOD, "h1": "Đề bài yêu cầu con làm gì?"}},
        {"answers": [], "key_ideas": [], "missing_asks": []},
    )
    plan = plan_and_bank()
    drafts = Drafter(router, tmp_path).draft(plan)
    assert plan.lessons["STP-Bài11"].item("STP-PH01-1").hints[0].text == GOOD["h1"]
    refused = [d for d in drafts if not d.ok and d.target == "STP-PH01-1:H1"]
    assert refused and refused[0].codes == ["GENERIC"]
    notes = [n for r in router.requests for n in r.get("SỬA LẠI", []) if n["id"] == "STP-PH01-1"]
    assert notes and notes[0]["lý do"] == RETRY_NOTES["GENERIC"]
    asked = [r["YÊU CẦU"] for r in router.requests if "SỬA LẠI" in r]
    assert asked and all('dấu "?"' in a for a in asked)  # a rewrite lost its question mark in the pilot
