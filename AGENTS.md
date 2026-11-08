## Evidence size check

Before requesting review, run `python3 scripts/check_evidence_size.py --tree HEAD`
on the final committed candidate (exit 0 = within budget, 1 = violation or
invalid budget, 2 = measurement error) and put the tested SHA, exit status and
measured size in the PR. Any HEAD change (amend, rebase, new commit) needs a
fresh run. A failure goes to the decision-record/authorization policy in
`sim/README.md` "Evidence size budget"; it grants no exception. If Python is
unavailable, say local validation is unavailable and cite the successful
`append-only-evidence` CI result for that exact commit; a skipped check is
never success.

<!-- BEGIN LOOM ORCHESTRATION (AGENTS) -->
This repository uses [Loom](https://github.com/rjwalters/loom) for AI-powered development orchestration (dual-runtime: Claude Code reads `CLAUDE.md`; OpenAI Codex CLI and other AGENTS.md-aware runtimes read this file). See the Loom repository for the full guide (roles, labels, worktrees, configuration). When installed, Loom also writes a locally-substituted copy of the runtime-neutral guide to `.loom/AGENTS.md`.
<!-- END LOOM ORCHESTRATION (AGENTS) -->
