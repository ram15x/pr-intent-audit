"""Error analysis: for each requirement where lexical misses the top-5 on a large PR, show the rank of the best gold hunk,
the gold hunk's file, and the top-ranked wrong hunks' files. Usage: python bench/miss_analysis.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "bench"))
from eval_retrieval import load
from pr_audit.lexical import lexical_scorer
from pr_audit.pairs import hunk_text

lex = lexical_scorer(); ranks = []; misses = []
for c in load():
    b = c["bundle"]
    if len(b.hunks) < 10: continue
    ht = [hunk_text(h, limit=1500) for h in b.hunks]
    sc = lex([(c["text"], h) for h in ht])
    order = [b.hunks[j] for j in sorted(range(len(ht)), key=lambda j: -sc[j])]
    best = min(i for i, h in enumerate(order) if h.id in c["rel"]) + 1
    ranks.append((best, len(order)))
    if best > 5:
        gold = [h for h in order if h.id in c["rel"]][0]
        misses.append((best, len(order), c["pr"], c["text"][:110], gold.file if hasattr(gold, "file") else gold.id, [getattr(h, "file", h.id) for h in order[:3]]))
print("large-PR cases:", len(ranks), "| ranks of best gold hunk:", sorted(r for r, _ in ranks))
for m in sorted(misses): print("\nrank %d/%d  %s\n  req: %s\n  gold file: %s\n  top3 files: %s" % m)
