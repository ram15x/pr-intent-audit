# Gold set — DRAFT labels by Claude, please review

Reply with the NUMBER of any line I got wrong and the right answer. Silence = you agree.
Legend: DONE | MISSING | PARTIAL | UNCLEAR (cannot be decided from the diff) | EXCLUDE (not a real requirement)
Labels marked low/medium confidence deserve your eyes first.

## https://github.com/CanastaWiki/Canasta-CLI/pull/924
_feat(reconcile): add 'canasta reconcile' to fix config/runtime drift_

1. **DONE** (medium) — `sync_compose_profiles` — re-derive COMPOSE_PROFILES from the feature flags + DB mode (self-heals internal-db / elasticsearch drift; tears d
   hunks: roles/instance_lifecycle/tasks/reconcile.yml:1-33
2. **DONE** (medium) — Regenerate rendered config (Caddyfile from the current wikis.yaml).
   hunks: roles/instance_lifecycle/tasks/reconcile.yml:1-33
3. **DONE** (medium) — `docker compose up -d` — start anything missing, recreate only what changed. **No `down`**, so it is non-disruptive.
   hunks: roles/instance_lifecycle/tasks/reconcile.yml:1-33
4. **DONE** (medium) — Non-disruptive (`up -d`, not `down`/`up`) — a full restart stays `canasta restart`.
   hunks: roles/instance_lifecycle/tasks/reconcile.yml:1-33, tests/unit/test_reconcile.py:1-64
5. **DONE** (medium) — Does NOT re-render from the gitops source — works on the current `.env` + derived rules (re-rendering is `gitops pull`'s job).
   hunks: roles/instance_lifecycle/tasks/reconcile.yml:1-33, tests/unit/test_reconcile.py:1-64
6. **DONE** (high) — `doctor`'s consistency warnings point operators at `canasta reconcile`.
   hunks: direct_commands/doctor.py:238-245, direct_commands/doctor.py:312-318, tests/unit/test_doctor_consistency.py:129-135

## https://github.com/aganezov/ont_qc_mcp/pull/135
_fix: update AnyIO and restore dependency audit_

7. **DONE** (high) — Issue #134: Restore scheduled dependency audit with a scoped AnyIO update Summary The September 19 scheduled CI run fails the dependency aud
   hunks: .github/workflows/ci.yml:110-116
   note: issue summary
8. **DONE** (high) — Update AnyIO without bundling unrelated dependency upgrades.
   hunks: pyproject.toml:23-29
   note: lockfile dropped as noise
9. **DONE** (high) — Remove the obsolete pytest audit exemption from CI and the local gate, and add a changelog entry.
   hunks: .github/workflows/ci.yml:110-116, scripts/ci-local.sh:44-50, CHANGELOG.md:7-13

## https://github.com/cisagov/manage.get.gov/pull/5156
_#5153: Add in psycogreen library - [none]_

10. **DONE** (high) — add in psycogreen
   hunks: src/Pipfile:21-27, src/requirements.txt:51-57
11. **DONE** (high) — update the gunicorn configuration to use psycogreen such that it's compatible with gunicorn gevent
   hunks: src/gunicorn.conf.py:1-30, src/run.sh:6-11
12. **EXCLUDE** (high) — Relates to #5090
   note: a reference, not a requirement
13. **SCOPE CREEP** (medium) — `src/requirements.txt:2-20` — unrelated version bumps (boto3, botocore ...)

## https://github.com/pfBlockerNG/pfBlockerNG/pull/672
_pfblockerng: resolve DNSBLIP reprocess marker folder from action (#655)_

14. **EXCLUDE** (high) — The IP-feed reprocess gate (~15329) checks `{$pfbfolder}/{$header}.update` with `$pfbfolder` = the action's folder.
   note: describes existing behaviour
15. **EXCLUDE** (high) — Pre-existing This predates #654 (the marker was hardcoded to `denydir` before that change too).
   note: background
16. **DONE** (high) — Fix Resolve the DNSBLIP marker folder (and the `DNSBLIP_<fam>.txt` destination, if applicable) from the `$pfb['dnsbl_ip']` action instead of
   hunks: src/usr/local/pkg/pfblockerng/pfblockerng.inc:1479-1508, src/usr/local/pkg/pfblockerng/pfblockerng.inc:14686-14702, src/usr/local/pkg/pfblockerng/pfblockerng.inc:14731-14747
17. **DONE** (high) — Add coverage for the Alias_Native action.
   hunks: tests/php/DnsblipMarkerFolderTest.php:1-130

## https://github.com/jt-mchorse/chunking-strategies-lab/pull/97
_fix(corpus): read documents with utf-8-sig to tolerate a BOM (#95)_

18. **EXCLUDE** (high) — shift chunk character offsets by 1 for the first chunk,
   note: bug symptom
19. **EXCLUDE** (high) — leak `﻿` into the first chunk's text and into any snippet-match comparison,
   note: bug symptom
20. **EXCLUDE** (high) — subtly perturb retrieval/scoring against a BOM-less twin.
   note: bug symptom
21. **DONE** (high) — A BOM-prefixed corpus document loads with identical text to its BOM-less twin (no leading `﻿`).
   hunks: chunking_lab/corpus.py:36-55
22. **DONE** (medium) — BOM-less documents unaffected.
   hunks: chunking_lab/corpus.py:36-55
   note: implicit; H4 may test it
23. **DONE** (high) — Lock test with a BOM fixture, confirmed failing pre-fix.
   hunks: tests/test_corpus.py:50-79
24. **SCOPE CREEP** (high) — `MEMORY/full_history_ai.md:1051-1074` — agent session log file
25. **SCOPE CREEP** (high) — `MEMORY/full_history_human.md:672-686` — agent session log file

## https://github.com/oddessentials/odd-bot-moltbook/pull/40
_perf(spa): gate Manus dev runtime out of prod + split brief data (#38)_

26. **PARTIAL** (medium) — `build.rollupOptions.output.manualChunks` to split vendor/route bundles.
   hunks: agent-brief/vite.config.ts:5-93
   note: CORRECTED: hunk only isolates data/briefs.json via manualChunks; vendor/route splitting not done. Issue lists approaches 'to evaluate, not commit to'.
27. **MISSING** (medium) — Route-level dynamic `import()` (wouter lazy routes).
   note: no routing/App file in the diff
28. **UNCLEAR** (low) — Audit heavy deps (the full Radix UI set is pulled in).
   note: manualChunks may group radix; cannot tell

## https://github.com/nanohype/eks-gitops/pull/84
_Keep a freshly vended spoke from deadlocking on IPs, arch, and Karpenter_

29. **EXCLUDE** (high) — Cilium ENI-mode per-node IP limit (~35 on m7g.large) is exceeded → pods stuck `ContainerCreating` with `cilium-cni: no IPs available`.
   note: problem statement
30. **EXCLUDE** (high) — Karpenter, itself scheduled on a saturated bootstrap node, loses DNS and can't resolve the EC2 API (`lookup ec2.us-west-2.amazonaws.com: i/o
   note: problem statement
31. **MISSING** (medium) — A dev/smoke addon profile that installs a minimal set (skip falco/trivy/gpu-operator/neuron/grafana-prometheus for non-prod), and/or
   note: no addon-profile hunk
32. **DONE** (high) — Size the bootstrap node group for the catalog (more/bigger nodes, or prefix-delegation for more IPs/node), and/or
   hunks: addons/networking/cilium/values.yaml:4-15
   note: prefix delegation in cilium values
33. **PARTIAL** (low) — Give Karpenter a priorityClass + anti-affinity so it isn't stranded on a saturated bootstrap node.
   hunks: addons/operations/karpenter/values.yaml:2-13
   note: priorityClass seen; anti-affinity not verified
34. **SCOPE CREEP** (low) — `addons/operations/karpenter-resources/base/nodepool.yaml:15-24` — arm64 nodepool; justified by the PR title, not by a listed requirement
35. **SCOPE CREEP** (low) — `addons/operations/karpenter-resources/base/nodepool.yaml:69-78` — same

## https://github.com/adamsuk/gh-factory/pull/10
_fix: issue form acceptance criteria uses a placeholder_

36. **DONE** (high) — The baseline issue form uses `placeholder` for Acceptance criteria, matching touchlineHQ/.github#2
   hunks: baseline/files/.github/ISSUE_TEMPLATE/task.yml:21-28
37. **DONE** (high) — gh-factory's own copy matches, so the drift check stays clean
   hunks: .github/ISSUE_TEMPLATE/task.yml:21-28
38. **DONE** (high) — A test covers it, and CHANGELOG.md has a dated entry
   hunks: tests/test_render.py:103-114, CHANGELOG.md:5-19

## https://github.com/ztrange/veri/pull/2693
_fix: tick wrapped criteria under the last Acceptance criteria heading (#2630)_

39. **EXCLUDE** (high) — the criteria sit under a **second** `## Acceptance criteria` heading — one that replaces an
   note: problem description
40. **EXCLUDE** (high) — the checkbox text **wraps over several lines**.
   note: problem description
41. **DONE** (medium) — With two unfenced `## Acceptance criteria` headings in the body, the tick applies under the last one: a matcher held only by a criterion und
   hunks: skills/tdd/scripts/veri/tick_issue_criterion.py:27-37, skills/tdd/scripts/veri/tick_issue_criterion.py:41-61, skills/tdd/scripts/veri/tick_issue_criterion.py:69-75, skills/tdd/scripts/tests/py/test_tick_issue_criterion.py:580-667
42. **DONE** (high) — A criterion whose checkbox text wraps over several lines is ticked when the matcher occurs in any of its lines, and only the checkbox line i
   hunks: skills/tdd/scripts/veri/tick_issue_criterion.py:41-61, skills/tdd/scripts/tests/py/test_tick_issue_criterion.py:580-667
43. **DONE** (medium) — The script exits 0 only when the issue body it writes back differs from the one it read; when the tick changed nothing it exits 3 and writes
   hunks: skills/tdd/scripts/tests/py/test_tick_issue_criterion.py:580-667, skills/tdd/scripts/veri/tick_issue_criterion.py:69-75
44. **SCOPE CREEP** (low) — `.tdd/issue-2630-metrics.md:1-168` — agent TDD metrics artifact; repo convention?
45. **SCOPE CREEP** (low) — `.tdd/issue-2630.md:1-6` — agent TDD plan artifact; repo convention?

## https://github.com/Agrim-Intelligence/sigma/pull/380
_test: record phase budget acceptance criteria_

46. **DONE** (high) — `evals/phase_context_budget.py`: for each agent (orchestrator, goal slot, research, plan, plan-review, implement, review before and after th
   hunks: evals/phase_context_budget.py:1-223, tests/test_phase_context_budget.py:1-119, evals/phase_context_budget.json:1-21
47. **DONE** (high) — `evals/phase_context_budget.json` holds the ceiling per agent. The test fails above the ceiling, and fails if a committed ceiling exceeds th
   hunks: evals/phase_context_budget.json:1-21, evals/phase_context_budget.py:1-223, tests/test_phase_context_budget.py:1-119
48. **DONE** (medium) — Measurement only: it changes no prompt.
   note: negative requirement ('changes no prompt'): evidence is absence of skills/ hunks
49. **DONE** (medium) — The printed table is committed with its date and the commit it was measured on.
   hunks: evals/phase_context_budget.json:1-21, evals/phase_context_budget.py:1-223
50. **DONE** (medium) — A planted 500-word paragraph in `skills/agrim-loop/references/running.md` fails the test (control, red first).
   hunks: tests/test_phase_context_budget.py:1-119, evals/README.md:16-38

## https://github.com/epr-ds/nutriplan/pull/759
_feat(mobile): serve cached plans first and refresh them from the network (DPL-404)_

51. **DONE** (high) — Reads served from cache then refreshed from network
   hunks: mobile/shared/src/commonMain/kotlin/com/nutriplan/shared/data/repository/CachedDietaryRepository.kt:19-27, mobile/shared/src/commonMain/kotlin/com/nutriplan/shared/data/repository/CachedDietaryRepository.kt:37-66, mobile/shared/src/androidHostTest/kotlin/com/nutriplan/shared/data/repository/CachedDietaryRepositoryTest.kt:213-242
52. **MISSING** (medium) — Create/add-meal write-through to cache
   note: no create/add-meal write-through hunk
53. **UNCLEAR** (low) — Errors surfaced as typed results; covered by commonTest
   note: typed errors not visible; tests are androidHostTest not commonTest
54. **EXCLUDE** (high) — #89 — `DPL-403`
   note: issue reference
55. **EXCLUDE** (high) — #70 — `DPL-102`
   note: issue reference

## https://github.com/iteam7/gateway7/pull/150
_Add actionlint workflow check and name it in the Definition of Done_

56. **EXCLUDE** (high) — None: CI workflow and Definition of Done upkeep.
   note: meta line
57. **PARTIAL** (medium) — AC-01: Pinned actionlint checks `.github/workflows/` on pull requests and main, and a deliberately invalid workflow produces a failing check
   hunks: .github/workflows/actionlint.yml:1-22
   note: workflow added; 'invalid workflow fails' not visible
58. **PARTIAL** (low) — AC-02: Third-party actions use full commit SHAs with version comments; each applicable lint, format, type-check, build and test check has an
   hunks: .github/workflows/python.yml:12-19, .github/workflows/python.yml:24-33
   note: named steps yes; SHA pinning not verified
59. **DONE** (medium) — AC-03: Existing tests for the QR-02 critical modules, process demo and packaging checks remain enabled; any genuinely inapplicable check is 
   hunks: .github/workflows/python.yml:12-19
60. **DONE** (medium) — AC-04: `docs/definition-of-done.md` explicitly requires actionlint and the applicable product checks before merge; no VM deployment job is a
   hunks: docs/definition-of-done.md:23-29, AGENTS.md:29-35
61. **UNCLEAR** (high) — AC-05: The workflow PR passes its checks, and the latest required runs on main are green before the Customer Review, with links available fo
   note: runtime outcome (checks green), not in diff

## https://github.com/nahuel893/agents-system/pull/215
_docs(process): add a definition of done and a release gate with live evals (#214)_

62. **DONE** (high) — `AGENTS.md`: a "Definition of done" section that every PR meets before merge: offline checks; the live scenarios that cover what the change 
   hunks: AGENTS.md:63-108
63. **DONE** (high) — `AGENTS.md`: a "Release gate": the full live suite, the installed-wheel smoke test, the feature page labels refreshed, and an install from t
   hunks: AGENTS.md:63-108, docs/operations/release-process.md:34-62
64. **DONE** (high) — `docs/operations/release-process.md` and its ES twin: the same gate as numbered steps.
   hunks: docs/operations/release-process.md:34-62, docs/operations_es/release-process.md:35-64
65. **DONE** (high) — Both sections exist in `AGENTS.md` and name the exact commands.
   hunks: AGENTS.md:63-108
66. **DONE** (high) — The release process (EN + ES) lists the full live suite and the feature-page refresh as steps before tagging.
   hunks: docs/operations/release-process.md:34-62, docs/operations_es/release-process.md:35-64

## https://github.com/YinceIuCode/assistant_core_lab/pull/26
_17 week 4 t1 implement post v1chat endpoint   doomsdaycome_

67. **EXCLUDE** (high) — Pull latest `main` after Core Setup is merged.
   note: process step
68. **DONE** (high) — Implement `chat(req: ChatRequest, request: Request) -> ChatResponse` in `src/assistant_api/main.py`.
   hunks: src/assistant_api/main.py:64-75
69. **DONE** (high) — Call `service.handle(Message(text=req.message, session_id=req.session_id))`.
   hunks: src/assistant_api/main.py:64-75
70. **DONE** (high) — Return `ChatResponse(**resp.model_dump(), request_id=uuid.uuid4().hex[:12])`.
   hunks: src/assistant_api/main.py:64-75
71. **UNCLEAR** (medium) — Run `pytest -q tests/test_api.py -k chat` to verify 200 response and 422 validation errors.
   note: an instruction to run tests, not code
72. **EXCLUDE** (high) — **Estimated hours**: 1
   note: form field
73. **EXCLUDE** (high) — **Actual hours**:
   note: form field
74. **EXCLUDE** (high) — **PR Link**: #<PR-Number>
   note: form field
75. **SCOPE CREEP** (medium) — `.github/workflows/ci.yml:7-13` — CI workflow edits not in the ask
76. **SCOPE CREEP** (medium) — `.github/workflows/ci.yml:22-31` — CI workflow edits not in the ask
77. **SCOPE CREEP** (medium) — `.github/workflows/ci.yml:56-91` — new CI api-testing job not in the ask
78. **SCOPE CREEP** (medium) — `src/assistant_api/main.py:77-88` — edits TODO comments of other endpoints
