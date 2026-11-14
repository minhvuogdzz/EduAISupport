"""ENG-5a: the validator of an English session (ADR-065, DI-137, DI-138; english-module-rules.md P3, V2b).

Every case is a sentence a tutor could say on an item of Unit 11 "Family time". The Math validator's own
verdicts are pinned by ``test_english_prompts.py::test_math_prompts_identical_to_before_eng5a``.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext
from cavat.modules.tutor.english_validator import (
    display_text,
    english_leak,
    english_spans,
    english_speech,
    is_english_word,
    is_say_after_me,
    mark_english,
    math_terms_in,
    normalize_en,
    speech_segments,
    unit_lexicon,
    validate_english_message,
    validator_for,
)
from cavat.modules.tutor.validator import validate_message

UNIT = Path(__file__).resolve().parents[3] / "docs/pedagogy/english-g5/unit-11-family-time"
PACKAGES = [load_lesson_package(p) for p in sorted(UNIT.glob("lesson-*.yaml"))]
ITEMS = {item.id: (item, pkg) for pkg in PACKAGES for item in pkg.items}
LEXICON = unit_lexicon(PACKAGES)
MATH_LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"


def ctx_for(item_id, move=Move.HINT, **kw):
    item, pkg = ITEMS[item_id]
    state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
    return RenderContext(decision=PolicyDecision(move=move), item=item, package=pkg, state=state, **kw)


def codes(text, item_id="U11-WD-PR-01", move=Move.HINT, say_after_me=None, **kw):
    result = validate_english_message(
        text, ctx_for(item_id, move, **kw), lexicon=LEXICON, say_after_me=say_after_me
    )
    return set(result.codes)


# ---------------------------------------------------------------------------------------------- marks


@pytest.mark.parametrize(
    ("text", "marked"),
    [
        ("Con nói theo cô: We swam in the sea.", "Con nói theo cô: [[en: We swam in the sea.]]"),
        (
            "Bạn hỏi 'Did you swim?' thì con trả lời thế nào?",
            "Bạn hỏi [[en: Did you swim?]] thì con trả lời thế nào?",
        ),
        ("Con chọn nhé: buy hay bought?", "Con chọn nhé: [[en: buy]] hay [[en: bought?]]"),  # unit words
        (
            "Con kể: We ate seafood in Nha Trang con nhé.",
            "Con kể: [[en: We ate seafood in Nha Trang]] con nhé.",
        ),
        ("Sau did, động từ giữ nguyên.", "Sau [[en: did]], động từ giữ nguyên."),
        ("Con nói tiếp nhé: We b… souvenirs.", "Con nói tiếp nhé: [[en: We b… souvenirs.]]"),
        ("Con nói theo cô: [[en: Yes, I did.]]", "Con nói theo cô: [[en: Yes, I did.]]"),  # kept as written
        ("Hôm qua con đi chơi ở Nha Trang à?", "Hôm qua con đi chơi ở Nha Trang à?"),  # no English
    ],
)
def test_mark_english(text, marked):
    assert mark_english(text, LEXICON) == marked
    assert mark_english(marked, LEXICON) == marked  # idempotent


def test_speech_and_screen_text():
    screen, speech = english_speech("Con nói theo cô: 'We swam in the sea.' Con nói nhé?")
    assert speech == "Con nói theo cô: [[en: We swam in the sea.]] Con nói nhé?"
    assert screen == "Con nói theo cô: We swam in the sea. Con nói nhé?"
    assert speech_segments(speech) == [
        ("vi", "Con nói theo cô:"),
        ("en", "We swam in the sea."),
        ("vi", "Con nói nhé?"),
    ]
    assert english_spans(speech) == ["We swam in the sea."]
    assert display_text("[[en: Yes, I did.]]") == "Yes, I did."


@pytest.mark.parametrize("word", ["swim", "did", "yes", "seafood", "photos", "we", "the", "you", "bought"])
def test_english_words(word):
    assert is_english_word(word)


@pytest.mark.parametrize("word", ["con", "hay", "so", "qua", "nhà", "bơi", "Nha", "a", "I", "sai"])
def test_vietnamese_or_ambiguous_words(word):
    assert not is_english_word(word, LEXICON)


def test_unit_words_make_ambiguous_syllables_english():
    assert not is_english_word("buy") and is_english_word("buy", LEXICON)
    assert not is_english_word("boat") and is_english_word("boat", LEXICON)


def test_lexicon_holds_the_unit_words_and_not_others():
    for word in ("swam", "seashells", "souvenirs", "didn't", "did", "not", "walked", "bay"):
        assert word in LEXICON
    for word in ("football", "played", "computer", "decimal", "qua", "con"):
        assert word not in LEXICON


def test_normalize_en_follows_di110():
    assert normalize_en("No, I didn't!  I TOOK photos.") == "no i did not i took photos"
    assert normalize_en("It's Mai’s book.") == "it is mai s book"


# ---------------------------------------------------------------------------------------------- leak


@pytest.mark.parametrize(
    ("item_id", "text"),
    [
        ("U11-WD-PR-01", "Con nói: We ate seafood. Con nói lại được không?"),
        ("U11-WD-PR-01", "Có phải [[en: We ate seafood]] không con?"),  # a question still tells
        ("U11-WD-PR-01", "con trả lời là we ATE some seafood nhé, đúng không?"),  # case, extra "some"
        (
            "U11-PA-PR-03",
            "Câu đúng là [[en: No, I did not. I took photos there.]] Con nói lại nhé?",
        ),  # DI-110
        ("U11-DY-TR-01", "Con trả lời: [[en: Yes, I did. I walked on the beach with my grandparents.]] nhé?"),
        ("U11-WD-TR-01", "Con nói: [[en: We bought souvenirs.]] được không?"),
        ("U11-DY-PR-02", "Con hỏi bạn: [[en: Did you collect seashells?]] nhé?"),
        ("U11-TR-TR-01", "Con kể: [[en: We took a boat trip and ate seafood.]] nhé?"),
    ],
)
def test_english_leak_detected(item_id, text):
    assert "ANSWER_LEAK" in codes(text, item_id)


@pytest.mark.parametrize(
    ("item_id", "text"),
    [
        # H2: the pattern with ANOTHER sentence
        ("U11-WD-PR-01", "Ví dụ: [[en: We swam in the sea.]] Còn ở Nha Trang, cả nhà con làm gì?"),
        # H4: part of the sentence
        ("U11-WD-PR-01", "Con nói tiếp giúp cô nhé: [[en: We a… seafood.]]"),
        # H5: a choice, the right form among two
        ("U11-WD-PR-01", "Con chọn nhé: [[en: eat]] hay [[en: ate]]?"),
        # the question's own words are not the answer
        ("U11-WD-PR-01", "Bạn hỏi: [[en: What did your family do in Nha Trang?]] Con trả lời bằng We nhé?"),
        # whole words: "eat seafood" is not "ate seafood"
        ("U11-VO-PR-02", "Cụm [[en: eat seafood]] là ăn hải sản. Hôm qua đã ăn rồi thì con nói sao?"),
        # a reason item (level C) is answered in Vietnamese: its words are not an English target
        ("U11-WD-PR-05", "Con nhớ nhé: câu hỏi có [[en: did]] rồi. Vậy động từ sau đó thế nào?"),
    ],
)
def test_no_leak_on_a_hint_that_keeps_the_target(item_id, text):
    assert "ANSWER_LEAK" not in codes(text, item_id)


def test_say_after_me_may_read_the_model_sentence_first():
    text = "Con nói theo cô: [[en: We ate seafood.]] Con nói theo nhé?"
    assert "ANSWER_LEAK" in codes(text, "U11-WD-PR-01")
    assert "ANSWER_LEAK" not in codes(text, "U11-WD-PR-01", say_after_me=True)  # DI-108
    assert "ANSWER_LEAK" not in codes(text, "U11-WD-PR-01", move=Move.FULL_EXPLANATION)  # H7
    assert "ANSWER_LEAK" not in codes(text, "U11-WD-PR-01", answer_revealed=True)
    assert "ANSWER_LEAK" not in codes(text, "U11-WD-PR-01", move=Move.CONFIRM_ADVANCE)  # after it is solved


def test_say_after_me_from_the_item_kind():
    assert is_say_after_me(SimpleNamespace(kind="say_after_me"))
    assert not is_say_after_me(SimpleNamespace(kind="practice"))
    item, _ = ITEMS["U11-DY-CP-01"]
    assert not is_say_after_me(item)  # no ``kind`` until ENG-3b: the session passes the completion list
    assert is_say_after_me(item, True)


def test_choice_item_singling_out_the_right_option():
    item, _ = ITEMS["U11-VO-CC-01"]
    assert english_leak("Đáp án là nhặt vỏ sò đó con.", item)
    assert english_leak("nhặt vỏ sò, mua quà hay đi bơi, con chọn cái nào?", item) is None


# ---------------------------------------------------------------------------------------------- other subject


@pytest.mark.parametrize(
    "text",
    [
        "Số thập phân 0,5 thì sao con? Giờ con nói câu tiếng Anh nhé?",
        "Mình tính diện tích hình thang trước nhé?",
        "Con thử 0,5 + 0,25 = 0,75 nhé?",
        "Đây là phân số, con biết không?",
    ],
)
def test_math_term_rejected_in_english_session(text):
    assert "MATH_TERM" in codes(text)


@pytest.mark.parametrize(
    "text",
    [
        "Con so sánh hai câu nhé: [[en: Did you swim?]] và [[en: Do you swim?]] Câu nào hỏi chuyện đã qua?",
        "Câu đó của môn Toán, mình để lúc khác nhé. Giờ con trả lời bạn bằng câu bắt đầu bằng We nhé?",
    ],
)
def test_ordinary_words_and_the_subject_name_pass(text):
    assert "MATH_TERM" not in codes(text)


def test_math_terms_list():
    assert math_terms_in("Diện tích tam giác bằng 6") == ["diện tích", "tam giác"]
    assert math_terms_in("3 x 4 = 12")  # arithmetic
    assert math_terms_in("Con so sánh do và did nhé") == []


def test_math_validator_rejects_an_english_sentence():
    """P3 the other way: the Math validator, unchanged, refuses English in a Math lesson."""
    pkg = load_lesson_package(MATH_LESSON)
    item = pkg.items[0]
    ctx = RenderContext(
        decision=PolicyDecision(move=Move.HINT),
        item=item,
        package=pkg,
        state=ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE),
    )
    assert (
        "FOREIGN_TEXT"
        in validate_message("We ate seafood in Nha Trang. Con so sánh phần nguyên nhé?", ctx).codes
    )


# ---------------------------------------------------------------------------------------------- unit, voice


def test_english_outside_the_unit_rejected():
    assert "OUT_OF_UNIT_ENGLISH" in codes("Con nói theo cô: [[en: We played football.]] Con nói nhé?")
    assert "OUT_OF_UNIT_ENGLISH" in codes("Con nói theo cô: We visited a beautiful computer. Con nói nhé?")
    assert "OUT_OF_UNIT_ENGLISH" not in codes("Ví dụ: [[en: We swam in the sea.]] Còn ở Nha Trang thì sao?")


@pytest.mark.parametrize(
    "text",
    [
        "We swam in the sea.",  # no Vietnamese at all
        "[[en: Did you swim?]]",
    ],
)
def test_bare_english_rejected(text):
    assert "BARE_ENGLISH" in codes(text)


@pytest.mark.parametrize(
    "text",
    [
        "Con nói theo cô: [[en: swim]]. Con nói nhé?",  # a lone word after a lead-in with a colon
        "Từ [[en: swim]] nghĩa là bơi, con đặt câu được không?",  # a word inside a Vietnamese sentence
        "Con chọn nhé: [[en: buy]] hay [[en: bought]]?",
        "Ví dụ: [[en: We swam in the sea.]] Còn con thì sao?",
    ],
)
def test_english_in_a_sentence_passes(text):
    assert "BARE_ENGLISH" not in codes(text)


def test_broken_marks():
    assert "BROKEN_MARKER" in codes("Con nói theo cô: [[en: We swam in the sea. Con nói nhé?")
    assert "BROKEN_MARKER" in codes("Con nói theo cô: [[en: con bơi ở biển]] nhé?")


# ---------------------------------------------------------------------------------------------- shared checks


def test_quoted_english_question_is_not_a_second_question():
    assert not codes("Bạn hỏi: [[en: Did you swim?]] Con trả lời thế nào?", "U11-DY-PR-01") & {
        "MULTIPLE_QUESTIONS",
        "MISSING_QUESTION",
    }
    assert "MULTIPLE_QUESTIONS" in codes("Con nhớ chưa? Bạn hỏi gì? Con trả lời thế nào?")


def test_english_question_closing_the_turn_counts_as_its_question():
    assert "MISSING_QUESTION" not in codes(
        "Giờ con hỏi bạn bằng tiếng Anh nhé: [[en: Did you swim?]]", "U11-DY-PR-01"
    )


def test_vietnamese_checks_still_apply():
    assert "WRONG_ADDRESS" in codes("Em thử nói lại câu bắt đầu bằng We nhé?")
    assert "PII_REQUEST" in codes("Nhà con ở đâu, số điện thoại là gì?")
    assert "INTELLIGENCE_PRAISE" in codes("Con thông minh quá! Con nói tiếp nhé?")
    long = "Con nói theo cô: [[en: We took a boat trip around the bay.]] " + "nhé " * 60 + "con nói nhé?"
    assert "TOO_LONG" in codes(long)


@pytest.mark.parametrize(
    ("item_id", "move", "text"),
    [
        (
            "U11-WD-PR-01",
            Move.HINT,
            "Câu hỏi có [[en: did]] là chuyện đã qua. Vậy sau We, con đổi eat thành gì?",
        ),
        ("U11-WD-PR-01", Move.PROBE, "Con nói [[en: We eat seafood]]. Con nghĩ chuyện này xảy ra lúc nào?"),
        (
            "U11-DY-PR-01",
            Move.HINT,
            "Bạn hỏi bằng [[en: Did]], vậy con trả lời [[en: Yes, I …]] bằng từ nào?",
        ),
        (
            "U11-WD-PR-01",
            Move.CONFIRM_ADVANCE,
            "Con dùng đúng dạng quá khứ rồi. Mình sang câu tiếp theo nhé.",
        ),
        ("U11-WD-PR-01", Move.REDIRECT, "Giờ mình ôn Tiếng Anh nhé. Bạn hỏi cả nhà con làm gì ở Nha Trang?"),
    ],
)
def test_good_unit11_turns_pass(item_id, move, text):
    assert codes(text, item_id, move) == set()


def test_validator_for_picks_by_subject():
    assert validator_for("math") is validate_message
    english = validator_for("english", lexicon=LEXICON)
    assert english("Con nói: We ate seafood. Con nói lại nhé?", ctx_for("U11-WD-PR-01")).codes
    with pytest.raises(ValueError):
        validator_for("english")
    for bad in (None, "", "Math", "history"):
        with pytest.raises(ValueError):
            validator_for(bad, lexicon=LEXICON)
