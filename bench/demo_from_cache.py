"""Render real audits from the saved judge responses (.cache/llm) only: no network, no quota. A prompt not in the cache
becomes a 'judge error' (shown as UNCLEAR), never a guess. Picks the gold PR whose requirements are best covered by the cache.
Usage: python bench/demo_from_cache.py [out.html]"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.audit import run_audit
from pr_audit.html_report import render_html
from pr_audit.judge import judge_requirement
from pr_audit.lexical import lexical_scorer
from pr_audit.llm import LLM
from pr_audit.schemas import PRBundle


class CacheOnly(LLM):
    def __call__(self, prompt):
        import hashlib
        f = self.dir / (hashlib.sha256(prompt.encode()).hexdigest()[:24] + ".json")
        if not f.exists():
            raise RuntimeError("not in cache")
        self.calls["cache"] += 1
        return json.loads(f.read_text(encoding="utf-8"))["text"]


bundles = {}
for f in ("bundles.jsonl", "gold_pool.jsonl", "large_pool.jsonl"):
    p = ROOT / "bench/data" / f
    if p.exists():
        for l in open(p, encoding="utf-8"):
            b = PRBundle.model_validate_json(l); bundles[b.source] = b
lic = json.loads((ROOT / "bench/results/licenses.json").read_text(encoding="utf-8"))     # only permissively licensed repos may appear in a published demo
ok_repos = {r for r, v in lic.items() if v["permissive"]}
bundles = {u: b for u, b in bundles.items() if "/".join(u.split("github.com/")[1].split("/")[:2]) in ok_repos}
llm = CacheOnly(ROOT / ".cache/llm", providers=())
best = None
for u, b in bundles.items():
    if not b.hunks or not b.ask.strip():
        continue
    n0 = llm.calls["cache"]
    errs = []
    def judge(i, t, top):
        j = judge_requirement(llm, i, t, top, verify=True)
        if j.reason.startswith("judge error"): errs.append(i)
        return j
    try:
        a = run_audit(b, lexical_scorer(), None, judge=judge)
    except Exception:
        continue
    hit = llm.calls["cache"] - n0
    if len(a.reqs) >= 3 and hit >= 3 and not errs and (best is None or (hit, len(a.bundle.hunks)) > best[0]):
        best = ((hit, len(a.bundle.hunks)), u, a)
if not best:
    sys.exit("no PR is fully covered by the cache")
(_, u, a) = best
# compare with the hand labels (same PR) so the demo shows where it is wrong, not only where it is right
gold = {}
for gf in ("gold_draft.json", "gold_extra_draft.json", "gold_large_draft.json"):
    for g in json.loads((ROOT / "bench/gold" / gf).read_text(encoding="utf-8")):
        gold[g["pr"]] = {" ".join(r["text"].split()): r["status"] for r in g["requirements"]}
for r in a.reqs:
    gs = gold.get(u, {}).get(" ".join(r.text.split()))
    if gs == "unclear" and r.status in ("done", "partial"):
        a.bundle.notes.append(f"Demo note: for requirement #{r.id} the hand label is UNCLEAR (not decidable from the diff alone) but this audit says {r.status.upper()}; check its evidence before trusting it.")
    if gs and gs not in ("exclude", "unclear") and r.status in ("done", "partial", "missing") and gs != r.status:
        a.bundle.notes.append(f"Demo note: for requirement #{r.id} the hand label is {gs.upper()} but this audit says {r.status.upper()}. That is a judge error, left in on purpose.")
out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs/demo_report.html")
out.write_text(render_html(a, "Demo: real audit built from saved judge responses (lexical retrieval + Groq gpt-oss-120b judge + our verifier); no live run."), encoding="utf-8")
print(u, "| requirements", len(a.reqs), "| rank", a.rank, a.band, "| statuses", [r.status for r in a.reqs], "->", out)
