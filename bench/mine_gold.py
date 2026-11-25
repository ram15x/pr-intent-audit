"""Mine a pool of merged PRs whose ask has explicit acceptance criteria / checklists (easier to label correctly)."""
import json, re, sys, time
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.env import load_env
load_env(ROOT / ".env")
from pr_audit.ingest import fetch_pr, _headers
from pr_audit.requirements import split_requirements

OUT = ROOT / "bench/data/gold_pool.jsonl"
skip = {g["pr"] for g in json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))}
skip |= {json.loads(l)["source"] for l in open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8")}   # keep gold out of training data
seen = {json.loads(l)["source"] for l in open(OUT, encoding="utf-8")} if OUT.exists() else set()
QS = ['is:pr is:merged linked:issue language:python "definition of done" comments:<8 created:2025-03-01..2026-10-30',
      'is:pr is:merged linked:issue language:python "## Requirements" comments:<8 created:2025-03-01..2026-10-30',
      'is:pr is:merged linked:issue language:go "acceptance criteria" comments:<8 created:2025-03-01..2026-10-30',
      'is:pr is:merged linked:issue language:javascript "- [ ]" comments:<8 created:2025-03-01..2026-10-30',
      'is:pr is:merged linked:issue language:python "acceptance criteria" comments:<6 created:2025-06-01..2026-10-30',
      'is:pr is:merged linked:issue language:python "- [ ]" comments:<6 created:2025-06-01..2026-10-30',
      'is:pr is:merged linked:issue language:typescript "acceptance criteria" comments:<6 created:2025-06-01..2026-10-30']
t0, kept = time.time(), 0
with httpx.Client(timeout=30) as c:
    for q in QS:
        for page in (1, 2, 3):
            if time.time() - t0 > 150: break
            r = c.get("https://api.github.com/search/issues", headers=_headers("application/vnd.github+json"),
                      params={"q": q, "per_page": 30, "page": page})
            if r.status_code != 200: time.sleep(8); continue
            for it in r.json()["items"]:
                u = it["html_url"]
                if u in skip or u in seen or time.time() - t0 > 150: continue
                seen.add(u)
                try: b = fetch_pr(u)
                except Exception: continue
                asc = sum(ch.isascii() for ch in b.ask) / max(1, len(b.ask))
                reqs = split_requirements(b.ask)
                if b.ask_source == "issue" and asc > 0.96 and 3 <= len(reqs) <= 8 and 3 <= len(b.hunks) <= 12 and len(b.ask) < 3500:
                    with OUT.open("a", encoding="utf-8") as f: f.write(b.model_dump_json() + "\n")
                    kept += 1
            time.sleep(2.2)
n = sum(1 for _ in OUT.open(encoding="utf-8")) if OUT.exists() else 0
print("kept this run:", kept, "| pool size:", n)
