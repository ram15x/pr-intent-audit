"""Audit local work, no PR needed: a git ref range (or the working tree) against an ask you provide
(the prompt you gave an agent, a spec, an issue text). Plain git + our diff parser; nothing is sent anywhere."""
from __future__ import annotations
import subprocess
from pathlib import Path
from .diffs import parse_diff
from .schemas import PRBundle


def _check_ref(ref: str) -> str:
    if not ref or ref.startswith("-") or any(c in ref for c in " \t\n\r\0;|&$`<>\\"):
        raise ValueError(f"not a plain git ref: {ref!r}")
    return ref


def git_diff(repo: Path, base: str, head: str | None = None) -> str:
    """Unified diff base..head, or base..working tree when head is None. Argument list, never a shell."""
    cmd = ["git", "-C", str(repo), "diff", "--no-color", "--no-ext-diff", "-U3", _check_ref(base)]
    if head:
        cmd.append(_check_ref(head))
    cmd.append("--")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise ValueError(f"git diff failed: {r.stderr.strip()[:200]}")
    return r.stdout


def bundle_from_git(repo: Path, ask: str, base: str = "HEAD~1", head: str | None = "HEAD",
                    ask_source: str = "agent_prompt") -> PRBundle:
    diff = git_diff(repo, base, head)
    hunks, notes = parse_diff(diff)
    label = f"local:{Path(repo).resolve().name}@{base}..{head or 'working-tree'}"
    return PRBundle(source=label, title=f"{Path(repo).resolve().name}: {base}..{head or 'working tree'}", body="",
                    ask=ask, ask_source=ask_source, hunks=hunks, notes=notes)
