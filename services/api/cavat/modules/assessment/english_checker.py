"""Deterministic checking of English answers (ENG-4, ADR-060 §5 and §10, ADR-063).

The LLM never decides whether an English answer is right (CLAUDE.md rules 1 and 2). This module compares
the child's sentence, typed or transcribed, with the accepted answers taken from the owner's documents,
after the normalization DI-110 (``core/en_text.normalize_answer``, DI-128). It is apart from the
``MathChecker`` (english-module-rules M1) and returns the same ``CheckResult`` the tutor policy reads.

Two answer types (the contract ENG-3b adds to the content schema; until it is merged the checker reads
its own ``PhraseSpec`` / ``WordOrderSpec``, and ``english_spec`` reads any object with the same fields):

- ``phrase``: ``accept`` (whole answers), ``required`` (groups: each idea needs one of its phrasings),
  ``normalize`` ("en-vi/1"), ``wrong_answers`` (a wrong sentence -> the misconception it shows),
  ``allow_name`` (another place name in the blank "in …" is accepted);
- ``word_order``: ``tokens`` (the shuffled words shown), ``accept`` (the right orders).

A wrong sentence gets the most serious English error code of the table DI-107 it shows (DI-129):
CONCEPTUAL (``EN_SHORT_ANSWER``, ``EN_TENSE``, ``EN_MEANING``) > PROCEDURAL (``EN_STRUCTURE``,
``EN_VERB_FORM`` on a node that targets the pattern; FORMAT elsewhere) > L1 > FORMAT (``EN_SLIP``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from cavat.core.en_text import IRREGULAR_PAST, contains_words, normalize_answer, sentences
from cavat.core.pedagogy import ErrorClass, Outcome
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.assessment.student_intent import read_intent

EN_NORMALIZER = "en-vi/1"
ENGLISH_ANSWER_TYPES = frozenset({"phrase", "word_order"})


class EnCode(StrEnum):
    """The English error codes of ADR-060 §5 (DI-107). The checker never emits PRONUNCIATION: it grades
    the confirmed transcript, and a pronunciation that does not change the meaning is not an error."""

    SHORT_ANSWER = "EN_SHORT_ANSWER"
    TENSE = "EN_TENSE"
    MEANING = "EN_MEANING"
    STRUCTURE = "EN_STRUCTURE"
    VERB_FORM = "EN_VERB_FORM"
    SLIP = "EN_SLIP"
    PRONUNCIATION = "EN_PRONUNCIATION"
    L1 = "EN_L1"


_CONCEPTUAL = frozenset({EnCode.SHORT_ANSWER, EnCode.TENSE, EnCode.MEANING})
_TARGET_DEPENDENT = frozenset({EnCode.STRUCTURE, EnCode.VERB_FORM})
# DI-107: "CONCEPTUAL > PROCEDURAL > L1 > FORMAT".
_SEVERITY = {ErrorClass.CONCEPTUAL: 4, ErrorClass.PROCEDURAL: 3, ErrorClass.L1: 2, ErrorClass.FORMAT: 1}


# --------------------------------------------------------------------------- specs


@dataclass(frozen=True)
class PhraseSpec:
    accept: tuple[str, ...] = ()
    required: tuple[tuple[str, ...], ...] = ()
    normalize: str = EN_NORMALIZER
    wrong_answers: Mapping[str, str] = field(default_factory=dict)
    allow_name: bool = False
    type: Literal["phrase"] = "phrase"


@dataclass(frozen=True)
class WordOrderSpec:
    tokens: tuple[str, ...]
    accept: tuple[tuple[str, ...], ...]
    type: Literal["word_order"] = "word_order"


EnglishSpec = PhraseSpec | WordOrderSpec


def _field(answer: Any, name: str, default: Any) -> Any:
    if isinstance(answer, Mapping):
        return answer.get(name, default)
    return getattr(answer, name, default)


def english_spec(answer: Any) -> EnglishSpec | None:
    """The English spec of an answer, read by field name (a schema model, a dict or a spec), or None when
    the answer is not of an English type. This is the one place that meets the content schema."""
    if isinstance(answer, PhraseSpec | WordOrderSpec):
        return answer
    kind = _field(answer, "type", None)
    if kind == "phrase":
        return PhraseSpec(
            accept=tuple(_field(answer, "accept", ())),
            required=tuple(tuple(g) for g in _field(answer, "required", ())),
            normalize=_field(answer, "normalize", EN_NORMALIZER),
            wrong_answers=dict(_field(answer, "wrong_answers", {}) or {}),
            allow_name=bool(_field(answer, "allow_name", False)),
        )
    if kind == "word_order":
        return WordOrderSpec(
            tokens=tuple(_field(answer, "tokens", ())),
            accept=tuple(tuple(o) for o in _field(answer, "accept", ())),
        )
    return None


@dataclass(frozen=True)
class EnglishContext:
    """What the checker knows of the item's place in the unit (DI-129).

    ``node_codes``: English error code -> misconception of the item's nodes whose ``error_class`` is that
    code (the patterns the node teaches). ``misconception_codes``: misconception -> its code.
    ``known_targets``: the package says which node teaches which pattern; while it does not (content
    without ``error_class``), a structure or verb-form error counts on the node (PROCEDURAL, the stricter).
    """

    node_codes: Mapping[str, str] = field(default_factory=dict)
    misconception_codes: Mapping[str, str] = field(default_factory=dict)
    known_targets: bool = False


NO_CONTEXT = EnglishContext()


def context_for(kc_ids: Sequence[str], misconceptions: Sequence[Any]) -> EnglishContext:
    """The context of an item from its nodes and the misconceptions of its lesson (``error_class`` per
    DI-107; read by name so that content without the field still loads)."""
    node_codes: dict[str, str] = {}
    codes: dict[str, str] = {}
    for m in misconceptions:
        code = _field(m, "error_class", None)
        if code not in EnCode.__members__.values():
            continue
        codes[_field(m, "id", "")] = str(code)
        if _field(m, "kc_id", None) in kc_ids:
            node_codes.setdefault(str(code), _field(m, "id", ""))
    return EnglishContext(node_codes=node_codes, misconception_codes=codes, known_targets=bool(codes))


def error_class_of(code: str, ctx: EnglishContext = NO_CONTEXT) -> ErrorClass:
    """DI-107: the shared class the projector reads for an English code (DI-129 for the node target)."""
    if code in _CONCEPTUAL:
        return ErrorClass.CONCEPTUAL
    if code in _TARGET_DEPENDENT:
        on_target = not ctx.known_targets or code in ctx.node_codes
        return ErrorClass.PROCEDURAL if on_target else ErrorClass.FORMAT
    if code == EnCode.L1:
        return ErrorClass.L1
    if code == EnCode.SLIP:
        return ErrorClass.FORMAT
    raise ValueError(f"no error class for {code!r}")


# --------------------------------------------------------------------------- verbs

# Bases of the irregular verbs, without the auxiliaries: "Yes, I do." is a short answer, not a narrative.
_IRREGULAR_BASE = {
    base: past for past, base in IRREGULAR_PAST.items() if past not in ("was", "were", "did", "had")
}
# Real English words that look like a wrong -ed form; never read as EN_VERB_FORM.
_REAL_WORDS = frozenset(
    {"seed", "bed", "wined", "sited", "waked", "payed", "sawed", "founded", "meted", "sated"}
)
_REAL_WORDS |= frozenset({"felted", "spited", "winged", "singed", "need", "feed"})


def _wrong_ed_forms() -> frozenset[str]:
    """ "buyed", "eated", "taked", "swimmed", "goed", "tooked": -ed on a verb with a past form of its own."""
    out: set[str] = set()
    for past, base in IRREGULAR_PAST.items():
        if past in ("was", "were", "did", "had"):
            continue
        out |= {base + "ed", past + "ed"}
        if base.endswith("e"):
            out.add(base + "d")
        if re.fullmatch(r".*[^aeiou][aeiou][bdgmnprt]", base):
            out.add(base + base[-1] + "ed")
        if base.endswith("y"):
            out.add(base[:-1] + "ied")
    return frozenset(out - _REAL_WORDS - set(IRREGULAR_PAST))


WRONG_ED = _wrong_ed_forms()
_NOT_PAST_ED = frozenset({"interested", "excited", "tired", "bored", "red", "bed", "need", "seed", "feed"})


def _is_past(word: str) -> bool:
    if word in IRREGULAR_PAST:
        return word not in ("did",)
    return len(word) >= 4 and word.endswith("ed") and word not in _NOT_PAST_ED and word not in WRONG_ED


def _bases_of(past: str) -> set[str]:
    """Base forms of a past verb: "went" -> go; "visited" -> visit; "sunbathed" -> sunbathe; "stopped" ->
    stop; "studied" -> study."""
    if past in IRREGULAR_PAST:
        return {IRREGULAR_PAST[past]}
    stem = past[:-2]
    out = {stem, past[:-1]}
    if past.endswith("ied"):
        out.add(past[:-3] + "y")
    if len(stem) >= 2 and stem[-1] == stem[-2]:
        out.add(stem[:-1])
    return out


def _present_forms(base: str) -> set[str]:
    out = {base, base + "s", base + "es"}
    if base.endswith("y"):
        out.add(base[:-1] + "ies")
    return out


SUBJECTS = frozenset({"i", "we", "he", "she", "they", "you"})
_POSSESSIVE = frozenset({"my", "his", "her", "their", "our", "your"})
_WH = ("what", "where", "when", "who", "how", "why")
_SHORT_WRONG = re.compile(
    r"^(?:yes|no) (?:i|we|he|she|they) "
    r"(?:do not|does not|will not|do|does|dont|doesnt|will|wont|am|is|are)(?: |$)"
)
_DID_SHORT = re.compile(r"^(?:yes|no) (?:i|we|he|she|they) did(?: |$)")


# --------------------------------------------------------------------------- accepted forms


@dataclass(frozen=True)
class _Form:
    """An accepted answer: its normalized words, and a pattern when names may change (``allow_name``)."""

    text: str
    pattern: re.Pattern[str] | None

    def matches(self, answer: str) -> bool:
        return self.pattern.fullmatch(answer) is not None if self.pattern else answer == self.text

    def inside(self, answer: str) -> bool:
        if self.pattern is None:
            return contains_words(answer, self.text)
        return self.pattern.search(f" {answer} ") is not None


# A word of a name slot: not a word of the sentence's grammar or time ("in the summer" is no place).
_NOT_NAME = (
    "the|a|an|my|your|his|her|our|their|this|that|these|those|last|next|yesterday|today|summer|winter|"
    "spring|autumn|weekend|week|month|year|morning|afternoon|evening|with|and|or|to|in|on|at|by|for|of|"
    "did|do|does|we|i|you|he|she|they|it"
)
_NAME_WORD = rf"(?!(?:{_NOT_NAME})(?: |$))[^\s]+"
_NAME_SLOT = rf"{_NAME_WORD}(?: {_NAME_WORD}){{0,2}}"


def _form(accepted: str, allow_name: bool) -> _Form:
    """DI-110 ``allow_name`` (DI-128): a run of capitalized words inside the sentence ("Ha Long", "Nha
    Trang"; not "I", not the first word of a sentence) is a name slot of one to three words."""
    text = normalize_answer(accepted)
    if not allow_name:
        return _Form(text, None)
    parts: list[str] = []
    in_name, start = False, True
    for raw in accepted.split():
        word = normalize_answer(raw)
        is_name = not start and raw[:1].isupper() and word not in ("i",) and word.replace(" ", "").isalnum()
        if is_name:
            if not in_name:
                parts.append(_NAME_SLOT)
            in_name = True
        elif word:
            parts.append(re.escape(word))
            in_name = False
        start = raw.rstrip()[-1:] in ".!?"
    if _NAME_SLOT not in parts:  # no name in this answer
        return _Form(text, None)
    body = " ".join(parts)
    return _Form(text, re.compile(rf"(?:^|(?<= )){body}(?:$|(?= ))"))


def _asks_yes_no(forms: Sequence[_Form]) -> bool:
    """DI-110: "yes,"/"no," is dropped when the item does not ask yes or no; it asks when an accepted
    answer starts with "yes" or "no"."""
    return any(f.text.split(" ")[0] in ("yes", "no") for f in forms)


_YES_NO = re.compile(r"^(?:yes|no) (?=\S)")
# Vietnamese courtesy around an English answer ("Dạ, we ate seafood ạ"): not part of the answer (DI-128).
_COURTESY_HEAD = re.compile(r"^(?:dạ|thưa cô|cô ơi)(?: |$)")
_COURTESY_TAIL = re.compile(r"(?:^| )(?:ạ|cô ơi|ạ cô)$")


def _answer_of(text: str, yes_no: bool) -> str:
    answer = normalize_answer(text)
    answer = _COURTESY_TAIL.sub("", _COURTESY_HEAD.sub("", answer)).strip()
    if not yes_no:
        answer = _YES_NO.sub("", answer)
    return answer


# --------------------------------------------------------------------------- error patterns


@dataclass(frozen=True)
class _Expect:
    """What the accepted answers say about the sentence the item wants."""

    did_short: bool  # "Yes, I did." / "No, I didn't."
    did_question: bool  # "Did you …?", "What did your family do …?"
    past: frozenset[str]  # past verbs of a narrative ("We ate seafood.")
    bases: frozenset[str]  # their base forms
    questions: tuple[tuple[str, ...], ...]  # accepted questions, word by word

    @staticmethod
    def of(texts: Sequence[str]) -> _Expect:
        did_short = did_question = False
        past: set[str] = set()
        questions: list[tuple[str, ...]] = []
        for text in texts:
            for sent in sentences(text) or [normalize_answer(text)]:
                words = sent.split()
                if not words:
                    continue
                if _DID_SHORT.match(sent):
                    did_short = True
                if words[0] == "did" or (len(words) > 1 and words[0] in _WH and words[1] == "did"):
                    did_question = True
                    questions.append(tuple(words))
                    continue
                past |= {w for w in words if _is_past(w)}
        bases = {b for p in past for b in _bases_of(p)}
        if past:  # a narrative in the past: every irregular base said as is, is the present
            bases |= set(_IRREGULAR_BASE)
        return _Expect(did_short, did_question, frozenset(past), frozenset(bases), tuple(questions))


def _did_then_past(words: list[str], expect: _Expect) -> bool:
    """EN_STRUCTURE "Did you bought …?": a question with "did" and the verb in the past."""
    if not words:
        return False
    i = 1 if words[0] == "did" else 2 if len(words) > 1 and words[0] in _WH and words[1] == "did" else 0
    if i == 0:
        return False
    for verb in words[i + 1 : i + 3]:  # the subject is one or two words ("you", "your family")
        if _is_past(verb) or verb in expect.past or verb in WRONG_ED:
            return True
    return False


def _without_did(words: list[str], expect: _Expect) -> bool:
    """EN_STRUCTURE "quên did": "Do you swim yesterday?", "What your family do …?", "You buy souvenirs?"."""
    if not expect.did_question or not words:
        return False
    head = words[0]
    nxt = words[1] if len(words) > 1 else ""
    if head in ("do", "does") and (nxt in SUBJECTS or nxt in _POSSESSIVE):
        return True
    if head in _WH and nxt in ("do", "does"):
        return True
    if head in _WH and (nxt in SUBJECTS or nxt in _POSSESSIVE):
        return True
    for question in expect.questions:
        k = question.index("did")
        bare = list(question[:k] + question[k + 1 :])
        if len(bare) == len(words) and all(
            a == b or _same_verb(a, b) for a, b in zip(bare, words, strict=True)
        ):
            return True
    return False


def _same_verb(base: str, said: str) -> bool:
    """``said`` is ``base`` in the past or the present (the verb of a question without "did")."""
    return (
        said in _present_forms(base) or IRREGULAR_PAST.get(said) == base or said in (base + "ed", base + "d")
    )


def _present_for_past(words: list[str], expect: _Expect) -> bool:
    """EN_TENSE "We eat seafood." where the answer tells what happened: a subject ("we", "my family")
    followed by the verb in the present, outside a question with "did"."""
    if not expect.past:
        return False
    for i, word in enumerate(words):
        if word in SUBJECTS:
            j = i + 1
        elif word in _POSSESSIVE and i + 1 < len(words):
            j = i + 2
        else:
            continue
        before = words[i - 1] if i > 0 else ""
        if before in ("did", "do", "does") or j >= len(words):
            continue
        verb = words[j]
        if any(verb in _present_forms(b) for b in expect.bases) and verb not in expect.past:
            return True
    return False


def _detect(answer: str, raw: str, expect: _Expect) -> list[EnCode]:
    """Every DI-107 code the sentence shows, from the patterns every item of the unit shares."""
    found: list[EnCode] = []
    parts = [s.split() for s in sentences(raw)] or [answer.split()]
    whole = answer.split()
    if expect.did_short and _SHORT_WRONG.match(answer):
        found.append(EnCode.SHORT_ANSWER)
    if any(_present_for_past(words, expect) for words in parts):
        found.append(EnCode.TENSE)
    if any(_did_then_past(words, expect) or _without_did(words, expect) for words in parts):
        found.append(EnCode.STRUCTURE)
    if any(w in WRONG_ED for w in whole):
        found.append(EnCode.VERB_FORM)
    return found


# --------------------------------------------------------------------------- slips and language


def _one_edit(a: str, b: str) -> bool:
    """One letter changed, added or left out (the Levenshtein distance is exactly 1)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def _repair(answer: str, vocabulary: set[str]) -> str:
    """DI-110 EN_SLIP: each word one letter away from an expected word of five letters or more becomes
    that word ("mothr" -> "mother"); a word the item expects, or a wrong -ed form, stays as it is."""
    out = []
    for word in answer.split():
        if word in vocabulary or word in WRONG_ED:
            out.append(word)
            continue
        fix = sorted(v for v in vocabulary if len(v) >= 5 and _one_edit(word, v))
        out.append(fix[0] if len(fix) == 1 else word)
    return " ".join(out)


_VI_LETTERS = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]")
# Vietnamese syllables a child types without marks that are not English words of a primary class.
_VI_PLAIN = frozenset(
    "con nha cua khong roi minh toi chung cung voi hom qua nay choi mua bien duoc nhieu lam cho "
    "ca ba me bo anh chi em ong vo so hai san thuyen vinh ngam qua luu niem".split()
)


def looks_vietnamese(text: str) -> bool:
    """EN_L1: an answer in Vietnamese (DI-129): it has Vietnamese letters, or at least two plain words of
    a Vietnamese sentence and they are most of it."""
    norm = normalize_answer(text)
    if _VI_LETTERS.search(norm):
        return True
    words = norm.split()
    plain = sum(w in _VI_PLAIN for w in words)
    return plain >= 2 and plain * 2 >= len(words)


# --------------------------------------------------------------------------- results


def _wrong(
    code: EnCode | None,
    ctx: EnglishContext,
    answer: str,
    correct: str | None,
    *,
    mis: str | None = None,
    confidence: float = 0.0,
    codes: Sequence[EnCode] = (),
) -> CheckResult:
    error = error_class_of(code, ctx) if code is not None else None
    detail: dict[str, Any] = {"en_code": None if code is None else str(code)}
    if codes:
        detail["en_codes"] = [str(c) for c in codes]
    return CheckResult(
        Outcome.WRONG,
        normalized=answer,
        correct_answer=correct,
        error_class=error,
        misconception_id=mis,
        misconception_confidence=confidence if mis else 0.0,
        candidates=[(mis, confidence)] if mis else [],
        detail=detail,
    )


def _worst(codes: Sequence[EnCode], ctx: EnglishContext) -> EnCode:
    """DI-107: the most serious error of the sentence; the first found breaks a tie."""
    return max(codes, key=lambda c: _SEVERITY[error_class_of(c, ctx)])


def _diagnosed(codes: list[EnCode], ctx: EnglishContext, answer: str, correct: str | None) -> CheckResult:
    code = _worst(codes, ctx)
    mis = ctx.node_codes.get(code)
    confidence = 0.7 if code in _CONCEPTUAL else 0.5
    return _wrong(code, ctx, answer, correct, mis=mis, confidence=confidence, codes=codes)


def _l1(answer: str, correct: str | None) -> CheckResult:
    """DI-107 EN_L1, the first time: not graded, the tutor asks for it in English (DI-129). The class is
    kept so that an item closed in Vietnamese scores 0.3 (``node-mastery-en``)."""
    return CheckResult(
        Outcome.UNPARSEABLE,
        normalized=answer,
        correct_answer=correct,
        error_class=ErrorClass.L1,
        detail={"en_code": str(EnCode.L1)},
    )


# --------------------------------------------------------------------------- phrase


def check_phrase(spec: PhraseSpec, text: str, ctx: EnglishContext = NO_CONTEXT) -> CheckResult:
    if spec.normalize != EN_NORMALIZER:
        raise ValueError(f"unknown English normalizer {spec.normalize!r}; expected {EN_NORMALIZER!r}")
    forms = [_form(a, spec.allow_name) for a in spec.accept]
    correct = spec.accept[0] if spec.accept else None
    yes_no = _asks_yes_no(forms)
    answer = _answer_of(text, yes_no)
    if not answer:
        return CheckResult(Outcome.NO_RESPONSE, correct_answer=correct)
    groups = [[normalize_answer(p) for p in group] for group in spec.required]
    expect = _Expect.of(list(spec.accept) + [p for g in spec.required for p in g])

    def right(candidate: str) -> bool:
        if any(f.matches(candidate) for f in forms):
            return True
        if groups:
            return all(any(contains_words(candidate, p) for p in g) for g in groups)
        return any(f.inside(candidate) for f in forms)  # DI-128: an accepted answer with words around it

    if any(f.matches(answer) for f in forms):
        return CheckResult(Outcome.CORRECT, normalized=answer, correct_answer=correct)

    # DI-128: an accepted answer may quote the error it corrects (a DIAG item: "Eated sai, phải là ate: …").
    # A wrong phrase or an error pattern that an accepted answer itself holds is then a quote, not an error,
    # when the answer is right otherwise.
    quoted_codes = {c for a in spec.accept for c in _detect(normalize_answer(a), a, expect)}
    quoting = right(answer)

    for pattern, mis in spec.wrong_answers.items():
        wrong = _answer_of(pattern, yes_no)
        if quoting and any(contains_words(f.text, wrong) for f in forms):
            continue
        if wrong and (answer == wrong or contains_words(answer, wrong)):
            codes = _detect(answer, text, expect)
            code = ctx.misconception_codes.get(mis) or (str(_worst(codes, ctx)) if codes else None)
            en = EnCode(code) if code else EnCode.MEANING
            return _wrong(en, ctx, answer, correct, mis=mis, confidence=0.9, codes=codes)

    vocabulary = {w for f in forms for w in f.text.split()} | {
        w for g in groups for p in g for w in p.split()
    }
    repaired = _repair(answer, vocabulary)
    codes = _detect(repaired, text, expect)
    if codes and not (quoting and set(codes) <= quoted_codes):
        return _diagnosed(codes, ctx, answer, correct)
    if right(answer):
        return CheckResult(Outcome.CORRECT, normalized=answer, correct_answer=correct)
    if repaired != answer and right(repaired):
        return _wrong(EnCode.SLIP, ctx, answer, correct, codes=[EnCode.SLIP])
    met = [any(contains_words(answer, p) for p in g) for g in groups]
    if any(met):
        missing = [i for i, ok in enumerate(met) if not ok]
        return CheckResult(
            Outcome.PARTIAL, normalized=answer, correct_answer=correct, detail={"missing_groups": missing}
        )
    if looks_vietnamese(answer):
        return _l1(answer, correct)
    return _wrong(None, ctx, answer, correct)


# --------------------------------------------------------------------------- word order


def check_word_order(spec: WordOrderSpec, text: str, ctx: EnglishContext = NO_CONTEXT) -> CheckResult:
    orders = [normalize_answer(" ".join(o)) for o in spec.accept]
    correct = " ".join(spec.accept[0]) if spec.accept else None
    answer = _answer_of(text, yes_no=True)
    if not answer:
        return CheckResult(Outcome.NO_RESPONSE, correct_answer=correct)
    if answer in orders:
        return CheckResult(Outcome.CORRECT, normalized=answer, correct_answer=correct)
    given = sorted(normalize_answer(" ".join(spec.tokens)).split())
    if sorted(answer.split()) == given:  # every word, in a wrong order: the structure (DI-107)
        return _wrong(EnCode.STRUCTURE, ctx, answer, correct, codes=[EnCode.STRUCTURE])
    vocabulary = set(given)
    repaired = _repair(answer, vocabulary)
    codes = _detect(repaired, text, _Expect.of([" ".join(o) for o in spec.accept]))
    if codes:
        return _diagnosed(codes, ctx, answer, correct)
    if repaired != answer and repaired in orders:
        return _wrong(EnCode.SLIP, ctx, answer, correct, codes=[EnCode.SLIP])
    if looks_vietnamese(answer):
        return _l1(answer, correct)
    return _wrong(None, ctx, answer, correct)


# --------------------------------------------------------------------------- entry points


def check_english(spec: EnglishSpec, text: str, ctx: EnglishContext = NO_CONTEXT) -> CheckResult:
    """Check one answer against an English spec. Never calls an LLM."""
    if isinstance(spec, PhraseSpec):
        return check_phrase(spec, text, ctx)
    return check_word_order(spec, text, ctx)


_STOP = frozenset({"yes", "no", "the", "and", "you", "did", "not", "was", "were"})


def _vocabulary(spec: EnglishSpec) -> set[str]:
    texts = (
        [*spec.accept, *(p for g in spec.required for p in g)]
        if isinstance(spec, PhraseSpec)
        else list(spec.tokens)
    )
    return {w for t in texts for w in normalize_answer(t).split() if len(w) >= 3 and w not in _STOP}


def check_english_item(item: Any, text: str, pkg: Any) -> CheckResult:
    """The checker of an item whose answer is ``phrase`` or ``word_order``: first what the message is (a
    help request, "cô nói lại", silence...: ``student_intent``, as for Mathematics), then the answer.

    The package must be an English one: an English answer in a Mathematics package is an error, never a
    silent fallback (english-module-rules S1, the test against a forgotten ``subject``).
    """
    if _field(pkg, "subject", None) != "english":
        raise ValueError(f"an English answer in a package of subject {_field(pkg, 'subject', None)!r}")
    spec = english_spec(item.answer)
    if spec is None:
        raise TypeError(f"not an English answer type: {_field(item.answer, 'type', None)!r}")
    words = set(normalize_answer(text).split())
    intent = read_intent(text, has_answer=bool(words & _vocabulary(spec)))
    if intent is not None:
        return CheckResult(intent)
    ctx = context_for(list(item.kc_ids), list(_field(pkg, "misconceptions", ()) or ()))
    return check_english(spec, text, ctx)
