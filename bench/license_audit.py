"""License of every repo behind the gold PRs (GitHub API). Writes bench/results/licenses.json. Needs GITHUB_TOKEN in .env."""
import json, sys
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from pr_audit.env import load_env
from pr_audit.ingest import _headers
load_env(ROOT / ".env")
PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "CC0-1.0", "0BSD", "MPL-2.0"}
repos = {}
for gf in ("gold_draft", "gold_extra_draft", "gold_large_draft"):
    for g in json.loads((ROOT / "bench/gold" / f"{gf}.json").read_text(encoding="utf-8")):
        repos.setdefault("/".join(g["pr"].split("github.com/")[1].split("/")[:2]), []).append(g["pr"])
out = {}
with httpx.Client(timeout=30, headers=_headers("application/vnd.github+json")) as c:
    for r in sorted(repos):
        j = c.get(f"https://api.github.com/repos/{r}").json()
        spdx = (j.get("license") or {}).get("spdx_id") or "none"
        out[r] = dict(license=spdx, permissive=spdx in PERMISSIVE, prs=len(repos[r]), private=j.get("private"))
        print(f"{r:48s} {spdx}")
(ROOT / "bench/results/licenses.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("permissive:", sum(v["permissive"] for v in out.values()), "of", len(out))
