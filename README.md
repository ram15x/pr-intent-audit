# PR Intent Audit

Did the pull request do what was asked? Especially when a coding agent wrote it.

Give it a PR URL and the ask (the prompt you gave Claude Code or Codex, or the issue/PR body). It splits the ask into
requirements, finds the hunks that address each one, and reports **done / partial / missing / unclear** with evidence
pinned to diff lines, plus hunks that no requirement claims (possible scope creep). It never approves or blocks a merge.

```
# any public PR; --ask-file is optional (use it when the ask is a prompt, not the PR body)
pr-audit run https://github.com/ztrange/veri/pull/2693 --out report.md
```

## How it works

1. **Ingest** the PR through the GitHub API; PR and issue text is treated as untrusted data.
2. **Split** the ask into requirements (rule-based; weak on free-form prose, see below).
3. **Retrieve** candidate hunks per requirement with a CodeBERT cross-encoder we trained (`bench/train_relevance.py`).
4. **Judge** each requirement on its top-5 hunks with an LLM (Gemini / Groq free tiers), JSON-only, temperature 0.
5. **Verify** deterministically: every cited hunk must exist and every quoted line must appear in it. Otherwise the
   verdict is downgraded to `unclear`. Evidence in the report is therefore real diff text.

`--local` skips the judge and uses only our trained models. In hybrid mode the PR text is sent to the judge provider;
free Gemini terms allow Google to train on it, so use public repos only.

## Benchmark

Fault injection with labels known by construction, plus a small gold set. Numbers below are generated from
`bench/results/*.json` by `bench/make_results_md.py`; nothing here is typed by hand.

<!-- RESULTS:START -->
Gold set: 14 PRs. Labels were drafted by Claude, approved by the owner without changes, then cross-checked by Claude, who changed 5 (docs/GOLD_CHANGES.md). Single annotator; no second labeller.
Faults: all hunks a requirement points at are removed; controls share no hunks with the fault.

| variant | done precision | done recall | abstained | faults no longer 'done' | 95% CI | faults -> 'missing' | false alarms | judge errors |
|---|---|---|---|---|---|---|---|---|
| ours-only (trained models) | 0.917 | 0.943 | 4 | 3/32 | 0.03-0.24 | 0/32 | 1/26 | n/a |
| hybrid: our top-5 hunks + LLM judge + our verifier | 0.966 | 0.824 | 5 | 21/28 | 0.57-0.87 | 15/28 | 1/19 | 0 |
| hybrid ablation: judge sees all hunks (no retrieval) | 0.963 | 0.839 | 9 | 20/26 | 0.58-0.89 | 16/26 | 2/18 | 0 |
| hybrid ablation: no verifier | 0.97 | 0.821 | 0 | 19/31 | 0.44-0.76 | 15/31 | 1/26 | 0 |

Caveats: faults are injected only where the baseline said 'done', so denominators differ per row;
gold base rate of 'done' is 39/42, so precision must be read against 0.85; judge calls were mostly Groq gpt-oss-120b.

### Large PRs (4 PRs, 13 requirements; labels by Claude, NOT human-reviewed; tiny sample)

| variant | done precision | done recall | abstained | faults no longer 'done' | 95% CI | faults -> 'missing' | false alarms | judge errors | confusion gold x pred [done,partial,missing,unclear] |
|---|---|---|---|---|---|---|---|---|---|
| large PRs (36-98 hunks): top-5 + verifier | 1.0 | 0.778 | 0 | 4/7 | 0.25-0.84 | 2/7 | 2/8 | n/a | {'done': [7, 0, 2, 0], 'partial': [0, 1, 0, 0], 'missing': [0, 0, 3, 0]} |
| large PRs: judge sees all hunks (prompt is length-capped) **(INVALID: 7 judge calls failed, HTTP 413/429)** | 1.0 | 1.0 | 7 | 4/5 | 0.38-0.96 | 2/5 | 0/6 | 7 | {'done': [5, 0, 0, 4], 'partial': [0, 0, 0, 1], 'missing': [0, 0, 1, 2]} |
| large PRs: top-5, no verifier | 1.0 | 0.778 | 0 | 4/7 | 0.25-0.84 | 2/7 | 2/8 | n/a | {'done': [7, 0, 2, 0], 'partial': [0, 1, 0, 0], 'missing': [0, 0, 3, 0]} |
<!-- RESULTS:END -->

## Where it fails (read this before trusting a number)

- **Our trained models cannot judge a requirement inside one PR.** The relevance model learned to tell whether a hunk
  belongs to a PR, not whether it satisfies a requirement. Alone it catches almost no removed requirements, and its
  "done" precision is no better than always answering "done" (see the base-rate line under the table). Supervising it with commit-message to hunk mappings did not fix this
  (within-PR AUC 0.502). The first version of this project shipped on that model and reported a falsely perfect score.
- **So the judge is an LLM.** Our parts are retrieval, the verifier, and the benchmark. The verifier's benefit over no
  verifier is not statistically established (intervals overlap). Retrieval's accuracy benefit over showing all hunks is
  also not established on small PRs; on large PRs it is needed to fit the free-tier token limit (the all-hunks run hit
  HTTP 413/429 on Groq), which is a cost argument, not an accuracy one.
- **The gold set is tiny and single-annotator.** 14 PRs plus 4 large PRs (the large set is not reviewed by the owner).
  Labels were drafted by Claude; the owner approved the 14-PR draft unchanged, and a later cross-check by Claude
  still found 5 wrong labels (docs/GOLD_CHANGES.md), which shows how weak "approved" is. The judge is also an LLM, so
  errors may be correlated. After the fixes the 14-PR set has no `missing` labels at all.
- **Clean-set precision/recall say little.** After the label fixes the 14-PR set has only 3 requirements that are not
  "done", so "false done" rates there rest on a handful of items. The fault-injection columns (labels known by
  construction) are the main evidence; they cover omissions, not partial implementations.
- **Fault injection undercounts.** Removing the hunks a label points at does not always remove the requirement
  (duplicate files, requirements satisfied elsewhere), so catch rates are likely underestimates by an unknown amount.
- **Requirement splitting is weak.** Checklists work; prose and issue templates produce non-requirements.
- **English, public repos only.** Non-English asks are mostly `unclear`. Judging used mostly Groq gpt-oss-120b because
  the Gemini free quota ran out repeatedly.
- **Scope-creep detection is low precision** and has not been validated within a PR.

Design history and every negative result: `docs/DECISIONS.md`.

## GitHub Action (experimental)

`action.yml` + `examples/pr-audit.yml` run the audit on each PR and comment the report. It needs no model files
(lexical retrieval) but needs a free Groq or Gemini key as a repo secret. **It has not been run on a live PR yet.**
Fork PRs get no secrets, so they are skipped.

## Train the models yourself

The trained weights are not in this repo (`models/` is gitignored); the data is mined from public PRs on your own
machine with your own `GITHUB_TOKEN`. A 4 GB GPU (RTX 3050) is enough. Mining and training are resumable.

```
pip install -r bench\requirements-train.txt
python bench\mine.py                 # merged public PRs that close an issue -> bench/data/bundles.jsonl
python bench\mine_deepen.py          # more PRs from the same repos (hard negatives)
python bench\mine_commits.py         # commit -> hunk supervision (did not help within-PR, kept for the record)
python bench\mine_gold.py            # acceptance-criteria PRs for the gold pool
python bench\train_relevance.py      # CodeBERT cross-encoder -> models/relevance
python bench\train_verdict.py        # verdict + scope-creep classifiers -> models/verdict.joblib
```

Without `models/`, `pr-audit run` cannot retrieve hunks.

## License

MIT, see `LICENSE`. Benchmark data is derived from public GitHub PRs; it is mined locally and not redistributed here
except short requirement excerpts and hunk ids in `bench/gold/`.

## Reproduce

```
python -m venv .venv && .venv\Scripts\activate && pip install -e .[dev]
copy .env.example .env      # add GEMINI_API_KEY and/or GROQ_API_KEY, GITHUB_TOKEN
python bench\eval_gold.py                 # ours-only
python bench\eval_gold_llm.py             # hybrid; add: all | noverify | large
python bench\make_results_md.py           # regenerates docs/RESULTS.md and the table above
pytest
```
