"""Model 2 (verdict) + model 3 (scope-creep) on top of the trained relevance model.

relevance model -> requirement x hunk score matrix -> coverage features -> small classifier.
Also: hunks no requirement claims are flagged as scope-creep candidates (measured on creep cases).
Compared against the same pipeline fed by plain keyword overlap, to show what the trained model adds.
Usage: python bench\\train_verdict.py     (needs models/relevance from train_relevance.py)
"""
import json, re, sys, joblib
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import confusion_matrix, f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.coverage import best_per_req, features, orphan_flags
from pr_audit.inject import build_cases
from pr_audit.pairs import hunk_text, repo_of, split_of
from pr_audit.requirements import clean_ask, split_requirements
from pr_audit.schemas import PRBundle

LABELS = ["done", "partial", "missing"]
dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(ROOT / "models/relevance")
model = AutoModelForSequenceClassification.from_pretrained(ROOT / "models/relevance").to(dev).eval()
cache: dict = {}


@torch.no_grad()
def model_scores(pairs):
    todo = [p for p in dict.fromkeys(pairs) if p not in cache]
    for i in range(0, len(todo), 32):
        b = todo[i:i + 32]
        enc = tok([x[0] for x in b], [x[1] for x in b], truncation="only_second", max_length=384,
                  padding=True, return_tensors="pt").to(dev)
        with torch.autocast(dev, enabled=dev == "cuda"):
            p = torch.softmax(model(**enc).logits.float(), -1)[:, 1].cpu().tolist()
        cache.update(zip(b, p))
    return [cache[p] for p in pairs]


words = lambda s: set(re.findall(r"[a-z][a-z0-9_]{2,}", s.lower()))
def kw_scores(pairs):
    return [len(words(r) & words(h)) / (len(words(r)) or 1) for r, h in pairs]


def matrix(scorer, reqs, htexts):
    flat = scorer([(r, h) for r in reqs for h in htexts])
    n = len(htexts)
    return [flat[i * n:(i + 1) * n] for i in range(len(reqs))]


bundles = [PRBundle.model_validate_json(l) for l in open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8")]
cases = build_cases(bundles, seed=0)
# old hunk-cutting "partial" labels are too noisy to train on; composite cases have exact truth
cases = [c for c in cases if c.kind != "partial"]
print("cases:", Counter(c.kind for c in cases))

rows = []
for c in cases:
    reqs = c.meta.get("reqs") or [r.text for r in split_requirements(c.ask)] or [clean_ask(c.ask)[:400] or c.ask[:400]]
    ht = [hunk_text(h) for h in c.hunks]
    repo = repo_of(c.case_id.split("#")[0])
    m_model, m_kw = matrix(model_scores, reqs, ht), matrix(kw_scores, reqs, ht)
    k, meta, n = c.kind, c.meta, len(reqs)
    if k == "composite_partial":
        na = len(meta["reqs_done_in_partial"]); truth = [1] * na + [0] * (n - na)
    else:
        truth = [0] * n if k == "mismatch" else [1] * n          # clean / composite_full / creep: ask is met
    rows.append(dict(c=c, repo=repo, req_best=best_per_req(m_model), req_truth=truth,
                     req_best_kw=best_per_req(m_kw),
                      split=split_of(repo), y=LABELS.index(c.label.value),
                     fm=features(m_model), fk=features(m_kw), om=orphan_flags(m_model), ok=orphan_flags(m_kw, 0.34)))
print("scored", len(rows), "cases")


def macro_f1_ci(rs, preds, n=1000):
    by = {}
    for r, p in zip(rs, preds): by.setdefault(r["repo"], []).append((r["y"], p))
    repos, rng, v = list(by), np.random.default_rng(0), []
    for _ in range(n):
        pick = [x for rp in rng.choice(repos, len(repos)) for x in by[rp]]
        v.append(f1_score([a for a, _ in pick], [b for _, b in pick], average="macro", labels=[0, 1, 2], zero_division=0))
    return [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]


out = {"n_prs": len(bundles), "labels": LABELS, "cases": dict(Counter(r["split"] for r in rows))}
for name, key in (("trained_relevance", "fm"), ("keyword_overlap", "fk")):
    tr = [r for r in rows if r["split"] == "train"]
    clf = GradientBoostingClassifier(n_estimators=150, max_depth=2, random_state=0).fit([r[key] for r in tr], [r["y"] for r in tr])
    res = {}
    for sp in ("val", "test"):
        rs = [r for r in rows if r["split"] == sp]
        pred = clf.predict([r[key] for r in rs]).tolist()
        y = [r["y"] for r in rs]
        res[sp] = {"n": len(rs), "acc": round(float(np.mean([a == b for a, b in zip(y, pred)])), 3),
                   "macro_f1": round(f1_score(y, pred, average="macro", labels=[0, 1, 2], zero_division=0), 3),
                   "macro_f1_95ci": macro_f1_ci(rs, pred) if len({r["repo"] for r in rs}) > 1 else None,
                   "confusion[done,partial,missing]": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist()}
    out[name] = res
out["majority_class_acc_test"] = round(max(Counter(r["y"] for r in rows if r["split"] == "test").values()) /
                                       max(1, sum(1 for r in rows if r["split"] == "test")), 3)

# scope-creep: on creep cases, are foreign hunks orphaned (recall) and own hunks spared (false alarm)?
creep = {}
for name, key in (("trained_relevance", "om"), ("keyword_overlap", "ok")):
    tp = fn = fp = tn = 0
    for r in rows:
        c = r["c"]
        if c.kind != "creep" or r["split"] == "train": continue
        for h, orphan in zip(c.hunks, r[key]):
            if h.id in c.unrequested: tp += orphan; fn += (not orphan)
            else: fp += orphan; tn += (not orphan)
    creep[name] = {"foreign_hunks_flagged": f"{tp}/{tp + fn}", "own_hunks_wrongly_flagged": f"{fp}/{fp + tn}"}
out["scope_creep_val_test"] = creep

# --- requirement-level threshold (picked on VAL, reported on TEST) ---
def req_pairs(sp, key="req_best"):
    return [(b, t) for r in rows if r["split"] == sp for b, t in zip(r[key], r["req_truth"])]
def f1_at(pairs, tau):
    tp = sum(b >= tau and t for b, t in pairs); fp = sum(b >= tau and not t for b, t in pairs)
    fn = sum(b < tau and t for b, t in pairs)
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return p, rc, (2 * p * rc / (p + rc) if p + rc else 0.0)
val_p = req_pairs("val")
tau = max((x / 100 for x in range(5, 96, 5)), key=lambda t: f1_at(val_p, t)[2])
band = 0.10
tp_, tr_, tf_ = f1_at(req_pairs("test"), tau)
test_p = req_pairs("test")
out["requirement_level"] = {"tau": tau, "unclear_band": band, "val_pairs": len(val_p), "test_pairs": len(test_p),
    "test_covered_precision": round(tp_, 3), "test_covered_recall": round(tr_, 3), "test_f1": round(tf_, 3),
    "test_share_in_unclear_band": round(sum(abs(b - tau) < band for b, _ in test_p) / max(1, len(test_p)), 3),
    "keyword_test_f1_at_best_val_tau": round(f1_at(req_pairs("test", "req_best_kw"),
        max((x / 100 for x in range(5, 96, 5)), key=lambda t: f1_at(req_pairs("val", "req_best_kw"), t)[2]))[2], 3)}
# --- final verdict classifier (train+val) saved for the CLI ---
fit = [r for r in rows if r["split"] != "test"]
final = GradientBoostingClassifier(n_estimators=150, max_depth=2, random_state=0).fit([r["fm"] for r in fit], [r["y"] for r in fit])
(ROOT / "models").mkdir(exist_ok=True)
joblib.dump(final, ROOT / "models/verdict.joblib")
(ROOT / "models/verdict.json").write_text(json.dumps({"tau": tau, "band": band, "labels": LABELS}), encoding="utf-8")
(ROOT / "bench/results/verdict_metrics.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
