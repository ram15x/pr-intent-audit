"""Map hunks from one commit onto the final PR hunks, so a commit message can supervise within-PR relevance."""
from __future__ import annotations
from .schemas import Hunk


def map_commit_hunks(commit_hunks: list[Hunk], final_hunks: list[Hunk], min_overlap: float = 0.5) -> list[str]:
    """Final-hunk ids whose added lines (same file) overlap the commit hunks' added lines."""
    norm = lambda ls: {l.strip() for l in ls if len(l.strip()) > 3}
    out: list[str] = []
    for fh in final_hunks:
        fa = norm(fh.added)
        if not fa:
            continue
        for ch in commit_hunks:
            if ch.file != fh.file:
                continue
            ca = norm(ch.added)
            if ca and len(fa & ca) / min(len(fa), len(ca)) >= min_overlap:
                out.append(fh.id)
                break
    return out
