"""Evidence verification. Plain code, no model.

A judgment that claims `done`/`partial` must cite real hunks and quote lines
that really exist in them. Anything else is downgraded to `unclear`.
"""
from __future__ import annotations
import re
from .schemas import Hunk, Judgment, Verdict


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def verify_judgment(j: Judgment, hunks: list[Hunk]) -> Judgment:
    by_id = {h.id: h for h in hunks}
    problems: list[str] = []

    if j.verdict in (Verdict.done, Verdict.partial):
        if not j.hunk_ids:
            problems.append("no hunk cited")
        if not j.quotes:
            problems.append("no quoted lines")
        cited = [by_id[i] for i in j.hunk_ids if i in by_id]
        for i in j.hunk_ids:
            if i not in by_id:
                problems.append(f"cited hunk does not exist: {i}")
        # quotes must appear in the added lines (or text) of a cited hunk
        pool = [_norm(l) for h in cited for l in (h.added + h.text.splitlines())]
        blob = " ".join(pool)
        for q in j.quotes:
            nq = _norm(q).rstrip(",;").strip() if _norm(q) not in blob else _norm(q)
            alt = _norm(re.sub(r"^[+-]\s?", "", q.strip())).rstrip(",;").strip()      # judge may copy our "+ " display marker
            if not nq or (nq not in blob and (not alt or alt not in blob)):
                problems.append(f"quote not found in cited hunks: {q[:60]!r}")

    if problems:
        return j.model_copy(update={
            "verdict": Verdict.unclear,
            "downgraded_because": problems,
        })
    return j


def quotes_in(h: Hunk, quotes: list[str]) -> list[str]:
    """The subset of `quotes` that really occur in this one hunk (same matching rule as verify_judgment)."""
    blob = " ".join(_norm(l) for l in (h.added + h.text.splitlines()))
    keep = []
    for q in quotes:
        nq = _norm(q).rstrip(",;").strip()
        alt = _norm(re.sub(r"^[+-]\s?", "", q.strip())).rstrip(",;").strip()
        if (nq and nq in blob) or (alt and alt in blob):
            keep.append(q)
    return keep
