"""Misconceptions of a published chapter, made detectable (MISC-1, DI-54, ``misconception-rules/0.1.0``).

A plan built from the teacher's documents names the typical mistakes of each period, in the teacher's own
words and examples ("Bé viết 3 m 5 cm = 3,5 m", "Quên chia 2 khi tính diện tích tam giác"), but no wrong
answer points to them, so the tutor never recognises one. This module reads them deterministically:

1. **Families.** Each misconception is matched to the families of mistakes its name and description show
   (keywords and worked examples, folded), e.g. "quên chia 2" is FORGOT_HALF, "3,05 → 3,5" ZERO_PLACEHOLDER.
2. **Wrong answers.** For each numeric item, the wrong answer each family produces is computed from the
   item's own numbers: its key and the numbers of its stem (a × h for FORGOT_HALF when a × h : 2 is the
   key, the key without the zero after the comma for ZERO_PLACEHOLDER, a chained rounding...). A wrong
   answer equal to the key, or produced by two families, is dropped (it would not tell them apart).
3. **Which misconception.** Among the misconceptions of the item's lesson in that family: the one of the
   item's own period, else of the closest earlier period, else a critical one.
4. **Compare and order items** get the existing bug rules (``math_checker.BUG_RULES``) on the matching
   misconception: "dài hơn thì lớn hơn" is ``longer_is_larger``.

Only items without teacher-written wrong answers are changed; nothing is stored, the chapter is enriched
when it is loaded. Everything is a DI (rule 9): the families and their keywords are this module's reading.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations

from cavat.modules.assessment.vi_numbers import ParsedNumber, extract_numbers, format_vi, parse_literal
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.content.lesson_package import (
    ChoiceAnswer,
    Item,
    LessonPackage,
    Misconception,
    NumericAnswer,
)

RULES_VERSION = "misconception-rules/0.1.0"

# Family -> (keywords, patterns) on the folded name + description of a misconception.
FAMILIES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "ZERO_PLACEHOLDER": (
        ("so 0 giu cho", "bo so 0", "chu so 0 ngay sau"),
        (r"\d,0[1-9]\s*(?:→|=|thành)", r"thay vì \d+,0[1-9]", r"đúng:\s*\d+,0[1-9]", r"/10+\s*=\s*0,[1-9]"),
    ),
    "AREA_AS_LENGTH": (("dien tich nhu do dai",), (r"m²\s*=\s*10\s*dm²",)),
    "UNIT_STEP": (("so buoc khi doi", "doi nham don vi"), (r"\d+\s*g\s*=\s*\d+,\d+\s*kg",)),
    "MISSING_COMMA": (("quen dau phay",), ()),
    "ROUND_CHAIN": (("day chuyen",), ()),
    "ROUND_LOOK": (("nhin sai chu so", "nhin chinh hang"), ()),
    "ROUND_CARRY": (("nho sang", "quen nho"), (r"9,96",)),
    "LONGER_IS_LARGER": (("dai hon thi lon hon",), (r"125\s*>\s*5", r"125 lon hon 5")),
    "INTEGER_PART": (("so sanh sai phan nguyen",), ()),
    "FORGOT_HALF": (("quen chia 2",), ()),
    "FORGOT_DOUBLE": (("quen nhan 2",), ()),
    "BASES_MULTIPLIED": (("nhan hai day",), ()),
    "MISSING_PARENS": (("quen ngoac", "can ngoac"), (r"a \+ b × h",)),
    "SLANT_AS_HEIGHT": (("canh nghieng lam duong cao", "canh nghieng la chieu cao", "canh huyen"), ()),
}
BUG_RULE_OF = {"LONGER_IS_LARGER": "longer_is_larger", "INTEGER_PART": "ignore_integer_part"}

_AREA_UNITS = re.compile(r"(?:mm|cm|dm|km|m)²|\bha\b")
_OTHER_UNITS = re.compile(r"\b(?:mm|cm|dm|m|km|g|kg|yến|tạ|tấn|hm|dam)\b")
_POINTS = re.compile(r"\(\s*\d+(?:,\d+)?\s*điểm\s*\)")
_PLACE = {"hàng đơn vị": 0, "hàng phần mười": 1, "hàng phần trăm": 2, "hàng phần nghìn": 3}


def families(m: Misconception) -> set[str]:
    from cavat.core.vi_text import fold

    raw = f"{m.name} {m.description}"
    text = fold(raw.lower())
    found = set()
    for family, (words, patterns) in FAMILIES.items():
        if any(w in text for w in words) or any(re.search(p, raw.lower()) for p in patterns):
            found.add(family)
    return found


@dataclass(frozen=True)
class Wrong:
    value: Fraction
    family: str


# --------------------------------------------------------------------------- wrong answers of an item


def _numbers(stem: str) -> list[Fraction]:
    clean = _POINTS.sub(" ", stem)
    clean = re.sub(r"\b[a-e]\)", " ", clean)  # "a)", "b)" of a list
    return [n.value for n in extract_numbers(clean) if n.form in ("integer", "decimal") and n.value > 0]


def _strip_zero(key: ParsedNumber) -> Fraction | None:
    """3,05 -> 3,5; 0,008 -> 0,8: the zeros right after the comma dropped."""
    frac = key.frac_part
    if not frac.startswith("0") or not frac.strip("0"):
        return None
    return parse_literal(f"{key.int_part or '0'},{frac.lstrip('0')}").value


def _round(digits: str, place: int) -> Fraction:
    """Half up at ``place`` decimals, from the written number (exact)."""
    value = parse_literal(digits).value
    step = Fraction(1, 10**place)
    return (value / step + Fraction(1, 2)).__floor__() * step


def _chain(n: ParsedNumber, place: int) -> Fraction:
    """3,449 -> 3,45 -> 3,5: rounded one digit at a time from the last."""
    value = n.value
    for p in range(len(n.frac_part) - 1, place - 1, -1):
        step = Fraction(1, 10**p)
        value = (value / step + Fraction(1, 2)).__floor__() * step
    return value


def _looked_at_place(n: ParsedNumber, place: int) -> Fraction | None:
    """5,261 to tenths read as 5,2: the digit at the place itself decides, not the one after it."""
    digits = n.int_part + n.frac_part
    at = len(n.int_part) + place - 1
    if at < 0 or at >= len(digits):
        return None
    step = Fraction(1, 10**place)
    down = (n.value / step).__floor__() * step
    return down + step if int(digits[at]) >= 5 else down


def _no_carry(n: ParsedNumber, place: int) -> Fraction | None:
    """9,96 to tenths written 9,10: the digit at ``place`` becomes "10" instead of carrying."""
    digits = n.int_part + n.frac_part
    at = len(n.int_part) + place - 1  # index of the digit kept
    if place < 1 or at + 1 >= len(digits) or digits[at] != "9" or int(digits[at + 1]) < 5:
        return None
    kept = n.int_part if place == 0 else f"{n.int_part},{n.frac_part[: place - 1]}"
    text = f"{kept[:-1]}10" if place == 0 else f"{kept}10"
    try:
        return parse_literal(text).value
    except ValueError:
        return None


def wrong_answers(item: Item, key: ParsedNumber, topic: str = "") -> list[Wrong]:
    """The wrong answers the families produce for this item. ``topic``: the name of the item's period, which
    says the figure when the stem does not ("Đáy 22 m, cao 14 m: S = ……" in a period on triangles)."""
    stem = item.stem
    out: list[Wrong] = []
    rounding = "làm tròn" in stem.lower() or "≈" in stem
    if rounding:
        place = next((p for words, p in _PLACE.items() if words in stem.lower()), None)
        source = max(
            (n for n in extract_numbers(_POINTS.sub(" ", stem)) if n.form == "decimal"),
            key=lambda n: len(n.frac_part),
            default=None,
        )
        if place is not None and source is not None and len(source.frac_part) > place:
            chained = _chain(source, place)
            out.append(Wrong(chained, "ROUND_CHAIN"))
            looked = _looked_at_place(source, place)
            if looked is not None:
                out.append(Wrong(looked, "ROUND_LOOK"))
            carry = _no_carry(source, place)
            if carry is not None:
                out.append(Wrong(carry, "ROUND_CARRY"))
        return out
    stripped = _strip_zero(key)
    if _AREA_UNITS.search(stem):
        if stripped is not None:
            out.append(Wrong(stripped, "AREA_AS_LENGTH"))
    elif _OTHER_UNITS.search(stem) and key.form == "decimal":
        if stripped is not None:
            out.append(Wrong(stripped, "UNIT_STEP"))
        if len(_numbers(stem.split("=")[0])) == 1:  # one quantity ("750 g = …… kg"): one step too few or many
            out += [Wrong(key.value * 10, "UNIT_STEP"), Wrong(key.value / 10, "UNIT_STEP")]
    if stripped is not None:
        out.append(Wrong(stripped, "ZERO_PLACEHOLDER"))
    if key.form == "decimal" and not _AREA_UNITS.search(stem) and not _OTHER_UNITS.search(stem):
        out.append(Wrong(Fraction(int(key.int_part + key.frac_part)), "MISSING_COMMA"))  # 0,3 written 3
    lower = f"{stem} {topic}".lower()
    out += _geometry(_numbers(stem), key.value, "tam giác" in lower, "hình thang" in lower)
    return out


def _geometry(nums: list[Fraction], key: Fraction, triangle: bool, trapezoid: bool) -> list[Wrong]:
    out: list[Wrong] = []
    if len(nums) > 6:
        return out
    for x, y in permutations(nums, 2) if triangle and not trapezoid else ():
        if x * y / 2 == key:  # a triangle's area: a × h : 2
            out.append(Wrong(x * y, "FORGOT_HALF"))
            out += [Wrong(z * x / 2, "SLANT_AS_HEIGHT") for z in nums if z not in (x, y)]
        if 2 * x / y == key:  # a side from the area: S × 2 : a
            out.append(Wrong(x / y, "FORGOT_DOUBLE"))
    for a, b, h in permutations(nums, 3) if trapezoid else ():
        if (a + b) * h / 2 == key:  # a trapezoid: (a + b) × h : 2
            out += [
                Wrong((a + b) * h, "FORGOT_HALF"),
                Wrong(a * b * h / 2, "BASES_MULTIPLIED"),
                Wrong(a + b * h / 2, "MISSING_PARENS"),  # "8 + 4 × 5 : 2" (the teacher's example)
            ]
    return out


# --------------------------------------------------------------------------- choosing the misconception


def _pick(
    candidates: list[Misconception], node: str | None, order: list[str], earlier: set[str]
) -> str | None:
    """The item's own period first, then the closest earlier period; a critical one first in each."""

    allowed = [m for m in candidates if m.kc_id == node or m.kc_id in earlier]
    if not allowed:  # a misconception of a later period is not the child's yet
        return None

    def rank(m: Misconception) -> tuple[int, int, int]:
        if m.kc_id == node:
            return (0, 0 if m.severity == "CRITICAL" else 1, 0)
        return (1, -order.index(m.kc_id) if m.kc_id in order else 0, 0 if m.severity == "CRITICAL" else 1)

    return min(allowed, key=rank).id


def _ancestors(chapter: Chapter, node: str) -> set[str]:
    found: set[str] = set()
    todo = list(chapter.prerequisites(node))
    while todo:
        n = todo.pop()
        if n not in found:
            found.add(n)
            todo.extend(chapter.prerequisites(n))
    return found


def enrich_lesson(pkg: LessonPackage, chapter: Chapter) -> LessonPackage:
    by_family: dict[str, list[Misconception]] = {}
    for m in pkg.misconceptions:
        for family in families(m):
            by_family.setdefault(family, []).append(m)
    if not by_family:
        return pkg
    order = chapter.topological_order()
    items = [_enrich_item(it, by_family, chapter, order) for it in pkg.items]
    misconceptions = _with_bug_rules(pkg, by_family, chapter, order)
    return pkg.model_copy(update={"items": items, "misconceptions": misconceptions})


def _mapping(
    item: Item,
    key: ParsedNumber,
    by_family: dict[str, list[Misconception]],
    chapter: Chapter,
    order: list[str],
) -> dict[Fraction, str]:
    node = next((k for k in item.kc_ids if k in order), None)
    earlier = _ancestors(chapter, node) if node else set()
    seen: dict[Fraction, set[str]] = {}
    topic = chapter.node(node).name if node else ""
    for w in wrong_answers(item, key, topic):
        if w.value != key.value and w.value > 0 and w.family in by_family:
            seen.setdefault(w.value, set()).add(w.family)
    out = {}
    for value, fams in seen.items():
        # ZERO_PLACEHOLDER is the general case of the unit and area families: the specific one wins.
        if len(fams) > 1:
            fams = fams - {"ZERO_PLACEHOLDER"}
        if len(fams) == 1:
            (family,) = fams
            picked = _pick(by_family[family], node, order, earlier)
            if picked is not None:
                out[value] = picked
    return out


def _enrich_item(
    item: Item, by_family: dict[str, list[Misconception]], chapter: Chapter, order: list[str]
) -> Item:
    ans = item.answer
    if isinstance(ans, NumericAnswer) and not ans.wrong_answers and ans.form != "fraction":
        try:
            key = parse_literal(ans.value)
        except ValueError:
            return item
        found = _mapping(item, key, by_family, chapter, order)
        if not found:
            return item
        wrong = {format_vi(v): mid for v, mid in found.items()}
        return item.model_copy(update={"answer": ans.model_copy(update={"wrong_answers": wrong})})
    if isinstance(ans, ChoiceAnswer) and not any(o.misconceptions for o in ans.options):
        right = next((o for o in ans.options if o.correct), None)
        key = _option_number(right.text) if right else None
        if key is None:
            return item
        found = _mapping(item, key, by_family, chapter, order)
        options = []
        for o in ans.options:
            n = None if o.correct else _option_number(o.text)
            mid = found.get(n.value) if n is not None else None
            options.append(o.model_copy(update={"misconceptions": [mid]}) if mid else o)
        if options != list(ans.options):
            return item.model_copy(update={"answer": ans.model_copy(update={"options": options})})
    return item


def _option_number(text: str) -> ParsedNumber | None:
    nums = [n for n in extract_numbers(text) if n.form in ("integer", "decimal")]
    return nums[0] if len(nums) == 1 else None


def _with_bug_rules(
    pkg: LessonPackage, by_family: dict[str, list[Misconception]], chapter: Chapter, order: list[str]
) -> list[Misconception]:
    """The comparison bug rules on one misconception each, for lessons with compare or order items."""
    if not any(it.answer.type in ("compare", "order") for it in pkg.items) or any(
        m.bug_rule for m in pkg.misconceptions
    ):
        return list(pkg.misconceptions)
    nodes = [k for it in pkg.items if it.answer.type in ("compare", "order") for k in it.kc_ids]
    node = max(set(nodes), key=nodes.count) if nodes else None
    earlier = _ancestors(chapter, node) if node else set()
    rule_of: dict[str, str] = {}
    for family, rule in BUG_RULE_OF.items():
        picked = _pick(by_family[family], node, order, earlier) if family in by_family else None
        if picked is not None:
            rule_of.setdefault(picked, rule)
    return [
        m.model_copy(update={"bug_rule": rule_of[m.id]}) if m.id in rule_of else m for m in pkg.misconceptions
    ]


def enrich_chapter(chapter: Chapter) -> Chapter:
    lessons = {lid: enrich_lesson(pkg, chapter) for lid, pkg in chapter.lessons.items()}
    items = {it.id: (it, lesson) for lesson in lessons.values() for it in lesson.items}
    return Chapter(package=chapter.package, lessons=lessons, _items=items)


def coverage(chapter: Chapter) -> Iterable[tuple[str, str, str, str]]:
    """(lesson, item, wrong answer, misconception) for a report."""
    for lid, pkg in chapter.lessons.items():
        for it in pkg.items:
            ans = it.answer
            if isinstance(ans, NumericAnswer):
                for wrong, mid in ans.wrong_answers.items():
                    yield lid, it.id, wrong, mid
            elif isinstance(ans, ChoiceAnswer):
                for o in ans.options:
                    for mid in o.misconceptions:
                        yield lid, it.id, o.text, mid
