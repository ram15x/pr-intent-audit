"""Scope-creep candidate quality (offline, no LLM): hunks (not tests/docs) whose best requirement relevance is below a
threshold are flagged; compared with the hand-labelled creep_hunks in bench/gold/gold_draft.json.
Only 11 labelled creep hunks exist (large/extra gold sets have none), so read this as anecdotal. Writes bench/results/creep.json"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.coverage import best_per_hunk
from pr_audit.inject import is_substantive
from pr_audit.lexical import lexical_scorer
from pr_audit.pairs import hunk_text
from pr_audit.schemas import PRBundle

bundles = {}
for f in ("bundles.jsonl", "gold_pool.jsonl"):
    for l in open(ROOT / "bench/data" / f, encoding="utf-8"):
        b = PRBundle.model_validate_json(l); bundles[b.source] = b
gold = json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))
lex = lexical_scorer()
rows = []
for g in gold:
    b = bundles[g["pr"]]
    texts = [r["text"] for r in g["requirements"] if r["status"] != "exclude"]
    ht = [hunk_text(h) for h in b.hunks]
    flat = lex([(t, h) for t in texts for h in ht]); n = len(ht)
    m = [flat[i * n:(i + 1) * n] for i in range(len(texts))]
    for h, s in zip(b.hunks, best_per_hunk(m)):
        if is_substantive(h):
            rows.append((s, h.id in {c["hunk"] for c in g.get("creep_hunks", [])}))
pos = sum(p for _, p in rows)
print(f"substantive hunks {len(rows)}, labelled creep {pos}, base rate {pos/len(rows):.2f}")
out = {"hunks": len(rows), "creep": pos, "thresholds": {}}
for thr in (0.2, 0.3, 0.4, 0.5, 0.6):
    fl = [p for s, p in rows if s < thr]; tp = sum(fl)
    out["thresholds"][str(thr)] = dict(flagged=len(fl), true_creep=tp, precision=round(tp / len(fl), 2) if fl else None, recall=round(tp / pos, 2) if pos else None)
    print(thr, out["thresholds"][str(thr)])
(ROOT / "bench/results/creep.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
