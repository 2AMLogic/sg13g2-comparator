# 0023: Evidence-size exception for PEX delta-table decision-state validity (issue #240)

- **Status**: proposed. **This record covers the evidence budget only.** It
  ratifies no bound and relaxes no Target or Stretch number. It authorizes one
  raise of the `sim/` total ceiling in `sim/evidence-size-budget.json` (issue
  #132's contract), exactly the measured overage of 11239 B. It takes effect
  with the reviewed merge of the PR that lands it, as for DR-0005 to DR-0022.
  The drafting agent does not merge it.
- **Date**: 2026-10-12
- **Decided by**: Doctor agent, PR #241 for issue #240 (after Judge review).
  The operator reviews the raise as a governance item at merge.
- **Related**:
  [`0022-noise-full-provenance-evidence-size-exception.md`](0022-noise-full-provenance-evidence-size-exception.md)
  (previous `sim/` total raise; still stands),
  [`0018-pex-delta-table-evidence-size-exception-2.md`](0018-pex-delta-table-evidence-size-exception-2.md),
  [`0009-pex-delta-table-evidence-size-exception.md`](0009-pex-delta-table-evidence-size-exception.md)
- **Supersedes**: none. **Superseded by**: [`evidence-size/323-retire-incremental-evidence-size-raises.md`](evidence-size/323-retire-incremental-evidence-size-raises.md) (the authorization below no longer applies)

## Context

Issue #240 makes the PEX delta-table renderer require matching valid decision
states (`regeneration.d*_first` / `d*_end` at the same canonical corner) before
an in-bound `td_a` / `td_c` can count toward "met at every PVT grid point".
After DR-0022 `sim/` was exactly at its ceiling, so any addition needs this
exception. The growth is code, tests and docs, not evidence; no existing
evidence file is modified and no report is regenerated:

| Path | Nature | Bytes |
|---|---|---|
| `sim/comparator-pex/make_delta_table.py` | decision-state join and summary | +3851 |
| `sim/comparator-pex/tests/test_delta_table.py` | `DecisionValidity` tests, fixture states | +6446 |
| `sim/comparator-pex/README.md` | decision-validity note | +857 |
| `sim/evidence-size-budget.json` | extended cumulative entry | +85 |

The total is the measured overage, 11154 + 85 = 11239 B. This record lives
under `spec/` and adds nothing to `sim/`.

## Decision

Raise the `sim/` total ceiling by exactly **11239 B**. The single `sim` entry
carries the cumulative 28169548 + 11239 = **28180787 B** and cites this
record. No ratified spec bound is relaxed or changed.

## Authorizations

```json
{"kind": "evidence-size", "path": "sim", "additional_bytes": 28180787}
```

(Cumulative: 28169548 B from DR-0005 to DR-0022 and 11239 B authorized here.)

## Consequences

- `python3 scripts/check_evidence_size.py --tree HEAD` passes with this entry
  and fails without it.
- Exact raise, not a standing allowance.
