"""Retrieval variants for the offline retrieval benchmark (bench/eval_retrieval.py). Same interface as the other scorers:
list[(requirement, hunk_text)] -> list[float]; scores only rank hunks within one requirement."""
from __future__ import annotations
import math
from .lexical import _toks


def bm25_scorer(k1: float = 1.5, b: float = 0.75):
    """Okapi BM25 over identifier-aware tokens (docs = the hunks passed in the same call)."""
    def score(pairs):
        docs = {h: _toks(h) for _, h in pairs}
        n = max(1, len(docs))
        avg = sum(len(t) for t in docs.values()) / n or 1.0
        df: dict[str, int] = {}
        for t in docs.values():
            for w in t:
                df[w] = df.get(w, 0) + 1
        out = []
        for req, h in pairs:
            d, s = docs[h], 0.0
            for w in _toks(req):
                if w in d:
                    idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                    s += idf * (k1 + 1) / (1 + k1 * (1 - b + b * len(d) / avg))
            out.append(s)
        return out
    return score


def fuse(*scorers, k: int = 60):
    """Reciprocal-rank fusion of several scorers (rank within each requirement's candidate list)."""
    def score(pairs):
        by_req: dict[str, list[int]] = {}
        for i, (r, _h) in enumerate(pairs):
            by_req.setdefault(r, []).append(i)
        out = [0.0] * len(pairs)
        for sc in scorers:
            s = sc(pairs)
            for idxs in by_req.values():
                for rank, i in enumerate(sorted(idxs, key=lambda i: -s[i])):
                    out[i] += 1.0 / (k + rank + 1)
        return out
    return score
