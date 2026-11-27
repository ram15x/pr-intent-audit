"""Offline (cache only, no quota): current evidence rule vs added-lines-only rule on the 14-PR gold set.
Usage: python bench/verifier_added_only.py"""
import json, sys, io, contextlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
import eval_gold_llm as E
import pr_audit.judge as J
import pr_audit.verify as V
from pr_audit.llm import LLM
from pr_audit.lexical import lexical_scorer
from pr_audit.schemas import PRBundle

CTX = "context" in sys.argv[1:]

def run(added_only):
    V.ADDED_ONLY = added_only
    E.ERRORS.clear(); E.CFG.update(topk=5, verify=True, escalate=False, context=CTX)
    llm = LLM(ROOT / ".cache/llm", providers=())
    gold = json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))
    bundles = {}
    for f in ("bundles.jsonl", "gold_pool.jsonl"):
        for l in open(ROOT / "bench/data" / f, encoding="utf-8"):
            b = PRBundle.model_validate_json(l); bundles[b.source] = b
    with contextlib.redirect_stdout(io.StringIO()):
        out = E.evaluate(llm, lexical_scorer(), gold, bundles)
    s = out["summary"]
    print(f"added_only={added_only!s:5} scored={s['requirements_scored']} abstained={s['abstained']} precision={s['done_precision']} recall={s['done_recall']} "
          f"false_done={s['false_done_on_notdone']} caught_not_done={s['fault_catch_not_done']} caught_missing={s['fault_catch_missing']} "
          f"false_alarm={s['false_alarm_other_reqs']} judge_errors={s['judge_errors']}")

if __name__ == "__main__":
    for a in (False, True): run(a)
