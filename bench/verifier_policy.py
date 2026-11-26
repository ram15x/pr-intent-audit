"""Offline experiment on cached judge answers (no network, no quota): how does the verifier policy trade recall against
false 'done'? 'all' = current rule (every quote must occur in a cited hunk). 'any' = keep done/partial if at least one quote
occurs in a cited hunk (unverified quotes are dropped from the evidence). Nothing is written to bench/results.
Usage: python bench/verifier_policy.py"""
import json, sys, io, contextlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
import eval_gold_llm as E
import pr_audit.judge as J
from pr_audit.llm import LLM
from pr_audit.lexical import lexical_scorer
from pr_audit.schemas import PRBundle, Verdict
from pr_audit.verify import verify_judgment, quotes_in

def verify_any(j, hunks):
    if j.verdict not in (Verdict.done, Verdict.partial):
        return j
    by_id = {h.id: h for h in hunks}
    cited = [by_id[i] for i in j.hunk_ids if i in by_id]
    good = [q for q in j.quotes if any(quotes_in(h, [q]) for h in cited)]
    if not cited or not good:
        return j.model_copy(update={"verdict": Verdict.unclear, "downgraded_because": ["no quote verified in a cited hunk"]})
    return j.model_copy(update={"quotes": good})

def run(policy):
    J.verify_judgment = verify_judgment if policy == "all" else verify_any
    E.ERRORS.clear(); E.CFG.update(topk=5, verify=True, escalate=False)
    llm = LLM(ROOT / ".cache/llm", providers=())          # cache only: a miss shows up as a judge error
    gold = json.loads((ROOT / "bench/gold/gold_draft.json").read_text(encoding="utf-8"))
    bundles = {}
    for f in ("bundles.jsonl", "gold_pool.jsonl"):
        for l in open(ROOT / "bench/data" / f, encoding="utf-8"):
            b = PRBundle.model_validate_json(l); bundles[b.source] = b
    with contextlib.redirect_stdout(io.StringIO()):
        out = E.evaluate(llm, lexical_scorer(), gold, bundles)
    s = out["summary"]
    print(f"{policy:4s} scored={s['requirements_scored']} abstained={s['abstained']} precision={s['done_precision']} recall={s['done_recall']} "
          f"false_done={s['false_done_on_notdone']} caught_not_done={s['fault_catch_not_done']} caught_missing={s['fault_catch_missing']} "
          f"false_alarm={s['false_alarm_other_reqs']} judge_errors={s['judge_errors']}")

if __name__ == "__main__":
    for p in ("all", "any"): run(p)
