# 0025: Evidence-size exception for CM-offset draw validation (issue #250)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 30220 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0023.
  The drafting agent does not merge it.
- **Date**: 2026-10-12
- **Decided by**: Builder agent for issue #250. The operator reviews the
  raise as a governance item at merge.
- **Related**:
  [`0023-pex-decision-validity-evidence-size-exception.md`](0023-pex-decision-validity-evidence-size-exception.md)
  (previous `sim/` total raise; still stands),
  [`0021-cm-decision-validation-evidence-size-exception.md`](0021-cm-decision-validation-evidence-size-exception.md),
  [`0011-cm-band-runner-tests-evidence-size-exception.md`](0011-cm-band-runner-tests-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)
- **Numbering**: DR-0024 is in use by open, unmerged PRs (#249, #243). If one
  of them merges first, the cumulative `sim` entry is re-measured on rebase.
  This record's own 30220 B does not change.

## Context

Issue #250 makes the whole-latch common-mode offset characterization
(`sim/kltsim/cmband.py`) validate its draw evidence before it reduces or pairs
anything:

- Offsets and the common-mode probe must be finite numbers in a compatible
  unit.
- Draw identities (`sample_index`, `seed`) must be unique nonnegative
  integers.
- Pairing needs two complete trusted populations.
- Reproduction reports a complete-reproduction verdict.

On main, `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code, tests and docs, not evidence. No existing
evidence file is modified and no report is regenerated:

| Path | Nature | Bytes |
|---|---|---|
| `sim/kltsim/cmband.py` | numeric/unit normalization, identity checks, pairing and reproduction verdict | +14273 |
| `sim/kltsim/tests/test_cmband.py` | `NumericEvidence`, `DrawIdentity`, `Pairing`, `Reproduction` tests | +14729 |
| `sim/comparator-offset-cm-band/README.md` | validation note | +945 |
| `sim/run_offset_cm_band.py` | strict JSON for `compare` | +152 |
| `sim/evidence-size-budget.json` | extended cumulative entry | +121 |

The total is the measured overage, 30099 + 121 = 30220 B. This record lives
under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **30220 B**. The single `sim` entry
carries the cumulative 28180787 + 30220 = **28211007 B** and cites this
record. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28211007}
```

(Cumulative: 28180787 B from DR-0005 to DR-0023 and 30220 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.
