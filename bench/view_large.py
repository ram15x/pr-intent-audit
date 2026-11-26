"""Labelling view for the large pool: python bench/view_large.py <substring of PR url> ..."""
import sys, json; from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from pr_audit.schemas import PRBundle
from pr_audit.requirements import split_requirements
from pr_audit.audit import _tokens
pool = [PRBundle.model_validate_json(l) for l in open(ROOT / "bench/data/large_pool.jsonl", encoding="utf-8")]
for key in sys.argv[1:]:
    for b in [b for b in pool if key in b.source]:
        rq = split_requirements(b.ask)
        print(f"\n######## {b.source} :: {b.title[:80]}")
        for i, h in enumerate(b.hunks, 1): print(f"  H{i} {h.id} +{len(h.added)}/-{len(h.removed)}")
        for r in rq:
            print(f"\n  R{r.id}: {r.text[:260]}")
            rt = _tokens(r.text); hits = []
            for i, h in enumerate(b.hunks, 1):
                ls = sorted(((len(rt & _tokens(l)), l.strip()) for l in h.added if l.strip()), key=lambda x: -x[0])
                if ls and ls[0][0] > 0: hits.append((ls[0][0] + 0.01 * len(ls[:3]), i, [l[:120] for s, l in ls[:3] if s > 0]))
            for sc, i, lines in sorted(hits, reverse=True)[:4]:
                print(f"     H{i} {b.hunks[i-1].file.split('/')[-1]}: " + " || ".join(lines))
