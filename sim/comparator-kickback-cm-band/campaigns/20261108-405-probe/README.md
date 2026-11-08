# Row 4b band-edge probe — series `20261108-405-probe` (issue #405)

**Supplementary characterization; no spec, window or DR-0004 change, no edit to
`20261011-165`, no sigma, no pass for the Row 4b cell.** The probe is never
merged into the #165 44/45 populations. Generated tables: `comparison.md` /
`comparison.json` (`python3 sim/run_kickback_cm_band.py probe-compare --series 20261108-405-probe`).

## What ran

Exactly the two #165 rejects (`vcm-m050` ss/1.200V/-40C, `vcm-p050` ss/1.080V/-40C)
and the `vcm-nom` control at both PVT points, as `klt sim` requests submitted with
`--backend batch` and `batch.capacity_wait_s = 600`, client `klt 0.9.0` (the fleet
runner is 0.9.0; the #165 pin 0.5.0 / CI 0.8.0 is refused by it, see below). Body is
byte-identical to the #165 body of the same condition (checked at build). Four arms,
each its own request per condition:

| arm | change vs #165 | purpose |
|---|---|---|
| `repro` | none (same cards, `tran 5p 60n`) | reproduction gate |
| `obs` | + both outputs of B/C at 30…55 ns, input differential at 1 ns and at the 30 ns strobe | tell wrong polarity / never decided / late |
| `xing` | `obs` + first decision-threshold crossing after 30 ns | decision timing |
| `step20p` | `obs` cards, `tran 5p 60n 0 20p` | max-step sensitivity (as #89) |

Fleet jobs (`environment.remote.job_id`; all PVT `ss`, -40 C, supply per row):
see the table in `comparison.md`. `state: failed` on an edge row is the fleet's
reflection of the failed decision gate, not a runner failure (envelopes exist, exit 3).

## Results

- **Reproduction gate: PASS.** `repro` equals the #165 envelope on every original
  card at all four points (bit-for-bit): `dout_float_big_end` = 6.81045e-09
  (m050), `dout_float_small_end` = 6.17971e-09 (p050); `obs` equals it too, so the
  extra cards do not perturb the solution.
- At both edge points the latch outputs are **rail-to-rail and constant from 30 ns
  to 55 ns** in every arm (no late or partial decision), and on the failing branch they hold
  the **wrong polarity** (m050 branch C: dp = 0 V, dn = 1.2 V; p050 branch B:
  dp = 0 V, dn = 1.08 V) while the other branch happens to hold the right one.
- The **floating-input differential is not what the bench programs**: at 1 ns and
  at the strobe, m050 reads B = 23.5 µV, C = 2.35 mV and p050 reads B = 16.9 µV, C = 1.69 mV,
  versus the programmed 1 mV / 100 mV and the control's 0.9996 mV / 99.96 mV (ss 1.08 V)
  and 0.9993 mV / 99.93 mV (ss 1.2 V). It is ~42x/59x low, at exactly the two rejected points.
- Both rejected points carry a DC-operating-point warning, `Dynamic gmin stepping
  failed` (diagnostic `nonconvergence`); the control corners have none.
- `xing`: the post-strobe crossing cards return no value (`out of interval`) at the
  two edge points, i.e. there is **no output transition after the strobe** there
  (the control at ss/1.08 V also has none, because its held state was already
  correct; at ss/1.2 V it transitions at the strobe).
- `step20p` changes nothing in kind: same wrong-polarity held outputs, gate values
  still ~1e-9 (m050 2.94e-09, p050 1.16e-08); the control passes.

## Conclusion (bench vs latch)

**The evidence favours a bench artifact (DC operating point / initial state of the
1 GOhm / 1 pF floating network and the SR output state), not a slow or marginal
decision; the latch's own marginality is not excluded and the root cause of the
non-convergence is still open.** At the two rejects the DC solve does not converge
cleanly (gmin stepping fails), the floating inputs start with a differential 40-60x
smaller than programmed, and the outputs show no post-strobe transition: the observed
polarity is the held state, not a decision on the programmed input. A tighter max step
does not move this, so it is not a step-control effect. No arm forced a converged DC
point (`.nodeset`/`.ic`, gmin/itl options) because that needs a body change; that is
the discriminating follow-up, and fixing the bench is out of scope here. Until then the
two cells stay rejected, as in #165.

### Shared with the #89 cold offset aborts?

**Not shown, and the evidence argues against a shared failure signature.** #89
(`sim/comparator-offset-cm-band/campaigns/20261105-58805e2fa-maxstep20p-r2.md`) was a
transient abort (`Timestep too small`, node `ibn`) in individual `mos_tt_mismatch` /
`mos_sf_mismatch` Monte-Carlo draws at -40 C, cured by max step 20p. Here the
process is `ss`, there is no Monte Carlo, the run completes (a DC `gmin` warning, no abort), and
the same 20p step does not cure it. Both are -40 C convergence phenomena and may share
a cold bias-network root, but this probe does not establish that.

## Notes on the run

- First submit of `vcm-m050/repro` used klt 0.8.0 and was refused by the 0.9.0
  runner before any simulation (`batch_runner_version_mismatch`, job
  klt-sim-c1a11620744d, nothing measured); kept as `*.unrun-klt-sim-c1a11620744d.json`.
- One `vcm-p050/step20p` submit was interrupted client-side by a shell timeout before an envelope
  was collected; it was resubmitted (job klt-sim-9b09469c51c2). The orphaned fleet job has no envelope here.
- The `xing` arm's envelope status is `error` where its crossing cards found no crossing;
  every other card in those corners is valid and is what `comparison.md` uses.
