"""Mine merged public PRs that close an issue. Resumable. Usage: python bench/mine.py [target] [per_repo_cap]"""
import json, random, sys, time
from collections import Counter
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pr_audit.env import load_env
load_env(Path(__file__).resolve().parents[1] / ".env")
from pr_audit.ingest import fetch_pr, _headers

OUT = Path(__file__).parent / "data" / "bundles.jsonl"
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 40
CAP = int(sys.argv[2]) if len(sys.argv) > 2 else 3
QUERY = "is:pr is:merged linked:issue language:python comments:<8 created:2024-01-01..2026-06-30"

seen, per_repo = set(), Counter()
if OUT.exists():
    for line in OUT.read_text(encoding="utf-8").splitlines():
        d = json.loads(line); seen.add(d["source"]); per_repo["/".join(d["source"].split("/")[3:5])] += 1
rng = random.Random(int(time.time()) % 1000)
t0, kept = time.time(), 0
with httpx.Client(timeout=30) as c:
    while kept < TARGET and time.time() - t0 < 150:
        page = rng.randint(1, 10)
        r = c.get("https://api.github.com/search/issues", headers=_headers("application/vnd.github+json"),
                  params={"q": QUERY, "per_page": 30, "page": page})
        if r.status_code != 200:
            print("search", r.status_code, r.text[:120]); time.sleep(10); continue
        for it in r.json()["items"]:
            url = it["html_url"]; repo = "/".join(url.split("/")[3:5])
            if url in seen or per_repo[repo] >= CAP:
                continue
            seen.add(url)
            try:
                b = fetch_pr(url)
            except Exception as e:
                continue
            if b.ask_source != "issue" or len(b.ask) < 120 or not (2 <= len(b.hunks) <= 30):
                continue
            with OUT.open("a", encoding="utf-8") as f:
                f.write(b.model_dump_json() + "\n")
            per_repo[repo] += 1; kept += 1
            print(f"kept {kept}: {repo} ({len(b.hunks)} hunks)")
            if kept >= TARGET or time.time() - t0 > 150: break
        time.sleep(2)
print("total in file:", sum(1 for _ in OUT.open(encoding="utf-8")), "repos:", len(per_repo))
