# Decisions log

## 2026-11-24 — Angle
Ticket-vs-PR checking already ships in Qodo, CodeRabbit, cubic and Augment, and all need a linked Jira/Linear ticket.
We build around the gap: **the ask is the prompt you gave a coding agent** (or an issue/PR body), not a ticket.
Three pillars: (1) agent-PR auditor, (2) public fault-injection benchmark as proof, (3) deterministic evidence verification as the engine.

## Stack changes vs the handoff SOP
- No Ollama (too slow on this machine). Cloud free tiers only: Gemini + Groq, OpenRouter as fallback. Every call cached by prompt hash.
- Groq free tier is ~8K tokens/min on gpt-oss-120b, so prompts stay small: one requirement + its hunks per call.
- Free-tier prompts may be used for training (Gemini): public repos only.
- Free limits are unstable; recheck on the provider console before each benchmark run.

## Repo
Name: pr-intent-audit (public). Not pushed yet.

## 2026-11-24 — Multi-model judges that learn
- 2+ judges from different model families (Gemini, Groq gpt-oss, Qwen) judge each requirement independently.
- A learned combiner (logistic regression / small GBM) trained on benchmark ground truth replaces plain voting. Features: each judge's verdict, evidence-verified flag, hunk-match score, diff size.
- Memory of past mistakes: retrieve similar failed cases into the prompt (in-context learning, no fine-tuning).
- Stretch: fine-tune a small open model on stored traces (Colab free GPU).
- Honesty: evaluate with repo-held-out cross-validation and confidence intervals; compare against single judge and plain voting; report if the combiner does not win.
- Every run is traced from day one so training data accumulates.

## 2026-11-24 — Our own models, no API keys (supersedes the API-key plan above)
Owner decision: the judging models are built by us, not rented. Rationale: ownership, zero quota risk, reproducible, stronger portfolio story.
- Training data comes free from the benchmark engine: take merged PRs, inject faults (revert hunks, add unrelated hunks), labels are known by construction. No LLM labeler.
- Model 1 `relevance`: cross-encoder (requirement sentence, hunk) -> relevant? Replaces keyword/embedding retrieval.
- Model 2 `verdict`: classifier (requirement, relevant hunks) -> done/partial/missing. Extractive: it points at hunks/lines, it never generates quotes, so fabricated evidence is impossible by construction.
- Model 3 `creep`: classifier for orphan hunks -> supporting / unrequested.
- Ensemble: 2+ different architectures/seeds, learned combiner (see above) trained on held-out repos.
- Requirements: rule-based splitting of checklists/sentences first; no LLM needed for v1.
- Frontier LLMs appear only as optional baselines in the benchmark, off by default.
- Training on free GPU (Kaggle/Colab) with small pretrained code encoders; inference on CPU.
- Risk: small models may reason worse than frontier LLMs. We measure and report.

## 2026-11-24 — First real report exposed a limit (keep in README "Where it fails")
- Audit of py-tg-moder#93 marked 3/3 requirements DONE from the same two generic hunks (config + test file); rank 100. Evidence lines were the first lines of the hunk, unrelated to the requirements.
- Root cause 1: the relevance model was trained on PR-level labels (hunk from same PR = relevant), so it cannot separate requirements WITHIN one PR. Our 0.908 requirement-level F1 only measures the cross-PR case.
- Root cause 2: evidence selection took first lines, not matching lines.
- Root cause 3: Russian ask vs English code model (no multilingual support).
- Mitigation now: a requirement is DONE only if a line in the cited hunk shares vocabulary with it; otherwise UNCLEAR.
- Real fix needs within-PR training signal: hand-labelled requirement->hunk gold set, and/or a multilingual encoder.

## 2026-11-24 — Gold eval: relevance model is a PR-membership detector (FAILURE, keep in README)
- Exact fault injection on 7 gold PRs: 0/9 omitted requirements caught. Deleting the hunks that implement a requirement leaves scores ~0.99 because every remaining hunk of the same PR still looks relevant.
- Clean run: a MISSING and a PARTIAL requirement were both called DONE. "done recall 1.0" is meaningless: it says done to everything.
- The earlier 0.908 requirement-level F1 only measured cross-PR discrimination. It does not support any claim about within-PR auditing.
- Fix in progress: within-PR supervision from commits. (commit message -> hunks of that commit) positive; hunks of OTHER commits in the same PR negative.

## 2026-11-24 — Within-PR supervision did NOT work; moving to a hybrid (NEGATIVE RESULT, keep in README)
- Relevance model v2 (CodeBERT + commit-message supervision, gold PRs held out): overall test AUC 0.801 [0.768, 0.845], but WITHIN-PR test AUC 0.502 (n=136 rows): chance.
- A plain IDF keyword overlap gets 0.61 on the same within-PR test rows: the learned model is worse than lexical matching for "which hunk implements this change".
- Gold fault injection (requirement's exclusive hunks deleted): still 0/9 caught. Clean gold run: 1 false MISSING, 2 abstentions, PARTIAL called DONE.
- Why (hypotheses, untested): ~110 PRs with commit supervision is too little; commit messages are often generic ("address review", "docs"); a 125M encoder with 384 tokens saturates on same-PR vocabulary.
- Decision: hybrid. Our components keep what they do well (ingest, requirement cleaning, retrieval, evidence verification, scope-creep orphans, PR-vs-ask mismatch, benchmark). The per-requirement implementation judgement goes to an LLM judge (free-tier APIs) whose output is checked by our verifier and fused by a learned combiner. Measure hybrid vs ours-only on the same gold + fault-injection set.

## 2026-11-25 — Hybrid on 14 gold PRs (46 scored requirements), labels still UNREVIEWED drafts
Judge for almost all new calls: Groq gpt-oss-120b (Gemini free quota exhausted); cached earlier answers mix Gemini 3.5 Flash and Groq.
- Hybrid (our top-5 retrieval -> LLM judge -> our verifier): done-precision 0.966, done-recall 0.824, abstained 5/46, false "done" on not-done 1/7, omitted requirement no longer "done" 10/13 (6/13 as "missing").
- Ablation, judge sees ALL hunks instead of our top-5: recall 0.839, abstained 9/46, faults 9/12. => our relevance model adds nothing measurable on these small (4-12 hunk) PRs. Untested on large PRs.
- Ablation, no verifier: abstained 0, precision/recall unchanged, but faults caught only 7/14 (vs 10/13): without it, a judge keeps saying "done" after the code is deleted. Verifier earns its keep (intervals overlap; suggestive, not proven).
- FLAW found: the fault harness removed only hunks "exclusive" to a requirement, so some faults were partial removals (e.g. sigma R5 kept its test hunk; gh-factory had duplicate files). Fixed: remove ALL hunks a requirement points at; controls = requirements sharing none of them. Numbers above predate the fix.

## 2026-11-25 (b) — Strict fault harness results, 14-PR gold set (labels NOT human-reviewed)

Gold base rate: 39/46 requirements are "done". Any "done precision" must be read against 0.85.

| Variant | done precision | done recall | abstained | faults no longer "done" (95% Wilson) | faults -> "missing" |
|---|---|---|---|---|---|
| ours-only (relevance + verdict + orphan) | 0.868 | 0.943 | 6 | 3/32 (~0.03-0.24) | 0/32 |
| hybrid top5 + verifier | 0.966 | 0.824 | 5 | 21/28 (0.57-0.87) | 15/28 (0.36-0.70) |
| hybrid top5, no verifier | 0.970 | 0.821 | 0 | 19/31 (0.44-0.76) | 15/31 (0.32-0.65) |

Findings:
- Ours-only precision (0.868) is ~ the base rate: it is effectively an "always done" detector on within-PR questions. Confirms the earlier 0/9 and within-PR AUC 0.502 results.
- Hybrid is clearly better than ours-only (intervals do not overlap). The verifier's gain (61% -> 75%) is NOT statistically established: intervals overlap heavily.
- Fault denominators differ per variant (faults are only injected where baseline said "done"); abstained requirements drop out, which is mildly generous to the verified variant.
- Remaining "misses" are partly harness noise: fault removes only the hunks the gold label points at; duplicate files (gh-factory baseline/ vs .github/) and incomplete gold hunk lists leave the requirement legitimately satisfied. True catch rate is likely underestimated, but we cannot say by how much until labels are reviewed.
- Judging is mostly Groq gpt-oss-120b (Gemini quota exhausted); cached answers mix providers.
- Gold labels were written by Claude and the judge is also an LLM: correlated bias is possible. Human review required.


## 2026-11-25 (c) — Re-run after gold corrections; lexical-retrieval ablation INVALID

Gold set after docs/GOLD_CHANGES.md: 42 scored requirements, 39 "done" (base rate 0.929), 3 "partial", 0 "missing".
- ours-only: done precision 0.917 (BELOW the always-"done" base rate), faults 3/32, "missing" 0/32. Within-PR it adds nothing.
- hybrid top5+verifier: precision 0.966, recall 0.824, faults 21/28, 0 judge errors. all-hunks: 20/26. no-verifier: 19/31.
  Fault numbers did not change with the label fixes (faults do not depend on the corrected labels).
- Clean-set metrics are now nearly uninformative (3 not-done items); fault injection is the real evidence.
- Lexical retrieval run: 33-39 of ~100 judge calls failed with Groq HTTP 429 (free-tier rate/daily limit; Gemini quota
  also exhausted), so abstentions and "false alarms" are mostly API failures. Result discarded; do not quote.
  To redo after the quota resets. Lesson: always check `judge_errors` before reading any LLM table (now printed and flagged).

## 2026-11-25 (d) — Splitter noise rules (offline, no API)

bench/eval_splitter.py compares splitter output with gold: before, 59/80 matched outputs were real requirements
(0.738); after dropping process/template noise (checklist boilerplate, issue refs, form fields, "reviewed by"),
59/73 (0.808), with all 59 gold requirements still produced. IN-SAMPLE: I wrote the rules after reading these PRs, so
this overstates real-world gains. Added `Requirement.optional` for bullets under "possible approaches / fix options":
a missing optional requirement no longer lowers the rank. Bug found while testing: noise filtering made single-item
lists fall back to sentence mode; list structure is now judged before filtering. 31 tests pass.

## 2026-11-26 (e) — Retrieval measured without an LLM; no new model training

- Question: is the CodeBERT retriever worth keeping over word overlap? The LLM-based comparison was invalid (judge errors), so we measured retrieval directly: hit@k of the gold hunks (`bench/eval_retrieval.py`, 73 requirements, no quota).
- Result: CodeBERT alone hit@1 0.56 / hit@3 0.81 / hit@5 0.93, no better than lexical (0.57 / 0.88 / 0.94) or BM25 (0.66 / 0.86 / 0.92). Fusion CodeBERT+lexical is nominally best (hit@5 0.97; large PRs 0.80 vs 0.50-0.70) but the large-PR sample is 10 requirements and the intervals overlap.
- Decision: keep lexical as the default (no model files, same accuracy within noise); keep CodeBERT optional; do NOT train or tune more models: the bottleneck is the amount of large-PR gold, not the architecture. Fusion stays a hypothesis until more large-PR labels exist.
- Scope-creep flags: precision 0.25 at the default threshold against a 0.17 base rate (`bench/eval_creep.py`, 7 positives). Documented as low precision.
- Identifier boost (named identifiers / file paths in the requirement matched verbatim in the hunk; weights fixed in advance, run once): hit@1 0.66 -> 0.73 (BM25) and 0.59 -> 0.67 (lexical), hit@5 unchanged, large PRs unchanged (0.60 / 0.70). About 5 of 73 requirements, intervals overlap. Not adopted as default; to be tested end to end (judge verdicts) when quota allows.
- Retrieval scores are now summed in sorted token order, so lexical/BM25 results are deterministic (earlier 0.57 vs 0.59 hit@1 jitter was float summation order over a set).

## 2026-11-26 (f) — Large-PR gold grew 4 -> 7 PRs; retrieval table re-read

- Mining with wider queries added 10 large PRs; 3 were usable and were labelled (Claude draft, unreviewed): Noesis/285, bec_widgets/686, juntagrico-paas/19 (+10 requirements). The other mined PRs were rejected because their "requirements" were checklists, repro steps or unrelated scaffolding.
- With the large-PR sample doubled (n=10 -> 20), the earlier reading changed: plain BM25 on large PRs is the worst (hit@5 0.45 vs 0.80 for lexical; random 0.19), and BM25+identifiers (0.75) / lexical+identifiers (0.80) are close to lexical. The earlier "BM25+identifiers 0.60 vs BM25 0.50 vs lexical 0.70" ordering was noise, which is why single-digit-n comparisons were labelled hypotheses.
- CodeBERT rows were dropped from `retrieval.json` because the gold set changed and this machine has no torch; the owner needs to re-run `python bench\eval_retrieval.py` for them. Earlier CodeBERT numbers (n=73) are in entry (e).
- Lexical stays the default. No retrieval change is adopted.

## 2026-11-26 (g) — CodeBERT re-measured on the larger gold set: no better than word overlap

- Same 83 requirements (20 on large PRs). CodeBERT alone: hit@1 0.53, hit@3 0.76, hit@5 0.89, large-PR hit@5 0.60. Lexical: 0.52 / 0.85 / 0.94 / 0.80. Fusion CodeBERT+lexical: 0.55 / 0.85 / 0.95 / 0.80, i.e. equal to lexical on large PRs.
- The "CodeBERT+lexical fusion looks best" reading in entry (e) (hit@5 0.97, large 0.80 on n=10) did not hold up on the larger sample. It was noise.
- Conclusion: the trained retriever has no demonstrated advantage over word overlap and is worse on its own. Lexical stays the default; CodeBERT stays an optional, documented negative result. No further model training.

## 2026-11-26 (h) — Verifier audit on cached judgments; splitter noise rules

- Of 34 cached judgments reachable with lexical top-5 prompts (63 more prompts were not cached), the verifier downgraded 5 "done" verdicts to unclear. Inspection: in 4 the quoted lines do not exist anywhere in the PR (invented or truncated by the judge), so the downgrade was correct; in 1 the judge cited a file path that matched several hunks. Fix: a bare file path is now resolved to the hunks of that file that contain a quoted line (no quote, no resolution). Now 4 downgrades; verdicts and prompts are unchanged, so the cache stays valid. Small sample, so no rate is claimed.
- Splitter: added rules for definition-of-done template items, short environment key/values (`**Python version**: 3.6.2`), "please run/update..." instructions, and `### 🪜 How to reproduce` style headings (emoji broke the heading match). Gold requirements still produced 72/72; precision on gold-covered outputs 72/86 (0.84), in-sample.

## 2026-11-26 (i) — Escalating judge (experimental, off by default) and local audits

- Why: on large PRs the judge sees only the top-5 hunks, and retrieval hits the right hunk in the top 5 about 80% of the time there (n=20). When pass 1 does not give a verified "done", `--escalate` shows the top 12 (max 2 calls per requirement). Pass 2 replaces pass 1 only if it is a verified done/partial.
- Risk it must be tested for: more chances to find a "done" could raise false "done" verdicts. The fault-injection protocol (`python bench\eval_gold_llm.py lexical escalate`, and `large lexical escalate`) measures exactly that; it is NOT adopted until judge_errors = 0 and fault catch / false-done do not get worse than the same run without `escalate`.
- `pr-audit local` audits a git range or the working tree against an ask file, for work that never went through a PR.

## 2026-11-26 (j) — Bug found by the new whole-pipeline test: cited hunks were also listed as scope creep

- The golden pipeline test showed a hunk that a verdict cites as verified evidence could still be flagged as "possible scope creep" (creep used only the relevance score threshold) and cost 5 points. Fixed: a hunk cited as evidence by any requirement is never creep. The demo report moved from 55 to 65 for this reason (two cited hunks no longer counted). Offline scope-creep precision numbers (`bench/eval_creep.py`) were computed from scores only and are unaffected.
- Added: thin-ask warning (a one-line or list-less ask is flagged on the report), a one-line "N of M requirements have verified evidence" summary, and a "Copy as PR comment" button in the HTML report.

## 2026-11-26 (k) — Licenses: audit, demo replaced, mining filtered

- Audit: 14/26 gold repos permissive, 12 not (none / NOASSERTION / GPL-3.0). The demo report had been built from a repo with no license (it embeds diff lines), so it was regenerated from an MIT repo; the hand-label comparison notes still appear. New demo: 4/4 requirements DONE, one of them (#4) on weak evidence where the hand label is UNCLEAR, 3 scope-creep candidates (-15).
- `bench/mine_large.py` now skips repos without a permissive license (cached in `bench/data/license_cache.json`) and takes a time budget via MINE_SECONDS.
- Owner decision (2026-11-26): keep the 12 non-permissive repos' short requirement excerpts in `bench/gold/*.json`. Residual risk is low, not zero: the excerpts are short and carry no code.

## 2026-11-26 (l) — Large-PR gold 7 -> 9 PRs (permissive licenses only); retrieval re-read again

- Added reduct-grafana/13 (MIT) and kadai/1329 (Apache-2.0), 9 requirements, Claude draft, unreviewed. Not used: concourse/9218 (env-form fields), jni-rs/596 (generic PR checklist), Wahllokalsystem/1794 (German refactor list; non-English).
- Large-PR sample is now n=28. Lexical large-PR hit@5 moved 0.80 -> 0.71 (random 0.26), BM25 0.45 -> 0.46, lexical+identifiers 0.80 -> 0.71, BM25+identifiers 0.75 -> 0.68. Ordering unchanged: lexical-based variants best, plain BM25 worst. The 0.80 figure in entry (g) was a small-sample high; the better estimate is about 0.7.
- CodeBERT rows are dropped again (gold set changed, no torch here). Re-run `python bench\eval_retrieval.py` once labelling stops, so it is done once.

## (m) Why lexical retrieval misses on large PRs (error analysis, no code change)

`python bench/miss_analysis.py` lists the 8 of 28 large-PR requirements where the best gold hunk is outside the top 5 (n is small; read as a pattern, not a rate). Of the 20 hits, 15 are at rank 1–2.

Causes seen in the misses:
- **Bare identifier requirements** (kadai `TaskHistoryEvent`, `WorkbasketHistoryEvent`, `ClassificationHistoryEvent`): sample/test SQL files named `*-history-event.sql` repeat the words and outrank the query implementation hunks. CamelCase is already split by the tokenizer, so this is not a tokenizer gap.
- **Generic requirements** ("Added tests", "Commit the generated folder"): little vocabulary to match, so ranking is close to arbitrary.
- **Docs/instruction files outranking code** in repos that ship many markdown instruction files (opnDossier, upm-entrepreneurship-platform).

Decision: no retrieval change. A path-type prior (down-weight docs/SQL data) would fit these 8 cases but I have no held-out large PRs to check it against, so it would be tuned on the test set. Revisit when the large gold set is bigger. The escalating judge (top-12) is the existing mitigation and is still unmeasured, pending Groq quota.

## (n) Large-PR gold 11 PRs / 47 requirements; retrieval re-read at n=40 large-PR requirements

Added gauss-quad/141 (Apache-2.0, 7 requirements) and StudyConnect-ZHAW/Backend/109 (MIT, 5 requirements); Claude drafts, unreviewed. Four StudyConnect requirements are plain "done"; R1, R2 and R4 are low confidence (vague wording, or the DTO exposes a User object rather than a bare id).
- Retrieval (n=103 requirements, 40 on large PRs, random 0.23 on large): lexical 0.72, lexical+identifiers 0.72, BM25+identifiers 0.72, fusion 0.70, BM25 full text 0.68, lexical full text 0.65, BM25 0.57.
- What changed: at n=28 plain BM25 was clearly worst (0.46) and lexical-based variants led. At n=40 the best variants tie at 0.72 and BM25 on full text (0.68) is close. The earlier ordering claim "lexical beats BM25" is weaker than I said; differences of 0.04 on n=40 are about one or two requirements.
- Decision unchanged: lexical stays the default (simplest, no dependency, tied for best), but no variant is shown to be better. CodeBERT rows are still missing (no torch here).

## (o) PR-template checklists are noise; 13 of 14 newly mined PRs were one repo's template

The last mining run kept 14 PRs; 13 were MaibornWolff/codecharta (BSD-3), whose PR template is a checklist ("changes have been manually tested", "CHANGELOG.md has been updated", ...). Those are process items, not requirements on the code, so labelling them would have added meaningless rows to the gold set. Not used.
- Splitter: added the template phrases to NOISE (test `test_pr_template_checklist_is_noise`). The miner needs 3-8 requirements after splitting, so such PRs are no longer collected. The 13 PRs were removed from the local large pool (they stay in `large_rejected.txt`).
- Used: canvas-lms-kit/20 (MIT), 6 requirements, Claude draft, unreviewed. "Code Style: PSR-12" is labelled unclear (not verifiable from a diff); the class-structure and DocBlock items are medium confidence.
- Splitter re-measure (in-sample, the gold sets also grew): 93 of 107 matched outputs are real requirements (0.87), all 93 gold requirements are still produced. Not comparable with the earlier 72/86.
- Lesson: one repo can dominate a mined batch. Mining should cap PRs per repo (not done yet).
