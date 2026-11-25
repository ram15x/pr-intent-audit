"""Diff parsing: unified diff text -> hunks with stable ids. No model involved."""
from __future__ import annotations
import fnmatch
from unidiff import PatchSet
from .schemas import Hunk

NOISE_GLOBS = [
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "go.sum", "*.min.js", "*.min.css", "*.map", "*.svg", "*.png",
    "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.pdf", "dist/*", "build/*",
    "*_pb2.py", "*.snap",
]


def is_noise(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(name, g) for g in NOISE_GLOBS)


def parse_diff(diff_text: str, max_hunks: int = 200) -> tuple[list[Hunk], list[str]]:
    notes: list[str] = []
    patch = PatchSet(diff_text)
    hunks: list[Hunk] = []
    dropped: list[str] = []
    for pf in patch:
        path = pf.path
        if pf.is_binary_file or is_noise(path):
            dropped.append(path)
            continue
        for h in pf:
            start = h.target_start
            end = h.target_start + max(h.target_length, 1) - 1
            hunks.append(Hunk(
                id=f"{path}:{start}-{end}", file=path, start=start, end=end,
                added=[l.value.rstrip("\n") for l in h if l.is_added],
                removed=[l.value.rstrip("\n") for l in h if l.is_removed],
                text=str(h),
            ))
    if dropped:
        notes.append(f"dropped {len(dropped)} noise/binary file(s): {', '.join(dropped[:5])}")
    if len(hunks) > max_hunks:
        notes.append(f"diff cut: kept first {max_hunks} of {len(hunks)} hunks")
        hunks = hunks[:max_hunks]
    return hunks, notes
