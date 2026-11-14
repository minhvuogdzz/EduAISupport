"""English checker (ENG-4, ADR-063): every row of the error table DI-107, the normalization DI-110, word
boundaries, real sentences of Unit 11 "Family time", the dispatch by answer type. Offline, no model."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from cavat.core.en_text import ANSWER_CONTRACTIONS, normalize_answer
from cavat.core.pedagogy import ErrorClass, Outcome
from cavat.modules.assessment import answer_check, math_checker
from cavat.modules.assessment.english_checker import (
    WRONG_ED,
    EnCode,
    EnglishContext,
    PhraseSpec,
    WordOrderSpec,
    check_english,
    check_english_item,
    context_for,
    english_spec,
    error_class_of,
    looks_vietnamese,
)
from cavat.modules.content.chapter_package import load_chapter

ROOT = Path(__file__).resolve().parents[3]
UNIT = load_chapter(ROOT / "docs/pedagogy/english-g5/unit-11-family-time/chapter.yaml")
MATH = load_chapter(ROOT / "docs/pedagogy/math-g5/chuong-so-thap-phan/chapter.yaml")


def check(spec, text, ctx=None):
    return check_english(spec, text, ctx or EnglishContext())


def code(result) -> str | None:
    return result.detail.get("en_code")


ATE = PhraseSpec(accept=("We ate seafood.",), required=(("ate seafood", "ate some seafood"),))
WALKED = PhraseSpec(
    accept=("Yes, I did. I walked on the beach with my grandparents.", "Yes, I did."),
    required=(("yes i did",), ("walked on the beach",)),
)
DID_YOU = PhraseSpec(accept=("Did you buy souvenirs?",))
WHAT_DID = PhraseSpec(accept=("What did your family do in Ha Long?",), allow_name=True)
BOUGHT = PhraseSpec(
    accept=("We bought souvenirs.",), required=(("bought souvenirs", "bought some souvenirs"),)
)
FAMILY = PhraseSpec(accept=("This is my grandmother.",))


# --------------------------------------------------------------------------- DI-107, row by row


def test_short_answer_that_does_not_match_did_is_conceptual():
    for text in ("Yes, I do.", "yes i will", "No, I don't.", "Yes, we do"):
        r = check(WALKED, text)
        assert r.outcome == Outcome.WRONG and code(r) == "EN_SHORT_ANSWER", text
        assert r.error_class == ErrorClass.CONCEPTUAL


def test_present_where_the_answer_tells_what_happened_is_conceptual():
    for text in ("We eat seafood.", "we eats seafood", "My family eat seafood."):
        r = check(ATE, text)
        assert code(r) == "EN_TENSE" and r.error_class == ErrorClass.CONCEPTUAL, text
    assert code(check(WALKED, "Yes, I did. I walk on the beach.")) == "EN_TENSE"


def test_a_confused_phrase_listed_by_the_teacher_is_a_meaning_error_with_its_misconception():
    spec = PhraseSpec(accept=("We ate seafood.",), wrong_answers={"We collected seashells": "ENG5-U11-M06"})
    r = check(spec, "We collected seashells.")
    assert r.outcome == Outcome.WRONG and r.misconception_id == "ENG5-U11-M06"
    assert code(r) == "EN_MEANING" and r.error_class == ErrorClass.CONCEPTUAL
    assert r.misconception_confidence == 0.9
    # the code the content gives the misconception wins over the default
    ctx = EnglishContext(misconception_codes={"ENG5-U11-M07": "EN_TENSE"}, known_targets=True)
    spec = PhraseSpec(accept=("We ate seafood.",), wrong_answers={"we eat seafood": "ENG5-U11-M07"})
    r = check(spec, "We eat seafood in Nha Trang.", ctx)
    assert (r.misconception_id, code(r), r.error_class) == ("ENG5-U11-M07", "EN_TENSE", ErrorClass.CONCEPTUAL)


@pytest.mark.parametrize(
    ("spec", "text"),
    [
        (WHAT_DID, "What your family do in Ha Long?"),  # quên did
        (WHAT_DID, "What do your family do in Ha Long?"),  # do thay did
        (DID_YOU, "You buy souvenirs?"),  # quên did
        (DID_YOU, "Do you buy souvenirs?"),
        (DID_YOU, "Did you bought souvenirs?"),  # quá khứ sau did
        (PhraseSpec(accept=("Did you collect seashells?",)), "Did you collected seashells?"),
    ],
)
def test_the_target_structure_broken_is_procedural_on_its_node(spec, text):
    r = check(spec, text)
    assert r.outcome == Outcome.WRONG and code(r) == "EN_STRUCTURE", text
    assert r.error_class == ErrorClass.PROCEDURAL


def test_words_in_a_wrong_order_are_a_structure_error():
    spec = WordOrderSpec(
        tokens=("swim", "you", "Did", "Sunday", "last", "?"),
        accept=(("Did", "you", "swim", "last", "Sunday", "?"),),
    )
    assert check(spec, "Did you swim last Sunday?").outcome == Outcome.CORRECT
    assert check(spec, "did you swim last sunday").outcome == Outcome.CORRECT
    r = check(spec, "You did swim last Sunday?")
    assert code(r) == "EN_STRUCTURE" and r.error_class == ErrorClass.PROCEDURAL
    assert code(check(spec, "Did you swam last Sunday?")) == "EN_STRUCTURE"
    assert code(check(spec, "Did you swim last Sundey?")) == "EN_SLIP"
    assert check(spec, "Did you go to school?").outcome == Outcome.WRONG


def test_a_structure_or_verb_form_error_on_a_node_that_does_not_teach_it_is_format():
    ctx = EnglishContext(node_codes={"EN_TENSE": "ENG5-U11-M04"}, known_targets=True)
    r = check(DID_YOU, "You buy souvenirs?", ctx)
    assert code(r) == "EN_STRUCTURE" and r.error_class == ErrorClass.FORMAT
    target = EnglishContext(node_codes={"EN_STRUCTURE": "ENG5-U11-M01"}, known_targets=True)
    r = check(DID_YOU, "You buy souvenirs?", target)
    assert r.error_class == ErrorClass.PROCEDURAL and r.misconception_id == "ENG5-U11-M01"


def test_ed_on_an_irregular_verb_is_a_verb_form_error():
    for text in ("We buyed souvenirs.", "We boughted souvenirs"):
        r = check(BOUGHT, text)
        assert code(r) == "EN_VERB_FORM" and r.error_class == ErrorClass.PROCEDURAL, text
    assert code(check(ATE, "We eated seafood")) == "EN_VERB_FORM"
    assert {"buyed", "eated", "taked", "swimmed", "goed", "tooked"} <= WRONG_ED
    assert not {"seed", "need", "bed", "visited", "walked"} & WRONG_ED


def test_one_letter_off_in_a_long_word_is_a_slip_and_in_a_short_word_is_wrong():
    r = check(FAMILY, "This is my grandmoter.")
    assert code(r) == "EN_SLIP" and r.error_class == ErrorClass.FORMAT and r.outcome == Outcome.WRONG
    assert code(check(PhraseSpec(accept=("This is my mother.",)), "This is my mothr")) == "EN_SLIP"
    r = check(ATE, "We ste seafood.")  # "ate" has three letters: not a slip
    assert r.outcome == Outcome.WRONG and code(r) != "EN_SLIP"


def test_a_transcript_said_with_an_accent_is_graded_on_its_words():
    # EN_PRONUNCIATION is not an error: the checker grades the confirmed transcript as it is.
    assert check(ATE, "we ate seafood").outcome == Outcome.CORRECT
    assert EnCode.PRONUNCIATION not in {code(check(ATE, t)) for t in ("We ate seafood.", "we eat seafood")}


def test_a_right_meaning_in_vietnamese_is_not_graded_the_first_time():
    r = check(ATE, "nhà con ăn hải sản")
    assert r.outcome == Outcome.UNPARSEABLE and r.error_class == ErrorClass.L1 and code(r) == "EN_L1"
    assert looks_vietnamese("nha con an hai san") and not looks_vietnamese("we ate seafood")
    assert error_class_of("EN_L1") == ErrorClass.L1


def test_the_most_serious_error_of_a_sentence_wins():
    r = check(ATE, "We eat seafod.")  # present (CONCEPTUAL) and a slip (FORMAT)
    assert code(r) == "EN_TENSE" and r.error_class == ErrorClass.CONCEPTUAL
    r = check(WALKED, "Yes, I do. I walk on the beach.")  # short answer and present: both CONCEPTUAL
    assert code(r) == "EN_SHORT_ANSWER" and set(r.detail["en_codes"]) == {"EN_SHORT_ANSWER", "EN_TENSE"}
    r = check(DID_YOU, "Did you buyed souvenirs?")  # structure and verb form: both PROCEDURAL
    assert code(r) == "EN_STRUCTURE"


def test_every_code_has_its_class():
    ctx = EnglishContext()
    assert {c: error_class_of(c, ctx) for c in EnCode if c != EnCode.PRONUNCIATION} == {
        EnCode.SHORT_ANSWER: ErrorClass.CONCEPTUAL,
        EnCode.TENSE: ErrorClass.CONCEPTUAL,
        EnCode.MEANING: ErrorClass.CONCEPTUAL,
        EnCode.STRUCTURE: ErrorClass.PROCEDURAL,
        EnCode.VERB_FORM: ErrorClass.PROCEDURAL,
        EnCode.SLIP: ErrorClass.FORMAT,
        EnCode.L1: ErrorClass.L1,
    }
    with pytest.raises(ValueError):
        error_class_of(EnCode.PRONUNCIATION)


# --------------------------------------------------------------------------- DI-110


@pytest.mark.parametrize(
    "text",
    ["We ate seafood.", "we ate seafood", "WE ATE SEAFOOD!!", "  We   ate,  seafood . ", "We ate seafood…"],
)
def test_case_punctuation_and_spaces_are_not_errors(text):
    assert check(PhraseSpec(accept=("We ate seafood.",)), text).outcome == Outcome.CORRECT


@pytest.mark.parametrize(("short", "full"), ANSWER_CONTRACTIONS)
def test_every_contraction_of_the_table_is_its_full_form(short, full):
    assert normalize_answer(f"x {short} y") == f"x {full} y"
    assert normalize_answer(f"X {short.upper()} y") == f"x {full} y"
    assert normalize_answer(f"x {short.replace(chr(39), '’')} y") == f"x {full} y"  # curly apostrophe


def test_contractions_work_both_ways_and_others_are_not_expanded():
    no = PhraseSpec(accept=("No, I didn't.",))
    assert check(no, "No, I did not.").outcome == Outcome.CORRECT
    assert check(PhraseSpec(accept=("No, I did not.",)), "No, I didn't").outcome == Outcome.CORRECT
    assert check(PhraseSpec(accept=("It's my mother.",)), "It is my mother").outcome == Outcome.CORRECT
    # "don't" is not in the table of DI-110: it is not "do not" (no variant without the owner, rule N4)
    assert normalize_answer("I don't") == "i dont"
    assert check(PhraseSpec(accept=("No, I do not.",)), "No, I don't.").outcome != Outcome.CORRECT


def test_yes_or_no_is_dropped_only_when_the_item_does_not_ask_it():
    assert check(ATE, "Yes, we ate seafood.").outcome == Outcome.CORRECT
    assert check(ATE, "No we ate seafood").outcome == Outcome.CORRECT
    asks = PhraseSpec(accept=("Yes, I did.",))
    assert check(asks, "Yes, I did").outcome == Outcome.CORRECT
    assert check(asks, "No, I didn't.").outcome == Outcome.WRONG
    assert check(asks, "I did").outcome == Outcome.WRONG


def test_another_place_name_is_accepted_only_when_the_answer_allows_it():
    for place in ("Da Nang", "Hue", "Ho Chi Minh City", "Sa Pa"):
        assert check(WHAT_DID, f"What did your family do in {place}?").outcome == Outcome.CORRECT
    strict = PhraseSpec(accept=("What did your family do in Ha Long?",))
    assert check(strict, "What did your family do in Ha Long?").outcome == Outcome.CORRECT
    assert check(strict, "What did your family do in Hue?").outcome != Outcome.CORRECT
    # the slot holds a name of one to three words, not a word of grammar or time
    for text in ("What did your family do in the summer?", "What did your family do in?"):
        assert check(WHAT_DID, text).outcome != Outcome.CORRECT, text
    # DI-128: an accepted answer with words after it is still the answer
    assert check(WHAT_DID, "What did your family do in Hue last summer?").outcome == Outcome.CORRECT


def test_vietnamese_courtesy_around_the_answer_is_not_part_of_it():
    assert check(ATE, "Dạ, we ate seafood ạ.").outcome == Outcome.CORRECT
    assert check(ATE, "We ate seafood cô ơi").outcome == Outcome.CORRECT


def test_an_unknown_normalizer_is_refused():
    with pytest.raises(ValueError):
        check(PhraseSpec(accept=("We ate seafood.",), normalize="en/2"), "We ate seafood.")


# --------------------------------------------------------------------------- word boundaries


def test_phrases_match_on_word_boundaries_only():
    assert check(ATE, "We ate seafood in Nha Trang.").outcome == Outcome.CORRECT
    assert check(ATE, "late seafood").outcome == Outcome.WRONG
    assert check(ATE, "we ate seafoodies").outcome == Outcome.WRONG
    swam = PhraseSpec(accept=("I swam.",), required=(("swam",),))
    assert check(swam, "I swamp").outcome != Outcome.CORRECT
    assert check(PhraseSpec(accept=("Did you swim?",)), "Did you swimming?").outcome != Outcome.CORRECT


def test_part_of_the_ideas_is_partial():
    spec = PhraseSpec(
        accept=("(1) Nha Trang (2) swam (3) seafood",), required=(("nha trang",), ("swam",), ("seafood",))
    )
    r = check(spec, "Nha Trang, swam")
    assert r.outcome == Outcome.PARTIAL and r.detail["missing_groups"] == [2]
    assert check(spec, "nha trang swam seafood").outcome == Outcome.CORRECT


def test_an_empty_answer_is_no_response():
    assert check(ATE, " ... ").outcome == Outcome.NO_RESPONSE


# --------------------------------------------------------------------------- Unit 11 sentences


def unit_items():
    """Items of Unit 11 whose answer is English (``phrase``, ``word_order``; ENG-3b, ADR-062)."""
    return [
        item_id
        for item_id in sorted(UNIT._items)
        if answer_check.is_english_answer(UNIT.item(item_id).answer)
    ]


UNIT_ITEMS = unit_items()


def grade(item_id, text):
    """The real path: the item and its lesson package as loaded, through the dispatch of the item loop."""
    return answer_check.check_answer(UNIT.item(item_id), text, UNIT.lesson_of(item_id))


def test_unit_11_has_english_sentences_to_check():
    assert len(UNIT_ITEMS) == 23 and UNIT.package.subject == "english"


@pytest.mark.parametrize("item_id", UNIT_ITEMS)
def test_the_accepted_answer_of_a_unit_11_item_is_correct(item_id):
    accepted = UNIT.item(item_id).answer.accept[0]
    for text in (accepted, accepted.lower().rstrip(".?!"), f"Dạ, {accepted}"):
        assert grade(item_id, text).outcome == Outcome.CORRECT, (item_id, text)


def test_the_teachers_wrong_answers_of_unit_11_give_their_misconception():
    seen = 0
    for item_id in UNIT_ITEMS:
        for wrong, mis in UNIT.item(item_id).answer.wrong_answers.items():
            r = grade(item_id, wrong)
            assert r.outcome == Outcome.WRONG and r.misconception_id == mis, (item_id, wrong, r)
            code_of = UNIT.lesson_of(item_id).misconception(mis).error_class
            assert code(r) == code_of, (item_id, wrong)
            seen += 1
    assert seen >= 14


def test_a_diag_answer_that_quotes_the_error_it_corrects_is_correct():
    """DI-128: "Eated sai, phải là ate" names the wrong form; it is the answer, not the error."""
    assert grade("U11-PA-PR-06", "Eated sai, phải là ate").outcome == Outcome.CORRECT
    assert grade("U11-PA-PR-06", "phải là ate ạ").outcome == Outcome.CORRECT
    r = grade("U11-PA-PR-06", "eated")
    assert r.outcome == Outcome.WRONG and r.misconception_id == "ENG5-U11-M05"
    assert grade("U11-WD-PR-06", "Buy sai, phải là bought").outcome == Outcome.CORRECT


def test_typical_errors_on_unit_11_items():
    cases = [
        ("U11-VO-PR-02", "We eat seafood.", "EN_TENSE", ErrorClass.CONCEPTUAL),
        ("U11-WD-PR-01", "We eats seafood.", "EN_TENSE", ErrorClass.CONCEPTUAL),
        ("U11-WD-TR-01", "We buyed souvenirs.", "EN_VERB_FORM", ErrorClass.FORMAT),  # taught by PAST
        ("U11-PA-PR-04", "His parents buyed some souvenirs.", "EN_VERB_FORM", ErrorClass.PROCEDURAL),
        ("U11-DY-TR-01", "Yes, I will. I walked on the beach.", "EN_SHORT_ANSWER", ErrorClass.CONCEPTUAL),
        ("U11-DY-PR-02", "You collect seashells?", "EN_STRUCTURE", ErrorClass.PROCEDURAL),
        ("U11-DY-PR-02", "Did you collected seashells?", "EN_STRUCTURE", ErrorClass.PROCEDURAL),
        ("U11-TR-PR-05", "Last summer, my family goed to Hue.", "EN_VERB_FORM", ErrorClass.FORMAT),
        ("U11-WD-PR-02", "We saw some intresting places.", "EN_SLIP", ErrorClass.FORMAT),
    ]
    for item_id, text, expected, cls in cases:
        r = grade(item_id, text)
        assert (r.outcome, code(r), r.error_class) == (Outcome.WRONG, expected, cls), (item_id, text, r)
    r = grade("U11-WD-PR-01", "We eats seafood.")  # the node's own misconception of the code
    assert r.misconception_id == "ENG5-U11-M07" and r.misconception_confidence == 0.7
    assert grade("U11-WD-PR-01", "nhà con ăn hải sản").error_class == ErrorClass.L1
    assert grade("U11-WD-PR-01", "con không biết").outcome == Outcome.HELP_REQUEST


def test_the_context_reads_the_error_class_of_the_misconceptions_of_the_item():
    lesson = UNIT.lesson_of("U11-WD-PR-01")
    ctx = context_for(["ENG5-U11-WHATDID"], lesson.misconceptions)
    assert ctx.node_codes == {"EN_TENSE": "ENG5-U11-M07", "EN_STRUCTURE": "ENG5-U11-M08",
                              "EN_MEANING": "ENG5-U11-M09"} and ctx.known_targets  # fmt: skip
    assert error_class_of("EN_VERB_FORM", ctx) == ErrorClass.FORMAT  # taught by PAST, not WHATDID
    assert error_class_of("EN_STRUCTURE", ctx) == ErrorClass.PROCEDURAL
    plain = [SimpleNamespace(id="X", kc_id="K")]
    assert not context_for(["K"], plain).known_targets


# --------------------------------------------------------------------------- dispatch


def english_item(answer, kc="ENG5-U11-WHATDID"):
    return SimpleNamespace(id="EN-1", kc_ids=[kc], answer=answer)


ENGLISH_PKG = SimpleNamespace(subject="english", misconceptions=[])


def test_the_spec_is_read_by_field_name_from_any_model():
    spec = english_spec({"type": "phrase", "accept": ["We ate seafood."], "required": [["ate seafood"]]})
    assert spec == PhraseSpec(accept=("We ate seafood.",), required=(("ate seafood",),))
    obj = SimpleNamespace(type="word_order", tokens=["you", "Did", "swim"], accept=[["Did", "you", "swim"]])
    assert english_spec(obj) == WordOrderSpec(tokens=("you", "Did", "swim"), accept=(("Did", "you", "swim"),))
    assert english_spec({"type": "numeric", "value": "1"}) is None


def test_an_english_answer_goes_to_the_english_checker():
    item = english_item(
        SimpleNamespace(type="phrase", accept=["We ate seafood."], required=[], allow_name=False)
    )
    assert answer_check.check_answer(item, "We ate seafood.", ENGLISH_PKG).outcome == Outcome.CORRECT
    r = answer_check.check_answer(item, "We eat seafood.", ENGLISH_PKG)
    assert code(r) == "EN_TENSE"


def test_a_message_that_is_not_an_answer_is_read_as_for_mathematics():
    item = english_item({"type": "phrase", "accept": ["We ate seafood."]})
    assert check_english_item(item, "con không biết", ENGLISH_PKG).outcome == Outcome.HELP_REQUEST
    assert check_english_item(item, "", ENGLISH_PKG).outcome == Outcome.NO_RESPONSE
    assert check_english_item(item, "We ate seafood", ENGLISH_PKG).outcome == Outcome.CORRECT


def test_an_english_answer_in_a_mathematics_package_is_an_error_not_a_fallback():
    item = english_item({"type": "phrase", "accept": ["We ate seafood."]})
    with pytest.raises(ValueError):
        check_english_item(item, "We ate seafood.", SimpleNamespace(subject="math"))
    with pytest.raises(ValueError):
        check_english_item(item, "We ate seafood.", SimpleNamespace())


def test_a_mathematics_answer_is_checked_exactly_as_before():
    texts = ["<", ">", "0,5", "A", "đúng", "sai", "123", "con không biết", "0,25; 0,3", "phần nguyên"]
    for lesson in MATH.lessons.values():
        for item in lesson.items:
            for text in texts:
                assert answer_check.check_answer(item, text, lesson) == math_checker.check_answer(
                    item, text, lesson
                )
