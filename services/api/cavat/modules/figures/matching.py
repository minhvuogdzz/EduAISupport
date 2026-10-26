"""Which figure of a page is which "[Hình: …]" description (FIG-1, ADR-034).

The document's text (read by Gemini, page by page) says "[Hình: tam giác ABC, đáy BC = 12 cm …]" where a
figure is drawn; ``finder`` returns the figures of the same page in reading order. Two signals pair them:

- the order: the n-th description of a page is the n-th figure of the page (one figure of panels "Hình 1,
  Hình 2, Hình 3" is one description and several drawings in a row);
- the content: the points (A, B, C, H) and the measures (12 cm, 7 cm) written on the drawing are the ones
  the description names. A description is a model's reading, so the content is evidence, not a proof.

A pairing is a monotone alignment of the descriptions with the figures (a figure may be left out, e.g. a
frame the finder took for a drawing; a description may stay without figure). Its score is the share of
shared points and measures. Below ``MIN_SCORE`` the pair is not made: a question with no figure is a lesser
fault than a question with the wrong one. Between ``MIN_SCORE`` and ``SURE_SCORE`` the pair is made and
waits for the teacher (``confidence`` "REVIEW"); above, it is shown (``confidence`` "SURE").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cavat.modules.figures.finder import Region, merge_row

MIN_SCORE = 0.3
SURE_SCORE = 0.5
SKIP_COST = 0.02  # a figure with no description (a frame): nearly free
LEAVE_COST = 0.1  # a description with no figure: the end of a search, not a goal

TAG = re.compile(r"\[Hình\b[^\]]*\]", re.DOTALL)
_PANEL = re.compile(r"Hình\s*\d+\s*:")
_PANEL_NUMBER = re.compile(r"Hình\s*\d+")
_NUMBER = re.compile(r"\d+(?:,\d+)?")
_POINTS = re.compile(r"(?<![\w])([A-Z]{1,5})(?![\w])")
_LETTER = re.compile(r"(?<![\w])([a-z])(?![\w])")
_UNIT_LETTERS = {"m", "x"}  # "6 m x 4 m": a unit and a times sign, not letters written on a drawing


def clean_tag(text: str) -> str:
    """The text of a tag as the page shows it: one line, the spaces of a model's reading collapsed."""
    return re.sub(r"\s+", " ", text).strip()


def alt_of(tag: str) -> str:
    """The description inside the brackets: the figure's alternative text."""
    inner = clean_tag(tag)
    inner = inner[1:-1] if inner.startswith("[") and inner.endswith("]") else inner
    return re.sub(r"^Hình\s*:\s*", "", inner).strip()


def tags_of(text: str) -> list[str]:
    """Every "[Hình …]" of a text, in order, cleaned."""
    return [clean_tag(m.group(0)) for m in TAG.finditer(text)]


def split_pages(text: str) -> dict[int, str]:
    """The text of a document by page ("[Trang n]" marks, ``library.extract``)."""
    parts = re.split(r"(?m)^\[Trang (\d+)\]\s*$", text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def panels_of(tag: str) -> int:
    """How many drawings a description speaks of: "Hình 1: … Hình 2: … Hình 3: …" is three."""
    return max(1, len(_PANEL.findall(tag)))


def evidence(tag: str) -> set[str]:
    """What a description names that a drawing also writes: points, letters of formulas, measures."""
    body = alt_of(tag)
    body = _PANEL_NUMBER.sub(" ", body)
    found = {f"n{n}" for n in _NUMBER.findall(body)}
    for word in _POINTS.findall(body):
        found |= {f"p{c}" for c in word}
    found |= {f"l{c}" for c in _LETTER.findall(body) if c not in _UNIT_LETTERS}
    return found


def drawn(region: Region) -> set[str]:
    """What a drawing writes on itself, in the same vocabulary as ``evidence``."""
    found = {f"n{n}" for n in region.numbers()}
    for label in region.labels:
        text = label.strip()
        if re.fullmatch(r"[A-Z]", text):
            found.add(f"p{text}")
        elif re.fullmatch(r"[a-z]", text):
            if text not in _UNIT_LETTERS:
                found.add(f"l{text}")
        else:  # "BM", "(a + b)", "12 cm"
            found |= {f"p{c}" for word in _POINTS.findall(text) for c in word}
            found |= {f"l{c}" for c in _LETTER.findall(text) if c not in _UNIT_LETTERS}
    return found


def score(tag: str, region: Region) -> float:
    """The share of the points and measures of the description that the drawing writes too.

    Jaccard on what both name. A description with nothing to compare (no letter, no number) scores 0.5 with
    any drawing: the order alone decides, and the pair waits for the teacher."""
    said = evidence(tag)
    if not said:
        return SURE_SCORE
    seen = drawn(region)
    if not seen:
        return 0.0
    return len(said & seen) / len(said | seen)


@dataclass(frozen=True)
class Pair:
    tag: str
    region: Region
    score: float

    @property
    def confidence(self) -> str:
        """SURE: shown to the children; REVIEW: the teacher looks first."""
        return "SURE" if self.score >= SURE_SCORE else "REVIEW"


@dataclass
class PageMatch:
    page: int
    pairs: list[Pair]  # by the order of the tags on the page
    unmatched_tags: list[str]  # descriptions with no drawing
    spare: list[Region]  # drawings with no description


def match_page(page: int, tags: list[str], regions: list[Region]) -> PageMatch:
    """Align the descriptions of a page with its drawings (the best monotone pairing)."""
    # best[i][j]: the best total for the first i tags and the first j regions, with the way it was reached.
    n, m = len(tags), len(regions)
    best = [[(0.0, None)] * (m + 1) for _ in range(n + 1)]
    merged: dict[tuple[int, int], Region] = {}
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            options: list[tuple[float, tuple[str, int, int]]] = []
            if j > 0:
                options.append((best[i][j - 1][0] - SKIP_COST, ("skip", i, j - 1)))
            if i > 0:
                options.append((best[i - 1][j][0] - LEAVE_COST, ("leave", i - 1, j)))
            if i > 0 and j > 0:
                panels = panels_of(tags[i - 1])
                start = j - panels
                if start >= 0:
                    region = _panels_region(regions, start, panels)
                    if region is not None:
                        value = score(tags[i - 1], region)
                        if value >= MIN_SCORE:
                            merged[(i, j)] = region
                            options.append((best[i - 1][start][0] + value, ("pair", i - 1, start)))
            best[i][j] = max(options, key=lambda o: o[0]) if options else (0.0, None)
    pairs: list[Pair] = []
    unmatched: list[str] = []
    used: set[int] = set()
    i, j = n, m
    while i > 0 or j > 0:
        step = best[i][j][1]
        if step is None:
            break
        kind, pi, pj = step
        if kind == "pair":
            region = merged[(i, j)]
            pairs.append(Pair(tags[i - 1], region, score(tags[i - 1], region)))
            used.update(range(pj, j))
        elif kind == "leave":
            unmatched.append(tags[i - 1])
        i, j = pi, pj
    pairs.reverse()
    unmatched.reverse()
    spare = [r for k, r in enumerate(regions) if k not in used]
    if unmatched and len(tags) == len(regions) and all(panels_of(t) == 1 for t in tags):
        # The words and the drawing share nothing ("tô màu 3 cột" and "= 0,3"), but the page has as many
        # drawings as descriptions: the order pairs them, and the teacher is asked.
        pairs = [Pair(tag, region, score(tag, region)) for tag, region in zip(tags, regions, strict=True)]
        unmatched, spare = [], []
    return PageMatch(page, pairs, unmatched, spare)


def _panels_region(regions: list[Region], start: int, panels: int) -> Region | None:
    """The drawing or row of drawings that ``panels`` panels of one description stand for."""
    if panels == 1:
        return regions[start]
    joined = merge_row(regions, start, panels)
    return joined[start] if joined is not None else None
