"""Keyword-overlap baseline for the relevance task. The trained model must beat this to count."""
import json, re, sys
from pathlib import Path
from sklearn.metrics import roc_auc_score
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pr_audit.schemas import PRBundle
from pr_audit.pairs import build_pairs

tok = lambda s: set(w for w in re.findall(r"[a-z][a-z0-9_]{2,}", s.lower()))
bs = [PRBundle.model_validate_json(l) for l in open(Path(__file__).parent / "data" / "bundles.jsonl", encoding="utf-8")]
rows = build_pairs(bs)
out = {"n_prs": len(bs)}
for split in ("val", "test"):
    r = [x for x in rows if x["split"] == split]
    sc = [len(tok(x["req"]) & tok(x["hunk"])) / (len(tok(x["req"])) or 1) for x in r]
    y = [x["label"] for x in r]
    hard = [(s, l) for s, l, x in zip(sc, y, r) if x["label"] == 1 or x.get("hard")]
    out[split] = {"n": len(r), "auc_all": round(roc_auc_score(y, sc), 3),
                  "auc_hard_negs_only": round(roc_auc_score([l for _, l in hard], [s for s, _ in hard]), 3)}
print(json.dumps(out, indent=1))
(Path(__file__).parent / "results" / "relevance_baseline.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
