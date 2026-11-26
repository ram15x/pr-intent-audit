"""Partial-implementation faults: for a requirement judged 'done' on the full PR, remove only SOME of the hunks it
points at and see whether the verdict drops. Weak truth (the remainder may still satisfy it), so read the rate as an
upper-bound-ish sensitivity measure, not exact recall. Check judge_errors == 0 before reading anything.

Usage: python bench/eval_partial.py [lexical] [large|extra]   -> bench/results/partial_fault[_tag].json"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
import eval_gold_llm as E
from pr_audit.inject import partial_drop
from pr_audit.schemas import PRBundle


def run(llm, scorer, gold, bundles, log=print):
    n = dropped_to = 0
    verdicts = {"done": 0, "partial": 0, "missing": 0, "unclear": 0}
    for g in gold:
        b = bundles[g["pr"]]
        reqs = [r for r in g["requirements"] if r["status"] != "exclude"]
        texts = [r["text"] for r in reqs]
        todo = [(i, r) for i, r in enumerate(reqs, 1) if r["status"] == "done" and partial_drop(r["hunks"])]
        if not todo:
            continue
        got = E.judge_all(llm, scorer, b, texts, only={i for i, _ in todo})
        for i, r in todo:
            if got[i] != "done":
                continue
            drop = partial_drop(r["hunks"])
            fb = b.model_copy(update={"hunks": [h for h in b.hunks if h.id not in drop]})
            if not fb.hunks:
                continue
            v = E.judge_all(llm, scorer, fb, texts, only={i})[i]
            n += 1; verdicts[v] += 1
            log(f'{g["pr"].split("github.com/")[1]} req {i}: drop {sorted(drop)} -> {v}')
    k = n - verdicts["done"]
    return dict(n=n, verdicts_after_partial_removal=verdicts, caught_not_done=f"{k}/{n}",
                caught_not_done_95ci=E.wilson(k, n), judge_errors=len(E.ERRORS),
                judge_error_examples=sorted(set(E.ERRORS))[:3],
                note="weak truth: remaining hunks may still satisfy the requirement")


if __name__ == "__main__":
    from pr_audit.audit import load_scorer
    from pr_audit.env import load_env
    from pr_audit.llm import LLM
    load_env(ROOT / ".env")
    a = sys.argv[1:]
    LARGE, EXTRA, LEX = "large" in a, "extra" in a, "lexical" in a
    tag = "".join(["_lexical" if LEX else "", "_large" if LARGE else "", "_extra" if EXTRA else ""])
    gold = json.loads((ROOT / ("bench/gold/gold_large_draft.json" if LARGE else "bench/gold/gold_extra_draft.json" if EXTRA else "bench/gold/gold_draft.json")).read_text(encoding="utf-8"))
    bundles = {b.source: b for b in (PRBundle.model_validate_json(l) for l in open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8"))}
    for l in open(ROOT / ("bench/data/large_pool.jsonl" if LARGE else "bench/data/gold_pool.jsonl"), encoding="utf-8"):
        b = PRBundle.model_validate_json(l); bundles[b.source] = b
    llm = LLM(ROOT / ".cache/llm")
    if LEX:
        from pr_audit.lexical import lexical_scorer
        scorer = lexical_scorer()
    else:
        scorer = load_scorer(ROOT / "models/relevance")
    out = run(llm, scorer, gold, bundles)
    out.update(variant="partial" + tag, llm_calls=llm.calls)
    (ROOT / f"bench/results/partial_fault{tag}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
