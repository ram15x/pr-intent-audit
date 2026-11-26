"""Mine LARGE merged PRs (30-150 hunks) with explicit acceptance criteria: tests whether retrieval matters when the judge cannot see everything."""
import json, re, sys, time
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.env import load_env
load_env(ROOT / ".env")
from pr_audit.ingest import fetch_pr, _headers
from pr_audit.requirements import split_requirements

OUT = ROOT / "bench/data/large_pool.jsonl"
skip = {g["pr"] for g in json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))}
skip |= {json.loads(l)["source"] for l in open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8")}
if (ROOT / "bench/data/gold_pool.jsonl").exists(): skip |= {json.loads(l)["source"] for l in open(ROOT / "bench/data/gold_pool.jsonl", encoding="utf-8")}   # keep gold out of training data
REJ = ROOT / "bench/data/large_rejected.txt"
seen = {json.loads(l)["source"] for l in open(OUT, encoding="utf-8")} if OUT.exists() else set()
if REJ.exists(): seen |= set(REJ.read_text(encoding="utf-8").split())
BASE = 'is:pr is:merged linked:issue comments:<15 '
QS = [BASE + f'language:{lang} "{kw}" created:{win}'
      for win in ("2025-03-01..2025-08-31", "2025-09-01..2026-02-28", "2026-03-01..2026-10-30")
      for lang in ("python", "typescript", "go", "javascript", "java", "rust", "csharp", "ruby", "php", "kotlin")
      for kw in ("acceptance criteria", "- [ ]", "definition of done", "requirements")]
PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "CC0-1.0", "0BSD", "MPL-2.0"}
LIC = ROOT / "bench/data/license_cache.json"
lic_cache = json.loads(LIC.read_text(encoding="utf-8")) if LIC.exists() else {}


def permissive(client, url):
    """Only permissively licensed repos are kept ('free to use'); license looked up once per repo and cached."""
    repo = "/".join(url.split("github.com/")[1].split("/")[:2])
    if repo not in lic_cache:
        try:
            r = client.get(f"https://api.github.com/repos/{repo}", headers=_headers("application/vnd.github+json"))
        except httpx.HTTPError:
            return False                      # network hiccup: skip this PR now, nothing cached, retried next run
        if r.status_code == 404:
            lic_cache[repo] = "none"
        elif r.status_code != 200:
            return False                      # rate limit or server error: do not cache a wrong "none"
        else:
            lic_cache[repo] = (r.json().get("license") or {}).get("spdx_id") or "none"
        LIC.write_text(json.dumps(lic_cache), encoding="utf-8")
    return lic_cache[repo] in PERMISSIVE


import os
BUDGET = int(os.environ.get("MINE_SECONDS", "540"))   # time budget per run; re-running continues where the caches left off
t0, kept = time.time(), 0
DONE = ROOT / "bench/data/large_queries_done.txt"     # search pages already fully processed: later runs continue after them
done_q = set(DONE.read_text(encoding="utf-8").splitlines()) if DONE.exists() else set()
PER_REPO = {}   # at most 2 kept PRs per repo per run, so one repo's template cannot flood the pool
with httpx.Client(timeout=30) as c:
    for q in QS:
        for page in (1, 2):
            if time.time() - t0 > BUDGET: break
            if f"{q}|{page}" in done_q: continue
            try:
                r = c.get("https://api.github.com/search/issues", headers=_headers("application/vnd.github+json"),
                          params={"q": q, "per_page": 30, "page": page})
            except httpx.HTTPError:
                time.sleep(8); continue
            if r.status_code != 200: time.sleep(8); continue
            for it in r.json()["items"]:
                u = it["html_url"]
                if u in skip or u in seen or time.time() - t0 > BUDGET: continue
                seen.add(u)
                if not permissive(c, u): continue
                repo_key = u.split('github.com/')[1].rsplit('/pull/', 1)[0]
                if PER_REPO.get(repo_key, 0) >= 2: continue
                try: b = fetch_pr(u)
                except Exception: continue
                with REJ.open("a", encoding="utf-8") as f: f.write(u + "\n")
                asc = sum(ch.isascii() for ch in b.ask) / max(1, len(b.ask))
                reqs = split_requirements(b.ask)
                if asc > 0.96 and 3 <= len(reqs) <= 8 and 30 <= len(b.hunks) <= 150 and len(b.ask) < 3500:
                    with OUT.open("a", encoding="utf-8") as f: f.write(b.model_dump_json() + "\n")
                    kept += 1; PER_REPO[repo_key] = PER_REPO.get(repo_key, 0) + 1
            if time.time() - t0 <= BUDGET:        # finished this page inside the budget -> never search it again
                with DONE.open("a", encoding="utf-8") as f: f.write(f"{q}|{page}\n")
            time.sleep(2.2)
n = sum(1 for _ in OUT.open(encoding="utf-8")) if OUT.exists() else 0
print("kept this run:", kept, "| pool size:", n)
