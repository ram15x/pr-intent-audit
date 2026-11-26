"""Hybrid evaluation on the gold PRs: our retrieval (relevance model) -> LLM judge -> our verifier.
Same clean + exact-fault-injection protocol as eval_gold.py. Writes bench/results/gold_eval_llm_<variant>.json.
Needs GEMINI_API_KEY and/or GROQ_API_KEY in .env. Responses are cached in .cache/llm (re-runs are free)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.judge import judge_requirement
from pr_audit.pairs import hunk_text
from pr_audit.schemas import PRBundle, Verdict

MAX_OTHERS = 2


def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 2), round(c + h, 2)]

ERRORS = []
CFG = {"topk": 5, "verify": True, "escalate": False}     # set from the command line: [all|top5] [noverify] [lexical] [large]


def judge_all(llm, scorer, bundle, texts, only=None):
    n = len(bundle.hunks)
    ht = [hunk_text(h) for h in bundle.hunks]
    out = {}
    for i, t in enumerate(texts, 1):
        if only is not None and i not in only:
            continue
        sc = scorer([(t, h) for h in ht])
        ranked = [bundle.hunks[j] for j in sorted(range(n), key=lambda j: -sc[j])]
        if CFG["escalate"]:
            from pr_audit.judge import judge_with_escalation
            jd = judge_with_escalation(llm, i, t, ranked, verify=CFG["verify"])
        else:
            jd = judge_requirement(llm, i, t, ranked[:CFG["topk"]], verify=CFG["verify"])
        if jd.reason.startswith("judge error"):
            ERRORS.append(jd.reason)
        out[i] = jd.verdict.value
    return out


def evaluate(llm, scorer, gold, bundles, log=print):
    clean = dict(tp=0, fp=0, fn=0, tn=0, abstain=0, n=0)
    faults = dict(n=0, caught_not_done=0, caught_missing=0, other=0, other_flipped=0)
    detail = []
    for g in gold:
        b = bundles[g["pr"]]
        reqs = [r for r in g["requirements"] if r["status"] != "exclude"]
        texts = [r["text"] for r in reqs]
        got = judge_all(llm, scorer, b, texts)
        log(f'{g["pr"].split("github.com/")[1]}: {got}')
        for i, r in enumerate(reqs, 1):
            if r["status"] == "unclear":
                continue
            td, pred = r["status"] == "done", got[i]
            clean["n"] += 1
            if pred == "unclear": clean["abstain"] += 1
            elif td and pred == "done": clean["tp"] += 1
            elif td: clean["fn"] += 1
            elif pred == "done": clean["fp"] += 1
            else: clean["tn"] += 1
            detail.append(dict(pr=g["pr"].split("github.com/")[1], req=i, gold=r["status"], pred=pred))
        done = [(i, r) for i, r in enumerate(reqs, 1) if r["status"] == "done" and r["hunks"]]
        for i, r in done:
            if got[i] != "done":
                continue
            drop = set(r["hunks"])                 # remove EVERYTHING this requirement points at
            fb = b.model_copy(update={"hunks": [h for h in b.hunks if h.id not in drop]})
            if not drop or not fb.hunks:
                continue
            oth = [j for j, o in done if j != i and got[j] == "done" and not (set(o["hunks"]) & drop)][:MAX_OTHERS]
            fa = judge_all(llm, scorer, fb, texts, only={i, *oth})
            faults["n"] += 1
            faults["caught_not_done"] += fa[i] != "done"
            faults["caught_missing"] += fa[i] == "missing"
            faults["other"] += len(oth)
            faults["other_flipped"] += sum(fa[j] != "done" for j in oth)
            log(f'  fault: drop {sorted(drop)} -> req {i}: {fa[i]} | others flipped {sum(fa[j] != "done" for j in oth)}/{len(oth)}')
    summ = dict(requirements_scored=clean["n"], abstained=clean["abstain"],
                done_precision=round(clean["tp"] / max(1, clean["tp"] + clean["fp"]), 3),
                done_recall=round(clean["tp"] / max(1, clean["tp"] + clean["fn"]), 3),
                false_done_on_notdone=f'{clean["fp"]}/{clean["fp"] + clean["tn"]}',
                fault_catch_not_done=f'{faults["caught_not_done"]}/{faults["n"]}',
                fault_catch_missing=f'{faults["caught_missing"]}/{faults["n"]}',
                false_alarm_other_reqs=f'{faults["other_flipped"]}/{faults["other"]}',
                labels_human_reviewed=all(x.get("reviewed_by_human") for x in gold))
    summ["judge_errors"] = len(ERRORS)
    summ["judge_error_examples"] = sorted(set(ERRORS))[:3]
    summ["fault_catch_not_done_95ci"] = wilson(faults["caught_not_done"], faults["n"])
    summ["fault_catch_missing_95ci"] = wilson(faults["caught_missing"], faults["n"])
    summ["done_recall_95ci"] = wilson(clean["tp"], clean["tp"] + clean["fn"])
    import collections
    cm = collections.Counter((d["gold"], d["pred"]) for d in detail)
    summ["confusion_gold_x_pred[done,partial,missing,unclear]"] = {g: [cm[(g, p)] for p in ("done", "partial", "missing", "unclear")]
                                                                 for g in ("done", "partial", "missing")}
    return dict(summary=summ, detail=detail)


if __name__ == "__main__":
    from pr_audit.audit import load_scorer
    from pr_audit.env import load_env
    from pr_audit.llm import LLM
    load_env(ROOT / ".env")
    args = sys.argv[1:]
    CFG["topk"] = 99 if "all" in args else 5
    CFG["verify"] = "noverify" not in args
    CFG["escalate"] = "escalate" in args
    tag = ("all" if "all" in args else "top5") + ("" if CFG["verify"] else "_noverify")
    LARGE = "large" in args
    LEX = "lexical" in args
    EXTRA = "extra" in args
    if CFG["escalate"]: tag = "escalate_" + tag
    if LEX: tag = "lexical_" + tag
    if LARGE: tag = "large_" + tag
    if EXTRA: tag = "extra_" + tag
    print("variant:", tag)
    gold = json.loads((ROOT / ("bench/gold/gold_large_draft.json" if LARGE else "bench/gold/gold_extra_draft.json" if EXTRA else "bench/gold/gold_draft.json")).read_text(encoding="utf-8"))
    bundles = {b.source: b for b in (PRBundle.model_validate_json(l) for l in
               open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8"))}
    for _l in open(ROOT / ("bench/data/large_pool.jsonl" if LARGE else "bench/data/gold_pool.jsonl"), encoding="utf-8"):
        _b = PRBundle.model_validate_json(_l); bundles[_b.source] = _b
    llm = LLM(ROOT / ".cache/llm")
    print("providers:", llm.providers)
    if LEX:
        from pr_audit.lexical import lexical_scorer
        scorer = lexical_scorer()
    else:
        scorer = load_scorer(ROOT / "models/relevance")
    out = evaluate(llm, scorer, gold, bundles)
    out["variant"] = tag; out["llm_calls"] = llm.calls; out["llm_by_provider_this_run"] = llm.by_provider; out["gemini_model"] = llm.gemini_model
    (ROOT / ("bench/results/gold_eval_llm_" + tag + ".json")).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], indent=1), llm.calls, "by provider:", llm.by_provider)
