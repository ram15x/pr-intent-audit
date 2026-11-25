"""Trivial retrieval baseline: IDF-weighted word overlap. No model, no GPU.

Same interface as the trained scorer (list[(requirement, hunk_text)] -> list[float]) so it can replace it for
retrieval. Scores are only meaningful for ranking hunks against one requirement, not as calibrated probabilities.
"""
from __future__ import annotations
import math
import re

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")
_STOP = frozenset("the and for with that this from are was have has not but all any can will should must when then into "
                  "its their they them these those also only each such per via use used using add adds added".split())


def _toks(s: str) -> set[str]:
    out = set()
    for w in _WORD.findall(s):
        for part in re.sub(r"([a-z])([A-Z])", r"\1 \2", w).replace("_", " ").split():
            p = part.lower()
            if len(p) > 2 and p not in _STOP:
                out.add(p)
        out.add(w.lower())
    return out - _STOP


def lexical_scorer():
    def score(pairs: list[tuple[str, str]]) -> list[float]:
        docs = {h: _toks(h) for _, h in pairs}
        n = max(1, len(docs))
        df: dict[str, int] = {}
        for t in docs.values():
            for w in t:
                df[w] = df.get(w, 0) + 1
        idf = lambda w: math.log(1 + n / (1 + df.get(w, 0)))
        out = []
        for req, h in pairs:
            rt = _toks(req)
            if not rt:
                out.append(0.0); continue
            tot = sum(idf(w) for w in rt) or 1.0
            out.append(sum(idf(w) for w in rt if w in docs[h]) / tot)
        return out
    return score
