"""Fine-tune a code encoder as a (requirement, hunk) relevance cross-encoder. Runs on a 4GB GPU.

Usage (on the GPU machine):  python bench/train_relevance.py [epochs=3] [base=microsoft/codebert-base]
Writes: models/relevance/ (gitignored) and bench/results/relevance_metrics.json
Select the checkpoint by VAL auc; report TEST once. Splits are by repository.
"""
import json, random, shutil, sys
from pathlib import Path
import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.schemas import PRBundle
from pr_audit.pairs import build_commit_pairs, build_pairs

EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BASE = sys.argv[2] if len(sys.argv) > 2 else "microsoft/codebert-base"
MAXLEN, BS, ACCUM, LR = 384, 8, 4, 2e-5
random.seed(0); torch.manual_seed(0)

bundles = [PRBundle.model_validate_json(l) for l in open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8")]
# hold out the gold PRs entirely, so gold evaluation is not contaminated by training
gold_prs = {g["pr"] for g in json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))}
bundles = [b for b in bundles if b.source not in gold_prs]
sup_file = ROOT / "bench/data/commit_supervision.jsonl"
sup = {}
if sup_file.exists():
    for l in open(sup_file, encoding="utf-8"):
        d = json.loads(l); sup[d["source"]] = d
rows = build_pairs(bundles) + build_commit_pairs(bundles, sup)
if (ROOT / "models/relevance").exists() and not (ROOT / "models/relevance_v1").exists():
    shutil.copytree(ROOT / "models/relevance", ROOT / "models/relevance_v1")   # keep the old model
split = {s: [r for r in rows if r["split"] == s] for s in ("train", "val", "test")}
split["train"] += [r for r in split["train"] if r.get("within")] * 2      # upweight within-PR rows x3
print({k: len(v) for k, v in split.items()}, "within-PR rows:", {k: sum(1 for r in v if r.get("within")) for k, v in split.items()})

dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=2).to(dev)
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
scaler = torch.cuda.amp.GradScaler(enabled=dev == "cuda")


def collate(batch):
    enc = tok([b["req"] for b in batch], [b["hunk"] for b in batch], truncation="only_second",
              max_length=MAXLEN, padding=True, return_tensors="pt")
    enc["labels"] = torch.tensor([b["label"] for b in batch])
    return enc


@torch.no_grad()
def evaluate(rs, ci=False):
    model.eval(); probs = []
    for b in DataLoader(rs, batch_size=16, collate_fn=collate):
        b = {k: v.to(dev) for k, v in b.items()}
        with torch.autocast(dev, enabled=dev == "cuda"):
            logits = model(**{k: v for k, v in b.items() if k != "labels"}).logits
        probs += torch.softmax(logits.float(), -1)[:, 1].cpu().tolist()
    y = [r["label"] for r in rs]
    hard = [i for i, r in enumerate(rs) if r["label"] == 1 or r.get("hard")]
    if ci:
        return bootstrap(rs, probs)
    wi = [i for i, r in enumerate(rs) if r.get("within")]
    aw = None
    if len({y[i] for i in wi}) == 2:
        aw = round(roc_auc_score([y[i] for i in wi], [probs[i] for i in wi]), 3)
    return {"auc_within_pr": aw, "n_within": len(wi), "auc": round(roc_auc_score(y, probs), 3),
            "auc_hard_negs_only": round(roc_auc_score([y[i] for i in hard], [probs[i] for i in hard]), 3),
            "acc@0.5": round(float(np.mean([(p > .5) == bool(l) for p, l in zip(probs, y)])), 3)}


def bootstrap(rs, probs, n=1000):
    """Resample whole repos (not rows) so the interval reflects repo-to-repo variation."""
    by = {}
    for r, p in zip(rs, probs):
        by.setdefault(r["repo"], []).append((r["label"], p, bool(r.get("hard"))))
    repos, rng, aucs, haucs = list(by), np.random.default_rng(0), [], []
    for _ in range(n):
        pick = [x for rp in rng.choice(repos, len(repos)) for x in by[rp]]
        y = [a for a, _, _ in pick]
        if len(set(y)) < 2: continue
        aucs.append(roc_auc_score(y, [b for _, b, _ in pick]))
        h = [(a, b) for a, b, hd in pick if a == 1 or hd]
        if len({a for a, _ in h}) == 2: haucs.append(roc_auc_score([a for a, _ in h], [b for _, b in h]))
    q = lambda v: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)] if v else None
    return {"auc_95ci": q(aucs), "auc_hard_95ci": q(haucs), "n_repos": len(repos)}


best, hist = -1, []
for ep in range(EPOCHS):
    model.train(); random.shuffle(split["train"]); step = 0
    for b in DataLoader(split["train"], batch_size=BS, collate_fn=collate):
        b = {k: v.to(dev) for k, v in b.items()}
        with torch.autocast(dev, enabled=dev == "cuda"):
            loss = model(**b).loss / ACCUM
        scaler.scale(loss).backward(); step += 1
        if step % ACCUM == 0:
            scaler.step(opt); scaler.update(); opt.zero_grad()
    m = evaluate(split["val"]); hist.append({"epoch": ep + 1, "val": m}); print(hist[-1])
    sel = (m["auc"] + m["auc_within_pr"]) / 2 if m["auc_within_pr"] else m["auc"]
    if sel > best:
        best = sel; model.save_pretrained(ROOT / "models/relevance"); tok.save_pretrained(ROOT / "models/relevance")

model = AutoModelForSequenceClassification.from_pretrained(ROOT / "models/relevance").to(dev)
res = {"base": BASE, "n_prs": len(bundles), "history": hist, "test": evaluate(split["test"]), "test_ci": evaluate(split["test"], ci=True)}
(ROOT / "bench/results/relevance_metrics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res["test"])); print(json.dumps(res["test_ci"]))
