# scripts/diagnostics

On-demand diagnostics. Nothing here is wired into CI, hooks, or the
circuit-evidence checks.

## `guard_index_scope.sh` — alternate-index wrapper reproduction

Handoff package for issue
[#188](https://github.com/2AMLogic/sg13g2-comparator/issues/188). It shows how
the destructive-command guard decides on `git read-tree` when a literal scratch
`GIT_INDEX_FILE=` assignment is inherited by an `sh -c` / `bash -c` wrapper.
An upstream maintainer can rerun the exact inputs and tell a guard *decision*
apart from a process *exit code*. The submitted Git commands are never run.

### Invocation

```bash
# Installed (vendored) guard only. A clean checkout of this repo is enough.
scripts/diagnostics/guard_index_scope.sh

# Also print permissionDecisionReason for ask/deny rows
scripts/diagnostics/guard_index_scope.sh --reasons

# Optional: compare against a local checkout of the canonical guard
scripts/diagnostics/guard_index_scope.sh \
    --canonical /path/to/rjwalters-repo/hooks/repo/guard-destructive.sh

# Observe a different guard file instead of the installed one (rows labelled "override")
scripts/diagnostics/guard_index_scope.sh --guard /path/to/guard.sh
```

Dependencies are `bash`, `jq`, and coreutils (`mktemp`, `sha256sum`,
`timeout`). `git` is used only to read the index path, `HEAD`, and status for
the fingerprint. The script does not use Python, a simulator, or the network.

How decisions are read. The script is strict on purpose, because the guard
itself turns its own internal errors into an empty-stdout allow:

| Guard process result | Reported decision |
|---|---|
| exit 0, zero-byte stdout | `allow` (defers to the normal permission flow) |
| exit 0, a single JSON object with `.hookSpecificOutput.permissionDecision` of `ask` / `deny` | that value. `ask` and `deny` stay separate. |
| exit 0, a single JSON object with `permissionDecision` `allow` | `allow-json`. An explicit allow bypasses the permission prompt, so it is a different outcome from empty stdout and is never shown as plain `allow`. |
| the `jq` serialization of the payload failed, or the payload did not round-trip the command string (the guard is not run; the exit column shows `-`) | `ERROR` |
| nonzero exit, a timeout (60 s), whitespace-only or invalid JSON, more than one object, or a missing or unknown decision | `ERROR`, never `allow` |
| the guard's own internal-error log (`<guard dir>/../logs/hook-errors.log`) grew during the case, whatever the decision looked like | `ERROR` |

The payload is written to a scratch file first and checked (jq exit 0,
non-empty, `.tool_input.command` equal to the input) before the guard reads
it. Without that check a failed `jq` would hand the guard empty stdin, which
it answers with an empty-stdout allow. The internal-error log is only
inspected by size. A missing log is fine. Because that log is shared with any
live hook invocations of the same guard copy, unrelated concurrent growth
can cause a spurious `ERROR`. That fails closed, so rerun if it happens.

Exit status: `0` means every case gave a valid observation. `1` means at least
one `ERROR`, or the Git index or worktree-status fingerprint changed during
the run. `2` means a usage error, `jq` is missing, or a guard path is
missing or unreadable. For example:
`guard_index_scope.sh: error: installed guard not found: /nonexistent/guard.sh`.

### The eight fixed inputs

| Case | Command string (data only) | What it checks |
|---|---|---|
| `sh-wrapper` | `GIT_INDEX_FILE=/tmp/doc176/idx sh -c 'git read-tree HEAD && git add -A sim && git write-tree'` | the exact reported wrapper |
| `bash-wrapper` | same with `bash -c` | equivalent interpreter |
| `direct-scratch` | `GIT_INDEX_FILE=/tmp/doc176/idx git read-tree HEAD` | direct literal scratch-index control |
| `bare-read-tree` | `git read-tree HEAD` | unisolated, must stay restrictive |
| `assign-other-cmd` | `GIT_INDEX_FILE=/tmp/doc176/idx git status && git read-tree HEAD` | assignment scoped to a different command |
| `live-index` | `GIT_INDEX_FILE=.git/index sh -c 'git read-tree HEAD'` | assignment names the live index |
| `unresolved-var` | `GIT_INDEX_FILE=$INDEX_PATH sh -c 'git read-tree HEAD'` | unresolved expansion (literal `$INDEX_PATH`) |
| `unisolated-after` | `GIT_INDEX_FILE=/tmp/doc176/idx sh -c 'git read-tree HEAD' && git read-tree HEAD` | unisolated command after a wrapper |

### Observed matrix — 2026-10-11

Command: `scripts/diagnostics/guard_index_scope.sh --canonical /home/ubuntu/GitHub/repo/hooks/repo/guard-destructive.sh`.
The run started at 2026-10-11T08:16:16Z (re-recorded after the strict-parsing
fixes; identical to the 08:10:32Z run) on a Loom AWS dispatch worker with
GNU bash 5.2.21 and jq-1.7. Every invocation of both guards exited `0`, so
only the decision field tells the cases apart.

| Case | Installed guard | Canonical local snapshot |
|---|---|---|
| `sh-wrapper` | `deny` | `ask` |
| `bash-wrapper` | `deny` | `ask` |
| `direct-scratch` | `allow` (empty stdout) | `allow` (empty stdout) |
| `bare-read-tree` | `deny` | `ask` |
| `assign-other-cmd` | `deny` | `ask` |
| `live-index` | `deny` | `ask` |
| `unresolved-var` | `deny` | `ask` |
| `unisolated-after` | `deny` | `ask` |

The installed column matches the eight-case curation recheck recorded in
#188. A later run with different results is something to investigate and
write down here, with a new date. It is not a reason to change either guard.

**Measured downstream `deny` vs canonical `ask`.** The vendored guard in this
repo blocks the wrapper outright (`deny`). The canonical guard asks for
confirmation (`ask`). So the upstream symptom is an unnecessary confirmation
prompt, while this consumer gets a hard block. Both guards allow the direct
literal scratch-index form. Two canonical snapshots have now been measured,
and both gave `ask`:

- `0d090dc36c2b9798ac42a4540183580a260c175e`, from the first curation pass
  of #188
- `0e093c16742b33631e1deff8d4b105d436a64781`, from the run above

Both are local checkouts. Neither is a claim about the current remote
`rjwalters/repo` main. Any fix should keep each guard's existing unsafe-command
policy (`deny` downstream, `ask` canonical) for the negative controls.

### Provenance

- Installed guard: `.loom/hooks/guard-destructive-generic.sh`
  - git blob `9c94d9e53d4dbf042a5a5fb414bb6fec154e46fc`
  - sha256 `64d4f0956cb15e03d7b9fcb582d0081dac9a218bb1d237c9844e37048fe88acb`
  - Identical at `origin/main` `ce8cb9370ba146541236a0e147c1bed82c0890a5`
    and at the branch base `161e83a1c5a4b7c468a32e7ca0528186a300b529`.
    Last changed in `58ba0077307c7b459682b1730fbb658a12481b02` (2026-10-10).
- Canonical local snapshot: `rjwalters/repo` checkout at
  `0e093c16742b33631e1deff8d4b105d436a64781` (2026-10-10), file
  `hooks/repo/guard-destructive.sh`
  - git blob `a87e18ecb9295e4625ac2d39ebe3ee85ee74dabb`
  - sha256 `feaa3f50c550826e9844476010e67ae7a9d55784443fcc6c71a17736b852dc08`
  - The checkout's `git status --porcelain --ignored` was the same before and
    after the run.
- The script prints the repo `HEAD` and the sha256 of each guard in its
  header, so every future run records its own provenance.
- Original telemetry: the guard-decision log entry at 2026-10-10T23:39:07Z in
  the issue-82 worktree (see #188).

### Safety properties

- **Payloads stay data.** Each command string is a single-quoted Bash literal.
  It is serialized only by `jq -n --arg cmd …` into
  `{hook_event_name:"PreToolUse", tool_name:"Bash", tool_input:{command}, cwd}`
  and piped to `bash <guard>`. The script has no `eval`, `source`, or
  `sh -c "$cmd"`. A capture stub confirmed the guard receives the eight
  strings byte-for-byte, including the unexpanded `$INDEX_PATH`. `/tmp/doc176`
  is never created.
- **The real index is checked.** Before and after the cases, the script hashes
  the file at `git rev-parse --git-path index` and
  `git status --porcelain=v1 --untracked-files=all`. Any difference is a
  diagnostic error. For the run above, the index sha256 was the same before
  and after, and `git status` was unchanged.
- **Telemetry goes outside the checkout.** `LOOM_GUARD_DECISION_LOG_FILE`
  points into a fresh `mktemp -d` directory under `$TMPDIR` (default `/tmp`).
  The script refuses to run if that directory resolves inside the checkout.
  The directory is removed on exit, and it is the only thing the script
  deletes. One caveat: the guard's own internal-error log
  (`hook-errors.log`, written next to the guard under the gitignored
  `.loom/logs/`) has no override variable. If the guard hits an internal
  error, it still writes there. The script only reads that file's size, and
  reports growth as `ERROR`.
- **Strict parsing.** Only a successful, zero-byte stdout counts as `allow`.
  Disposable stubs that were not committed confirmed this. Each row is all
  eight cases:

  | Stub output | Reported decision | Exit status |
  |---|---|---|
  | empty stdout | `allow` | 0 |
  | JSON `ask` | `ask` | 0 |
  | JSON `deny` | `deny` | 0 |
  | JSON `allow` | `allow-json` | 0 |
  | malformed text | `ERROR` | 1 |
  | whitespace only | `ERROR` | 1 |
  | two JSON objects | `ERROR` | 1 |
  | unknown decision | `ERROR` | 1 |
  | exit 3 | `ERROR` | 1 |
  | exit 0, empty stdout, appends to `../logs/hook-errors.log` | `ERROR` | 1 |
  | installed guard, `jq` wrapper on `PATH` failing for `-n` | `ERROR` (exit `-`) | 1 |

  A missing guard or missing `jq` exits `2` with a clear message.

### Upstream handoff

Canonical venue: [rjwalters/repo](https://github.com/rjwalters/repo).

- Implementation: `hooks/repo/guard-destructive.sh`
- Regression suite: `hooks/repo/tests/test-guard-destructive.sh`, in its
  existing `read-tree` group

The installed file in this repository is a vendored copy. Do not patch it
here. The expected sequence for a future fix:

1. **Upstream fix.** A separately approved change to the canonical guard and
   its tests, in one change. It would carry proven, literal scratch-index
   assignment scope into literal `sh -c` / `bash -c` payloads. These must keep
   their current restrictive decision:
   - `bare-read-tree`
   - `assign-other-cmd`
   - `live-index`
   - `unresolved-var`
   - `unisolated-after`
   - path aliases that cannot be resolved

   The tests feed command text and must never run the payloads.
2. **Loom vendoring.** Loom re-vendors the released canonical guard into
   `.loom/hooks/guard-destructive-generic.sh` through its normal release and
   resync. Nobody edits that file by hand.
3. **Consumer verification.** After the resync lands here, rerun this
   diagnostic. Record a new dated matrix with the new guard sha256, and expect
   the wrapper rows to move while every negative control stays restrictive.

**Status: not yet established.** This local deliverable does not establish an
approved upstream issue, fix, or release. Nothing was filed upstream, and no
upstream checkout was modified. Guard behavior, hook settings, vendoring
configuration, CI, and circuit evidence are unchanged by this package. Closing
#188 means only that this reproduction package exists and can be rerun.
