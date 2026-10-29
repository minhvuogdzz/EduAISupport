"""Audit decimal notation independently of model fluency; never reads an assessment key."""

import re
from fractions import Fraction

from cavat.core.vi_text import fold
from cavat.modules.assessment.vi_words import whole_number


def notation_facts(text: str) -> list[dict]:
    """Digits as WRITTEN, including trailing zeroes, rather than a rounded float."""
    facts = []
    for number in dict.fromkeys(re.findall(r"(?<![\w,])\d+,\d+(?![\d,])", text)):
        whole, part = number.split(",")
        facts.append(
            {
                "so": number,
                "phan_nguyen": whole,
                "phan_thap_phan": part,
                "so_chu_so_sau_dau_phay": len(part),
                "so_chu_so_0_trong_phan_thap_phan": part.count("0"),
            }
        )
    return facts[:10]


def claim_errors(text: str) -> list[str]:
    """Reject the false rule equating denominator zeroes with decimal zeroes.

    This checks a mathematical claim, not the student's intent or the tutor's next move.
    Unparsed language remains the independent semantic reviewer's responsibility.
    """
    errors = []
    for sentence in re.split(r"[.!?;]", fold(text.lower())):
        if re.search(r"\b(?:khong phai|chua dung|noi sai|noi nham|khong dung)\b", sentence):
            continue
        if re.search(r"(?:tuong ung|bang|theo) (?:voi )?so chu so (?:cua|trong) mau so", sentence):
            errors.append("Số chữ số sau dấu phẩy dựa vào số chữ số 0, không phải toàn bộ chữ số mẫu")
        if re.search(
            r"mau so.{0,55}(?:may|bao nhieu|mot|hai|ba|\d+) chu so (?:0|khong)"
            r".{0,35}(?:thi|nen).{0,15}phan thap phan.{0,55}chu so (?:0|khong)\b",
            sentence,
        ):
            errors.append("Số chữ số sau dấu phẩy khác với số chữ số 0 trong phần thập phân")
    counts = {
        "khong": 0,
        "mot": 1,
        "hai": 2,
        "ba": 3,
        "bon": 4,
        "nam": 5,
        "sau": 6,
        "bay": 7,
        "tam": 8,
        "chin": 9,
        "muoi": 10,
    }
    for match in re.finditer(
        r"(\d+,\d+)\s+(?:co|gom)\s+(\d+|khong|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)"
        r"\s+chu so (0|sau dau phay)\b",
        fold(text.lower()),
    ):
        part = match[1].split(",")[1]
        count = int(match[2]) if match[2].isdigit() else counts[match[2]]
        actual = part.count("0") if match[3] == "0" else len(part)
        if count != actual:
            errors.append(match[0])
    return errors


def fraction_facts(text: str) -> list[dict]:
    """A fraction's number of parts and size of each part, independent of the model's explanation."""
    facts = []
    for n, d in dict.fromkeys(re.findall(r"(?<![\w/])(\d+)\s*/\s*(\d+)(?![\d/])", text)):
        if int(d):
            facts.append(
                {
                    "phan_so": f"{n}/{d}",
                    "so_phan_da_lay": int(n),
                    "moi_phan": f"1/{d}",
                    "so_phan_bang_nhau_cua_mot_don_vi": int(d),
                }
            )
    return facts[:10]


def quantity_errors(text: str) -> list[str]:
    """Check explicit fraction-to-word quantity explanations, not arbitrary prose."""
    errors = []
    number_words = r"(?:không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mươi|trăm|nghìn|linh|lẻ)"
    pattern = (
        r"(\d+)\s*/\s*(\d+)\s*(?:=\s*\d+(?:[.,]\d+)?)?\s*"
        r"(?:vì có|nghĩa là|tức là|tương đương với)\s+("
        + number_words
        + r"(?:\s+"
        + number_words
        + r")*)\s+phần\s+"
        r"(mười|trăm|nghìn|hai|ba|bốn|năm|sáu|bảy|tám|chín)\b"
    )
    units = {"mười": 10, "trăm": 100, "nghìn": 1000}
    for match in re.finditer(pattern, text.lower()):
        rest = text[match.end() :].split(".", 1)[0][:60]
        if re.search(r"\b(?:và|thêm|cộng|nhân|lần)\b", rest):
            continue  # a decomposition/product needs more context than a direct quantity reading
        amount = whole_number(match[3].split())
        denominator = units.get(match[4]) or whole_number([match[4]])
        if int(match[2]) and amount is not None and denominator:
            if Fraction(int(match[1]), int(match[2])) != Fraction(amount, denominator):
                errors.append(match[0])
    return errors
