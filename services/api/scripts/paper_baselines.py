"""Numbers of the market-comparison section of the paper: output docs/paper/data/baselines.json.

Read only, no model call: it reads the replies, the judge's marks and the gradings that
``scripts/eval_vs_baselines.py`` (EVAL-1) stored in its cache, and aggregates them by system and by role.
The three systems answer the same thirteen hard students (25 turns): B1 a chatbot with the plain system
prompt a parent would write (Gemini), B2 the very model of CAVAT with a careful Socratic prompt, C CAVAT.
"""

from __future__ import annotations

import json
import re
import sys
import time
from statistics import fmean

import eval_vs_baselines as ev
import yaml
from cavat.config import REPO_ROOT, get_settings
from cavat.core.pedagogy import Outcome
from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest
from cavat.modules.ai_gateway.gemini import GeminiChat
from cavat.modules.ai_gateway.router import build_router
from cavat.modules.assessment.math_checker import check_answer
from cavat.modules.content.chapter_package import load_chapter
from cavat.modules.teaching.conductor import clean

OUT = REPO_ROOT / "docs/paper/data/baselines.json"
GRADING_V2 = REPO_ROOT / "evals/datasets/grading-vi-v2.yaml"  # held out: written and tagged before GRADE-1
V2_CACHE = get_settings().storage_dir / "eval" / "paper-grading-v2.json"
MAX_WORDS = ev.MAX_WORDS
# The replies to the four wrong answers of the thirteen roles (12 replies) were read by the author: those that
# tell the child a wrong answer is right. A word list found more "approvals" than there are (a reply that
# says "kết quả chính xác nhất" is not one), so the labels are by hand and listed here.
APPROVES_WRONG = {
    ("B1", "Bi, đoán bừa", "C"),  # "Tuyệt vời! Bạn đã hiểu bài rất nhanh" to the choice 10/3
    ("B2", "Mít, sai mà chắc chắn", "0,09"),  # "Con đã viết đúng số thập phân rồi" to 0,09
}


def replies() -> list[ev.Reply]:
    cache = ev._cache()
    chapter = load_chapter(ev.CHAPTER)
    out: list[ev.Reply] = []
    for system in ("B1", "B2"):
        for role, item_id, messages in ev.SCENARIOS:
            before = ""
            for k, said in enumerate(messages):
                got = cache.get(f"{system}|{role}|{k}")
                if got is None:
                    continue
                r = ev.Reply(system, role, item_id, said, got["text"], before, model=got["model"])
                key = f"judge|{system}|{role}|{said}|{got['text']}"
                r.judged = cache.get(key) or {}
                out.append(r)
                before = got["text"]
    for role, _item_id, _messages in ev.SCENARIOS:
        for raw in cache.get(f"C|{role}") or []:
            r = ev.Reply(**raw)
            r.judged = cache.get(f"judge|C|{role}|{r.said}|{r.text}") or {}
            out.append(r)
    for r in out:
        r.item = chapter.item(r.item_id)  # type: ignore[attr-defined]
    return out


def wrong_turn(r: ev.Reply, chapter) -> bool:
    """The child's words are an attempt that the deterministic checker marks wrong."""
    item = r.item  # type: ignore[attr-defined]
    result = check_answer(item, clean(r.said).text, chapter.lesson_of(r.item_id))
    return result.outcome == Outcome.WRONG


def summarise(rs: list[ev.Reply], chapter) -> dict:
    judged = [r.judged for r in rs if "socratic" in r.judged]
    wrong = [r for r in rs if wrong_turn(r, chapter)]
    approves = [r for r in wrong if (r.system, r.role, r.said) in APPROVES_WRONG]
    avg = lambda key: round(fmean(j[key] for j in judged), 2) if judged else None  # noqa: E731
    return {
        "turns": len(rs),
        "says_answer": sum(ev.says_answer(r.item, r.text, r.said) for r in rs),  # type: ignore[attr-defined]
        "judge_leak": sum(bool(r.judged.get("leaked_answer")) for r in rs),
        "judged": len(judged),
        "more_than_one_question": sum(r.questions > 1 for r in rs),
        "no_question": sum(r.questions == 0 for r in rs),
        "over_limit_words": sum(r.words > MAX_WORDS for r in rs),
        "words_mean": round(fmean(r.words for r in rs), 1),
        "words_max": max(r.words for r in rs),
        "wrong_turns": len(wrong),
        "approves_wrong": len(approves),
        "approves_wrong_cases": [{"role": r.role, "said": r.said, "reply": r.text[:200]} for r in approves],
        "follows_intent": avg("follows_intent"),
        "socratic": avg("socratic"),
        "child_friendly": avg("child_friendly"),
        "on_topic": avg("on_topic"),
    }


def grade_v2(chapter, cases) -> dict[str, list[bool]]:
    """The same grading prompt as part B of EVAL-1, on the held-out set v2: one batch for each model, kept in
    a cache of its own (the EVAL-1 cache holds v1 under the same system names)."""
    cache = json.loads(V2_CACHE.read_text(encoding="utf-8")) if V2_CACHE.exists() else {}
    lines = "\n".join(
        f"{i + 1}. Đề: {chapter.item(c['item']).stem} | Học sinh trả lời: {c['answer']}"
        for i, c in enumerate(cases)
    )
    request = ChatRequest(
        messages=(ChatMessage("system", ev.GRADE_PROMPT), ChatMessage("user", lines)),
        max_output_tokens=800,
        temperature=0.0,
    )
    settings = get_settings()
    calls = {
        "B1": lambda: GeminiChat(settings.gemini_api_key, models=ev.GEMINI_MODELS).chat(request).text,
        "B2": lambda: ev.qwen_text(build_router(), request),
    }
    for system, call in calls.items():
        if system in cache:
            continue
        time.sleep(ev.PAUSE_S)
        raw = call()
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        cache[system] = [bool(x) for x in data["correct"]][: len(cases)]
        V2_CACHE.parent.mkdir(parents=True, exist_ok=True)
        V2_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


def confusion(got: list[bool], truth: list[bool]) -> dict | None:
    if len(got) != len(truth):
        return None
    pairs = list(zip(got, truth, strict=True))
    return {
        "right": sum(a == b for a, b in pairs),
        "false_positive": sum(a and not b for a, b in pairs),
        "false_negative": sum(b and not a for a, b in pairs),
    }


def main() -> None:
    chapter = load_chapter(ev.CHAPTER)
    rs = replies()
    systems = {s: [r for r in rs if r.system == s] for s in ("B1", "B2", "C")}
    if not all(systems.values()):
        sys.exit("a system has no stored reply: run scripts/eval_vs_baselines.py first")
    out: dict = {
        "judge": ev.JUDGE_MODEL,
        "models": {s: sorted({r.model for r in v if r.model}) for s, v in systems.items()},
        "systems": {s: summarise(v, chapter) for s, v in systems.items()},
        "roles": {},
    }
    roles = [role for role, _, _ in ev.SCENARIOS]
    for role in roles:
        out["roles"][role] = {}
        for s, v in systems.items():
            sel = [r for r in v if r.role == role]
            if not sel:
                continue
            out["roles"][role][s] = {
                "turns": len(sel),
                "says_answer": sum(ev.says_answer(r.item, r.text, r.said) for r in sel),  # type: ignore[attr-defined]
                "judge_leak": sum(bool(r.judged.get("leaked_answer")) for r in sel),
                "words": round(fmean(r.words for r in sel), 1),
                "questions": round(fmean(r.questions for r in sel), 2),
                "socratic": round(fmean(r.judged["socratic"] for r in sel if "socratic" in r.judged), 2)
                if any("socratic" in r.judged for r in sel)
                else None,
            }
    # grading: v1 (seen: its misses were read before GRADE-1) and v2 (held out)
    out["grading"] = {}
    cache = ev._cache()
    for tag, path in (("v1", ev.GRADING), ("v2", GRADING_V2)):
        cases = yaml.safe_load(path.read_text(encoding="utf-8"))["cases"]
        truth = [c["correct"] for c in cases]
        got = {
            "C": [
                check_answer(
                    chapter.item(c["item"]), clean(c["answer"]).text, chapter.lesson_of(c["item"])
                ).outcome
                == Outcome.CORRECT
                for c in cases
            ]
        }
        if tag == "v1":
            got["B1"], got["B2"] = cache.get("grade|B1") or [], cache.get("grade|B2") or []
        else:
            stored = grade_v2(chapter, cases)
            got["B1"], got["B2"] = stored.get("B1", []), stored.get("B2", [])
        out["grading"][tag] = {"n": len(truth), "positives": sum(truth)} | {
            s: confusion(g, truth) for s, g in got.items()
        }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for s, v in out["systems"].items():
        print(
            s,
            {
                k: v[k]
                for k in (
                    "turns",
                    "says_answer",
                    "judge_leak",
                    "more_than_one_question",
                    "over_limit_words",
                    "words_mean",
                    "wrong_turns",
                    "approves_wrong",
                    "socratic",
                    "follows_intent",
                )
            },
        )
        for c in v["approves_wrong_cases"]:
            print("   approves:", c["role"], "|", c["said"], "|", c["reply"][:120].replace("\n", " "))
    print("grading", out["grading"])
    print("written", OUT.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
