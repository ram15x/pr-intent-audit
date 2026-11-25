"""Fetch a GitHub PR into a PRBundle. Public repos work without a token (60 req/h)."""
from __future__ import annotations
import os
import re
import httpx
from .diffs import parse_diff
from .schemas import PRBundle

PR_URL = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")
CLOSES = re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", re.I)


def _headers(accept: str) -> dict:
    h = {"Accept": accept, "User-Agent": "pr-intent-audit"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def fetch_pr(url: str, ask_override: str | None = None) -> PRBundle:
    m = PR_URL.search(url)
    if not m:
        raise ValueError(f"not a GitHub PR url: {url}")
    owner, repo, num = m.groups()
    api = f"https://api.github.com/repos/{owner}/{repo}"
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        meta = c.get(f"{api}/pulls/{num}", headers=_headers("application/vnd.github+json"))
        meta.raise_for_status()
        meta = meta.json()
        diff = c.get(f"{api}/pulls/{num}", headers=_headers("application/vnd.github.diff"))
        diff.raise_for_status()
        body = meta.get("body") or ""
        ask, src = body, "pr_body"
        notes: list[str] = []
        if ask_override:
            ask, src = ask_override, "agent_prompt"
        else:
            issues = []
            for n in sorted(set(CLOSES.findall(body + " " + meta["title"]))):
                r = c.get(f"{api}/issues/{n}", headers=_headers("application/vnd.github+json"))
                if r.status_code == 200:
                    j = r.json()
                    issues.append(f"# Issue #{n}: {j['title']}\n{j.get('body') or ''}")
            if issues:
                ask, src = "\n\n".join(issues), "issue"
    hunks, dnotes = parse_diff(diff.text)
    return PRBundle(source=url, title=meta["title"], body=body, ask=ask,
                    ask_source=src, hunks=hunks, notes=notes + dnotes)
