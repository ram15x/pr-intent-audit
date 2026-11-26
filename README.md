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

### Retrieval only: is the right hunk in the top k? (73 gold requirements, 23 PRs; no LLM involved)

| retrieval | hit@1 | hit@3 | hit@5 (95% CI) | hit@5 on PRs with 10+ hunks (n=10) |
|---|---|---|---|---|
| lexical (IDF overlap) | 0.589 | 0.877 | 0.945 [0.87, 0.98] | 0.7 |
| lexical, full hunk text | 0.562 | 0.904 | 0.932 [0.85, 0.97] | 0.5 |
| bm25 | 0.658 | 0.863 | 0.918 [0.83, 0.96] | 0.5 |
| bm25, full hunk text | 0.658 | 0.932 | 0.959 [0.89, 0.99] | 0.7 |
| fusion lexical+bm25 | 0.63 | 0.877 | 0.932 [0.85, 0.97] | 0.6 |
| bm25 + named identifiers/paths (full text) | 0.726 | 0.918 | 0.945 [0.87, 0.98] | 0.6 |
| lexical + named identifiers/paths | 0.671 | 0.89 | 0.945 [0.87, 0.98] | 0.7 |
| CodeBERT cross-encoder (ours) | 0.562 | 0.808 | 0.932 [0.85, 0.97] | 0.6 |
| fusion CodeBERT+lexical | 0.589 | 0.89 | 0.973 [0.91, 0.99] | 0.8 |

Random ranking would reach hit@5 = 0.838 overall (most gold PRs are small) and 0.256 on the large ones, so only the large-PR column discriminates, and with n=10 a difference of one or two requirements is noise. No gold PR was in the CodeBERT training set (gold PRs were held out). Reading: our trained retriever is not better than word-overlap or BM25 on its own; the CodeBERT+lexical fusion is nominally best (0.97 / 0.80) but the intervals overlap, so that is a hypothesis, not a result. Boosting BM25 / word overlap with identifiers the requirement names verbatim (backticked names, file paths, snake_case/camelCase; fixed weights chosen before looking at the results) raised hit@1 from 0.66 to 0.73 and 0.59 to 0.67 with no loss at hit@5; that is about 5 of 73 requirements and does not help on large PRs, so it is a candidate, not an established gain.
<!-- RESULTS:END -->

## HTML report

`pr-audit run <PR_URL> --retrieval lexical --html report.html` also writes one self-contained HTML file: the score, a
step-by-step breakdown of how it was computed (done = 1, partial = 0.5, missing = 0, minus a capped scope-creep
penalty), a map of which hunks back which requirement, and for every verdict the exact diff lines the judge quoted
(verified to exist in the hunk). No network, no external assets; PR text is rendered as text, never as HTML.

## Where it fails (read this before trusting a number)

- **Our trained models cannot judge a requirement inside one PR.** The relevance model learned to tell whether a hunk
  belongs to a PR, not whether it satisfies a requirement. Alone it catches almost no removed requirements, and its
  "done" precision is no better than always answering "done" (see the base-rate line under the table). Supervising it with commit-message to hunk mappings did not fix this
  (within-PR AUC 0.502). The first version of this project shipped on that model and reported a falsely perfect score.
- **So the judge is an LLM.** Our parts are retrieval, the verifier, and the benchmark. The verifier's benefit over no
  verifier is not statistically established (intervals overlap). Retrieval's accuracy benefit over showing all hunks is
  also not established on small PRs; on large PRs it is needed to fit the free-tier token limit (the all-hunks run hit
  HTTP 413/429 on Groq), which is a cost argument, not an accuracy one.
- **Scope-creep flags are low precision.** On the 14-PR gold set (40 non-test/doc hunks, 7 labelled creep, base rate 0.17),
  flagging at the default threshold (0.5) gives precision 0.25 and recall 1.0; a stricter 0.2 gives 0.42 and 0.71
  (`bench/eval_creep.py`). With 7 positives and the threshold looked at on the same data, treat these as a rough
  guide: the flags are candidates for a human to look at, not findings.
- **The gold set is tiny and single-annotator.** 14 PRs plus 4 large PRs (the large set is not reviewed by the owner).
  Labels were drafted by Claude; the owner approved the 14-PR draft unchanged, and a later cross-check by Claude
  still found 5 wrong labels (docs/GOLD_CHANGES.md), which shows how weak "approved" is. The judge is also an LLM, so
  errors may be correlated. After the fixes the 14-PR set has no `missing` labels at all.
- **Clean-set precision/recall say little.** After the label fixes the 14-PR set has only 3 requirements that are not
  "done", so "false done" rates there rest on a handful of items. The fault-injection columns (labels known by
  construction) are the main evidence; they cover omissions, not partial implementations.
- **Fault injection undercounts.** Removing the hunks a label points at does not always remove the requirement
  (duplicate files, requirements satisfied elsewhere), so catch rates are likely underestimates by an unknown amount.
- **Requirement splitting is weak.** Checklists work; prose and issue templates produce non-requirements. Measured on
  the gold PRs by `bench/eval_splitter.py` (`bench/results/splitter.json`): about 4 in 5 outputs that gold covers are
  real requirements after the noise rules, up from about 3 in 4 before. That score is in-sample (the rules were written
  after reading those PRs), so expect worse on new PRs. Lists of "possible approaches" are flagged optional and a
  missing option is not counted as a gap.
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

Without `models/`, use lexical retrieval (the default quick start): `pr-audit run <PR_URL> --retrieval lexical`. It needs a free Groq or Gemini key in `.env`. Whether lexical retrieval matches the CodeBERT retriever is not established yet: the comparison runs were invalid (judge errors) and are not reported.

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
