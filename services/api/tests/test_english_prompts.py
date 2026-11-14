"""ENG-5a: the English prompt set, chosen by subject, and the proof that Mathematics did not change.

- Math regression (english-module-rules.md P1, CLAUDE.md rule 7): everything the Math tutor sends to a model,
  the exact Groq body for each model of the default chain, and the Math validator's verdicts on a fixed
  corpus are compared string for string with ``golden/math-prompts-before-eng5a.json``, written from main
  (6ac53b9) before ENG-5a changed any code. The golden is never rewritten by this test.
- English prompts (P2, P4, P5): under 3.000 token, no term of the other subject, OFF_TOPIC kept out.
"""

import importlib.util
import json
from pathlib import Path

import pytest
from cavat.core.pedagogy import HintLevel, Move
from cavat.modules.ai_gateway.base import MAX_PROMPT_TOKENS, ChatRequest, estimate_prompt_tokens
from cavat.modules.ai_gateway.groq import reasoning_effort_for
from cavat.modules.session.service import lesson_packages
from cavat.modules.tutor import brain, prompt_builder
from cavat.modules.tutor.brain import BrainPack
from cavat.modules.tutor.english import (
    EN_DIALOGUE_LABELS,
    HINT_LADDER_EN,
    OFF_TOPIC_STUDENT,
    OFF_TOPIC_TASK,
    SAY_AFTER_ME_TASK,
    TASKS_EN,
    build_english_request,
    check_request_en,
    english_off_topic,
    english_system_prompt,
    listen_request_en,
    task_for_en,
    unit_targets,
    verified_en,
)
from cavat.modules.tutor.english_validator import math_terms_in
from cavat.modules.tutor.prompt_builder import (
    PROMPT_SETS,
    Turn,
    _prompt_file,
    prompt_set,
    tutor_system_prompt,
)

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = Path(__file__).parent / "golden" / "math-prompts-before-eng5a.json"
PACKAGES = [pkg for _, pkg in sorted(lesson_packages("english").items())]  # the subject loader (ADR-062)
WORDS = unit_targets(PACKAGES)
ENGLISH_FILES = [PROMPT_SETS["english"].__dict__[k] for k in ("constitution", "subject_module", "listener")]
ENGLISH_FILES.append(PROMPT_SETS["english"].curriculum_check)


def _snapshot_module():
    spec = importlib.util.spec_from_file_location(
        "math_prompts_snapshot", GOLDEN.with_name("math_prompts_snapshot.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------------------------- Mathematics


def test_math_prompts_identical_to_before_eng5a():
    """Brain, listener and curriculum-check requests, the Groq body per model, the legacy renderer's
    request for every item and move of the Math lessons, and the Math validator on a fixed corpus."""
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(_snapshot_module().snapshot(), ensure_ascii=False))
    assert actual.keys() == expected.keys()
    for section in expected:
        if isinstance(expected[section], dict):
            assert actual[section].keys() == expected[section].keys(), section
            for key in expected[section]:
                assert actual[section][key] == expected[section][key], f"{section}:{key}"
        else:
            assert actual[section] == expected[section], section


def test_math_prompt_set_is_what_the_math_code_reads():
    math = PROMPT_SETS["math"]
    assert (math.constitution, math.subject_module) == (brain.CONSTITUTION, brain.SUBJECT_MODULE)
    assert tutor_system_prompt("math") == brain.system_prompt()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["requests"]
    assert golden["listener"]["messages"][0][1] == _prompt_file(math.listener)
    assert golden["curriculum_check"]["messages"][0][1] == _prompt_file(math.curriculum_check)


@pytest.mark.parametrize("subject", [None, "", "Math", "history", "en"])
def test_prompt_set_never_falls_back_to_math(subject):
    with pytest.raises(ValueError):
        prompt_set(subject)


def test_math_prompts_carry_no_english_target():
    """P2 the other way: no English target sentence of the unit in any Math prompt."""
    math_text = json.dumps(json.loads(GOLDEN.read_text(encoding="utf-8"))["requests"], ensure_ascii=False)
    for phrase in WORDS:
        if len(phrase.split()) >= 3:
            assert phrase not in math_text
    assert "[[en:" not in math_text


# ---------------------------------------------------------------------------------------------- English


def test_english_set_is_its_own_files():
    english = prompt_set("english")
    assert set(ENGLISH_FILES).isdisjoint(PROMPT_SETS["math"].__dict__.values())
    assert english_system_prompt() == "\n\n".join(
        (_prompt_file(english.constitution), _prompt_file(english.subject_module))
    )
    assert english_system_prompt() != brain.system_prompt()


@pytest.mark.parametrize("name", ENGLISH_FILES)
def test_english_prompt_files_have_no_math(name):
    text = _prompt_file(name)
    assert math_terms_in(text) == []
    assert "toán" not in text.lower()
    assert "<!--" not in text  # the header comment is not sent


def test_legacy_renderer_never_uses_the_math_constitution_for_english():
    assert prompt_builder.system_prompt(PACKAGES[0]) == english_system_prompt()


def test_hint_ladder_covers_every_level():
    assert set(HINT_LADDER_EN) == {int(level) for level in HintLevel}
    assert all(math_terms_in(text) == [] for text in HINT_LADDER_EN.values())
    assert "nguyên câu mẫu" in HINT_LADDER_EN[7] and "không gợi ý" in HINT_LADDER_EN[0]


def test_every_move_has_an_english_task():
    assert set(TASKS_EN) == set(brain.TASKS)
    for move in TASKS_EN:
        task = task_for_en(move, level=3, asks="nghĩa của souvenirs")
        assert math_terms_in(task) == [] and "toán" not in task.lower()
    assert task_for_en(Move.HINT, say_after_me=True) == SAY_AFTER_ME_TASK
    assert task_for_en(Move.HINT, reasons=("OFF_TOPIC",)) == OFF_TOPIC_TASK


def _worst_pack(item, move, student="We eat seafood"):
    long = "chữ " * 400
    return BrainPack(
        task=task_for_en(move, level=4),
        question=item.stem,
        student_text=student,
        verdict="Chưa đúng: động từ chưa ở dạng quá khứ.",
        hints_given=tuple(h.text for h in item.hints),
        recent=tuple(Turn("tutor" if i % 2 else "student", long) for i in range(8)),
        grounds=tuple(long for _ in range(5)),
        name="An",
        lesson=PACKAGES[0].title,
    )


@pytest.mark.parametrize("item", [i for p in PACKAGES for i in p.items], ids=lambda i: i.id)
def test_english_request_fits_3000_tokens_and_has_no_math(item):
    for move in (Move.HINT, Move.EXPLAIN, Move.FULL_EXPLANATION):
        request = build_english_request(_worst_pack(item, move), unit_words=WORDS, hint_level=4)
        assert estimate_prompt_tokens(request) <= MAX_PROMPT_TOKENS
        text = "\n".join(m.content for m in request.messages)
        assert math_terms_in(text) == [], item.id
        assert "toán" not in text.lower()


def test_english_request_shape():
    item = PACKAGES[1].items[3]
    request = build_english_request(_worst_pack(item, Move.HINT), unit_words=WORDS, hint_level=3)
    user = request.messages[1].content
    assert request.messages[0].content == english_system_prompt()
    assert "[TỪ VÀ MẪU CÂU CỦA BÀI] swim; take photos" in user
    assert f"[MỨC GỢI Ý] {HINT_LADDER_EN[3]}" in user
    assert request.json_schema == prompt_builder.TUTOR_OUTPUT_SCHEMA
    assert not hasattr(request, "reasoning_effort")  # the Groq adapter sets it per model (P5)
    assert (reasoning_effort_for("qwen/qwen3.8-27b"), reasoning_effort_for("openai/gpt-oss-120b")) == (
        "none",
        "low",
    )


@pytest.mark.parametrize(
    "said",
    [
        "Cô ơi 0,5 + 0,25 bằng mấy?",
        "cô giải giúp con bài toán diện tích hình thang với",
        "3 x 4 = ?",
        "phân số 3/4 đọc sao cô",
        "12 chia 3 được mấy ạ",
    ],
)
def test_math_question_in_english_session_is_off_topic(said):
    assert english_off_topic(said) == "OFF_TOPIC"
    pack = BrainPack(
        task=task_for_en(Move.REDIRECT, reasons=("OFF_TOPIC",)), question="Did you swim?", student_text=said
    )
    request = build_english_request(pack, unit_words=WORDS)
    user = request.messages[1].content
    assert OFF_TOPIC_STUDENT in user and OFF_TOPIC_TASK in user
    assert said not in user  # the model never sees the other subject's question (DI-139)
    assert math_terms_in(user) == []
    check = check_request_en("x", question="Did you swim?", scope="Unit 11", student=said)
    assert said not in check.messages[1].content


@pytest.mark.parametrize(
    "said",
    [
        "We ate seafood.",
        "Yes, I did. I swam with my mother.",
        "con không biết",
        "ok cô",
        "We went there last weekend",
    ],
)
def test_english_answers_are_not_off_topic(said):
    assert english_off_topic(said) is None


def test_listener_and_check_requests():
    listen = listen_request_en(
        stem="Did you swim?", last_tutor="Con trả lời bạn nhé?", said="yes i did", recent=(), phase="ANSWER"
    )
    assert listen.messages[0].content == _prompt_file(prompt_set("english").listener)
    assert "OFF_TOPIC" in listen.json_schema["properties"]["label"]["enum"]
    assert set(EN_DIALOGUE_LABELS) >= {"PASS", "CONTINUE", "REPAIR", "DECLINE", "REACTION", "OFF_TOPIC"}
    assert estimate_prompt_tokens(listen) <= MAX_PROMPT_TOKENS
    check = check_request_en(
        "Con nói theo cô: [[en: We swam in the sea.]]",
        question="Did you swim?",
        scope="Unit 11",
        unit_words=WORDS,
        references=["x " * 500] * 5,
        recent=["y " * 500] * 4,
        say_after_me=True,
        hint_level=7,
    )
    case = json.loads(check.messages[1].content)
    assert (
        case["loi_co"] == "Con nói theo cô: We swam in the sea."
    )  # marks are for the voice, not the checker
    assert case["duoc_doc_mau"] is True and case["gioi_han_goi_y"] == "H7"
    assert estimate_prompt_tokens(check) <= MAX_PROMPT_TOKENS
    assert isinstance(check, ChatRequest)


def test_verified_en():
    ok = {
        "english_correct": True,
        "within_scope": True,
        "task_preserved": True,
        "addresses_student": True,
        "solution_leaked": False,
        "reason": "",
        "needs_pedagogy_support": False,
    }
    assert verified_en(ok)
    assert not verified_en({**ok, "solution_leaked": True})
    assert not verified_en({**ok, "within_scope": False})
    assert not verified_en(None)
