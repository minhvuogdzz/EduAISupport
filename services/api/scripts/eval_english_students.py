"""ENG-9a: simulated students study Unit 11 "Family time" through the real session API, and we measure.

What it is. Each profile is a scripted child with a probability model and a fixed seed: the chance of a right
answer on a node starts at the profile's ability and grows a little with every hint or wrong answer the tutor
answered on that node; some profiles have a habit (forgetting "did", the base form after "We", "Yes, I do",
answering in Vietnamese, asking for the answer, asking a Mathematics question, mumbling into the microphone,
only repeating the teacher). The child plays against the session API in this process: the same routes the web
calls (``POST /v1/sessions``, ``/responses``, ``/hint-requests``, ``/v1/voice/transcribe``), the in-memory
database (nothing is written anywhere), templates only (no model) unless ``--live``. Spoken turns go through
a scripted speech-to-text with the profile's confidence ``q`` (ADR-064).

What is measured, per profile: whether the six-step cycle (ADR-059) was gone through and where the child
stopped; the checker's verdict on every graded answer against the label the script gave it (right/wrong,
and the error code where the script made a typed error); the mastery, level and pass of every node with the
English policy (``node-mastery-en/0.1.0``); answer leaks before the child answered; Mathematics words in the
tutor's messages; Mathematics passages retrieved; Mathematics questions brought back to the lesson; low-q
spoken turns that lowered a mastery. Then the teacher, student and parent report views (ADR-067) are read
for all the simulated children, and a Mathematics session is checked against its golden after the English
sessions ran in the same process, and interleaved with an English session.

What it is not: children. The answers are built from the unit's own data and a declared probability model;
the numbers say whether the system behaves as designed on these behaviours, not how real children learn.

Run (offline): ``cd services/api && .venv/bin/python scripts/eval_english_students.py``.
Live (Groq quota, a few turns of 2-3 profiles): ``--live --profiles gioi,quen_did --max-turns 14``, with the
keys of ``services/api/.env`` in the environment. Writes ``docs/thesis/data/english-simulated-students.json``
(``--out``); the live run writes ``english-simulated-students-live.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import statistics
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API_DIR = Path(__file__).resolve().parents[1]
REPO = API_DIR.parents[1]
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(API_DIR / "tests"))
os.environ.setdefault("AUTH_MODE", "demo")

from cavat.config import get_settings  # noqa: E402
from cavat.core.en_text import IRREGULAR_PAST, normalize_answer  # noqa: E402
from cavat.core.memory_db import InMemoryDatabase  # noqa: E402
from cavat.db import ensure_indexes  # noqa: E402
from cavat.main import app  # noqa: E402
from cavat.modules.ai_gateway.fake import FakeSpeechToText  # noqa: E402
from cavat.modules.ai_gateway.router import AIRouter, build_router  # noqa: E402
from cavat.modules.assessment.answer_check import check_answer  # noqa: E402
from cavat.modules.assessment.projector import ENGLISH_POLICY, project_chapter  # noqa: E402
from cavat.modules.session import api as session_api  # noqa: E402
from cavat.modules.session import chapter_service, progress  # noqa: E402
from cavat.modules.session.api import get_database  # noqa: E402
from cavat.modules.tutor.english_validator import math_terms_in  # noqa: E402
from cavat.modules.voice import api as voice_api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

UNIT_ID = "eng-g5-u11-family-time"
TEACHER = {"X-Demo-Teacher": "1"}
PARENT = {"X-Demo-Parent": "1"}
DEFAULT_OUT = REPO / "docs" / "thesis" / "data" / "english-simulated-students.json"
LIVE_OUT = REPO / "docs" / "thesis" / "data" / "english-simulated-students-live.json"
BASE_FORM = {past: base for past, base in IRREGULAR_PAST.items() if past not in {"did", "was", "were"}}
REGULAR_PAST = {"visited": "visit", "collected": "collect", "walked": "walk", "sunbathed": "sunbathe"}

DONT_KNOW = ["Con không biết ạ.", "con chịu ạ", "Con không nhớ cô ơi."]
DEMAND = ["Cô cho con đáp án luôn đi ạ.", "cô nói đáp án đi cô", "Con lười nghĩ lắm, cô nói luôn đi."]
MATH_QUESTIONS = [
    "Cô ơi 2 + 3 là mấy ạ?",
    "cô ơi 12,5 + 3,7 bằng bao nhiêu?",
    "Số thập phân 0,5 đọc là gì ạ?",
    "Diện tích hình tam giác tính thế nào ạ?",
]
VAGUE_WHY = ["Vì con thấy vậy ạ.", "tại vì đúng mà cô", "Con đoán thôi ạ."]
WRONG_THEORY = ["Con chưa hiểu lắm ạ.", "swim in the sea", "Con quên rồi ạ."]
UNSURE_OPEN = ["Con nghĩ vì nó đẹp hơn ạ.", "Vì bạn ấy thích đi chơi ạ."]
# Vietnamese replies for an English answer: what a child says when they know the meaning, not the words.
VIETNAMESE = [
    "Cả nhà con đã đi biển ạ.",
    "Con đã nhặt vỏ sò với anh trai ạ.",
    "Nhà con đi ăn hải sản ạ.",
    "Dạ có, con đã đi bơi với mẹ.",
]


# --------------------------------------------------------------------------- profiles


@dataclass(frozen=True)
class Profile:
    key: str
    label: str
    ability: float  # chance of a right answer on a node before any help
    gain: float = 0.06  # added per hint or answered wrong answer on the node
    p_dont_know: float = 0.0
    p_hint: float = 0.0
    p_vietnamese: float = 0.0  # an English answer said in Vietnamese
    p_demand: float = 0.0
    p_math: float = 0.0
    habit: str = ""  # grammar | yes_i_do | meaning | echo
    p_habit: float = 0.0  # chance the habit shapes an answer where it applies
    habit_decay: float = 0.92  # the habit fades with every correction on its node
    voice_turns: int = 0
    voice_q: tuple[float, float] = (0.88, 0.97)
    p_garble: float = 0.0  # the speech-to-text wrote something else than the child said
    adr_case: str = ""  # the row of ADR-060 §10 the profile stands for


PROFILES: tuple[Profile, ...] = (
    Profile("gioi", "Giỏi", ability=0.93, gain=0.03, voice_turns=3, adr_case="học tốt"),
    Profile(
        "trung_binh", "Trung bình", ability=0.68, gain=0.06, p_hint=0.05, p_dont_know=0.03, voice_turns=2
    ),
    Profile("yeu", "Yếu", ability=0.38, gain=0.05, p_hint=0.10, p_dont_know=0.12),
    Profile(
        "quen_did",
        "Quên did / nguyên mẫu sau We",
        ability=0.75,
        habit="grammar",
        p_habit=0.85,
        adr_case="dùng nguyên mẫu sau We; quên did",
    ),
    Profile(
        "tieng_viet", "Hay trả lời tiếng Việt", ability=0.72, p_vietnamese=0.45, adr_case="trả lời tiếng Việt"
    ),
    Profile("doi_dap_an", "Đòi đáp án", ability=0.55, p_demand=0.35, p_hint=0.10),
    Profile("hoi_toan", "Hỏi lạc sang Toán", ability=0.75, p_math=0.15),
    Profile(
        "noi_khong_ro",
        "Nói không rõ (q thấp)",
        ability=0.75,
        voice_turns=10,
        voice_q=(0.22, 0.55),
        p_garble=0.5,
        adr_case="nói không rõ (q thấp)",
    ),
    # The three other rows of ADR-060 §10 that the task's list does not name.
    Profile(
        "yes_i_do", "Trả lời 'Yes, I do'", ability=0.75, habit="yes_i_do", p_habit=0.9, adr_case="'Yes, I do'"
    ),
    Profile(
        "nham_nghia", "Nhầm nghĩa cụm từ", ability=0.7, habit="meaning", p_habit=0.7, adr_case="nhầm nghĩa"
    ),
    Profile(
        "noi_theo_co", "Chỉ nói theo cô", ability=0.0, habit="echo", p_habit=1.0, adr_case="chỉ nói theo cô"
    ),
    # A reference, not a child: every answer right at once (what the unit allows at best).
    Profile("moc_dung_het", "Mốc: đúng hết", ability=1.0, gain=0.0),
)


# --------------------------------------------------------------------------- the unit's answers


def unit():
    return chapter_service.chapters("english")[UNIT_ID]


def _plain(text: str) -> str:
    return normalize_answer(text)


def correct_answer(item: Any, rng: random.Random) -> str:
    """A right answer, in one of the forms a child types (case, punctuation, a polite word)."""
    a = item.answer
    if a.type == "phrase":
        text = a.accept[0]
        if rng.random() < 0.3:
            text = text.lower().rstrip(".?!")
        if rng.random() < 0.15:
            text = f"Dạ {text}"
        return text
    if a.type == "choice":
        right = next(o for o in a.options if o.correct)
        return right.id if rng.random() < 0.5 else right.text
    if a.type == "boolean":
        return item.explanation or ("Đúng ạ." if a.value else "Chưa đúng ạ.")
    if a.type == "open":
        return a.sample_answer
    return item.explanation or "Con không biết ạ."


def _swap_past_to_base(sentence: str) -> str | None:
    """'We ate seafood.' -> 'We eat seafood.' (the base form after We), or None when no past verb."""
    words = sentence.split()
    for i, w in enumerate(words):
        core = w.strip(".,?!").lower()
        base = BASE_FORM.get(core) or REGULAR_PAST.get(core)
        if base and i > 0:
            words[i] = w.lower().replace(core, base)
            return " ".join(words)
    return None


def habit_answer(profile: Profile, item: Any) -> tuple[str, str] | None:
    """The habit's wrong answer on this item and the code the checker should give, or None."""
    a = item.answer
    if profile.habit == "grammar" and a.type == "phrase":
        for wrong, code in (a.wrong_answers or {}).items():
            if code in {"ENG5-U11-M01", "ENG5-U11-M02", "ENG5-U11-M07", "ENG5-U11-M04"}:
                return wrong, code
        accept = a.accept[0]
        if accept.lower().startswith("did you "):
            return "You " + accept[8:], "EN_STRUCTURE"  # "did" forgotten
        if accept.lower().startswith("what did "):
            return accept.replace("did ", "", 1), "EN_STRUCTURE"
        if re.match(r"(?i)^(yes, i did|no, i didn't)", accept):
            return None
        swapped = _swap_past_to_base(accept)
        if swapped:
            return swapped, "EN_TENSE"
    if profile.habit == "yes_i_do":
        if a.type == "phrase" and re.match(r"(?i)^yes, i did", a.accept[0]):
            return re.sub(r"(?i)^yes, i did", "Yes, I do", a.accept[0]), "EN_SHORT_ANSWER"
        if a.type == "phrase" and re.match(r"(?i)^no, i didn't", a.accept[0]):
            return re.sub(r"(?i)^no, i didn't", "No, I don't", a.accept[0]), "EN_SHORT_ANSWER"
        if a.type == "choice":
            for o in a.options:
                if not o.correct and re.match(r"(?i)^(yes|no), i (do|don't|will|am)", o.text):
                    return o.text, (o.misconceptions[0] if o.misconceptions else "WRONG")
    if profile.habit == "meaning":
        if a.type == "choice":
            for o in a.options:
                if not o.correct and "ENG5-U11-M06" in o.misconceptions:
                    return o.text, "ENG5-U11-M06"
        if a.type == "phrase":
            for wrong, code in (a.wrong_answers or {}).items():
                if code == "ENG5-U11-M06":
                    return wrong, code
        if a.type == "boolean" and (a.wrong_answers or {}).get("true") == "ENG5-U11-M06":
            return "Bạn ấy nói đúng rồi ạ.", "ENG5-U11-M06"
    return None


def wrong_answer(item: Any, rng: random.Random) -> tuple[str, str]:
    """A plain wrong answer and its expected code ('WRONG' when the script names none)."""
    a = item.answer
    if a.type == "choice":
        o = rng.choice([o for o in a.options if not o.correct])
        return (o.id if rng.random() < 0.5 else o.text), (
            o.misconceptions[0] if o.misconceptions else "WRONG"
        )
    if a.type == "boolean":
        return ("Bạn ấy nói đúng rồi ạ." if not a.value else "Chưa đúng ạ."), "WRONG"
    if a.type == "open":
        return rng.choice(UNSURE_OPEN), "WRONG"
    if a.type == "phrase":
        wrongs = list((a.wrong_answers or {}).items())
        if wrongs and rng.random() < 0.5:
            return rng.choice(wrongs)
        swapped = _swap_past_to_base(a.accept[0])
        if swapped and rng.random() < 0.5:
            return swapped, "EN_TENSE"
        words = a.accept[0].rstrip(".?!").split()
        return " ".join(words[: max(1, len(words) // 3)]), "WRONG"  # a sentence cut short
    return "Con không biết ạ.", "WRONG"


def garble(text: str, rng: random.Random) -> str:
    """What a weak speech-to-text writes for a mumbled sentence: a word dropped or misheard."""
    words = text.split()
    if len(words) <= 1:
        return "uh " + text
    i = rng.randrange(len(words))
    if rng.random() < 0.5:
        del words[i]
    else:
        words[i] = {"ate": "eight", "took": "look", "swam": "swan", "bought": "boat"}.get(
            words[i].lower().strip(".,?!"), "the"
        )
    return " ".join(words)


# --------------------------------------------------------------------------- the API


class Api:
    def __init__(self, client: TestClient, stt: FakeSpeechToText | None, who: dict[str, str]):
        self.client, self.stt, self.who, self.keys = client, stt, who, 0

    def _key(self) -> str:
        self.keys += 1
        return f"{self.who['X-Demo-Student']}-{self.keys}"

    def open(self, name: str) -> dict:
        created = self.client.post(
            "/v1/sessions", json={"lesson_id": UNIT_ID, "student_display_name": name}, headers=self.who
        )
        assert created.status_code == 201, created.text
        joined = self.client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=self.who)
        assert joined.status_code == 200, joined.text
        return joined.json()

    def state(self, sid: str) -> dict:
        return self.client.get(f"/v1/sessions/{sid}/state", headers=self.who).json()

    def send(
        self, state: dict, text: str, *, modality: str = "TEXT", voice_turn_id: str | None = None
    ) -> dict:
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": text},
            "modality": modality,
            "expected_state_version": state["state_version"],
            **({"voice_turn_id": voice_turn_id} if voice_turn_id else {}),
        }
        sent = self.client.post(
            f"/v1/sessions/{state['session_id']}/responses",
            json=body,
            headers={**self.who, "Idempotency-Key": self._key()},
        )
        assert sent.status_code == 200, sent.text
        return self.state(state["session_id"])

    def hint(self, state: dict) -> dict:
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "expected_state_version": state["state_version"],
        }
        sent = self.client.post(
            f"/v1/sessions/{state['session_id']}/hint-requests",
            json=body,
            headers={**self.who, "Idempotency-Key": self._key()},
        )
        assert sent.status_code == 200, sent.text
        return self.state(state["session_id"])

    def speak(self, state: dict, heard: str, q: float) -> tuple[dict, str]:
        assert self.stt is not None
        self.stt.script.append((heard, q))
        files = {"audio": ("rec.webm", b"\x1aE\xdf\xa3 opus", "audio/webm")}
        got = self.client.post(
            "/v1/voice/transcribe",
            files=files,
            data={"session_id": state["session_id"], "language": state["voice"]["language"]},
            headers=self.who,
        )
        assert got.status_code == 200, got.text
        body = got.json()
        return self.send(
            state, body["text"], modality="VOICE", voice_turn_id=body.get("voice_turn_id")
        ), body["text"]


# --------------------------------------------------------------------------- one child


@dataclass
class Turn:
    kind: str  # ANSWER | EXPLANATION | THEORY | RETELL | HINT | DEMAND | MATH | VIETNAMESE | DONT_KNOW | ECHO
    item_id: str | None
    text: str
    label: str = ""  # CORRECT | WRONG for a graded answer
    expected: str = ""  # the code the script made the error with
    modality: str = "TEXT"
    q: float | None = None
    heard: str | None = None
    intended_correct: bool | None = None
    outcome: str | None = None
    error_class: str | None = None
    misconception_id: str | None = None
    en_code: str | None = None
    off_topic_back: bool | None = None
    events: list[str] = field(default_factory=list)


class Child:
    def __init__(self, profile: Profile, seed: int):
        self.p, self.rng = profile, random.Random(seed)
        self.exposure: Counter[str] = Counter()
        self.habit_left: dict[str, float] = {}
        self.voice_left = profile.voice_turns

    def p_right(self, node: str) -> float:
        return min(0.98, self.p.ability + self.p.gain * self.exposure[node])

    def habit_chance(self, node: str) -> float:
        return self.habit_left.setdefault(node, self.p.p_habit)

    def corrected(self, node: str) -> None:
        self.exposure[node] += 1
        if self.p.habit and self.p.habit != "echo":
            self.habit_left[node] = self.habit_chance(node) * self.p.habit_decay


def last_tutor_sentence(state: dict) -> str:
    tutor = [t["text"] for t in state.get("transcript", []) if t["actor"] == "tutor" and t.get("text")]
    if not tutor:
        return "Dạ."
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", tutor[-1]) if s.strip()]
    return parts[-1] if parts else tutor[-1]


def decide(child: Child, state: dict, ch: Any) -> Turn:
    p, rng, teaching = child.p, child.rng, state["teaching"]
    node = teaching["current_node_id"]
    if p.habit == "echo":
        return Turn("ECHO", (state.get("item") or {}).get("item_id"), last_tutor_sentence(state))
    if teaching["awaiting"] == "THEORY_REPLY":
        if rng.random() < child.p_right(node):
            n = ch.node(node)
            variant = next((t for t in n.theory if t.ask == teaching["prompt"]), None)
            accepts = (
                variant.accept if variant and variant.accept else [a for t in n.theory for a in t.accept]
            )
            return Turn("THEORY", None, accepts[0] if accepts else "Con hiểu rồi ạ.")
        return Turn("THEORY", None, rng.choice(WRONG_THEORY))
    if teaching["awaiting"] == "RETELL":
        if rng.random() < child.p_right(node):
            return Turn("RETELL", None, ". ".join(k[0] for k in ch.node(node).explain.key_ideas))
        return Turn("RETELL", None, rng.choice(DONT_KNOW))
    item = ch.item(state["item"]["item_id"])
    if state["item"]["expecting"] == "EXPLANATION":
        good = rng.random() < child.p_right(node)
        return Turn("EXPLANATION", item.id, item.explanation if good else rng.choice(VAGUE_WHY))
    # an answer is expected
    if rng.random() < p.p_math:
        return Turn("MATH", item.id, rng.choice(MATH_QUESTIONS))
    if rng.random() < p.p_demand:
        return Turn("DEMAND", item.id, rng.choice(DEMAND))
    if "HINT_REQUEST" in state["allowed_commands"] and rng.random() < p.p_hint:
        return Turn("HINT", item.id, "")
    if rng.random() < p.p_dont_know:
        return Turn("DONT_KNOW", item.id, rng.choice(DONT_KNOW))
    english = state["voice"]["language"] == "en" or getattr(item, "response_language", "") == "en"
    if english and item.answer.type == "phrase" and rng.random() < p.p_vietnamese:
        return Turn("VIETNAMESE", item.id, rng.choice(VIETNAMESE), label="WRONG", expected="EN_L1")
    habit = habit_answer(p, item)
    if habit and rng.random() < child.habit_chance(node):
        return Turn("ANSWER", item.id, habit[0], label="WRONG", expected=habit[1])
    if rng.random() < child.p_right(node):
        return Turn("ANSWER", item.id, correct_answer(item, rng), label="CORRECT", intended_correct=True)
    text, code = wrong_answer(item, rng)
    return Turn("ANSWER", item.id, text, label="WRONG", expected=code, intended_correct=False)


async def stored(db: InMemoryDatabase, sid: str):
    return await session_api._repo(db).get(sid)


def run_child(
    client: TestClient,
    db: InMemoryDatabase,
    stt: FakeSpeechToText | None,
    profile: Profile,
    seed: int,
    max_turns: int,
) -> dict:
    ch = unit()
    sid_name = f"sim-{profile.key.replace('_', '-')}"
    api = Api(client, stt, {"X-Demo-Student": sid_name})
    child = Child(profile, seed)
    state = api.open(f"HS giả {profile.label}")
    sid = state["session_id"]
    steps = [state["teaching"]["step"]]
    turns: list[Turn] = []
    loop = asyncio.new_event_loop()
    n_events = len(loop.run_until_complete(stored(db, sid)).events)
    for _ in range(max_turns):
        if state["lifecycle_state"] == "COMPLETED":
            break
        turn = decide(child, state, ch)
        before = (state["teaching"]["awaiting"], state["teaching"]["input_id"], state["teaching"]["prompt"])
        item_open = state["item"] is not None and state["item"]["expecting"] == "ANSWER"
        if turn.kind == "HINT":
            state = api.hint(state)
        elif (
            stt is not None
            and child.voice_left > 0
            and turn.kind == "ANSWER"
            and item_open
            and child.rng.random() < 0.6
        ):
            child.voice_left -= 1
            turn.modality = "VOICE"
            turn.q = round(child.rng.uniform(*profile.voice_q), 2)
            heard = turn.text
            if child.rng.random() < profile.p_garble:
                heard = garble(turn.text, child.rng)
                if heard != turn.text:
                    turn.label, turn.expected = "WRONG", "GARBLED"  # graded on what was heard
            state, turn.heard = api.speak(state, heard, turn.q)
        else:
            state = api.send(state, turn.text)
        events = loop.run_until_complete(stored(db, sid)).events
        new = events[n_events:]
        n_events = len(events)
        turn.events = [e.event_type for e in new]
        sent_text = turn.heard if turn.heard is not None else turn.text
        for e in new:
            if e.event_type == "ANSWER_SUBMITTED" and e.payload["raw_text"] == sent_text:
                turn.outcome = e.payload["outcome"]
                turn.error_class = e.payload["error_class"]
                turn.misconception_id = e.payload["misconception_id"]
                if turn.item_id:
                    item = ch.item(turn.item_id)
                    again = check_answer(item, sent_text, ch.lesson_of(turn.item_id))
                    # ENG-5c (DI-149): a second answer in Vietnamese is recorded WRONG with the class L1
                    l1_graded = again.outcome.value == "UNPARSEABLE" and turn.error_class == "L1"
                    assert l1_graded or again.outcome.value == turn.outcome
                    turn.en_code = (again.detail or {}).get("en_code")
        if turn.kind == "MATH":
            off = [
                e
                for e in new
                if e.event_type == "STUDENT_MESSAGE" and e.payload["item_id"].endswith(":OFF_TOPIC")
            ]
            back = [
                e
                for e in new
                if e.event_type == "TEACH_MESSAGE_SENT" and e.payload.get("ref") == "OFF_SUBJECT"
            ]
            after = (
                state["teaching"]["awaiting"],
                state["teaching"]["input_id"],
                state["teaching"]["prompt"],
            )
            graded = any(e.event_type in {"ANSWER_SUBMITTED", "HINT_DELIVERED", "RAG_RETRIEVED"} for e in new)
            turn.off_topic_back = bool(off and back and not graded and after[:2] == before[:2])
        node = before and state["teaching"]["current_node_id"]
        if turn.kind in {"HINT", "DEMAND", "DONT_KNOW"} or turn.outcome in {"WRONG", "PARTIAL"}:
            child.corrected(node or "")
        turns.append(turn)
        if state["teaching"]["step"] is not None:
            steps.append(state["teaching"]["step"])
    loop.close()
    doc = asyncio.run(stored(db, sid))
    return {
        "profile": profile,
        "sid": sid,
        "student": sid_name,
        "state": state,
        "turns": turns,
        "steps": steps,
        "doc": doc,
    }


# --------------------------------------------------------------------------- measures


def kappa(tp: int, fn: int, fp: int, tn: int) -> float | None:
    n = tp + fn + fp + tn
    if not n:
        return None
    po = (tp + tn) / n
    pe = ((tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def code_matches(expected: str, t: Turn) -> bool | None:
    if expected in {"", "WRONG", "GARBLED"}:
        return None
    if expected.startswith("ENG5-U11-M"):
        return t.misconception_id == expected
    if expected == "EN_L1":
        return t.en_code == "EN_L1" or t.error_class == "L1"
    return t.en_code == expected


def _level(value: Any) -> int:
    if value is None:
        return 0
    return int(str(value).lstrip("H") or 0)


def leaks(events: list, ch: Any) -> list[dict]:
    """A phrase answer of an item said by the tutor while the item was open, before a right answer and before
    the full solution (H7, after which the answer is given on purpose), on an item that is not done together
    with the teacher (DI-108) and whose stem does not already show it (reading items quote the text)."""
    completion = {i for n in ch.package.nodes for i in n.completion}
    open_items: dict[str, dict] = {}
    found = []
    for e in events:
        p = e.payload
        iid = p.get("item_id") if isinstance(p, dict) else None
        if e.event_type == "QUESTION_SHOWN" and iid:
            open_items[iid] = {"level": 0}
        elif e.event_type == "POLICY_DECISION" and iid in open_items:
            open_items[iid]["level"] = max(open_items[iid]["level"], _level(p.get("hint_level")))
        elif e.event_type == "ANSWER_SUBMITTED" and iid in open_items and p["outcome"] == "CORRECT":
            open_items.pop(iid, None)
        elif e.event_type == "ITEM_RESOLVED":
            open_items.pop(iid, None)
        elif e.event_type == "TUTOR_MESSAGE_SENT" and iid in open_items:
            item = ch.item(iid)
            if item.answer.type != "phrase" or iid in completion or open_items[iid]["level"] >= 7:
                continue
            said, stem = _plain(p["text"]), _plain(str(item.stem))
            for accept in item.answer.accept:
                a = _plain(accept)
                if len(a.split()) >= 3 and f" {a} " in f" {said} " and f" {a} " not in f" {stem} ":
                    found.append(
                        {
                            "item_id": iid,
                            "move": p.get("move"),
                            "level": open_items[iid]["level"],
                            "text": p["text"],
                        }
                    )
    return found


def low_q_drops(events: list, ch: Any) -> tuple[int, int]:
    """(spoken answers heard with q < 0,6 that were not right, of them those after which a node's mastery went
    down). The spoken turn is the STUDENT_MESSAGE with modality VOICE and its VOICE_TURN_RECORDED (the
    ANSWER_SUBMITTED of a spoken answer says TEXT, see the report)."""
    checked = dropped = 0
    voice_q: float | None = None
    spoken = False
    for i, e in enumerate(events):
        if e.event_type == "STUDENT_MESSAGE":
            spoken, voice_q = e.payload.get("modality") == "VOICE", None
        elif e.event_type == "VOICE_TURN_RECORDED":
            voice_q = e.payload.get("asr_confidence")
        elif e.event_type == "ANSWER_SUBMITTED" and spoken and e.payload["outcome"] != "CORRECT":
            if voice_q is None or voice_q >= 0.6:
                continue
            checked += 1
            end = next(
                (j for j in range(i + 1, len(events)) if events[j].event_type == "STUDENT_MESSAGE"),
                len(events),
            )
            a, b = project_chapter(events[:i], ch), project_chapter(events[:end], ch)
            if any((b.nodes[k].mastery or 0) < (a.nodes[k].mastery or 0) - 1e-9 for k in a.nodes):
                dropped += 1
    return checked, dropped


def active_at_pass(events: list, ch: Any, node_id: str, passed_at: int | None) -> list[str] | None:
    """The misconceptions of the node still ACTIVE when it passed (None when it never passed)."""
    if passed_at is None:
        return None
    state = project_chapter(events[: passed_at + 1], ch).nodes[node_id]
    return [m.id for m in state.misconceptions if m.status == "ACTIVE"]


def measure(run: dict, ch: Any) -> dict:
    profile: Profile = run["profile"]
    events, turns, state = run["doc"].events, run["turns"], run["state"]
    projection = project_chapter(events, ch)
    assert projection.policy_version == ENGLISH_POLICY.version
    graded = [
        t
        for t in turns
        if t.label in {"CORRECT", "WRONG"}
        and t.outcome is not None
        and t.kind == "ANSWER"
        and t.expected != "GARBLED"
    ]
    garbled = [
        {"item": t.item_id, "said": t.text, "heard": t.heard, "q": t.q, "outcome": t.outcome}
        for t in turns
        if t.expected == "GARBLED"
    ]
    firsts = [
        e.payload for e in events if e.event_type == "ANSWER_SUBMITTED" and e.payload["attempt_no"] == 1
    ]
    resolved = [e.payload for e in events if e.event_type == "ITEM_RESOLVED"]
    stopped = sorted(
        {
            e.payload["node_id"]
            for e in events
            if e.event_type == "NODE_DECISION" and "NO_ITEMS_LEFT" in (e.payload.get("reason_codes") or [])
        }
    )
    spoken_answers = sum(
        1
        for i, e in enumerate(events)
        if e.event_type == "ANSWER_SUBMITTED"
        and any(x.event_type == "VOICE_TURN_RECORDED" for x in events[max(0, i - 2) : i])
    )
    spoken_said_text = sum(
        1
        for i, e in enumerate(events)
        if e.event_type == "ANSWER_SUBMITTED"
        and e.payload["modality"] == "TEXT"
        and any(x.event_type == "VOICE_TURN_RECORDED" for x in events[max(0, i - 2) : i])
    )
    tp = sum(1 for t in graded if t.label == "CORRECT" and t.outcome == "CORRECT")
    fn = sum(1 for t in graded if t.label == "CORRECT" and t.outcome != "CORRECT")
    fp = sum(1 for t in graded if t.label == "WRONG" and t.outcome == "CORRECT")
    tn = sum(1 for t in graded if t.label == "WRONG" and t.outcome != "CORRECT")
    coded = [(t, code_matches(t.expected, t)) for t in turns if t.label == "WRONG" and t.outcome is not None]
    coded = [(t, ok) for t, ok in coded if ok is not None]
    vietnamese = [t for t in turns if t.kind == "VIETNAMESE"]
    tutor_texts = [
        e.payload.get("text", "")
        for e in events
        if e.event_type in {"TUTOR_MESSAGE_SENT", "TEACH_MESSAGE_SENT"}
    ]
    math_nodes = {n.id for c in chapter_service.chapters().values() for n in c.package.nodes}
    chunks = [c["chunk_id"] for e in events if e.event_type == "RAG_RETRIEVED" for c in e.payload["chunks"]]
    foreign = [c for c in chunks if c.split(":")[0] in math_nodes or not c.startswith("ENG5-")]
    maths = [t for t in turns if t.kind == "MATH"]
    nodes = {}
    for node in ch.package.nodes:
        s = projection.nodes[node.id]
        nodes[node.id] = {
            "mastery": None if s.mastery is None else round(s.mastery, 1),
            "level": s.level,
            "passed": s.passed_at is not None,
            "understood": s.understood,
            "items": s.items,
            "successes": s.successes,
            "misconceptions": [m.model_dump(mode="json") for m in s.misconceptions],
            "active_at_pass": active_at_pass(events, ch, node.id, s.passed_at),
            "missing": s.missing,
        }
    view_nodes = {n["node_id"]: n["status"] for n in state["teaching"]["nodes"]}
    low_checked, low_dropped = low_q_drops(events, ch)
    kinds = Counter(e.event_type for e in events)
    leak = leaks(events, ch)
    masteries = [v["mastery"] or 0.0 for v in nodes.values()]
    return {
        "profile": profile.key,
        "label": profile.label,
        "adr_case": profile.adr_case,
        "turns": len(turns),
        "completed": state["lifecycle_state"] == "COMPLETED",
        "steps_seen": sorted(set(s for s in run["steps"] if s is not None)),
        "end_node": state["teaching"]["current_node_id"],
        "end_step": state["teaching"]["step"],
        "passed_nodes": sum(1 for v in nodes.values() if v["passed"]),
        "view_status": view_nodes,
        "mean_mastery": round(statistics.mean(masteries), 1),
        "nodes": nodes,
        "grading": {
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "n": len(graded),
            "agreement": round((tp + tn) / len(graded), 3) if graded else None,
            "kappa": kappa(tp, fn, fp, tn),
        },
        "codes": {
            "n": len(coded),
            "matched": sum(1 for _, ok in coded if ok),
            "misses": [
                {
                    "item": t.item_id,
                    "text": t.heard or t.text,
                    "expected": t.expected,
                    "got": t.misconception_id or t.en_code or t.error_class,
                    "outcome": t.outcome,
                }
                for t, ok in coded
                if not ok
            ][:12],
        },
        "vietnamese": {
            "n": len(vietnamese),
            "outcomes": dict(Counter(str(t.outcome) for t in vietnamese)),
            "l1": sum(1 for t in vietnamese if t.error_class == "L1" or t.en_code == "EN_L1"),
        },
        "garbled": garbled,
        "first_attempt_correct": round(sum(1 for f in firsts if f["outcome"] == "CORRECT") / len(firsts), 3)
        if firsts
        else None,
        "independent_share": round(
            sum(1 for r in resolved if r["resolution"] == "INDEPENDENT") / len(resolved), 3
        )
        if resolved
        else None,
        "hints_per_item": round(sum(r["hints_count"] for r in resolved) / len(resolved), 2)
        if resolved
        else None,
        "nodes_out_of_items": stopped,
        "spoken_answers": spoken_answers,
        "spoken_answer_submitted_as_text": spoken_said_text,
        "turn_kinds": dict(Counter(t.kind for t in turns)),
        "hint_requests": kinds.get("HINT_REQUESTED", 0),
        "hints_delivered": kinds.get("HINT_DELIVERED", 0),
        "max_hint_levels": dict(
            Counter(e.payload.get("max_hint_level") for e in events if e.event_type == "ITEM_RESOLVED")
        ),
        "resolutions": dict(
            Counter(e.payload.get("resolution") for e in events if e.event_type == "ITEM_RESOLVED")
        ),
        "leaks": leak,
        "math_terms": [t for t in tutor_texts if math_terms_in(t)][:5],
        "math_terms_n": sum(1 for t in tutor_texts if math_terms_in(t)),
        "rag_chunks": len(chunks),
        "foreign_chunks": foreign,
        "math_questions": len(maths),
        "math_brought_back": sum(1 for t in maths if t.off_topic_back),
        "output_rejected": kinds.get("OUTPUT_REJECTED", 0),
        "voice": {
            "turns": kinds.get("VOICE_TURN_RECORDED", 0),
            "low_q": sum(1 for t in turns if t.q is not None and t.q < 0.6),
            "low_q_not_right_checked": low_checked,
            "low_q_mastery_dropped": low_dropped,
            "garbled": sum(1 for t in turns if t.expected == "GARBLED"),
        },
        "model_calls": kinds.get("MODEL_CALLED", 0),
        "model_fallbacks": kinds.get("MODEL_FALLBACK", 0),
        "model_answered": dict(
            Counter(str(e.payload.get("model")) for e in events if e.event_type == "MODEL_CALLED")
        ),
        "model_purposes": dict(
            Counter(e.payload.get("purpose") for e in events if e.event_type == "MODEL_CALLED")
        ),
        "fallback_reasons": dict(
            Counter(e.payload.get("reason") for e in events if e.event_type == "MODEL_FALLBACK")
        ),
        "rejected_codes": [e.payload.get("issue_codes") for e in events if e.event_type == "OUTPUT_REJECTED"],
    }


def transcript_excerpt(
    run: dict, kinds: set[str], before: int = 1, after: int = 2, limit: int = 2
) -> list[list[str]]:
    """A few lines around turns of the given kinds, from the stored conversation (no names: 'Con'/'Cô')."""
    lines: list[tuple[str, str]] = []
    for e in run["doc"].events:
        p = e.payload
        if e.event_type == "STUDENT_MESSAGE":
            lines.append(("Con", p.get("text", "")))
        elif e.event_type in {"TUTOR_MESSAGE_SENT", "TEACH_MESSAGE_SENT"}:
            lines.append(("Cô", p.get("text", "")))
    targets = {t.heard or t.text for t in run["turns"] if t.kind in kinds}
    out = []
    for i, (who, text) in enumerate(lines):
        if who == "Con" and text in targets and len(out) < limit:
            out.append([f"{w}: {x[:260]}" for w, x in lines[max(0, i - before) : i + after + 1]])
            targets.discard(text)
    return out


def adr_checks(rows: list[dict]) -> dict:
    """The rows of ADR-060 §10 "Học sinh mô phỏng" and the task's ordering, on the profiles that ran."""
    by = {r["profile"]: r for r in rows}
    out: dict[str, Any] = {}
    if "noi_theo_co" in by:
        out["echo_passes_no_node"] = by["noi_theo_co"]["passed_nodes"] == 0
    out["low_q_wrong_never_lowers_m"] = all(r["voice"]["low_q_mastery_dropped"] == 0 for r in rows)
    out["low_q_wrong_checked"] = sum(r["voice"]["low_q_not_right_checked"] for r in rows)
    if "yes_i_do" in by:
        out["yes_i_do_didyou_active_at_pass"] = by["yes_i_do"]["nodes"]["ENG5-U11-DIDYOU"]["active_at_pass"]
    if "quen_did" in by:
        n = by["quen_did"]["nodes"]
        out["base_form_whatdid_active_at_pass"] = n["ENG5-U11-WHATDID"]["active_at_pass"]
        out["forgot_did_didyou_active_at_pass"] = n["ENG5-U11-DIDYOU"]["active_at_pass"]
    if "gioi" in by:
        out["good_passes_whole_unit"] = by["gioi"]["passed_nodes"] == 6
    if {"gioi", "trung_binh", "yeu"} <= set(by):
        g, t, y = (by[k] for k in ("gioi", "trung_binh", "yeu"))
        out["order_mean_mastery"] = g["mean_mastery"] > t["mean_mastery"] > y["mean_mastery"]
        out["order_first_attempt"] = (
            g["first_attempt_correct"] > t["first_attempt_correct"] > y["first_attempt_correct"]
        )
        out["order_independent_share"] = (
            g["independent_share"] > t["independent_share"] > y["independent_share"]
        )
        out["order_turns"] = g["turns"] < t["turns"] < y["turns"]
    out["answer_leaks"] = sum(len(r["leaks"]) for r in rows)
    out["math_terms"] = sum(r["math_terms_n"] for r in rows)
    out["foreign_chunks"] = sum(len(r["foreign_chunks"]) for r in rows)
    out["math_questions_brought_back"] = (
        sum(r["math_brought_back"] for r in rows),
        sum(r["math_questions"] for r in rows),
    )
    out["output_rejected"] = sum(r["output_rejected"] for r in rows)
    return out


# --------------------------------------------------------------------------- reports and Mathematics


def check_reports(client: TestClient, runs: list[dict]) -> dict:
    def q(path: str) -> str:
        return f"{path}{'&' if '?' in path else '?'}chapter={UNIT_ID}"

    out: dict[str, Any] = {}
    klass = client.get(q("/v1/teachers/class"), headers=TEACHER)
    out["class_status"] = klass.status_code
    klass = klass.json()
    out["class_subject"] = klass.get("chapter", {}).get("subject")
    out["class_kpis"] = klass.get("kpis")
    out["class_students"] = len(klass.get("students", []))
    out["class_attention"] = {
        s["display_name"]: [a["kind"] for a in s.get("attention", [])] for s in klass.get("students", [])
    }
    out["class_misconceptions"] = [m["id"] for m in klass.get("misconceptions", [])]
    per = {}
    for run in runs:
        who = run["student"]
        view = client.get(q(f"/v1/teachers/students/{who}"), headers=TEACHER).json()
        days = view.get("activity", [])
        groups = {
            g: sum(d.get(g, 0) for d in days) for g in ("independent", "supported", "worked", "unresolved")
        }
        overview = client.get(q("/v1/students/me/overview"), headers={"X-Demo-Student": who}).json()
        parent = client.get(q(f"/v1/parents/children/{progress.parent_code(who)}"), headers=PARENT).json()
        parent_text = json.dumps(parent, ensure_ascii=False)
        resolved = Counter(
            e.payload["resolution"] for e in run["doc"].events if e.event_type == "ITEM_RESOLVED"
        )
        per[run["profile"].key] = {
            "groups": groups,
            "groups_match_events": groups
            == {
                "independent": resolved.get("INDEPENDENT", 0),
                "supported": resolved.get("SUPPORTED", 0),
                "worked": resolved.get("WORKED", 0),
                "unresolved": resolved.get("UNRESOLVED", 0),
            },
            "resolutions_in_events": dict(resolved),
            "attention": [a["kind"] for a in view.get("attention", [])],
            "voice_turns": len(view.get("voice_turns", [])),
            "asr_low_days": sum(d.get("asr_low", 0) for d in days),
            "misconceptions": sorted(
                {m["id"] for n in view.get("nodes", []) for m in n.get("misconceptions", [])}
            ),
            "student_quality": {n["node_id"]: n.get("quality") for n in overview.get("nodes", [])},
            "student_has_score": any("mastery" in n for n in overview.get("nodes", [])),
            "student_step": overview.get("current_step"),
            "parent_tips": len(parent.get("home_tips", [])),
            "parent_secret_fields": [
                s
                for s in ("voice_turns", "transcript", "audio_ref", "asr_confidence", '"mastery"')
                if s in parent_text
            ],
        }
    out["students"] = per
    return out


def math_golden_after_english() -> dict:
    """The Mathematics golden of ENG-5b in a fresh database, after the English sessions ran here."""
    import test_math_session_golden as golden

    database = InMemoryDatabase()
    asyncio.run(ensure_indexes(database))
    app.dependency_overrides[get_database] = lambda: database
    try:
        got = golden._record(TestClient(app), database)
    finally:
        app.dependency_overrides.pop(get_database, None)
    want = json.loads(golden.GOLDEN.read_text(encoding="utf-8"))
    differ = []
    for key in want:
        if key == "view_digests":
            if len(got["views"]) != len(want[key]):
                differ.append("view count")
                continue
            for i, (view, b) in enumerate(zip(got["views"], want[key], strict=True)):
                if golden._digest({k: view.get(k) for k in b["keys"]}) != b["sha"]:
                    differ.append(f"view {i}")
        elif key in ("last_view", "mine"):
            wanted = want[key] if key == "last_view" else want[key][0]
            have = got[key] if key == "last_view" else got[key][0]
            if {k: have.get(k) for k in wanted} != wanted:
                differ.append(key)
        elif got[key] != want[key]:
            differ.append(key)
    return {"identical": not differ, "differ": differ, "views": len(got["views"])}


def math_interleaved(profile: Profile, seed: int) -> dict:
    """A Mathematics session alone, and the same one interleaved turn by turn with an English child."""
    from test_chapter_session_api import reply_text
    from test_math_session_golden import normalize

    def math_events(interleave: bool) -> list:
        database = InMemoryDatabase()
        asyncio.run(ensure_indexes(database))
        app.dependency_overrides[get_database] = lambda: database
        try:
            client = TestClient(app)
            who = {"X-Demo-Student": "sim-math"}
            api = Api(client, None, who)
            state = client.post("/v1/sessions", json={}, headers=who).json()
            state = client.post(f"/v1/sessions/{state['session_id']}/join", headers=who).json()
            child, ch = Child(profile, seed), unit()
            english = Api(client, None, who).open("HS giả") if interleave else None
            for _ in range(60):
                if state["lifecycle_state"] == "COMPLETED":
                    break
                state = api.send(state, reply_text(state))
                if english is not None and english["lifecycle_state"] != "COMPLETED":
                    t = decide(child, english, ch)
                    english = api.hint(english) if t.kind == "HINT" else api.send(english, t.text)
            doc = asyncio.run(stored(database, state["session_id"]))
            return [
                {"type": e.event_type, "payload": e.payload, "activity": e.activity_id}
                for e in doc.events
                if e.event_type != "SESSION_STARTED"
            ]
        finally:
            app.dependency_overrides.pop(get_database, None)

    alone, mixed = math_events(False), math_events(True)
    return {"identical": normalize(alone, {}) == normalize(mixed, {}), "events": len(alone)}


# --------------------------------------------------------------------------- main


COLUMNS = (
    "Hồ sơ",
    "Lượt",
    "Xong",
    "Bước",
    "Dừng ở",
    "Qua nút",
    "M TB",
    "Đúng lần 1",
    "Tự làm",
    "Gợi ý/câu",
    "Khớp chấm",
    "κ",
    "Mã lỗi",
    "Lộ",
    "Toán (từ/chunk)",
    "Toán→bài",
)


def table(rows: list[dict]) -> str:
    out = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rows:
        g, c = r["grading"], r["codes"]
        end = (r["end_node"] or "-").replace("ENG5-U11-", "")
        cells = [
            r["label"],
            r["turns"],
            "có" if r["completed"] else "không",
            ",".join(map(str, r["steps_seen"])),
            f"{end}/{r['end_step']}",
            f"{r['passed_nodes']}/6",
            r["mean_mastery"],
            r["first_attempt_correct"],
            r["independent_share"],
            r["hints_per_item"],
            f"{g['agreement']} ({g['tp'] + g['tn']}/{g['n']})",
            g["kappa"],
            f"{c['matched']}/{c['n']}",
            len(r["leaks"]),
            f"{r['math_terms_n']}/{len(r['foreign_chunks'])}",
            f"{r['math_brought_back']}/{r['math_questions']}",
        ]
        out.append("| " + " | ".join(str(x) for x in cells) + " |")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, default=20261115)
    parser.add_argument("--max-turns", type=int, default=320)
    parser.add_argument("--profiles", default="", help="comma-separated keys (default: all)")
    parser.add_argument("--live", action="store_true", help="the real model chain (TUTOR_MODELS), Groq quota")
    parser.add_argument(
        "--relaxed",
        action="store_true",
        help="with --live: let approved template lines through (model_only_speech = False); a measuring "
        "mode, not the deployed one, where every line must come from a model",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--skip-math", action="store_true")
    args = parser.parse_args()

    chosen = [p for p in PROFILES if not args.profiles or p.key in args.profiles.split(",")]
    storage = Path(tempfile.mkdtemp(prefix="eng9a-voice-"))
    voice_api._storage = lambda: storage
    stt: FakeSpeechToText | None = None
    if args.live:
        os.environ["TUTOR_RENDERER"] = "llm"
        get_settings.cache_clear()
        chosen = [
            Profile(**{**p.__dict__, "voice_turns": 0}) for p in chosen
        ]  # the real router hears nothing
        live_router = build_router()
        if args.relaxed:
            live_router.model_only_speech = False
        session_api.tutor_router = lambda: live_router
    else:
        session_api.tutor_router = lambda: None
        stt = FakeSpeechToText(script=[])
        session_api._shared_router = lambda: AIRouter(stt_provider=stt)

    database = InMemoryDatabase()
    asyncio.run(ensure_indexes(database))
    app.dependency_overrides[get_database] = lambda: database
    client = TestClient(app)
    ch = unit()
    runs = []
    for i, profile in enumerate(chosen):
        run = run_child(client, database, stt, profile, args.seed + i, args.max_turns)
        runs.append(run)
        print(f"{profile.key}: {len(run['turns'])} lượt, {run['state']['lifecycle_state']}", flush=True)
    rows = [measure(r, ch) for r in runs]
    reports = check_reports(client, runs)
    result_checks = adr_checks(rows)
    app.dependency_overrides.pop(get_database, None)

    excerpts = {}
    for run in runs:
        key = run["profile"].key
        kinds = {
            "hoi_toan": {"MATH"},
            "doi_dap_an": {"DEMAND"},
            "tieng_viet": {"VIETNAMESE"},
            "quen_did": {"ANSWER"},
            "noi_theo_co": {"ECHO"},
            "yes_i_do": {"ANSWER"},
        }.get(key)
        if kinds:
            excerpts[key] = transcript_excerpt(run, kinds)

    result: dict[str, Any] = {
        "task": "ENG-9a",
        "live": args.live,
        "relaxed": args.relaxed,
        "seed": args.seed,
        "max_turns": args.max_turns,
        "policy": ENGLISH_POLICY.version,
        "profiles": rows,
        "adr_checks": result_checks,
        "reports": reports,
        "excerpts": excerpts,
    }
    if not args.skip_math and not args.live:
        session_api.tutor_router = lambda: None
        result["math_golden_after_english"] = math_golden_after_english()
        result["math_interleaved"] = math_interleaved(PROFILES[1], args.seed)
    live_out = LIVE_OUT.with_name(LIVE_OUT.stem + ("-relaxed" if args.relaxed else "") + LIVE_OUT.suffix)
    out = args.out or (live_out if args.live else DEFAULT_OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(table(rows))
    print(json.dumps(result_checks, ensure_ascii=False))
    if "math_golden_after_english" in result:
        print("Toán golden:", result["math_golden_after_english"], "xen kẽ:", result["math_interleaved"])
    print(f"Đã ghi {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")


if __name__ == "__main__":
    main()
