"""Offline measurement of the requirement splitter against the gold labels (no LLM, no API).

For each gold PR: split its ask, match each output to a gold entry by normalised text, then report
  precision = outputs that gold calls real requirements / all outputs that match a gold entry
  kept      = gold non-exclude requirements that the splitter still produces
Gold entries were created from an earlier version of the splitter, so recall for requirements it never produced
is NOT measured here. Unmatched outputs are listed so a human can look at them."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.requirements import split_requirements

norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
B = {}
for f in ("bundles.jsonl", "gold_pool.jsonl", "large_pool.jsonl"):
    p = ROOT / "bench/data" / f
    if p.exists():
        for l in open(p, encoding="utf-8"):
            b = json.loads(l); B[b["source"]] = b
tot = dict(out=0, matched=0, real=0, gold_real=0, kept=0)
unmatched, lost = [], []
for gf in ("gold_draft.json", "gold_large_draft.json"):
    for g in json.load(open(ROOT / "bench/gold" / gf, encoding="utf-8")):
        outs = [norm(r.text) for r in split_requirements(B[g["pr"]]["ask"])]
        gold = {norm(r["text"]): r["status"] for r in g["requirements"]}
        for o in outs:
            tot["out"] += 1
            if o in gold:
                tot["matched"] += 1; tot["real"] += gold[o] != "exclude"
            else:
                unmatched.append((g["pr"].split("github.com/")[1], o[:90]))
        for t, st in gold.items():
            if st != "exclude":
                tot["gold_real"] += 1
                if t in outs: tot["kept"] += 1
                else: lost.append((g["pr"].split("github.com/")[1], st, t[:90]))
print(json.dumps(tot))
(ROOT / "bench/results/splitter.json").write_text(json.dumps(dict(
    **tot, precision_on_matched=round(tot["real"] / max(1, tot["matched"]), 3),
    note="in-sample: noise rules were written after reading these gold PRs; not a held-out score"), indent=1), encoding="utf-8")
print(f'precision on matched outputs: {tot["real"]}/{tot["matched"]} = {tot["real"]/max(1,tot["matched"]):.3f}')
print(f'gold real requirements still produced: {tot["kept"]}/{tot["gold_real"]}')
if "-v" in sys.argv:
    print("\nLOST gold requirements:"); [print(" ", x) for x in lost]
    print("\nUNMATCHED outputs (new, not in gold):"); [print(" ", x) for x in unmatched]
