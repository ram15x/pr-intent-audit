# Gold label changes

Process: Claude drafted all labels; the owner read bench/gold/REVIEW.md and approved it without changes (2026-11-25);
Claude then re-read the cited hunks of every medium/low-confidence label against the actual diff text. The owner's
approval missed the problems below, which is why this file exists. Labels remain single-annotator (no second labeller).

| PR | req | before | after | why |
|---|---|---|---|---|
| oddessentials/odd-bot-moltbook/pull/40 | 1 | partial | exclude | issue lists 'possible approaches (to evaluate, not commit to)'; not a requirement. Real acceptance (no chunk-size warning, LCP measured, no regression) was never extracted |
| oddessentials/odd-bot-moltbook/pull/40 | 2 | missing | exclude | same: an approach to evaluate, not a requirement |
| oddessentials/odd-bot-moltbook/pull/40 | 3 | unclear | exclude | same: an approach to evaluate, not a requirement |
| nanohype/eks-gitops/pull/84 | 3 | missing | exclude | one of three 'and/or' fix options; not choosing it is not a gap |
| epr-ds/nutriplan/pull/759 | 2 | missing | unclear | retrieved hunks show only a doc comment 'Successful writes refresh the cache'; write path not visible in the diff |

Also noted, not changed: gateway7 AC-02 stays `partial` but my note 'SHA pinning not verified' was wrong; SHA pinning is
visible for the new actionlint workflow, what is not visible is whether the python.yml actions are pinned.
Canasta-CLI #924 requirements 1-5 are `done` mostly by reuse of an existing start.yml (the diff shows the call, not the
profile sync itself); the evidence is partly comments, so treat them as medium.

Effect on the 14-PR set: it had 3 `missing` and 4 `partial` labels; it now has 0 `missing` and 3 `partial`
(scored requirements 46 -> 42, 'done' 39). Earlier 'missing -> missing 3/3' results rested on the changed labels and
must not be quoted. 'Missing' is now only exercised by fault injection (labels known by construction) and by the 3
`missing` labels in the 4-PR large set, which the owner has NOT reviewed (bench/gold/gold_large_draft.json).
