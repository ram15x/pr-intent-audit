"""H1: the naive 'whole PR, one prompt' baseline on the same gold set and the same fault-injection protocol.

Usage: python bench/eval_naive.py [large|extra]     Writes bench/results/gold_eval_llm_naive[_large|_extra].json
Same cache, providers and judge_errors accounting as eval_gold_llm.py. Check judge_errors before reading anything."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
import eval_gold_llm as E
from pr_audit.naive import naive_verdicts
from pr_audit.schemas import PRBundle


def naive_judge_all(llm, scorer, bundle, texts, only=None):
    verdicts, err = naive_verdicts(llm, texts, bundle.hunks)
    if err:
        E.ERRORS.extend([err] * len(texts if only is None else only))
    return {i: v for i, v in verdicts.items() if only is None or i in only}


if __name__ == "__main__":
    from pr_audit.env import load_env
    from pr_audit.llm import LLM
    load_env(ROOT / ".env")
    args = sys.argv[1:]
    suffix = "_large" if "large" in args else "_extra" if "extra" in args else ""
    gfile = {"_large": "gold_large_draft.json", "_extra": "gold_extra_draft.json", "": "gold_draft.json"}[suffix]
    pool = {"_large": "large_pool.jsonl"}.get(suffix, "gold_pool.jsonl")
    E.judge_all = naive_judge_all
    gold = json.loads((ROOT / "bench/gold" / gfile).read_text(encoding="utf-8"))
    bundles = {b.source: b for b in (PRBundle.model_validate_json(l) for l in open(ROOT / "bench/data/bundles.jsonl", encoding="utf-8"))}
    for l in open(ROOT / "bench/data" / pool, encoding="utf-8"):
        b = PRBundle.model_validate_json(l); bundles[b.source] = b
    llm = LLM(ROOT / ".cache/llm")
    print("variant: naive" + suffix, "| providers:", llm.providers)
    out = E.evaluate(llm, None, gold, bundles)
    out.update(variant="naive" + suffix, llm_calls=llm.calls, llm_by_provider_this_run=llm.by_provider, gemini_model=llm.gemini_model)
    (ROOT / f"bench/results/gold_eval_llm_naive{suffix}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["summary"], indent=1), llm.calls, "by provider:", llm.by_provider)
