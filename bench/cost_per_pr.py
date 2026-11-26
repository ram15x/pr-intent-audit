"""Free-tier cost of one audit, computed offline: one judge call per requirement, prompt built exactly as in production
(lexical top-5). Tokens are estimated as chars/4 (rough). Writes bench/results/cost.json. No LLM calls."""
import json, statistics as st, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pr_audit.judge import build_prompt
from pr_audit.lexical import lexical_scorer
from pr_audit.pairs import hunk_text
from pr_audit.schemas import PRBundle

bundles = {}
for f in ("bundles.jsonl", "gold_pool.jsonl", "large_pool.jsonl"):
    p = ROOT / "bench/data" / f
    if p.exists():
        for l in open(p, encoding="utf-8"):
            b = PRBundle.model_validate_json(l); bundles[b.source] = b
lex = lexical_scorer(); rows = []
for gf in ("gold_draft.json", "gold_extra_draft.json", "gold_large_draft.json"):
    for g in json.loads((ROOT / "bench/gold" / gf).read_text(encoding="utf-8")):
        b = bundles.get(g["pr"])
        if not b: continue
        texts = [r["text"] for r in g["requirements"] if r["status"] != "exclude"]
        ht = [hunk_text(h) for h in b.hunks]; chars = 0
        for t in texts:
            sc = lex([(t, h) for h in ht])
            top = [b.hunks[j] for j in sorted(range(len(ht)), key=lambda j: -sc[j])[:5]]
            chars += len(build_prompt(t, top))
        rows.append(dict(pr=g["pr"], hunks=len(b.hunks), requirements=len(texts), calls=len(texts), est_tokens=chars // 4))
tok = [r["est_tokens"] for r in rows]; calls = [r["calls"] for r in rows]
out = dict(prs=len(rows), calls_median=st.median(calls), calls_max=max(calls), est_tokens_median=int(st.median(tok)),
           est_tokens_max=max(tok), minutes_at_8k_tpm_median=round(st.median(tok) / 8000, 1), minutes_at_8k_tpm_max=round(max(tok) / 8000, 1),
           note="input tokens only (chars/4); Groq free tier is about 8K tokens/minute; output tokens add a little", rows=rows)
(ROOT / "bench/results/cost.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print({k: v for k, v in out.items() if k != "rows"})
