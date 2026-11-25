"""Rule-based ask cleaning + requirement splitting. No model.

Strips issue-template boilerplate (environment, versions, logs), then splits what's left into
atomic requirement candidates: checklist items first, bullets second, sentences last.
"""
from __future__ import annotations
import re
from .schemas import Requirement

# Sections that describe the reporter's setup, not the ask.
SKIP_HEADINGS = re.compile(
    r"^(environment|env|system info|versions?|logs?|stack ?trace|traceback|screenshots?|"
    r"additional context|checklist before|reproduc\w*|steps to reproduce|"
    r"os|platform|configuration|labels?)\b", re.I)
CHECKBOX = re.compile(r"^\s*[-*]\s*\[( |x|X)\]\s+(.*\S)")
BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*\S)")
MODAL = re.compile(r"\b(should|must|need(?:s)? to|needs|add|remove|fix|support|allow|ensure|make|"
                   r"return|raise|handle|replace|rename|implement|update|change)\b", re.I)


def clean_ask(text: str) -> str:
    out, skipping = [], False
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^#{1,6}\s*(.+)", line)
        if m:
            skipping = bool(SKIP_HEADINGS.match(m.group(1).strip()))
            if not skipping:
                out.append(line)
            continue
        if skipping:
            continue
        line = re.sub(r"<!--.*?-->", "", line)
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def split_requirements(text: str, max_reqs: int = 12) -> list[Requirement]:
    cleaned = clean_ask(text)
    items: list[str] = []
    for line in cleaned.splitlines():
        m = CHECKBOX.match(line) or BULLET.match(line)
        if m:
            items.append(m.group(m.lastindex))
    if len(items) < 2:  # no list structure: fall back to modal-verb sentences
        flat = re.sub(r"\s+", " ", re.sub(r"^#+\s*", "", cleaned, flags=re.M))
        sents = re.split(r"(?<=[.!?])\s+", flat)
        items = [s for s in sents if MODAL.search(s) and 15 <= len(s) <= 300]
    reqs = []
    for i, s in enumerate(items[:max_reqs], 1):
        s = re.sub(r"\s+", " ", s).strip()
        reqs.append(Requirement(id=i, text=s, source_sentence=s, unclear=not MODAL.search(s)))
    return reqs
