"""Tests for reading and writing numbers the Vietnamese way (T01)."""

import re
import unicodedata
from fractions import Fraction

import pytest
from cavat.modules.assessment.vi_numbers import (
    extract_numbers,
    fold,
    format_vi,
    normalize_text,
    parse_literal,
    parse_number,
    tolerant_pattern,
)


@pytest.mark.parametrize(
    ("text", "value", "form", "ambiguous"),
    [
        ("0,25", Fraction(1, 4), "decimal", False),
        ("0.25", Fraction(1, 4), "decimal", False),  # English decimal point, typed out of habit
        ("1.250", Fraction(5, 4), "decimal", True),  # 1,25 or 1250? Must be confirmed with the student
        ("12.500", Fraction(25, 2), "decimal", True),
        ("0.250", Fraction(1, 4), "decimal", False),  # "0.250" cannot be a thousands group
        ("1,250", Fraction(5, 4), "decimal", False),  # a comma is always the decimal separator
        ("1.234,5", Fraction(2469, 2), "decimal", False),
        ("1.234.567", Fraction(1234567), "integer", False),
        ("3/4", Fraction(3, 4), "fraction", False),
        ("3 / 4", Fraction(3, 4), "fraction", False),
        ("75%", Fraction(3, 4), "percent", False),
        ("0,5%", Fraction(1, 200), "percent", False),
        ("12", Fraction(12), "integer", False),
    ],
)
def test_parse_number(text, value, form, ambiguous):
    n = parse_number(text)
    assert n is not None
    assert (n.text, n.value, n.form, n.ambiguous_separator) == (text, value, form, ambiguous)


def test_decimal_keeps_its_written_digits():
    n = parse_number("0,50")
    assert (n.int_part, n.frac_part, n.value) == ("0", "50", Fraction(1, 2))
    assert parse_number("1.234,5").int_part == "1234"


@pytest.mark.parametrize("text", ["1,2,3", "1/0", "0,5/2", "0.123.456", "0.123,5", "không phẩy năm", ""])
def test_malformed_or_missing_numbers_are_skipped(text):
    assert extract_numbers(text) == []
    assert parse_number(text) is None


def test_extract_numbers_gives_reading_order_and_spans():
    text = "Con nghĩ 0,25 < 0,3; còn 3/4 = 75%"
    nums = extract_numbers(text)
    assert [n.text for n in nums] == ["0,25", "0,3", "3/4", "75%"]
    assert [text[n.start : n.end] for n in nums] == ["0,25", "0,3", "3/4", "75%"]
    assert nums[2].value == nums[3].value == Fraction(3, 4)


def test_extract_numbers_splits_a_list_on_separators():
    for text in ("0,3; 0,25; 0,305; 0,2", "0,3, 0,25, 0,305, 0,2", "0,3 0,25 0,305 0,2"):
        assert [n.text for n in extract_numbers(text)] == ["0,3", "0,25", "0,305", "0,2"]


def test_extract_numbers_reads_digits_next_to_letters():
    assert [n.text for n in extract_numbers("x=6")] == ["6"]
    assert [n.text for n in extract_numbers("0,x5")] == ["0", "5"]


def test_parse_literal():
    assert parse_literal("0,305").value == Fraction(61, 200)
    assert parse_literal(" 2,1 ").value == Fraction(21, 10)
    for bad in ("0,25 và 0,3", "abc", "", "0,25 m"):
        with pytest.raises(ValueError):
            parse_literal(bad)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (Fraction(1, 4), "0,25"),
        (Fraction(1, 2), "0,5"),
        (Fraction(5, 2), "2,5"),
        (Fraction(3, 20), "0,15"),
        (Fraction(1, 1000), "0,001"),
        (Fraction(-1, 4), "-0,25"),
        (Fraction(5), "5"),
        (Fraction(0), "0"),
        (Fraction(1234567, 1000), "1234,567"),
        (Fraction(1, 3), "1/3"),
        (Fraction(2, 3), "2/3"),
    ],
)
def test_format_vi(value, text):
    assert format_vi(value) == text


@pytest.mark.parametrize(
    "value", [Fraction(1, 4), Fraction(61, 200), Fraction(2469, 2), Fraction(12500), Fraction(1234567, 1000)]
)
def test_format_vi_reads_back(value):
    assert parse_literal(format_vi(value)).value == value


def test_fold_and_normalize_text():
    assert fold("  Bé   Hơn ") == "be hon"
    assert fold("Đúng rồi") == "dung roi"
    assert normalize_text("  Bằng   NHAU ") == "bằng nhau"
    assert normalize_text(unicodedata.normalize("NFD", "Bằng")) == "bằng"  # decomposed input


@pytest.mark.parametrize(
    ("phrase", "typed", "matches"),
    [
        ("bằng", "bằng", True),
        ("bằng", "bang", True),  # no diacritics at all
        ("bằng", "băng", True),  # some diacritics left out
        ("bằng", "bảng", False),  # "bảng" (table) is another word
        ("đúng", "dung", True),
        ("đúng", "đung", True),
        ("đúng", "dùng", False),  # "dùng" (use) is another word
        ("lớn hơn", "lon  hon", True),
        ("lớn hơn", "Lơn hơn", True),
        ("hoa", "hoan", False),  # whole words only
        ("hoa", "thoa", False),
        ("<", "0,25<0,3", True),  # signs need no spaces around them
    ],
)
def test_tolerant_pattern(phrase, typed, matches):
    assert bool(re.search(tolerant_pattern(phrase), normalize_text(typed))) is matches


def test_tolerant_pattern_covers_every_vietnamese_vowel():
    for vowel in "aăâeêioôơuưy":
        for tone in ("", "̀", "́", "̉", "̃", "̣"):
            letter = unicodedata.normalize("NFC", vowel + tone)
            pattern = tolerant_pattern(letter)
            assert re.fullmatch(pattern, letter)
            assert re.fullmatch(pattern, fold(letter))
    assert re.fullmatch(tolerant_pattern("đ"), "d")
