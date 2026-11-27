from __future__ import annotations
from .audit import Audit

ICON = {"done": "DONE", "partial": "PARTIAL", "missing": "MISSING", "unclear": "UNCLEAR"}


def render_markdown(a: Audit, run_info: str = "") -> str:
    b = a.bundle
    rank = "n/a" if a.rank is None else f"{a.rank}/100"
    out = [f"# PR Intent Audit", "", f"**PR:** {b.source}  ", f"**Title:** {b.title}  ",
           f"**Ask source:** {b.ask_source}  ", f"**Rank:** {rank} ({a.band})"
           + ("  **low confidence: many requirements unclear**" if a.low_confidence else ""), ""]
    if b.notes:
        out += ["> " + n for n in b.notes] + [""]
    out += ["## Requirements", "", "| # | Requirement | Verdict | Relevance | Evidence |", "|---|---|---|---|---|"]
    for r in a.reqs:
        ev = "<br>".join(f"`{h}` ({s:.2f})" for h, s, _ in r.evidence) or (r.note or "-")
        out.append(f"| {r.id} | {r.text[:140].replace('|', '/')} | {ICON[r.status]}{' (option)' if r.optional else ''} | {r.score:.2f} | {ev} |")
    out += ["", "## Asked vs changed", ""]
    for r in a.reqs:
        out.append(f"**{r.id}. {ICON[r.status]}{' (option: not doing it is not a gap)' if r.optional else ''}** - {r.text[:200]}")
        for h, s, quotes in r.evidence:
            out.append(f"- `{h}` (relevance {s:.2f})")
            out += [f"  - `{q[:120].replace(chr(10), ' / ')}`" for q in quotes]
        if r.note and r.evidence:
            out.append(f"- judge: {r.note[:240]}")
        if not r.evidence:
            out.append("- " + (r.note[:240] if r.note else "no hunk matched this requirement above the threshold"))
        out.append("")
    out += ["## Unmapped changes", ""]
    if a.creep:
        out.append("Hunks (excluding tests/docs) that no requirement claims. They may be scope creep or needed supporting work; not scored.")
        out += [f"- `{h}` (best relevance to any requirement {s})" for h, s in a.creep]
    else:
        out.append("None flagged.")
    out += ["", "## Whole-PR verdict (classifier)", ""]
    if a.pr_probs:
        out.append(f"**{a.pr_verdict}** - " + ", ".join(f"{k} {v:.2f}" for k, v in a.pr_probs.items()))
    out += ["", "## How the rank was computed", ""] + [f"- {l}" for l in a.rank_lines]
    out += ["", "## Honesty notes", "",
            "- Hybrid mode: an LLM judges each requirement on our top-ranked hunks and our verifier rejects any verdict whose cited hunks or quotes do not exist (downgraded to UNCLEAR). Local mode uses only our small trained models, which cannot judge within-PR requirements (see docs/RESULTS.md). Benchmarks use unreviewed labels.",
            "- Evidence is extractive: every line shown exists in the cited hunk.",
            "- This tool never approves or blocks a merge."]
    if run_info:
        out += ["", f"_{run_info}_"]
    return "\n".join(out) + "\n"
