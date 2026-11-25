"""Add more merged, issue-closing PRs from repos already in the dataset (for same-repo hard negatives)."""
import json, sys, time
from collections import Counter
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pr_audit.env import load_env
load_env(Path(__file__).resolve().parents[1] / ".env")
from pr_audit.ingest import fetch_pr, _headers

OUT = Path(__file__).parent / "data" / "bundles.jsonl"
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 6
seen, per = set(), Counter()
for l in OUT.read_text(encoding="utf-8").splitlines():
    s = json.loads(l)["source"]; seen.add(s); per["/".join(s.split("/")[3:5])] += 1
# smallest-but-not-empty repos first, so coverage evens out
repos = [r for r, _ in sorted(per.items(), key=lambda kv: kv[1]) if per[r] < CAP]
t0, kept = time.time(), 0
with httpx.Client(timeout=30) as c:
    for repo in repos:
        if time.time() - t0 > 150: break
        r = c.get("https://api.github.com/search/issues", headers=_headers("application/vnd.github+json"),
                  params={"q": f"repo:{repo} is:pr is:merged linked:issue", "per_page": 20})
        if r.status_code != 200:
            time.sleep(8); continue
        for it in r.json().get("items", []):
            url = it["html_url"]
            if url in seen or per[repo] >= CAP or time.time() - t0 > 150: continue
            seen.add(url)
            try: b = fetch_pr(url)
            except Exception: continue
            if b.ask_source != "issue" or len(b.ask) < 120 or not (2 <= len(b.hunks) <= 30): continue
            with OUT.open("a", encoding="utf-8") as f: f.write(b.model_dump_json() + "\n")
            per[repo] += 1; kept += 1
        time.sleep(2.2)   # search API: 30/min
print("added", kept)
c2 = Counter()
for l in OUT.read_text(encoding="utf-8").splitlines():
    c2["/".join(json.loads(l)["source"].split("/")[3:5])] += 1
print("PRs", sum(c2.values()), "| repos", len(c2), "| repos with >=3 PRs:", sum(1 for v in c2.values() if v >= 3))
