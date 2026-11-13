"""ENG-5a: snapshot of everything the Math tutor sends to a model, and of the Math validator's verdicts.

``tests/golden/math-prompts-before-eng5a.json`` was written by this module from main at 6ac53b9, before
ENG-5a touched anything (``python -m tests.golden.math_prompts_snapshot`` from services/api). The test
``test_english_prompts.py::test_math_prompts_identical_to_before_eng5a`` rebuilds the same snapshot and
compares it string for string (english-module-rules.md P1, P3; CLAUDE.md rule 7).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.tutor import brain, conversation, prompt_builder
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
from cavat.modules.tutor.prompt_builder import Turn
from cavat.modules.tutor.validator import validate_message

ROOT = Path(__file__).resolve().parents[4]
GOLDEN = Path(__file__).with_name("math-prompts-before-eng5a.json")
LESSONS = sorted((ROOT / "docs/pedagogy/math-g5").glob("**/lesson.yaml"))

MESSAGES = (
    "Con thử so sánh phần nguyên trước nhé. Phần nguyên của hai số thế nào?",
    "Vì 2 < 3 nên 0,25 < 0,3. Con thấy đúng không?",
    "Đúng rồi! Con giỏi quá. Con giải thích vì sao nhé?",
    "Con nói theo cô: We swam in the sea.",
    "We ate seafood in Nha Trang. Did you swim?",
    "Em ơi, nhà em ở đâu? Con có số điện thoại không?",
    "Cô gợi ý nhé: hàng phần mười của 0,7 là chữ số nào? Còn hàng phần trăm?",
    "Ok con, mình làm tiếp nhé. Con nhìn hàng phần mười trước nhé?",
    "Số 0,3 > 0,25 nhé. Con điền dấu nào?",
    "",
)
MOVES = (Move.HINT, Move.PROBE, Move.VERIFY, Move.EXPLAIN, Move.FULL_EXPLANATION, Move.CONFIRM_ADVANCE)


class _Router:
    def __init__(self):
        self.requests = []

    def chat(self, model_class, request, calls_used=0):
        self.requests.append(request)
        return SimpleNamespace(result=None, calls_made=0, fallback_reason=None)


def _request(request) -> dict:
    return {
        "messages": [[m.role, m.content] for m in request.messages],
        "schema_name": request.schema_name,
        "json_schema": request.json_schema,
        "max_output_tokens": request.max_output_tokens,
        "temperature": request.temperature,
    }


def _digest(data: dict) -> str:
    """The legacy renderer's 100+ requests repeat one system prompt: kept as a hash to keep the file small."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def snapshot() -> dict:
    out: dict = {"brain_system": brain.system_prompt(), "requests": {}, "validator": {}}
    pack = brain.BrainPack(
        task=brain.task_for(Move.HINT, level=2),
        question="Điền dấu >, <, = vào chỗ chấm: 0,25 … 0,3",
        student_text="con nghĩ 0,25 lớn hơn vì 25 > 3",
        verdict="Chưa đúng: con so sánh phần thập phân như số tự nhiên.",
        hints_given=("Con so sánh hàng phần mười trước nhé.",),
        recent=(Turn("tutor", "Con điền dấu nào?"), Turn("student", "dấu lớn")),
        grounds=("So sánh hai số thập phân: so phần nguyên, rồi hàng phần mười, hàng phần trăm.",),
        name="An",
        lesson="So sánh hai số thập phân",
    )
    out["requests"]["brain"] = _request(brain.build_request(pack))
    out["requests"]["brain_correction"] = _request(
        brain.build_request(brain.BrainPack(**{**pack.__dict__, "correction_required": True}))
    )
    router = _Router()
    model = SimpleNamespace(router=router, calls_used=0, calls_made=0)
    conversation.listen(
        model, stem=pack.question, last_tutor="Con điền dấu nào?", said="ok cô", recent=pack.recent, phase="ANSWER"
    )
    out["requests"]["listener"] = _request(router.requests[0])
    from cavat.modules.teaching.curriculum import verification

    out["requests"]["curriculum_check"] = _request(
        verification("Hàng phần mười của 0,25 là 2.", question=pack.question, scope="So sánh số thập phân")
    )
    for path in LESSONS:
        pkg = load_lesson_package(path)
        out["requests"][f"system:{pkg.lesson_id}"] = prompt_builder.system_prompt(pkg)
        for item in pkg.items:
            state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
            for move in MOVES:
                decision = PolicyDecision(move=move, target=HintTarget.STEP, level=HintLevel.H2)
                ctx = RenderContext(
                    decision=decision, item=item, package=pkg, state=state, student_text="con không biết"
                )
                key = f"{pkg.lesson_id}:{item.id}:{move.value}"
                if move in (Move.HINT, Move.EXPLAIN):
                    request = prompt_builder.build_request(ctx, anchor=item.stem, student_name="Nguyễn An")
                    out["requests"][f"legacy:{key}"] = _digest(_request(request))
                out["validator"][key] = [list(validate_message(m, ctx).codes) for m in MESSAGES]
    return out


if __name__ == "__main__":
    data = snapshot()
    GOLDEN.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(f"{GOLDEN} ({len(data['requests'])} requests, {len(data['validator'])} validator cases)\n")
