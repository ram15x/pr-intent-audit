"""Evaluate the audit on the hand-checked gold PRs (requirement-level), plus exact fault injection.

1. clean:   audit each gold PR with its curated requirements; compare to gold labels (done vs not-done).
2. faults:  for each gold DONE requirement, delete the hunks only it relies on; the audit should stop saying DONE
            for it (caught) without flipping the other requirements (false alarm).
Writes bench/results/gold_eval.json. NOTE: labels are drafts unless reviewed_by_human is true.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.audit import run_audit
from pr_audit.schemas import PRBundle


def evaluate(scorer, clf, tau, band, gold, bundles):
    res = {"clean": {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "abstain": 0, "n": 0},
           "faults": {"n": 0, "caught_not_done": 0, "caught_missing": 0, "other_reqs": 0, "other_flipped": 0},
           "detail": []}
    for g in gold:
        b = bundles[g["pr"]]
        reqs = [r for r in g["requirements"] if r["status"] != "exclude"]
        texts = [r["text"] for r in reqs]
        clean = run_audit(b, scorer, clf, tau, band, req_texts=texts)
        got = {r.id: r.status for r in clean.reqs}
        for i, r in enumerate(reqs, 1):
            if r["status"] == "unclear":
                continue
            truth_done, pred = r["status"] == "done", got[i]
            res["clean"]["n"] += 1
            if pred == "unclear":
                res["clean"]["abstain"] += 1
            elif truth_done and pred == "done": res["clean"]["tp"] += 1
            elif truth_done: res["clean"]["fn"] += 1
            elif pred == "done": res["clean"]["fp"] += 1
            else: res["clean"]["tn"] += 1
            res["detail"].append(dict(pr=g["pr"].split("github.com/")[1], req=i, gold=r["status"], pred=pred,
                                      score=round(clean.reqs[i - 1].score, 2)))
        # exact fault injection
        done = [(i, r) for i, r in enumerate(reqs, 1) if r["status"] == "done" and r["hunks"]]
        for i, r in done:
            drop = set(r["hunks"])                 # remove EVERYTHING this requirement points at
            if not drop or got[i] != "done":      # clean run must have said done
                continue
            fb = b.model_copy(update={"hunks": [h for h in b.hunks if h.id not in drop]})
            if not fb.hunks:
                continue
            fa = {x.id: x.status for x in run_audit(fb, scorer, clf, tau, band, req_texts=texts).reqs}
            res["faults"]["n"] += 1
            res["faults"]["caught_not_done"] += fa[i] != "done"
            res["faults"]["caught_missing"] += fa[i] == "missing"
            for j, o in done:
                if j != i and got[j] == "done" and not (set(o["hunks"]) & drop):   # controls share nothing with the dropped hunks
                    res["faults"]["other_reqs"] += 1
                    res["faults"]["other_flipped"] += fa[j] != "done"
    c = res["clean"]
    res["summary"] = {
        "requirements_scored": c["n"], "abstained": c["abstain"],
        "done_precision": round(c["tp"] / max(1, c["tp"] + c["fp"]), 3),
        "done_recall": round(c["tp"] / max(1, c["tp"] + c["fn"]), 3),
        "gold_not_done_total": c["fp"] + c["tn"] + sum(1 for d in res["detail"] if d["gold"] != "done" and d["pred"] == "unclear"),
        "fault_catch_rate_not_done": f'{res["faults"]["caught_not_done"]}/{res["faults"]["n"]}',
        "fault_catch_rate_missing": f'{res["faults"]["caught_missing"]}/{res["faults"]["n"]}',
        "false_alarm_other_reqs": f'{res["faults"]["other_flipped"]}/{res["faults"]["other_reqs"]}',
        "labels_human_reviewed": all(g.get("reviewed_by_human") for g in gold)}
    return res


if __name__ == "__main__":
    import joblib
    from pr_audit.audit import load_scorer
    gold = json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))
    bundles = {b.source: b for b in (PRBundle.model_validate_json(l) for l in
               open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8"))}
    for _l in open(ROOT / "bench/data/gold_pool.jsonl", encoding="utf-8"):
        _b = PRBundle.model_validate_json(_l); bundles[_b.source] = _b
    cfg = json.loads((ROOT / "models/verdict.json").read_text(encoding="utf-8"))
    out = evaluate(load_scorer(ROOT / "models/relevance"), joblib.load(ROOT / "models/verdict.joblib"),
                   cfg["tau"], cfg["band"], gold, bundles)
    (ROOT / "bench/results/gold_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], indent=1))
    for d in out["detail"]:
        print(d)
