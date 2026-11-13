"""Keyword index of the Hybrid RAG (plan v1, 5.5.2): BM25 written here, on syllables and pairs of adjacent
syllables ("phần mười" stays a phrase), on two forms of the text: with diacritics (exact) and folded
(children type "tai sao phai them so 0"). Numbers have one form: 0.25 and 0,25 are the same token.

BM25 and RRF rank passages; neither says whether any passage answers the question at all (the top one is
always first). ``coverage`` does: the share of the question's content syllables, weighted by idf, that a
passage contains. A syllable the corpus never uses ("mèo") weighs the most, so an off-topic question has
low coverage everywhere (DI-17). A syllable typed with diacritics must match with the same diacritics
("thủ đô Việt Nam" shares no word with "thứ", "độ", "viết", "năm"); one typed without matches the folded
text ("phan nguyen" matches "phần nguyên").
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from cavat.core.vi_text import fold
from cavat.modules.rag.analyzers import FILLER, MATH, Analyzer, content_words, tokens

# FILLER, content_words and tokens are the Mathematics analyzer (ENG-2 moved them to ``analyzers``); the
# names stay here for the modules that import them from bm25.
__all__ = ["BM25", "FILLER", "TwoFormBM25", "content_words", "tokens"]

K1, B = 1.2, 0.75  # DI-17


class BM25:
    """Okapi BM25 over a fixed list of documents (token lists)."""

    def __init__(self, docs: Sequence[Sequence[str]]) -> None:
        self.n = len(docs)
        self.lengths = [len(d) for d in docs]
        self.avg = (sum(self.lengths) / self.n) if self.n else 0.0
        self.freqs = [Counter(d) for d in docs]
        df: Counter[str] = Counter()
        for f in self.freqs:
            df.update(f.keys())
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, query: Sequence[str]) -> list[float]:
        out = [0.0] * self.n
        terms = [t for t in dict.fromkeys(query) if t in self.idf]
        for i, f in enumerate(self.freqs):
            length_norm = K1 * (1 - B + B * self.lengths[i] / self.avg) if self.avg else K1
            total = 0.0
            for t in terms:
                tf = f.get(t, 0)
                if tf:
                    total += self.idf[t] * tf * (K1 + 1) / (tf + length_norm)
            out[i] = total
        return out


class TwoFormBM25:
    """BM25 on the text with diacritics and on its folded form; a document keeps its better score.

    ``analyzer``: how the subject's texts are cut into words (ENG-2, DI-121); Mathematics by default, the
    analyzer this class always used. A ``RagIndex`` always passes its subject's analyzer."""

    def __init__(self, texts: Sequence[str], analyzer: Analyzer = MATH) -> None:
        self.analyzer = analyzer
        self.exact = BM25([analyzer.tokens(t, folded=False) for t in texts])
        self.folded = BM25([analyzer.tokens(t, folded=True) for t in texts])

    def scores(self, query: str) -> list[float]:
        exact = self.exact.scores(self.analyzer.tokens(query, folded=False))
        folded = self.folded.scores(self.analyzer.tokens(query, folded=True))
        return [max(a, b) for a, b in zip(exact, folded, strict=True)]

    def coverage(self, query: str) -> list[float]:
        """For every document, the idf-weighted share of the query's content words it contains (0..1).

        A word unknown to the corpus weighs as a word in no document, the highest idf. A query with no
        content word ("là sao ạ") covers nothing: there is nothing to ground.
        """
        words = self.analyzer.content_words(query)
        n = self.folded.n
        if not words or not n:
            return [0.0] * n
        unknown = math.log(1 + (n + 0.5) / 0.5)
        # (form, word, weight): a word typed without diacritics is looked up in the folded index.
        terms = [(self.folded if fold(w) == w else self.exact, w) for w in words]
        weights = [form.idf.get(w, unknown) for form, w in terms]
        total = sum(weights)
        return [
            sum(wt for (form, w), wt in zip(terms, weights, strict=True) if w in form.freqs[i]) / total
            for i in range(n)
        ]
