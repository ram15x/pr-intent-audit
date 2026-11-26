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
            for w in sorted(_toks(req)):
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


import re as _re

_IDENT = _re.compile(r"`([^`\n]{2,80})`|((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)|\b([a-z]+(?:_[a-z0-9]+)+|[a-z]+(?:[A-Z][a-z0-9]+)+|[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b")


def identifiers(req: str) -> list[str]:
    """Things a requirement names verbatim: `backticked` spans, file paths, snake_case / camelCase / PascalCase names.
    These are exact-match signals that word overlap dilutes."""
    out = []
    for m in _IDENT.finditer(req):
        t = next(g for g in m.groups() if g).strip().strip("()")
        t = _re.sub(r"\(.*$", "", t).strip()          # `func(arg)` -> func
        if len(t) >= 3 and t not in out:
            out.append(t)
    return out


def identifier_boost(base, w_ident: float = 1.0, w_path: float = 1.0):
    """base score (normalised per requirement) + share of the requirement's named identifiers found verbatim in the hunk
    + a bonus when the requirement names the hunk's file path. Fixed a-priori weights, not tuned on the gold set."""
    def score(pairs):
        s = base(pairs)
        by_req: dict[str, list[int]] = {}
        for i, (r, _h) in enumerate(pairs):
            by_req.setdefault(r, []).append(i)
        out = [0.0] * len(pairs)
        for r, idxs in by_req.items():
            ids = identifiers(r)
            top = max((s[i] for i in idxs), default=0.0) or 1.0
            for i in idxs:
                h = pairs[i][1]
                first, _, body = h.partition("\n")                 # hunk_text = "<file>\n<lines>"
                hit = sum(1 for t in ids if t in h) / len(ids) if ids else 0.0
                path = 1.0 if any(t in first or first.endswith(t) for t in ids if "/" in t or "." in t) else 0.0
                out[i] = s[i] / top + w_ident * hit + w_path * path
        return out
    return score
