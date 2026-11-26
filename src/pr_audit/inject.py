"""Fault injection: build labelled cases from real merged PRs. No model involved.

Labels are known BY CONSTRUCTION (weak but principled):
  clean      ask A + diff A                      -> done      (assumes merged PR met its ask)
  mismatch   ask A + diff B (same repo)          -> missing   (diff does not address the ask)
  partial    ask A + diff A with some hunks cut  -> partial   (only if A has >=3 substantive hunks)
  creep      ask A + diff A + foreign hunks      -> done + foreign hunk ids are 'unrequested'
Hand-labelled gold subset is evaluated separately.
"""
from __future__ import annotations
import random
from pydantic import BaseModel, Field
from .pairs import repo_of
from .schemas import PRBundle, Hunk, Verdict

DOC_TEST_MARKERS = ("test", "tests/", "docs/", ".md", ".rst", "changelog", "CHANGES")


def is_substantive(h: Hunk) -> bool:
    f = h.file.lower()
    return not any(m.lower() in f for m in DOC_TEST_MARKERS)


class Case(BaseModel):
    case_id: str
    kind: str                       # clean | mismatch | partial | creep
    ask: str
    ask_source: str
    hunks: list[Hunk]
    label: Verdict                  # label for the ask as a whole
    unrequested: list[str] = Field(default_factory=list)   # hunk ids that are creep
    meta: dict = Field(default_factory=dict)


def clean(a: PRBundle) -> Case:
    return Case(case_id=f"{a.source}#clean", kind="clean", ask=a.ask, ask_source=a.ask_source,
                hunks=a.hunks, label=Verdict.done)


def mismatch(a: PRBundle, b: PRBundle) -> Case:
    assert a.source != b.source
    return Case(case_id=f"{a.source}#mismatch:{b.source}", kind="mismatch", ask=a.ask,
                ask_source=a.ask_source, hunks=b.hunks, label=Verdict.missing,
                meta={"diff_from": b.source})


def partial(a: PRBundle, rng: random.Random, keep_frac: float = 0.5) -> Case | None:
    sub = [h for h in a.hunks if is_substantive(h)]
    if len(sub) < 3:
        return None
    n_drop = max(1, round(len(sub) * (1 - keep_frac)))
    drop = {h.id for h in rng.sample(sub, n_drop)}
    if len(drop) >= len(sub):
        return None
    kept = [h for h in a.hunks if h.id not in drop]
    return Case(case_id=f"{a.source}#partial", kind="partial", ask=a.ask, ask_source=a.ask_source,
                hunks=kept, label=Verdict.partial, meta={"dropped": sorted(drop)})


def creep(a: PRBundle, b: PRBundle, rng: random.Random, n: int = 1) -> Case | None:
    pool = [h for h in b.hunks if is_substantive(h)]
    if not pool:
        return None
    foreign = rng.sample(pool, min(n, len(pool)))
    # re-id foreign hunks so ids cannot collide with A's
    tagged = [h.model_copy(update={"id": f"foreign::{h.id}"}) for h in foreign]
    return Case(case_id=f"{a.source}#creep", kind="creep", ask=a.ask, ask_source=a.ask_source,
                hunks=a.hunks + tagged, label=Verdict.done,
                unrequested=[h.id for h in tagged], meta={"foreign_from": b.source})


def composite(a: PRBundle, b: PRBundle) -> list[Case]:
    """Two-PR ask with exact requirement-level truth: A's requirements vs B's requirements.
    full:    ask A+B, diff A+B -> done          partial: ask A+B, diff A only -> partial (B's reqs missing)
    """
    from .requirements import split_requirements
    ra = [r.text for r in split_requirements(a.ask)]
    rb = [r.text for r in split_requirements(b.ask)]
    if not ra or not rb:
        return []
    meta = {"reqs": ra + rb, "reqs_done_in_partial": ra, "reqs_missing_in_partial": rb, "b": b.source}
    ask = a.ask + "\n\n" + b.ask
    bh = [h.model_copy(update={"id": f"b::{h.id}"}) for h in b.hunks]
    return [
        Case(case_id=f"{a.source}#composite_full:{b.source}", kind="composite_full", ask=ask,
             ask_source=a.ask_source, hunks=a.hunks + bh, label=Verdict.done, meta=meta),
        Case(case_id=f"{a.source}#composite_partial:{b.source}", kind="composite_partial", ask=ask,
             ask_source=a.ask_source, hunks=a.hunks, label=Verdict.partial, meta=meta),
    ]


def build_cases(bundles: list[PRBundle], seed: int = 0) -> list[Case]:
    rng = random.Random(seed)
    out: list[Case] = []
    for i, a in enumerate(bundles):
        if not a.hunks or not a.ask.strip():
            continue
        out.append(clean(a))
        others = [b for j, b in enumerate(bundles) if j != i and b.hunks]
        if others:
            same = [o for o in others if repo_of(o.source) == repo_of(a.source)]
            b = rng.choice(same or others)   # prefer same-repo (hard) over cross-repo (easy)
            out.append(mismatch(a, b))
            c = creep(a, b, rng)
            if c:
                out.append(c)
            out.extend(composite(a, b))
        p = partial(a, rng)
        if p:
            out.append(p)
    return out


def partial_drop(hunk_ids: list[str]) -> set[str] | None:
    """Ids to remove so that a requirement keeps SOME but not ALL of its own hunks (deterministic: first half, sorted).

    Weak truth: the remainder may still satisfy the requirement, so a 'done' after this fault is a miss only if the
    removed hunks were really needed. bench/eval_partial.py reports it as such, never as exact."""
    ids = sorted(set(hunk_ids))
    if len(ids) < 2:
        return None
    return set(ids[: len(ids) // 2])
