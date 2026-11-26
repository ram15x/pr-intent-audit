"""Offline retrieval benchmark: does the right hunk land in the top-k for each gold requirement? No LLM, no quota.

For each gold requirement labelled done/partial with hunk ids: hit@k = any gold hunk in the top-k; recall@k = share of
gold hunks in the top-k. Also reported for PRs with >= 10 hunks, where retrieval actually has to discriminate, and
against the expectation for random ranking. CodeBERT is included only if torch + models/relevance are present.
Writes bench/results/retrieval.json. Usage: python bench/eval_retrieval.py"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from eval_gold_llm import wilson
from pr_audit.lexical import lexical_scorer
from pr_audit.pairs import hunk_text
from pr_audit.retrieval import bm25_scorer, fuse, identifier_boost
from pr_audit.schemas import PRBundle

SETS = [("gold_draft.json", "gold_pool.jsonl"), ("gold_extra_draft.json", "gold_pool.jsonl"), ("gold_large_draft.json", "large_pool.jsonl")]
KS = (1, 3, 5)


def load():
    bundles = {}
    for f in ("bundles.jsonl", "gold_pool.jsonl", "large_pool.jsonl"):
        p = ROOT / "bench/data" / f
        if p.exists():
            for l in open(p, encoding="utf-8"):
                b = PRBundle.model_validate_json(l); bundles[b.source] = b
    cases = []
    for gf, _ in SETS:
        for g in json.loads((ROOT / "bench/gold" / gf).read_text(encoding="utf-8")):
            b = bundles.get(g["pr"])
            if not b:
                continue
            ids = {h.id for h in b.hunks}
            for r in g["requirements"]:
                rel = [h for h in r["hunks"] if h in ids]
                if r["status"] in ("done", "partial") and rel:
                    cases.append(dict(pr=g["pr"], text=r["text"], rel=set(rel), bundle=b))
    return cases


def evaluate(scorer, cases, full=False):
    agg = {k: dict(hit=0, rec=0.0, n=0) for k in KS}; sub = {k: dict(hit=0, n=0) for k in KS}; rnd = {k: 0.0 for k in KS}; rbig = {k: 0.0 for k in KS}; nbig = 0
    for c in cases:
        b = c["bundle"]
        ht = [hunk_text(h, limit=10**9 if full else 1500) for h in b.hunks]
        sc = scorer([(c["text"], h) for h in ht])
        order = [b.hunks[j].id for j in sorted(range(len(ht)), key=lambda j: -sc[j])]
        big = len(b.hunks) >= 10; nbig += big
        for k in KS:
            top = set(order[:k]); hit = bool(top & c["rel"])
            agg[k]["hit"] += hit; agg[k]["rec"] += len(top & c["rel"]) / len(c["rel"]); agg[k]["n"] += 1
            if big:
                sub[k]["hit"] += hit; sub[k]["n"] += 1
            n, m = len(order), len(c["rel"])
            rh = 1.0 if k >= n else 1 - (1 - min(k, n) / n) ** m      # rough random-ranking hit chance
            rnd[k] += rh; rbig[k] += rh if big else 0.0
    out = {}
    for k in KS:
        n = agg[k]["n"]
        out[f"hit@{k}"] = dict(value=round(agg[k]["hit"] / n, 3), ci=wilson(agg[k]["hit"], n), n=n,
                               recall=round(agg[k]["rec"] / n, 3), random_baseline=round(rnd[k] / n, 3))
        if sub[k]["n"]:
            out[f"hit@{k}_big_prs"] = dict(value=round(sub[k]["hit"] / sub[k]["n"], 3), ci=wilson(sub[k]["hit"], sub[k]["n"]), n=sub[k]["n"], random_baseline=round(rbig[k] / sub[k]["n"], 3))
    return out


if __name__ == "__main__":
    cases = load()
    lex = lexical_scorer()
    variants = {"lexical (IDF overlap)": (lex, False), "lexical, full hunk text": (lex, True),
                "bm25": (bm25_scorer(), False), "bm25, full hunk text": (bm25_scorer(), True),
                "fusion lexical+bm25": (fuse(lex, bm25_scorer()), False),
                "bm25 + named identifiers/paths (full text)": (identifier_boost(bm25_scorer()), True),
                "lexical + named identifiers/paths": (identifier_boost(lex), False)}
    try:
        from pr_audit.audit import load_scorer
        cb = load_scorer(ROOT / "models/relevance")
        variants["CodeBERT cross-encoder (ours)"] = (cb, False)
        variants["fusion CodeBERT+lexical"] = (fuse(cb, lex), False)
    except Exception as e:
        print("CodeBERT skipped:", type(e).__name__, str(e)[:80])
    res = {"n_requirements": len(cases), "n_prs": len({c["pr"] for c in cases}), "variants": {}}
    for name, (sc, full) in variants.items():
        res["variants"][name] = evaluate(sc, cases, full)
        v = res["variants"][name]
        print(f"{name:34s} hit@1 {v['hit@1']['value']:.2f}  hit@3 {v['hit@3']['value']:.2f}  hit@5 {v['hit@5']['value']:.2f} {v['hit@5']['ci']}"
              + (f"  big-PR hit@5 {v['hit@5_big_prs']['value']:.2f} (n={v['hit@5_big_prs']['n']}, random {v['hit@5_big_prs']['random_baseline']:.2f})" if "hit@5_big_prs" in v else ""))
    print("random hit@5:", res["variants"]["lexical (IDF overlap)"]["hit@5"]["random_baseline"], "| n =", len(cases))
    out_p = ROOT / "bench/results/retrieval.json"
    if out_p.exists():      # keep rows from an earlier run that this machine cannot reproduce (e.g. CodeBERT without torch)
        prev = json.loads(out_p.read_text(encoding="utf-8"))
        if prev.get("n_requirements") != res["n_requirements"]:
            print("NOTE: the gold set changed since the earlier run; rows that need torch (CodeBERT) are dropped, re-run on a machine with torch")
            prev = {}
        for name, v in prev.get("variants", {}).items():
            if name not in res["variants"]:
                res["variants"][name] = v
                print(f"(kept from earlier run: {name})")
    out_p.write_text(json.dumps(res, indent=1), encoding="utf-8")
