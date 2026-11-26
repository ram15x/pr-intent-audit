# Final pass (do once, at the end, after the gold set and Groq runs stop changing)

1. Mining/labelling finished -> `python bench\eval_retrieval.py` once (restores CodeBERT rows), then `python bench\make_results_md.py`.
2. Groq quota back -> `check_llm.py`, `eval_gold_llm.py lexical`, `... lexical escalate`, `eval_naive.py`, `eval_partial.py`, large-PR runs. `judge_errors` must be 0 before any table is read.
3. `python bench\license_audit.py`; update the license counts in README.
4. README: refresh every number below from `docs/RESULTS.md`, nothing from memory:
   - gold-set sizes (14-PR set, large set, "4 large PRs" vs current)
   - hybrid table, large-PR table, retrieval table and the random-baseline sentence
   - cost section PR count/tokens, scope-creep and splitter figures, license counts
5. Add the measured end-to-end result for the lexical default and `--escalate` to DECISIONS, even if negative.
6. Rebuild `docs/demo_report.html` and screenshots only if the report template changed.
7. `pytest`, clean-clone install check, then `git push`.
