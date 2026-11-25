"""For each mined PR, fetch its commits and map each commit's hunks onto the final PR hunks. Resumable."""
import json, sys, time
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pr_audit.env import load_env
load_env(Path(__file__).resolve().parents[1] / ".env")
from pr_audit.commits import map_commit_hunks
from pr_audit.diffs import parse_diff
from pr_audit.ingest import PR_URL, _headers
from pr_audit.schemas import PRBundle

D = Path(__file__).parent / "data"
OUT = D / "commit_supervision.jsonl"
bundles = [PRBundle.model_validate_json(l) for l in open(D / "bundles.jsonl", encoding="utf-8")]
done = {json.loads(l)["source"] for l in open(OUT, encoding="utf-8")} if OUT.exists() else set()
t0, kept, tried = time.time(), 0, 0
with httpx.Client(timeout=30, follow_redirects=True) as c:
    for b in bundles:
        if b.source in done: continue
        if time.time() - t0 > 150: break
        o, r, n = PR_URL.search(b.source).groups(); api = f"https://api.github.com/repos/{o}/{r}"
        rec = {"source": b.source, "commits": []}
        try:
            cm = c.get(f"{api}/pulls/{n}/commits", headers=_headers("application/vnd.github+json"), params={"per_page": 40})
            cm.raise_for_status(); cm = cm.json()
            if 2 <= len(cm) <= 15:
                for x in cm:
                    if len(x.get("parents", [])) > 1: continue
                    d = c.get(f"{api}/commits/{x['sha']}", headers=_headers("application/vnd.github.diff"))
                    if d.status_code != 200: continue
                    hs, _ = parse_diff(d.text)
                    ids = map_commit_hunks(hs, b.hunks)
                    if ids: rec["commits"].append({"sha": x["sha"][:10], "message": x["commit"]["message"][:400], "hunks": ids})
        except Exception as e:
            pass
        tried += 1
        with OUT.open("a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")   # also records empties so we skip them next time
        kept += len(rec["commits"]) >= 2
print(f"tried {tried}, usable (>=2 mapped commits) {kept}, elapsed {int(time.time()-t0)}s")
useful = [json.loads(l) for l in open(OUT, encoding="utf-8")]
print("total records", len(useful), "| usable PRs", sum(len(u["commits"]) >= 2 for u in useful),
      "| commit->hunks examples", sum(len(u["commits"]) for u in useful if len(u["commits"]) >= 2))
