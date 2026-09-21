# spec — porting plan + decision records

The ratified target-spec table lives in the top-level
[`README.md`](../README.md#target-specification-ratified--dr-0002); this
directory holds the plan behind it and the records that ratified it:

```
spec/
  README.md               this file
  porting-plan.md          what transfers from the nearest siblings (testbench
                            methodology) versus what is designed fresh from the
                            literature and SG13G2's own PDK models (topology),
                            and why
  decision-records/
    0001-comparator-topology.md
                          the topology call: single-tail StrongARM latch, no
                            continuous-time preamp (issue #10). Ratifies no
                            README row on its own.
    0002-target-spec-ratification.md
                          sets every row of README.md's target-spec table,
                            changes one (Kickback), and closes two scope
                            questions -- on the measured, provenance:schematic
                            records taken against DR-0001's design (issue #12)
```

## Decision-record process

Per `CLAUDE.md`, **spec changes go through `spec/` with a decision record —
agents do not relax the ratified spec to make results pass.** A decision
record (DR) is required whenever the target-spec table in the top-level
README is:

- **set** — the table's bounds are ratified for the first time (done once, by
  [`decision-records/0002-target-spec-ratification.md`](decision-records/0002-target-spec-ratification.md)),
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
append-only convention [`sim/README.md`](../sim/README.md) uses for evidence.

Ratification flows through the standard two-key mechanism (EE key + market
key, both installed by the standard tooling); scope-only spec DRs ratified
with both keys need no per-PR operator statement. Per
[2AMLogic/2am#372](https://github.com/2AMLogic/2am/issues/372), **neither key
may be held by the record's author**, the merge commit of the ratifying PR
*is* the ratification act, and a relax-after-measured-FAIL proposal requires
the market key's explicit competitiveness finding or escalates to the
operator. DR-0002 is the worked example of all three.

**Status: the table is ratified.** DR-0002 set every row against measured
`provenance: schematic` evidence; see
[`porting-plan.md`](porting-plan.md) for the engineering judgment the DRAFT
bounds started from, and
[gap-to-T1 tracker issue #3](https://github.com/2AMLogic/sg13g2-comparator/issues/3)
for the state of everything downstream. Item 5 there (full PVT corner
simulation vs. a *ratified* spec) is no longer structurally blocked — the
table it must be scored against now exists — but item 5 itself is separate
work that DR-0002 does not perform. Ratified is not met: DR-0002 records
three rows that the current design misses, deliberately unrelaxed.

## Review-bar note

One-command characterization plus README reproducibility is a standing bar
for this block — it applies from the first testbench onward, not only once
the design is "done." See
[issue #3](https://github.com/2AMLogic/sg13g2-comparator/issues/3) for how
this bar is tracked alongside the artifact-presence checklist.
