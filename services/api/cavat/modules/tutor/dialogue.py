"""BRAIN-3: read answers to the question actually asked, using the approved deterministic key.

This extracts a verdict/component, never lets a model decide mathematical correctness. Assessment keeps
the full-item checker. Missing parts are different from false parts.
"""

from __future__ import annotations

import re
from dataclasses import replace

from cavat.core.pedagogy import Outcome
from cavat.core.vi_text import fold, normalize
from cavat.modules.assessment.math_checker import CheckResult, _check_facts, check_answer, parse_verdict
from cavat.modules.assessment.student_intent import asks_question
from cavat.modules.content.lesson_package import BooleanAnswer, Item, KeyFacts, LessonPackage, OpenAnswer

DIALOGUE_VERSION = 2
_OPPOSITES = (("trong", "ngoài"),)


def _negative(text: str, property_: str) -> bool:
    return bool(re.search(rf"kh[oô]ng(?:\s+\w+){{0,3}}\s+{re.escape(property_)}", text.lower()))


def _has(text: str, phrase: str) -> bool:
    return bool(re.search(rf"\b{re.escape(fold(normalize(phrase)))}\b", fold(normalize(text))))


def verbal_verdict(stem: str, said: str) -> bool | None:
    """A counterexample to 'always inside' says false without the child having to repeat 'Sai'.

    Only explicit binary predicates are read. Different numerical operands/shape conditions, a question,
    both opposing predicates or uncertainty are left ungraded. The expected true/false key is NOT read.
    """
    if asks_question(said) or re.search(
        r"\b(?:hình như|chắc là|không biết|có lẽ|luôn|mọi|tất cả|bao giờ cũng)\b", said.lower()
    ):
        return None
    if parse_verdict(said) is not None:
        return None  # the regular checker handles the explicit verdict
    from cavat.modules.assessment.vi_numbers import extract_numbers

    given = {n.value for n in extract_numbers(stem)}
    theirs = {n.value for n in extract_numbers(said)}
    if theirs or given:
        return None  # operand order and arithmetic need the mathematical checker
    if not any(_has(stem, term) and _has(said, term) for term in ("đường cao", "chiều cao", "hai đáy")):
        if not set(re.findall(r"\w+", said.lower())) <= {
            "à",
            "nó",
            "ở",
            "nằm",
            "bên",
            "ạ",
            "thì",
            "ra",
            "ngoài",
            "trong",
        }:
            return None
    for shape in ("tam giác nhọn", "tam giác vuông", "tam giác tù"):
        if _has(stem, shape) and any(
            _has(said, other)
            for other in ("tam giác nhọn", "tam giác vuông", "tam giác tù")
            if other != shape
        ):
            return None
    for first, second in _OPPOSITES:
        source = (_has(stem, first), _has(stem, second))
        reply = (_has(said, first), _has(said, second))
        if sum(source) == 1 and sum(reply) == 1:
            # General quantifier negations need more than a local predicate comparison.
            if "không" in stem.lower():
                return None
            spoken = first if reply[0] else second
            return (source == reply) != _negative(said, spoken)
    # A direct restatement of a mathematical property, without confusing its negation.
    for property_ in ("vuông góc", "song song"):
        if _has(stem, property_) and _has(said, property_):
            return _negative(stem, property_) == _negative(said, property_)
    return None


def boolean_read(item: Item, text: str, package: LessonPackage, asked: str = "") -> CheckResult | None:
    if not isinstance(item.answer, BooleanAnswer):
        return None
    if not any(_has(text, term) for term in ("đường cao", "chiều cao", "hai đáy")):
        if not any(_has(asked, word) for word in ("trong", "ngoài", "vị trí", "ở đâu")):
            return None  # 'ở ngoài' only answers a question about position
    verdict = verbal_verdict(item.stem, text)
    if verdict is None:
        return None
    checked = check_answer(item, "Đúng" if verdict else "Sai", package)
    return replace(
        checked,
        detail={
            **checked.detail,
            "verbal_verdict": verdict,
            "reason_supplied": len(text.split()) >= 6
            and any(_has(text, term) for term in ("đường cao", "chiều cao", "hai đáy")),
        },
    )


def relation_step(item: Item, text: str, asked: str, knowledge: tuple[str, ...]) -> CheckResult | None:
    """Read the small question about an approved relation, without grading the whole item right."""
    if asks_question(text) or re.search(r"\b(?:không|chưa|hình như)\b", text.lower()):
        return None
    source = " ".join(knowledge)
    families = (
        ("vuông góc", ("cạnh nào", "với gì"), ("đáy", "cạnh đối diện")),
        ("phần nguyên", ("ở đâu", "bên nào"), ("bên trái", "trái")),
        ("phần thập phân", ("ở đâu", "bên nào"), ("bên phải", "phải")),
        ("mẫu số", ("ở đâu", "bên nào"), ("dưới gạch ngang", "ở dưới")),
        ("tử số", ("ở đâu", "bên nào"), ("trên gạch ngang", "ở trên")),
    )
    for concept, queries, answers in families:
        if not _has(asked, concept) or not any(_has(asked, q) for q in queries) or not _has(source, concept):
            continue
        if not any(_has(text, a) and _has(source, a) for a in answers):
            continue
        if (concept == "phần nguyên" and _has(text, "phải")) or (
            concept == "phần thập phân" and _has(text, "trái")
        ):
            return None
        follow = "Con thử trả lời câu đang làm nhé?"
        if isinstance(item.answer, OpenAnswer) and item.answer.facts:
            missing = [k for k, _ in _components(item.answer.facts) if k.startswith("pairs:")]
            follow = remaining_question(item, missing)
        return CheckResult(
            Outcome.PARTIAL,
            normalized=text.strip(),
            detail={"partial_reason": "VERBAL_STEP", "follow_up": follow},
        )
    return None


def _components(facts: KeyFacts) -> list[tuple[str, KeyFacts]]:
    parts = []
    for name in ("numbers", "phrases", "pairs"):
        for i, group in enumerate(getattr(facts, name)):
            parts.append((f"{name}:{i}", KeyFacts(**{name: [group]})))
    for name in ("relations", "order", "reading"):
        value = getattr(facts, name)
        if value:
            parts.append((name, KeyFacts(**{name: value})))
    return parts


def parts_read(item: Item, text: str, last_tutor: str, progress: dict[str, str]) -> CheckResult | None:
    answer = item.answer
    if not isinstance(answer, OpenAnswer) or answer.facts is None:
        return None
    components = _components(answer.facts)
    if (
        len(components) < 2
        or answer.facts.only_numbers
        or asks_question(text)
        or re.search(r"\b(?:không|chưa|hình như|có lẽ|chắc là)\b", text.lower())
    ):
        return None
    matched: dict[str, str] = {}
    for key, facts in components:
        value = text
        # An explicit revision cancels previous evidence for that component.
        if facts.order and all(_has(text, term) for term in facts.order):
            progress.pop(key, None)
        if facts.pairs and _has(text, facts.pairs[0][0]):
            progress.pop(key, None)
            from cavat.modules.assessment.vi_numbers import extract_numbers

            names = {str(n.value) for n in extract_numbers(text)}
            if facts.pairs[0][1].isdigit() and names and names != {facts.pairs[0][1]}:
                continue
        if facts.pairs:
            word, name = facts.pairs[0]
            # An answer 'hình số 3' to 'hình nào có đường cao ở ngoài?' supplies the object of
            # precisely that predicate. Do not inject any expected object into the child's words.
            if (
                _has(last_tutor, word)
                and _has(text, name)
                and re.fullmatch(
                    r"(?:à |vậy |thì |nó |là |con |chọn |hình |số |ạ |đó |nên |vâng |dạ |"
                    r"được |rồi |\d+\s*)+[.! ]*",
                    text.lower().strip(),
                )
            ):
                value = f"{word} {text}"
        sub = answer.model_copy(update={"facts": facts})
        if _check_facts(sub, value).outcome == Outcome.CORRECT:
            matched[key] = text
    if not matched:
        return None
    accumulated = {**progress, **matched}
    remaining = [key for key, _ in components if key not in accumulated]
    progress.update(matched)
    question = remaining_question(item, remaining)
    return CheckResult(
        Outcome.PARTIAL if remaining else Outcome.CORRECT,
        normalized=text.strip(),
        correct_answer=answer.sample_answer,
        detail={
            "partial_reason": "FACTS_PROGRESS",
            "matched_parts": list(matched),
            "remaining_parts": remaining,
            "follow_up": question,
        },
    )


def remaining_question(item: Item, remaining: list[str]) -> str:
    answer = item.answer
    if isinstance(answer, OpenAnswer) and answer.facts and remaining == ["order"]:
        if set(answer.facts.order) <= {"nhọn", "vuông", "tù"}:
            return "Còn hình 1, 2, 3 lần lượt là tam giác loại nào con?"
        return "Con nêu tiếp các ý còn lại theo thứ tự trong đề nhé?"
    stem = item.stem.split("[Hình:")[0].strip()
    if remaining and all(k.startswith("pairs:") for k in remaining):
        part = re.search(r"(?:và )?cho biết (.+?)(?:\.|\?|$)", stem, re.IGNORECASE)
        if part:
            return f"Còn {part[1].strip().rstrip('.?')}?"
    return "Con làm tiếp phần còn lại của đề nhé?"
