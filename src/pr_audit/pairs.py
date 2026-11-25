"""Build (requirement, hunk, label) pairs for the relevance model. No model involved.

Weak labels: a hunk from the SAME PR as the requirement is relevant (1); a hunk from ANOTHER PR is not (0),
preferring same-repo negatives (hard) over cross-repo ones (easy). Split is by repository so the
validation/test sets contain repos the model never saw.
"""
from __future__ import annotations
import hashlib
import random
from .requirements import split_requirements
from .schemas import Hunk, PRBundle


def repo_of(source: str) -> str:
    return "/".join(source.split("/")[3:5])


def split_of(repo: str) -> str:
    h = int(hashlib.md5(repo.encode()).hexdigest(), 16) % 10
    return "test" if h == 0 else "val" if h == 1 else "train"


def hunk_text(h: Hunk, limit: int = 1500) -> str:
    body = "\n".join([f"+ {l}" for l in h.added] + [f"- {l}" for l in h.removed])
    return f"{h.file}\n{body}"[:limit]


def build_pairs(bundles: list[PRBundle], seed: int = 0, pos_per_req: int = 4) -> list[dict]:
    rng = random.Random(seed)
    by_repo: dict[str, list[PRBundle]] = {}
    for b in bundles:
        by_repo.setdefault(repo_of(b.source), []).append(b)
    rows: list[dict] = []
    for b in bundles:
        if not b.hunks:
            continue
        repo = repo_of(b.source)
        reqs = split_requirements(b.ask) or []
        texts = [r.text for r in reqs] or [b.title]
        same = [o for o in by_repo[repo] if o.source != b.source and o.hunks]
        anyo = [o for o in bundles if o.source != b.source and o.hunks]
        for t in texts:
            for h in rng.sample(b.hunks, min(pos_per_req, len(b.hunks))):
                rows.append(dict(req=t, hunk=hunk_text(h), label=1, repo=repo, pr=b.source, split=split_of(repo)))
                pool = same or anyo
                if pool:
                    o = rng.choice(pool)
                    rows.append(dict(req=t, hunk=hunk_text(rng.choice(o.hunks)), label=0, repo=repo,
                                     pr=b.source, split=split_of(repo), hard=bool(same)))
    return rows


def clean_message(msg: str) -> str:
    keep = []
    for line in msg.splitlines():
        low = line.lower()
        if low.startswith(("co-authored-by", "signed-off-by", "claude-session")) or "generated with" in low:
            continue
        keep.append(line.strip())
    return " ".join(x for x in keep if x)[:300]


def build_commit_pairs(bundles: list[PRBundle], supervision: dict[str, dict], seed: int = 0, per_commit: int = 3) -> list[dict]:
    """Within-PR supervision. Positive: (commit message, a hunk that commit introduced).
    Negative: (same message, a hunk of the SAME PR introduced only by OTHER commits). All rows are hard negatives."""
    rng = random.Random(seed)
    rows: list[dict] = []
    for b in bundles:
        rec = supervision.get(b.source)
        if not rec or len(rec["commits"]) < 2:
            continue
        by_id = {h.id: h for h in b.hunks}
        repo = repo_of(b.source)
        for c in rec["commits"]:
            mine = [i for i in c["hunks"] if i in by_id]
            others = sorted({i for o in rec["commits"] if o is not c for i in o["hunks"] if i in by_id} - set(c["hunks"]))
            msg = clean_message(c["message"])
            if not mine or not others or len(msg) < 12:
                continue
            for hid in rng.sample(mine, min(per_commit, len(mine))):
                rows.append(dict(req=msg, hunk=hunk_text(by_id[hid]), label=1, repo=repo, pr=b.source,
                                 split=split_of(repo), within=True))
                rows.append(dict(req=msg, hunk=hunk_text(by_id[rng.choice(others)]), label=0, repo=repo,
                                 pr=b.source, split=split_of(repo), hard=True, within=True))
    return rows
