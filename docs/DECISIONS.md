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
