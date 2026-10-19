"""AUTO-3: the chooser measured outside the session cap (``scripts/eval_chooser.py``). Offline: a recording
chooser that picks nothing, the count per menu, the cache that spares the quota, and a report that quotes
reasons only for the chapter whose content is in the repo."""

from __future__ import annotations

import json
from dataclasses import replace

from cavat.modules.ai_gateway.base import ChatResult
from cavat.modules.ai_gateway.router import ChatOutcome, FallbackReason
from cavat.modules.tutor.chooser import Choice
from scripts.eval_chooser import REPO_CHAPTER, Recorder, ask, report, summarize, unique
from test_move_chooser import tutor

TEACHER_CHAPTER = "math-g5-area-triangle-trapezoid"


def recorded_cases(chapter: str = REPO_CHAPTER):
    recorder = Recorder(chapter)
    t = tutor(recorder)
    turn = t.on_student("0,5")
    assert turn.move.value == "PROBE"  # the recorder picks nothing: the policy's own move
    return recorder.cases


class ScriptedRouter:
    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def chat(self, model_class, request, *, calls_used):
        self.requests.append(request)
        data = self.answers.pop(0) if self.answers else None
        if data is None:
            return ChatOutcome(None, FallbackReason.QUOTA_EXCEEDED, 0)
        return ChatOutcome(ChatResult("qwen-test", str(data), data), None, 1)


def test_the_recorder_keeps_the_turn_and_the_menu():
    [case] = recorded_cases()
    assert case.kind == "PROBE → HINT" and case.moves == ("PROBE", "HINT")
    assert case.said == "0,5" and case.turn == 1 and "R-FIRST-WRONG" in case.rules
    assert [o.id for o in case.menu()] == ["A", "B"]
    assert unique([case, case]) == [case]


def test_the_count_tells_kept_other_and_none_apart():
    [a] = recorded_cases()
    [b] = recorded_cases(TEACHER_CHAPTER)
    s = summarize([a], {a.key: Choice("A", "")})
    assert (s["turns"], s["kept"], s["other"], s["none"]) == (1, 1, 0, 0)
    s = summarize([a], {a.key: Choice("B", "")})
    assert (s["kept"], s["other"]) == (0, 1)
    s = summarize([a], {a.key: Choice("Z", "")})  # off the menu: counted as no answer
    assert s["none"] == 1 and s["by_kind"]["PROBE → HINT"]["turns"] == 1
    assert a.key == b.key  # the same menu on the same words: asked once whatever the chapter


def test_the_cache_spares_the_quota_and_a_refusal_is_asked_again(tmp_path):
    [case] = recorded_cases()
    cache = tmp_path / "cache.json"
    picks, spent, cached = ask([case], ScriptedRouter(None), cache, 0)  # quota: nothing kept
    assert picks[case.key] is None and spent == 0 and not cache.exists()
    router = ScriptedRouter({"choice": "B", "reason": "Con cần một gợi ý nhỏ."})
    picks, spent, cached = ask([case], router, cache, 0)
    assert picks[case.key] == Choice("B", "Con cần một gợi ý nhỏ.") and (spent, cached) == (1, 0)
    assert json.loads(cache.read_text())[case.key]["option_id"] == "B"
    again = ScriptedRouter()
    picks, spent, cached = ask([case], again, cache, 0)
    assert again.requests == [] and (spent, cached) == (0, 1) and picks[case.key].option_id == "B"


def test_the_report_quotes_reasons_only_for_the_repo_chapter():
    [mine] = recorded_cases()
    theirs = recorded_cases(TEACHER_CHAPTER)[0]
    picks = {mine.key: Choice("B", "Lý do có thể nhắc nội dung bài.")}
    meta = {"date": "2026-10-19", "collected": 2, "sessions": 2, "calls": 1, "cached": 0}
    text = report([mine], picks, meta)
    assert "| PROBE → HINT | 1 | 0 | 1 | 0 |" in text and "Lý do có thể nhắc nội dung bài." in text
    text = report([theirs], picks, meta)
    assert "Lý do" not in text.split("|---|")[-1]


def test_the_report_tells_the_first_answer_from_a_repeated_mistake():
    [first] = recorded_cases()
    assert first.stage == "lần trả lời đầu" and dict(first.situation)["so_lan_tra_loi"] == 1
    later = replace(first, situation=(("so_goi_y_da_nhan", 1), ("so_lan_tra_loi", 2)))
    assert later.stage == "đã sai hoặc đã có gợi ý" and later.key != first.key
    picks = {first.key: Choice("A", ""), later.key: Choice("B", "")}  # A asks back, B is a hint
    s = summarize([first, later], picks)
    assert s["by_stage"] == {
        "lần trả lời đầu": {"turns": 1, "least": 1},
        "đã sai hoặc đã có gợi ý": {"turns": 1, "more": 1},
    }
    meta = {"date": "2026-10-19", "collected": 2, "sessions": 1, "calls": 0, "cached": 2}
    assert "| đã sai hoặc đã có gợi ý | 1 | 0 | 1 |" in report([first, later], picks, meta)
