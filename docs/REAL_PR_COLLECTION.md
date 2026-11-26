# Real-PR collection (the missing "missing" cases)

Goal: 10-15 PRs where the ask is a REAL prompt or issue and the outcome was not chosen by us, so that real partial/missing
cases exist. The current gold set has none, which is its biggest hole.

## Where to get them (own work first, then public)
1. Your own repos: any PR or branch made by Claude Code or Codex. Use the exact prompt as the ask (save it as `asks/<repo>-<n>.txt`).
2. Public PRs made by coding agents (Copilot coding agent, Codex, Claude Code), permissive license only, issue text as the ask.
3. Do NOT pick PRs because the tool does well on them. Take them in the order you find them and keep failures.

## Protocol (write this down before running)
- Freeze the prompt text and the PR/commit range before running the tool.
- Run: `pr-audit run <PR_URL> --ask-file asks/<name>.txt --retrieval lexical --html out/<name>.html`
  or `pr-audit local asks/<name>.txt --base <sha> --head <sha> --retrieval lexical --html out/<name>.html`
- BEFORE opening the report, label each requirement yourself in `labels/<name>.csv` with columns
  `req_id,requirement,your_label(done|partial|missing|unclear),why`. Only then open the report.
- Record per requirement: tool verdict, your label, agree?, whether the cited evidence was right.
- Keep every PR in the table, including ones where the tool failed or the splitter produced junk requirements.

## Report (one table, no cherry-picking)
PRs run / PRs kept (with reasons for any dropped), requirements, agreement (tool vs you), confusion matrix, count of real
`missing`/`partial` found, count of wrong "done", requirements the splitter got wrong, tokens per audit.
Label owner: Ram. Claude may draft labels only if they are marked "Claude draft, unreviewed".

## Stop rule
If after 10 PRs the tool agrees with you on fewer than ~70% of requirements, write that in the README and fix the splitter
before adding anything else.
