"""One place that wires retrieval + judge + verifier, shared by the CLI and the web app."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Pipeline:
    scorer: Callable
    clf: object
    cfg: dict
    judge: Callable | None
    info: str
    use_lexical: bool
    llm: object | None = None
    notes: list[str] = field(default_factory=list)


def make_pipeline(root: Path, models: Path, local: bool = False, retrieval: str = "auto", escalate: bool = False,
                  context: bool = False, log: Callable[[str], None] = lambda s: None) -> Pipeline:
    """Raises ValueError for a configuration the user can fix (missing models/keys)."""
    from .audit import load_scorer
    have_models = (models / "relevance").exists() and (models / "verdict.joblib").exists()
    use_lexical = retrieval == "lexical" or (retrieval == "auto" and not have_models)
    if retrieval == "model" and not have_models:
        raise ValueError(f"no trained models in {models}; see README 'Train the models yourself' or use lexical retrieval")
    if use_lexical and local:
        raise ValueError("--local needs the trained models; train them or drop --local")
    if use_lexical:
        from .lexical import lexical_scorer
        scorer, clf, cfg = lexical_scorer(), None, {"tau": 0.5, "band": 0.10}
        log("retrieval: lexical word overlap (no trained models found or lexical requested)")
    else:
        cfg = json.loads((models / "verdict.json").read_text(encoding="utf-8"))
        import joblib
        clf = joblib.load(models / "verdict.joblib")
        scorer = load_scorer(models / "relevance")
    judge, mode, llm, notes = None, "local models only", None, []
    if not local:
        from .llm import LLM
        from .judge import judge_requirement
        llm = LLM(root / ".cache/llm")
        if llm.providers:
            if escalate:
                from .judge import judge_with_escalation
                judge = lambda i, t, ranked: judge_with_escalation(llm, i, t, ranked)
                judge.wants_wide = True
            else:
                judge = lambda i, t, top: judge_requirement(llm, i, t, top, verify=True, context=context)
            mode = f"hybrid (judge providers: {', '.join(llm.providers)}; PR text is sent to them)"
        else:
            if use_lexical:
                raise ValueError("lexical retrieval needs an LLM judge: set GEMINI_API_KEY and/or GROQ_API_KEY")
            notes.append("no GEMINI_API_KEY / GROQ_API_KEY found: falling back to local models only (weak within-PR)")
            log(notes[-1])
    info = f"mode: {mode}; retrieval: {'lexical word overlap' if use_lexical else 'trained CodeBERT relevance model'}"
    return Pipeline(scorer, clf, cfg, judge, info, use_lexical, llm, notes)
