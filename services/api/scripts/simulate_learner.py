"""A learner who starts by understanding little, studied through the real session API (``make simulate``).

The owner asked (2026-10-12) to let the student account study every situation a child brings, from not
understanding much to understanding, so the teacher's charts show real data. This script plays that child
against the session API in this process: the same code path as the web app, the same database (the one of
services/api/.env), the same Qwen budget per session. The student account is chosen explicitly
(``--student-id``) and nothing is written unless ``--write`` is given: CLAUDE.md rule 11 keeps scripts away
from cavat_dev, and this one runs there only when the owner asks for it. Every session it makes is listed
at the end, so they can be told apart from the child's own sessions.

The child ("Vương"): understanding of each period starts low and grows with what the tutor does (a hint, a
worked example, an explanation, feedback on a wrong answer). Below its threshold an answer is wrong in a
way children are wrong (the comma moved, the sign turned, the list cut short); on the way the child types
teen code, emoji, stretched words, a heap of keywords, asks what a word means, says it is bored, talks
about football, asks for a hint, writes a long message with the answer at its end.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from fractions import Fraction

from cavat.config import get_settings
from cavat.main import app
from cavat.modules.assessment.math_checker import parse_literal
from cavat.modules.session import chapter_service
from cavat.modules.session.api import account_name, student_identity
from fastapi.testclient import TestClient

CHAPTERS = ("math-g5-decimals", "math-g5-area-triangle-trapezoid")
OFF_TOPIC = [
    "Cô ơi con thích đá bóng lắm 😆",
    "hôm nay con được 10 điểm tiếng việt á cô",
    "cô ơi mấy giờ rồi ạ",
]
AFFECT = ["chán wá à 😴", "khó wá con hk làm đc đâu 😭", "con ngu toán lắm cô ơi"]
DONT_KNOW = ["ko bít j hết á cô", "kbt ạ", "hk hiu cô ơi 😢", "con chịu ạaaa"]
DUMP = {
    "math-g5-decimals": "phân số thập phân mẫu số tử số phần mười phần trăm",
    "math-g5-area-triangle-trapezoid": "tam giác hình thang đáy chiều cao diện tích",
}
ASK_WORD = {
    "math-g5-decimals": ["phần thập phân là j vậy cô?", "mẫu số là gì ạ?", "tại sao 0,05 khác 0,5 ạ?"],
    "math-g5-area-triangle-trapezoid": [
        "đường cao là j vậy cô?",
        "sao phải chia 2 ạ?",
        "đáy lớn là cạnh nào ạ?",
    ],
}


VAGUE_WHY = ["vì con làm theo quy tắc cô dạy ạ", "tại vì con thấy vậy á cô", "vì đúng mà cô 😅"]


def specific_why(chapter, item_id: str) -> str:
    """A reason with the numbers of the item, as a child who got it says it."""
    item = chapter.item(item_id)
    nums = re.findall(r"\d+(?:,\d+)?", item.stem)[:3]
    return (
        f"vì con lấy {' với '.join(nums)} rồi tính ra {right_answer(chapter, item_id)}"
        if nums
        else "vì con so sánh từng hàng ạ"
    )


def right_answer(chapter, item_id: str) -> str:
    ans = chapter.item(item_id).answer
    if ans.type == "compare":
        left, right = parse_literal(ans.left).value, parse_literal(ans.right).value
        sign = "<" if left < right else ">" if left > right else "="
        larger, smaller = (ans.left, ans.right) if left > right else (ans.right, ans.left)
        return {"sign": sign, "larger": larger, "smaller": smaller}[ans.ask]
    if ans.type == "order":
        key = lambda n: Fraction(parse_literal(n).value)  # noqa: E731
        return "; ".join(sorted(ans.numbers, key=key, reverse=ans.direction == "desc"))
    if ans.type == "numeric":
        return ans.value
    if ans.type == "choice":
        return next(o.id for o in ans.options if o.correct)
    if ans.type == "boolean":
        return "đúng" if ans.value else "sai"
    return ans.sample_answer


def wrong_answer(chapter, item_id: str, rng: random.Random) -> str:
    """Wrong the way a child is wrong: most often the typical mistake the teacher's documents name for
    this item (MISC-1: "quên chia 2", "3,05 viết 3,5"...), else a generic slip."""
    ans = chapter.item(item_id).answer
    typical = list(getattr(ans, "wrong_answers", {}) or {})
    if typical and rng.random() < 0.75:
        return rng.choice(typical)
    if ans.type == "choice" and rng.random() < 0.75:
        marked = [o.id for o in ans.options if o.misconceptions and not o.correct]
        if marked:
            return rng.choice(marked)
    if ans.type == "compare":
        return {"<": ">", ">": "<", "=": "<"}.get(right_answer(chapter, item_id), "<")
    if ans.type == "order":
        return "; ".join(ans.numbers)  # as listed: not sorted
    if ans.type == "numeric":
        v = ans.value
        if "/" in v:
            return str(parse_literal(v).value.numerator / parse_literal(v).value.denominator).replace(
                ".", ","
            )
        if "," in v:  # the comma one place off: 0,7 -> 0,07
            whole, frac = v.split(",")
            return f"{whole},0{frac}" if rng.random() < 0.5 else f"{whole}{frac[:1]},{frac[1:] or '0'}"
        return str(int(v) * 2 if v.isdigit() and int(v) < 1000 else int(v) + 10) if v.isdigit() else "12"
    if ans.type == "choice":
        return next(o.id for o in ans.options if not o.correct)
    if ans.type == "boolean":
        return "sai" if ans.value else "đúng"
    numbers = re.findall(r"\d+(?:,\d+)?", ans.sample_answer)
    return numbers[0] if numbers else "con nghĩ là cái kia ạ"


def teen(text: str) -> str:
    """The right answer written the way the child types when it starts to get it."""
    return rng_choice(["đáp án là {} ạ", "{} ạaa", "{} đúng hơm cô", "dạ {} 😁"]).format(text)


_RNG = random.Random(7)


def rng_choice(xs):
    return _RNG.choice(xs)


class Vuong:
    def __init__(self, chapter, chapter_id: str, seed: int = 7):
        self.chapter, self.chapter_id = chapter, chapter_id
        self.rng = random.Random(seed)
        self.understanding: dict[str, float] = {}
        self.tries: dict[str, int] = {}
        self.said: set[tuple[str, str]] = set()  # (node, behaviour) already shown in this period
        self.log: list[str] = []

    def learn(self, node: str | None, amount: float) -> None:
        if node:
            self.understanding[node] = min(0.97, self.understanding.get(node, 0.12) + amount)

    def notice(self, tutor_texts: list[str], node: str | None) -> None:
        """What the tutor just did teaches the child something."""
        for t in tutor_texts:
            low = t.lower()
            if "gợi ý" in low or "con thử" in low or "con hãy" in low:
                self.learn(node, 0.12)
            if "cô làm mẫu" in low or "bước 1" in low or "đáp số" in low:
                self.learn(node, 0.22)
            if "đúng rồi" in low:
                self.learn(node, 0.05)
            if "nhắc lại ý chính" in low or "mình cùng xem lại" in low:
                self.learn(node, 0.1)

    def once(self, node: str, what: str, chance: float) -> bool:
        if (node, what) in self.said or self.rng.random() > chance:
            return False
        self.said.add((node, what))
        return True

    def reply(self, state: dict) -> tuple[str, str]:
        """(command, text): ANSWER with a text, HINT, or CHOICE with a choice id."""
        t, node = state["teaching"], state["teaching"]["current_node_id"]
        u = self.understanding.setdefault(node, 0.12) if node else 0.5
        if state.get("pending_choice"):
            return ("CHOICE", "HINT" if u < 0.5 else "RETRY")
        if t["awaiting"] == "THEORY_REPLY":
            if self.once(node, "dump", 0.3):
                return ("ANSWER", DUMP[self.chapter_id])
            if self.once(node, "dontknow-theory", 0.5 if u < 0.4 else 0.1):
                return ("ANSWER", self.rng.choice(DONT_KNOW))
            if self.once(node, "offtopic", 0.2):
                return ("ANSWER", self.rng.choice(OFF_TOPIC))
            if self.once(node, "question", 0.4):  # a question on the lesson: the RAG of this period answers
                return ("ANSWER", self.rng.choice(ASK_WORD[self.chapter_id]))
            variant = next(
                (v for n in self.chapter.nodes for v in n.theory if v.ask and v.ask in (t["prompt"] or "")),
                None,
            )
            self.learn(node, 0.08)
            if variant is not None and variant.reply and u > 0.2:
                return ("ANSWER", variant.reply)
            return ("ANSWER", "con nghĩ là vậy ạ")
        if t["awaiting"] == "RETELL":
            ideas = self.chapter.node(node).explain.key_ideas
            if u < 0.45 and self.once(node, "weak-retell", 0.8):
                return ("ANSWER", "ko nhớ lắm ạ 😅")
            self.learn(node, 0.05)
            return ("ANSWER", ". ".join(phr[0] for phr in ideas))
        item = state["item"]
        item_id = item["item_id"]
        if item["expecting"] == "EXPLANATION":
            # WHY-1: a child who does not get it yet says something vague first; asked again, the numbers.
            if u < 0.55 and self.once(item_id, "vague-why", 0.8):
                return ("ANSWER", self.rng.choice(VAGUE_WHY))
            return ("ANSWER", self.chapter.item(item_id).explanation or specific_why(self.chapter, item_id))
        self.tries[item_id] = self.tries.get(item_id, 0) + 1
        first = self.tries[item_id] == 1
        if first:
            if self.once(node, "ask", 0.35):
                return ("ANSWER", self.rng.choice(ASK_WORD[self.chapter_id]))
            if self.once(node, "affect", 0.25 if u < 0.4 else 0.05):
                return ("ANSWER", self.rng.choice(AFFECT))
            if self.once(node, "offtopic-item", 0.12):
                return ("ANSWER", self.rng.choice(OFF_TOPIC))
            if self.once(node, "dontknow", 0.35 if u < 0.35 else 0.05):
                return ("ANSWER", self.rng.choice(DONT_KNOW))
            if u < 0.3 and self.once(node, "hint-button", 0.4):
                return ("HINT", "")
        if self.rng.random() < u:
            answer = right_answer(self.chapter, item_id)
            if self.once(node, "long", 0.1):
                return ("ANSWER", "con nghĩ mãi " * 10 + f"nên con ra là {answer}")
            if self.once(node, "stretch", 0.15):
                return ("ANSWER", f"{answer} đúnggggg hônggg cô 😁")
            if self.once(node, "o-zero", 0.3) and re.fullmatch(r"0,\d+", answer):
                return ("ANSWER", "o" + answer[1:])
            return ("ANSWER", teen(answer) if self.rng.random() < 0.3 else answer)
        self.learn(node, 0.06)  # a wrong answer, and the tutor's feedback on it
        return ("ANSWER", wrong_answer(self.chapter, item_id, self.rng))


def run(client: TestClient, chapter_id: str, student: str, max_sessions: int, max_turns: int) -> list[dict]:
    sessions = []
    vuong = None
    for n in range(max_sessions):
        created = client.post("/v1/sessions", json={"lesson_id": chapter_id})
        assert created.status_code == 201, created.text
        sid = created.json()["session_id"]
        state = client.post(f"/v1/sessions/{sid}/join").json()
        chapter = chapter_service.chapters()[chapter_id]
        vuong = vuong or Vuong(chapter, chapter_id)
        turns = 0
        seen = len(state["transcript"])
        while state["lifecycle_state"] != "COMPLETED" and turns < max_turns:
            node = state["teaching"]["current_node_id"]
            vuong.notice([x["text"] for x in state["transcript"][seen:] if x["actor"] == "tutor"], node)
            seen = len(state["transcript"])
            command, text = vuong.reply(state)
            v = state["state_version"]
            key = {"Idempotency-Key": f"sim-{sid}-{v}"}
            if command == "CHOICE":
                r = client.post(
                    f"/v1/sessions/{sid}/choices",
                    json={"choice_id": text, "expected_state_version": v},
                    headers=key,
                )
            elif command == "HINT":
                body = {"item_attempt_id": state["teaching"]["input_id"], "expected_state_version": v}
                r = client.post(f"/v1/sessions/{sid}/hint-requests", json=body, headers=key)
            else:
                body = {
                    "item_attempt_id": state["teaching"]["input_id"] or "",
                    "kind": "ANSWER",
                    "content": {"text": text[:500]},
                    "expected_state_version": v,
                }
                r = client.post(f"/v1/sessions/{sid}/responses", json=body, headers=key)
            if r.status_code != 200:
                print(f"  ! {r.status_code} {r.text[:200]} on {command} {text!r}")
                break
            state = client.get(f"/v1/sessions/{sid}/state").json()
            turns += 1
        if state["lifecycle_state"] != "COMPLETED" and "--debug" in sys.argv:
            for x in state["transcript"][-40:]:
                print(f"    {x['actor'][:5]}: {x['text'][:150]}")
        passed = state["teaching"]["passed"]
        total = state["teaching"]["total"]
        print(f"  buổi {n + 1}: {sid} lượt={turns} {state['lifecycle_state']} tiết qua={passed}/{total}")
        sessions.append(
            {"session_id": sid, "turns": turns, "lifecycle": state["lifecycle_state"], "passed": passed}
        )
        if passed == state["teaching"]["total"]:
            break
    return sessions


def _in_memory(settings) -> None:
    """Copy the teacher's documents and plans into an in-memory database: nothing reaches the real one."""
    import asyncio

    from cavat import db
    from cavat.core.memory_db import InMemoryDatabase
    from cavat.modules.session import api as session_api
    from cavat.modules.session.api import get_database

    memory = InMemoryDatabase()

    async def copy() -> None:
        real = db.get_db(settings)
        await db.ensure_indexes(memory)
        for name in ("documents", "item_banks", "teaching_plans"):
            docs = await real[name].find({}).to_list(None)
            if docs:
                await memory[name].insert_many(docs)
        await db.close_client()

    asyncio.run(copy())
    app.dependency_overrides[get_database] = lambda: memory
    session_api.tutor_router = lambda: None  # templates only: no model call


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--name", default="Vuong")
    parser.add_argument("--chapter", choices=[*CHAPTERS, "all"], default="all")
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument("--turns", type=int, default=400, help="turns per session at most")
    parser.add_argument(
        "--write", action="store_true", help="really write the sessions to the database of .env"
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="copy the plans to an in-memory database, run there, templates only",
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    print(f"Database: {settings.mongodb_db} · học sinh {args.student_id} ({args.name})")
    if args.memory:
        _in_memory(settings)
    elif not args.write:
        sys.exit("Thêm --write để ghi thật (CLAUDE.md quy tắc 11: chỉ khi chủ dự án yêu cầu), hoặc --memory.")
    app.dependency_overrides[student_identity] = lambda: args.student_id
    app.dependency_overrides[account_name] = lambda: args.name
    made = {}
    with TestClient(app) as client:
        for chapter_id in CHAPTERS if args.chapter == "all" else (args.chapter,):
            print(chapter_id)
            made[chapter_id] = run(client, chapter_id, args.student_id, args.sessions, args.turns)
    if args.memory:
        return
    out = settings.storage_dir / "reports" / "simulated-sessions.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(out.read_text()) if out.exists() else []
    out.write_text(
        json.dumps(
            [*previous, {"student_id": args.student_id, "sessions": made}], ensure_ascii=False, indent=1
        )
    )
    print(f"Các buổi đã tạo được ghi ở {out}")


if __name__ == "__main__":
    main()
