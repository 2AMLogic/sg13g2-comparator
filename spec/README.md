# spec — porting plan + decision records

The ratified target-spec table (once ratified) will live in the top-level
[`README.md`](../README.md#target-specification-draft--engineering-to-ratify).
Until then, this directory holds:

```
spec/
  README.md               this file
  porting-plan.md          what transfers from the nearest siblings (testbench
                            methodology) versus what is designed fresh from the
                            literature and SG13G2's own PDK models (topology),
                            and why
  decision-records/
    (not populated yet — see below)
```

## Decision-record process

Per `CLAUDE.md`, **spec changes go through `spec/` with a decision record —
agents do not relax the ratified spec to make results pass.** A decision
record (DR) is required whenever the target-spec table in the top-level
README is:

- **set** — the DRAFT table's bounds are ratified for the first time,
- **changed** — an existing ratified row's numbers move, or
- **scoped** — a row's applicability changes (e.g. the 3.3 V HV I/O flavor is
  scoped in or out; see the Supply/power row's "scoped in only if a future
  decision record ratifies it" note).

Each decision is recorded as one file under `spec/decision-records/`,
numbered sequentially (mirroring
[`sg13g2-bandgap/spec/decision-records/`](https://github.com/2AMLogic/sg13g2-bandgap/tree/main/spec/decision-records)'s
`NNNN-<slug>.md` convention: e.g. `0001-bipolar-device-selection.md`,
`0002-supply-voltage-scope.md` in that repo). A record is never deleted or
rewritten once ratified — a later change supersedes it with a new,
higher-numbered record rather than editing history in place, the same
append-only convention `sim/README.md` will use for evidence once `sim/`
exists.

Ratification flows through the standard two-key mechanism (EE key + market
key, both installed by the standard tooling); scope-only spec DRs ratified
with both keys need no per-PR operator statement.

**This pass does not populate `spec/decision-records/`.** The target-spec
table in the top-level README stays **DRAFT / unratified** — see
[`porting-plan.md`](porting-plan.md) for the engineering judgment behind each
row's current bound, and
[gap-to-T1 tracker issue #3](https://github.com/2AMLogic/sg13g2-comparator/issues/3)
for the honest, unchecked state of everything downstream of ratification
(item 5, full PVT corner simulation vs. a *ratified* spec, is blocked on
this table being set).

## Review-bar note

One-command characterization plus README reproducibility is a standing bar
for this block — it applies from the first testbench onward, not only once
the design is "done." See
[issue #3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) for how
this bar is tracked alongside the artifact-presence checklist.
