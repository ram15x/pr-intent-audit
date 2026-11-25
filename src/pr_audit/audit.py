"""End-to-end audit: bundle -> requirements -> relevance matrix -> verdicts, evidence, creep, rank.

The scorer is injected (a callable: list[(requirement, hunk_text)] -> list[float]) so the pipeline
is testable offline; `load_scorer` builds the real CodeBERT-based one (needs torch).
Evidence is extractive: it points at real hunks and real added lines, so it cannot be fabricated.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from .coverage import best_per_req, features, orphan_flags
from .inject import is_substantive
from .pairs import hunk_text
from .requirements import clean_ask, split_requirements
from .schemas import Hunk, PRBundle, Verdict
from .verify import quotes_in, verify_judgment
from .schemas import Judgment

Scorer = Callable[[list[tuple[str, str]]], list[float]]


@dataclass
class ReqResult:
    id: int
    text: str
    status: str                      # done | partial | missing | unclear
    score: float
    evidence: list[tuple[str, float, list[str]]] = field(default_factory=list)  # (hunk_id, score, quoted lines)
    note: str = ""
    optional: bool = False


@dataclass
class Audit:
    bundle: PRBundle
    reqs: list[ReqResult]
    pr_verdict: str
    pr_probs: dict[str, float]
    creep: list[tuple[str, float]]
    rank: int | None
    band: str
    rank_lines: list[str]
    low_confidence: bool


def load_scorer(model_dir: str | Path) -> Scorer:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(dev).eval()
    cache: dict = {}

    @torch.no_grad()
    def score(pairs):
        todo = [p for p in dict.fromkeys(pairs) if p not in cache]
        for i in range(0, len(todo), 32):
            b = todo[i:i + 32]
            enc = tok([x[0] for x in b], [x[1] for x in b], truncation="only_second", max_length=384,
                      padding=True, return_tensors="pt").to(dev)
            with torch.autocast(dev, enabled=dev == "cuda"):
                p = torch.softmax(model(**enc).logits.float(), -1)[:, 1].cpu().tolist()
            cache.update(zip(b, p))
        return [cache[p] for p in pairs]
    return score


STOP = {"the", "and", "for", "with", "that", "this", "should", "must", "add", "not", "are", "from",
        "into", "when", "have", "has", "all", "any", "can", "use", "new", "get", "set", "its", "one"}


def _tokens(text: str) -> set[str]:
    """lowercase subtokens; splits snake_case and camelCase; drops short/stop words."""
    import re
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return {t for t in re.findall(r"[a-z][a-z0-9]{2,}", text.lower()) if t not in STOP}


def _evidence(hunk: Hunk, req: str, n: int = 3) -> list[str]:
    """Lines of the hunk that share real vocabulary with the requirement (best first). Empty if none do."""
    rt = _tokens(req)
    scored = [(len(rt & _tokens(l)), l.strip()) for l in hunk.added if len(l.strip()) > 3]
    return [l for sc, l in sorted(scored, key=lambda x: -x[0]) if sc > 0][:n]


def run_audit(bundle: PRBundle, scorer: Scorer, clf, tau: float = 0.5, band: float = 0.10,
              req_texts: list[str] | None = None, judge=None, topk: int = 5) -> Audit:
    """judge: optional callable (req_id, text, top_hunks) -> Judgment (already verified). When given it decides each
    requirement's status; our relevance model only retrieves the candidate hunks."""
    reqs = [] if req_texts else split_requirements(bundle.ask)
    texts = list(req_texts or []) or [r.text for r in reqs] or [clean_ask(bundle.ask)[:400] or bundle.title]
    opts = [r.optional for r in reqs] if reqs else []
    opts += [False] * (len(texts) - len(opts))
    hunks = bundle.hunks
    ht = [hunk_text(h) for h in hunks]
    flat = scorer([(r, h) for r in texts for h in ht]) if hunks else []
    n = len(ht)
    m = [flat[i * n:(i + 1) * n] for i in range(len(texts))]

    results: list[ReqResult] = []
    for i, (t, row) in enumerate(zip(texts, m), 1):
        best = max(row) if row else 0.0
        status = "done" if best >= tau + band else "missing" if best < tau - band else "unclear"
        ev = []
        for j in sorted(range(n), key=lambda j: -row[j])[:2]:
            if row[j] >= tau - band:
                j_ = Judgment(req_id=i, verdict=Verdict.done, hunk_ids=[hunks[j].id],
                              quotes=_evidence(hunks[j], t))
                if j_.quotes and verify_judgment(j_, hunks).verdict == Verdict.done:
                    ev.append((hunks[j].id, row[j], j_.quotes))
        if status == "done" and not ev:
            status, note = "unclear", "hunk looks related but no line in it matches this requirement's wording (generic match, or non-English ask)"
        else:
            note = ""
        if judge is not None:
            top = [hunks[j] for j in sorted(range(n), key=lambda j: -row[j])[:topk]]
            jd = judge(i, t, top)
            idx = {h.id: j for j, h in enumerate(hunks)}
            status = jd.verdict.value
            ev = [(hid, row[idx[hid]], quotes_in(hunks[idx[hid]], jd.quotes)) for hid in jd.hunk_ids if hid in idx] if status in ("done", "partial") else []
            note = jd.reason + (f" [{jd.downgraded_because}]" if jd.downgraded_because else "")
        results.append(ReqResult(i, t, status, best, ev, note, optional=opts[i - 1]))

    if hunks and m and clf is not None:
        probs = clf.predict_proba([features(m)])[0]
        labels = list(clf.classes_)
        names = ["done", "partial", "missing"]
        pr_probs = {names[int(c)]: float(p) for c, p in zip(labels, probs)}
        pr_verdict = max(pr_probs, key=pr_probs.get)
    else:
        pr_probs, pr_verdict = {}, "unclear"

    orphans = orphan_flags(m, tau) if m else []
    creep = [(h.id, round(s, 2)) for h, o, s in zip(hunks, orphans, _best_hunk(m)) if o and is_substantive(h)]

    decided = [r for r in results if r.status != "unclear" and not (r.optional and r.status == "missing")]
    low = len(results) > 0 and (len(results) - len(decided)) / len(results) > 0.30
    lines: list[str] = []
    if decided:
        cov = sum(1.0 if r.status == "done" else 0.5 if r.status == "partial" else 0.0 for r in decided) / len(decided)
        rank = round(100 * cov)
        lines.append(f"coverage {cov:.2f} over {len(decided)} decided requirement(s) -> {rank}")
        pen = min(5 * len(creep), 20)
        if pen:
            rank -= pen
            lines.append(f"scope-creep candidates {len(creep)} -> -{pen}")
        rank = max(rank, 0)
    else:
        rank = None
        lines.append("no requirement could be decided")
    n_unc = len(results) - len(decided)
    if n_unc:
        lines.append(f"{n_unc} requirement(s) unclear, excluded from coverage")
    band_name = ("n/a" if rank is None else "matches the ask" if rank >= 90 else "minor gaps" if rank >= 70
                 else "significant gaps" if rank >= 40 else "does not match")
    return Audit(bundle, results, pr_verdict, pr_probs, creep, rank, band_name, lines, low)


def _best_hunk(m):
    from .coverage import best_per_hunk
    return best_per_hunk(m)
