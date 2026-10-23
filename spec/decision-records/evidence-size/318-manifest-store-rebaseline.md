# Evidence goes to the artifact store; size ceiling restored and re-baselined — issue #318

- **Status**: implements 2AMLogic/2am#5562 (consumer 1 of the fleet artifact
  store, epic 2AMLogic/2am#5553) and records operator decision 1.1
  (2026-10-22): **evidence bytes are private, manifests are public.**
- **Supersedes**: the suspension in
  [`312-suspend-evidence-size-ceiling.md`](312-suspend-evidence-size-ceiling.md)
  and the cumulative exceptions of DR-0005 and DR-0032. Those records stay as
  history; nothing in them is edited.
- **Scope**: `sim/evidence-size-budget.json`, `sim/harness/evidence_store.py`,
  `sim/run_corners.py` (via `sim/harness/cli.py`), `sim/run_store_evidence.py`,
  `scripts/check_artifact_manifests.py`, `manifests/artifacts/`.

## Decision

1. **New evidence is stored, not committed.** A corner-runner record or a
   campaign writes its bytes through `klt artifact put` (klayout-tools
   PR #4066, `docs/cli/artifact.md`). Git keeps one manifest per run,
   `manifests/artifacts/<bench>-<run-id>.manifest.json` (entries carry
   `sha256`, `size`, `kind=evidence`, `producer`, `uri`, and the logical
   `name` under `sim/`), plus the run's Markdown summary under `sim/<bench>/`.
2. **Fail closed.** If the broker is not configured, unreachable or refuses,
   or a put fails, the writer exits 10 and commits nothing. There is no
   fallback that commits the bytes. The corner runner checks the store before
   it simulates.
3. **Bytes private, manifests public** (operator decision 1.1). A manifest is
   safe to commit in this public repo; only callers the broker admits can
   resolve its `uri`s. The broker URL and bucket come from the environment
   (`KLT_ARTIFACT_BROKER`, `KLT_ARTIFACT_BUCKET`); this repo configures neither.
4. **The ceiling is restored, re-baselined at `main`.** The `suspended` block is
   removed. The baseline moves to `4c0db1c86b9318a5f4af922f6750d8d7e3441adb`
   (115,641 blobs / 587,974,295 B repo; 114,687 blobs / 567,379,629 B under
   `sim/`). Every existing evidence unit is grandfathered at its size there.
   The policy is unchanged (10% of baseline `sim/` bytes rounded up to the
   next MiB): ceil(10% x 567,379,629 B / 1 MiB) = 55 MiB = 57,671,680 B, so
   the total ceiling is 625,051,309 B and a new unit is capped at 57,671,680 B.
5. **`exceptions` cleared.** The re-baseline absorbs every byte the old
   exceptions authorized, so the list is empty. New growth is manifests,
   summaries and source code, which needs no per-PR exception (the #276
   failure mode). An overage still takes the decision-record route in
   `sim/README.md`.

## Why now, before the broker is deployed

The 312 record restores the ceiling "when the store is live and evidence is
committed as manifests and summaries". The client and the writer land here,
and the writer refuses to commit bytes without the store. So once this merges
there is no sanctioned path for a new blob into `sim/`, and an enforced
ceiling is what makes a hand-committed blob visible. A run that cannot reach
the store simply cannot mint evidence until the broker (2AMLogic/2am#5560) is
deployed. That is the intended fail-closed behaviour, not a regression.

## What does not change

- The append-only guard (`scripts/check_append_only_evidence.py`). No existing
  evidence path is deleted, moved or altered by this change, and history is
  not rewritten. The old blobs stay in the working tree and in history.
- The measurement (`git ls-tree -rl` blob bytes) and its fail-closed rules.

## Machine-checked

`scripts/check_evidence_size.py --tree HEAD` validates the derivation above.
`scripts/check_artifact_manifests.py check --tree HEAD` (CI,
`append-only-evidence` job) validates every committed manifest and fails if a
stored object's bytes are also committed. `verify` re-hashes the stored bytes
through the broker. It needs the broker, so it is an out-of-band step until
the broker is deployed.
