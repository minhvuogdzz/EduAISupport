"""What the teacher's documents leave out, drafted by Qwen and checked before it reaches the plan (INGEST-3b).

The owner chose (2026-10-12) to have the AI draft the hint ladders from the documents, for the teacher to
approve. Qwen writes; it never decides what is right:

- a hint ladder H1 (TASK), H2 (CONCEPT), H3 (STRATEGY) for every practice item, from the rule, the steps
  and the mistakes of its own period. Each hint goes through the tutor's own validator (no answer leak, one
  question at the end, numbers of the item, Vietnamese, the child called "con") and must use only the
  mathematical terms of the item and the rule. A hint that fails is left out, never replaced;
- for every period: a sample answer and the accepted short answers of its open questions, the key ideas of
  its retell (each phrasing in the words of the rule), and a question for an explanation without one. Their
  numbers and terms must come from the period's own text;
- FIX-3: for every period, the "vì sao" asked after a right answer (``Node.verify_prompt``): one question,
  no number (it serves every item of the period), terms of the period, the child called "con". Asked in a
  request of its own, so the cached drafts above stay as they were.

Test items are never sent (CLAUDE.md rule 2). Every draft is recorded with its model and what the checks
said (``Draft``), and the plan stays a DRAFT for the teacher (INGEST-4). Calls are cached on disk by their
request, so building again costs no quota; the requests stay under the 3 000 tokens of a Groq prompt.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move
from cavat.core.vi_text import fold
from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ModelClass
from cavat.modules.assessment.math_terms import terms_in, terms_missing
from cavat.modules.assessment.vi_numbers import extract_numbers
from cavat.modules.content.chapter_package import Node, TheoryVariant
from cavat.modules.content.lesson_package import HintTemplate, Item, LessonPackage
from cavat.modules.ingest.teaching import Plan
from cavat.modules.rag.bm25 import content_words
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
from cavat.modules.tutor.validator import foreign_text, validate_message, wrong_address

DRAFTER_VERSION = "drafting/0.1.0"
PROMPTS = Path(__file__).parent / "prompts"
HINT_PROMPT, NODE_PROMPT = "draft-hints.v1.md", "draft-node.v1.md"
VERIFY_PROMPT = "draft-verify.v1.md"  # FIX-3
MAX_VERIFY_WORDS = 25
VERIFY_LEAD = "Đúng rồi!"  # the tutor's praise before the "vì sao", as in the hand-written lessons
BATCH = 6  # items per request: the prompt stays well under the 3 000 tokens of a Groq request
LADDER = ((HintLevel.H1, HintTarget.TASK, "h1"), (HintLevel.H2, HintTarget.CONCEPT, "h2"))
LADDER += ((HintLevel.H3, HintTarget.STRATEGY, "h3"),)
MAX_HINT_WORDS = 40
MIN_KEY_WORDS = 0.8  # DI-46: share of a key-idea phrasing's words found in the period's text
RETRY_NOTES = {
    "MISSING_QUESTION": "phải kết thúc bằng đúng một câu hỏi (dấu ?)",
    "MULTIPLE_QUESTIONS": "chỉ được một câu hỏi",
    "NEW_MATH_TERM": "dùng thuật ngữ Toán không có trong đề hoặc quy tắc của bài",
    "UNGROUNDED_NUMBER": "dùng số không có trong đề của câu",
    "ANSWER_LEAK": "đã nói ra đáp án",
    "TOO_LONG": "quá dài, tối đa 35 từ",
    "REPEATS": "trùng một gợi ý khác",
}
# A formula's signs say the operations: "a × h : 2" is a multiplication and a division.
_SIGN_WORDS = {
    "×": "nhân",
    ":": "chia",
    "+": "cộng",
    "−": "trừ",
    "-": "trừ",
    "<": "bé hơn nhỏ hơn",
    ">": "lớn hơn",
}

HINT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in ("id", "h1", "h2", "h3")},
                "required": ["id", "h1", "h2", "h3"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "hoi": {"type": "string"}},
                "required": ["id", "hoi"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}
_PHRASES = {"type": "array", "items": {"type": "string"}}
NODE_SCHEMA = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"ask": {"type": "string"}, "reply": {"type": "string"}, "accept": _PHRASES},
                "required": ["ask", "reply", "accept"],
                "additionalProperties": False,
            },
        },
        "key_ideas": {"type": "array", "items": _PHRASES},
        "missing_asks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "ask": {"type": "string"}},
                "required": ["id", "ask"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answers", "key_ideas", "missing_asks"],
    "additionalProperties": False,
}


@dataclass
class Draft:
    """One piece Qwen wrote, and what the checks said (kept in the plan for the teacher)."""

    kind: str  # HINT | REPLY | ACCEPT | KEY_IDEA | ASK | VERIFY
    target: str  # "STP-BT-07a:H2", "STP-T01/T1", "STP-T01"
    text: str
    ok: bool
    codes: list[str] = field(default_factory=list)
    model: str = ""


def prompt_text(name: str) -> str:
    """A prompt file without its comment block (the comment is for the people who edit it)."""
    return re.sub(r"<!--.*?-->\s*", "", (PROMPTS / name).read_text(encoding="utf-8"), flags=re.DOTALL).strip()


class Drafter:
    def __init__(
        self,
        router: Any,
        cache: Path,
        *,
        pause: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        only: frozenset[str] | None = None,
    ):
        """``only``: the kinds of drafts that may call the model ("HINT", "NODE", "VERIFY"); the others
        come from the cache only (FIX-3: draft the periods' "vì sao" without drafting the hints again)."""
        self.router, self.cache, self.pause, self.sleep = router, cache, pause, sleep
        self.only = only
        self.calls = 0  # requests that reached the model (not the cache)

    def _ask(
        self, prompt: str, payload: dict[str, Any], schema: dict[str, Any], tokens: int, kind: str = "HINT"
    ) -> tuple[dict, str]:
        body = json.dumps(payload, ensure_ascii=False)
        key = hashlib.sha256(f"{DRAFTER_VERSION}\n{prompt}\n{body}".encode()).hexdigest()
        kept = self.cache / f"{key}.json"
        if kept.exists():
            saved = json.loads(kept.read_text(encoding="utf-8"))
            return saved["data"], saved["model"]
        if self.router is None or (self.only is not None and kind not in self.only):
            return {}, ""  # cache only: a teacher's decision never waits for a model
        if self.calls and self.pause:
            self.sleep(self.pause)  # 8 000 tokens a minute on the free tier
        request = ChatRequest(
            messages=(ChatMessage("system", prompt), ChatMessage("user", body)),
            json_schema=schema,
            schema_name="draft",
            max_output_tokens=tokens,
            temperature=0.2,
        )
        outcome = self.router.chat(ModelClass.TUTOR_REASONING, request, calls_used=0)
        self.calls += outcome.calls_made
        if outcome.result is None or outcome.result.data is None:
            return {}, ""
        self.cache.mkdir(parents=True, exist_ok=True)
        kept.write_text(
            json.dumps({"data": outcome.result.data, "model": outcome.result.model}, ensure_ascii=False)
        )
        return outcome.result.data, outcome.result.model

    def draft(self, plan: Plan) -> list[Draft]:
        drafts: list[Draft] = []
        nodes = list(plan.package.nodes)
        for i, node in enumerate(nodes):
            nodes[i], node_drafts = self._node(node)
            drafts += node_drafts
        nodes, verify_drafts = self._verify(nodes)
        drafts += verify_drafts
        plan.package = plan.package.model_copy(update={"nodes": nodes})
        for lesson_id, lesson in list(plan.lessons.items()):
            if lesson_id.endswith("-KT"):
                continue  # the chapter test: never sent to a model
            items, hint_drafts = self._hints(lesson, {n.id: n for n in nodes})
            plan.lessons[lesson_id] = lesson.model_copy(update={"items": items})
            drafts += hint_drafts
        return drafts

    # -- hints ---------------------------------------------------------------------------------------------

    def _hints(self, lesson: LessonPackage, nodes: dict[str, Node]) -> tuple[list[Item], list[Draft]]:
        items = list(lesson.items)
        drafts: list[Draft] = []
        by_node: dict[str, list[int]] = {}
        for i, item in enumerate(items):
            if not item.hints and item.purpose != "EXIT":
                by_node.setdefault(item.kc_ids[0], []).append(i)
        prompt = prompt_text(HINT_PROMPT)
        for node_id, indexes in by_node.items():
            node = nodes[node_id]
            for start in range(0, len(indexes), BATCH):
                batch = indexes[start : start + BATCH]
                payload = {
                    "QUY TẮC": _rule_text(node),
                    "CÂU": [
                        {"id": items[i].id, "đề": items[i].stem, "đáp án": _answer_text(items[i])}
                        for i in batch
                    ],
                }
                data, model = self._ask(prompt, payload, HINT_SCHEMA, 260 * len(batch))
                written = {row.get("id"): row for row in data.get("items", []) if isinstance(row, dict)}
                refused: dict[int, dict[str, list[str]]] = {}
                for i in batch:
                    hints, item_drafts = _checked_hints(
                        items[i], written.get(items[i].id, {}), lesson, node, model
                    )
                    items[i] = items[i].model_copy(update={"hints": hints})
                    drafts += item_drafts
                    wrong = {d.target.rsplit(":", 1)[1].lower(): d.codes for d in item_drafts if not d.ok}
                    if wrong:
                        refused[i] = wrong
                if refused:
                    drafts += self._retry(prompt, payload, written, refused, items, lesson, node)
        return items, drafts

    def _retry(
        self,
        prompt: str,
        payload: dict[str, Any],
        written: dict[Any, dict],
        refused: dict[int, dict[str, list[str]]],
        items: list[Item],
        lesson: LessonPackage,
        node: Node,
    ) -> list[Draft]:
        """One more request for the refused hints, each with why it was refused (like the tutor's renderer
        retries a refused message). What passes fills the gap at its level; nothing is written by us."""
        notes = []
        for i, wrong in refused.items():
            row = written.get(items[i].id, {})
            for key, codes in wrong.items():
                why = "; ".join(RETRY_NOTES.get(c, c) for c in codes)
                notes.append(
                    {"id": items[i].id, "bậc": key.upper(), "câu bị loại": row.get(key, ""), "lý do": why}
                )
        again = {
            **payload,
            "CÂU": [r for r in payload["CÂU"] if any(r["id"] == items[i].id for i in refused)],
        }
        again["SỬA LẠI"] = notes
        again["YÊU CẦU"] = (
            "Chỉ viết lại các gợi ý trong [SỬA LẠI] (đúng mã câu và bậc), sửa đúng lý do bị loại; "
            "các bậc khác để chuỗi rỗng."
        )
        data, model = self._ask(prompt, again, HINT_SCHEMA, 260 * len(refused))
        rewritten = {row.get("id"): row for row in data.get("items", []) if isinstance(row, dict)}
        drafts: list[Draft] = []
        for i, wrong in refused.items():
            row = rewritten.get(items[i].id, {})
            kept = {int(h.level): h for h in items[i].hints}
            for level, target, key in LADDER:
                if key not in wrong:
                    continue
                text = " ".join(str(row.get(key, "")).split())
                codes = _hint_codes(text, items[i], lesson, node, level, target)
                if text and fold(text) in {fold(h.text) for h in kept.values()}:
                    codes.append("REPEATS")
                drafts.append(
                    Draft("HINT", f"{items[i].id}:H{int(level)}:retry", text, not codes, codes, model)
                )
                if not codes:
                    kept[int(level)] = HintTemplate(target=target, level=level, text=text)
            items[i] = items[i].model_copy(update={"hints": [kept[k] for k in sorted(kept)]})
        return drafts

    # -- the period's "vì sao" (FIX-3) ---------------------------------------------------------------------

    def _verify(self, nodes: list[Node]) -> tuple[list[Node], list[Draft]]:
        nodes = list(nodes)
        wanted = [i for i, n in enumerate(nodes) if not n.verify_prompt]
        drafts: list[Draft] = []
        prompt = prompt_text(VERIFY_PROMPT)
        for start in range(0, len(wanted), BATCH):
            batch = wanted[start : start + BATCH]
            payload = {
                "TIẾT": [
                    {"id": nodes[i].id, "tên": nodes[i].name, "quy tắc": _rule_text(nodes[i])[:400]}
                    for i in batch
                ]
            }
            data, model = self._ask(prompt, payload, VERIFY_SCHEMA, 90 * len(batch), "VERIFY")
            written = {r.get("id"): r for r in data.get("items", []) if isinstance(r, dict)}
            for i in batch:
                text = " ".join(str(written.get(nodes[i].id, {}).get("hoi", "")).split())
                codes = verify_codes(text, nodes[i])
                drafts.append(Draft("VERIFY", nodes[i].id, text, not codes, codes, model))
                if not codes:
                    nodes[i] = nodes[i].model_copy(update={"verify_prompt": f"{VERIFY_LEAD} {text}"})
        return nodes, drafts

    # -- the period's own text ---------------------------------------------------------------------------

    def _node(self, node: Node) -> tuple[Node, list[Draft]]:
        asks = [t.ask for t in node.theory if t.ask and not t.reply]
        missing = [t.id for t in node.theory if not t.ask.rstrip().endswith("?")]
        need_ideas = not node.explain.key_ideas
        if not (asks or missing or need_ideas):
            return node, []
        payload = {
            "BÀI": _node_text(node),
            "CÂU HỎI": asks,
            "THIẾU CÂU HỎI": [{"id": t.id, "cách giảng": t.text} for t in node.theory if t.id in missing],
        }
        data, model = self._ask(prompt_text(NODE_PROMPT), payload, NODE_SCHEMA, 700, "NODE")
        source = _node_text(node)
        drafts: list[Draft] = []
        theory = list(node.theory)
        replies = {row.get("ask", ""): row for row in data.get("answers", []) if isinstance(row, dict)}
        for i, variant in enumerate(theory):
            update: dict[str, Any] = {}
            if variant.id in missing:
                ask = next(
                    (r.get("ask", "") for r in data.get("missing_asks", []) if r.get("id") == variant.id), ""
                )
                codes = _grounded(ask, source) + ([] if ask.rstrip().endswith("?") else ["NOT_A_QUESTION"])
                drafts.append(
                    Draft("ASK", f"{node.id}/{variant.id}", ask, not codes and bool(ask), codes, model)
                )
                if ask and not codes:
                    update["ask"] = ask
            row = (
                replies.get(update.get("ask", variant.ask))
                if variant.ask in asks or update.get("ask")
                else None
            )
            if row:
                reply = str(row.get("reply", ""))
                codes = _grounded(reply, source) + (["TOO_LONG"] if len(reply.split()) > 35 else [])
                drafts.append(
                    Draft("REPLY", f"{node.id}/{variant.id}", reply, not codes and bool(reply), codes, model)
                )
                if reply and not codes:
                    update["reply"] = reply
                accepted = []
                for phrase in row.get("accept", [])[:4]:
                    phrase = str(phrase).strip()
                    # A refused reply is no evidence for the phrasings that go with it.
                    evidence = f"{source} {reply}" if "reply" in update else source
                    codes = _grounded(phrase, evidence) + (["TOO_LONG"] if len(phrase.split()) > 6 else [])
                    drafts.append(Draft("ACCEPT", f"{node.id}/{variant.id}", phrase, not codes, codes, model))
                    if not codes:
                        accepted.append(phrase)
                if accepted and "reply" in update:
                    update["accept"] = accepted
            if update:
                theory[i] = variant.model_copy(update=update)
        explain = node.explain
        if need_ideas:
            ideas = []
            for idea in data.get("key_ideas", [])[:3]:
                kept = []
                for phrase in (idea if isinstance(idea, list) else [idea])[:3]:
                    phrase = str(phrase).strip()
                    codes = _key_idea_codes(phrase, node)
                    drafts.append(Draft("KEY_IDEA", node.id, phrase, not codes, codes, model))
                    if not codes:
                        kept.append(phrase)
                if kept:
                    ideas.append(kept)
            if ideas:
                explain = explain.model_copy(update={"key_ideas": ideas})
        return node.model_copy(update={"theory": theory, "explain": explain}), drafts


def verify_codes(text: str, node: Node) -> list[str]:
    """Why a drafted "vì sao" cannot serve every item of its period (empty: it can)."""
    if not text:
        return ["EMPTY"]
    codes = []
    if text.count("?") != 1 or not text.rstrip().endswith("?"):
        codes.append("NOT_ONE_QUESTION")
    if extract_numbers(text):
        codes.append("HAS_NUMBER")  # one question for every item of the period: no item's numbers
    if len(text.split()) > MAX_VERIFY_WORDS:
        codes.append("TOO_LONG")
    if foreign_text(text):
        codes.append("FOREIGN_TEXT")
    if wrong_address(text, "con"):
        codes.append("WRONG_ADDRESS")
    if fold(text).lower().startswith(("dung roi", "chinh xac", "gioi")):
        codes.append("STARTS_WITH_PRAISE")  # the tutor adds its own "Đúng rồi!"
    if terms_missing(terms_in(text), [_node_text(node, full=True)]):
        codes.append("NEW_MATH_TERM")
    return codes


def _rule_text(node: Node) -> str:
    steps = " ".join(node.method.steps) if node.method.steps != [node.method.rule] else ""
    return " ".join(t for t in (node.method.rule, steps) if t)[:900]


def _node_text(node: Node, *, full: bool = False) -> str:
    """What the period says: its rule, its explanations, its worked examples (the drafts' evidence). The
    prompt gets the first 1 800 characters; a check reads all of it (``full``) and its formulas' signs."""
    parts = [node.name, node.description, node.method.rule, *node.method.steps]
    parts += [f"{t.text} {t.ask}" for t in node.theory]
    examples = node.worked_examples if full else node.worked_examples[:2]
    parts += [f"{w.problem}: {' '.join(w.steps)} {w.answer}" for w in examples]
    text = " ".join(p for p in parts if p)
    return f"{text} {_sign_words(text)}" if full else text[:1800]


def _answer_text(item: Item) -> str:
    ans = item.answer
    if ans.type == "choice":
        right = next((o for o in ans.options if o.correct), None)
        return f"{right.id}. {right.text}" if right else ""
    if ans.type == "compare":
        return f"so sánh {ans.left} và {ans.right}"
    if ans.type == "order":
        return " ; ".join(ans.numbers)
    if ans.type == "numeric":
        return ans.value
    if ans.type == "boolean":
        return "Đúng" if ans.value else "Sai"
    return ans.sample_answer


def _grounded(text: str, source: str) -> list[str]:
    """Numbers and mathematical terms of a draft must be in the period's text (or the item)."""
    codes = []
    have = {n.value for n in extract_numbers(source)}
    if any(n.value not in have for n in extract_numbers(text)):
        codes.append("UNGROUNDED_NUMBER")
    if terms_missing(terms_in(text), [source]):
        codes.append("NEW_MATH_TERM")
    return codes


def _key_idea_codes(phrase: str, node: Node) -> list[str]:
    """A key idea is said in the words of the period (DI-46): most of its words are in its text."""
    if not phrase or len(phrase.split()) > 8:
        return ["TOO_LONG" if phrase else "EMPTY"]
    words = [fold(w) for w in content_words(phrase)]
    have = {fold(w) for w in content_words(_node_text(node))}
    if words and sum(w in have for w in words) / len(words) < MIN_KEY_WORDS:
        return ["NOT_IN_THE_RULE"]
    return _grounded(phrase, _node_text(node))


def _checked_hints(
    item: Item, written: dict[str, Any], lesson: LessonPackage, node: Node, model: str
) -> tuple[list[HintTemplate], list[Draft]]:
    hints: list[HintTemplate] = []
    drafts: list[Draft] = []
    seen: set[str] = set()
    for level, target, key in LADDER:
        text = " ".join(str(written.get(key, "")).split())
        codes = _hint_codes(text, item, lesson, node, level, target)
        if fold(text) in seen:
            codes.append("REPEATS")
        seen.add(fold(text))
        drafts.append(Draft("HINT", f"{item.id}:H{int(level)}", text, not codes, codes, model))
        if not codes:
            hints.append(HintTemplate(target=target, level=level, text=text))
    return hints, drafts


def _hint_codes(
    text: str, item: Item, lesson: LessonPackage, node: Node, level: HintLevel, target: HintTarget
) -> list[str]:
    if not text:
        return ["EMPTY"]
    ctx = RenderContext(
        decision=PolicyDecision(move=Move.HINT, level=level, target=target),
        item=item,
        package=lesson,
        state=ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE),
        max_words=MAX_HINT_WORDS,
        evidence=(node.method.rule,),
    )
    try:
        codes = [str(issue.code) for issue in validate_message(text, ctx).issues]
    except ValueError:  # an answer the tutor's validator cannot read: the hint is not checked, so not kept
        codes = ["NOT_CHECKABLE"]
    if terms_missing(terms_in(text), [item.stem, _node_text(node, full=True), _sign_words(item.stem)]):
        codes.append("NEW_MATH_TERM")
    return codes


def _sign_words(text: str) -> str:
    """The operations a text writes with signs, as words; a fraction "7/10" has a numerator and a
    denominator."""
    words = [w for sign, w in _SIGN_WORDS.items() if sign in text]
    if re.search(r"\d+\s*/\s*\d+", text):
        words.append("phân số tử số mẫu số")
    return " ".join(words)


def summary(drafts: Sequence[Draft]) -> dict[str, dict[str, int]]:
    """Kept and refused drafts by kind, for the report."""
    out: dict[str, dict[str, int]] = {}
    for d in drafts:
        row = out.setdefault(d.kind, {"kept": 0, "refused": 0})
        row["kept" if d.ok else "refused"] += 1
    return out


def as_records(drafts: Sequence[Draft]) -> list[dict[str, Any]]:
    return [asdict(d) for d in drafts]


__all__ = ["DRAFTER_VERSION", "Draft", "Drafter", "TheoryVariant", "as_records", "summary"]
