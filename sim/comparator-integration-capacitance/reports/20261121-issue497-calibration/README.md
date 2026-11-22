# Issue #497 Phase 1 calibration: candidate density at the integration nodes

**Characterization, not compliance.** Four-point batch run of the Phase 1
loop-broken front-end method ([issue #477](https://github.com/2AMLogic/sg13g2-comparator/issues/477),
[Phase 1 report](../../../comparator-preamp-noise/reports/20261120-issue477/pvt-batch.md))
with the study's added capacitance mapped onto the reduced sub-model, plus a
mechanism control proving the parameter applies. Fleet run 2026-11-21,
runner klt 0.9.x / ngspice 47, OSDI preloaded from the runner image, 4 jobs
(`--batch-set --wait-for-capacity 600`), 16 of 16 cells `pass`, then a
two-row mechanism control.

## The mapping

The loop-broken `comparator_dut_analog` sub-model carries the same
integration nodes under model names: `np` (XM1 drain, vinp side) is `aon`
(XM1A drain, vinp side), and `nn` ↔ `aop`.
[`front-end-cadd.spice`](front-end-cadd.spice) is the Phase 1
characterization circuit with a `c_add` parameter and one matched
capacitor pair per subckt at those nodes, each capacitor node-to-`vss` —
the same declaration the candidate netlists carry
([`candidates/`](../../candidates/)). The request
([`calibration.request.json`](calibration.request.json)) zips four
parameter rows — control (`c_add = 0`), `cadd1f`, `cadd2f`, `cadd4f` — every
row at the archived `ib10_sw20lat6` geometry (8 µm/0.34 µm pair, 20 µm
switch, 6 µm latch) and 10 µA bias, at `tt_27c_1.20v`, `sf_-40c_1.32v`,
`ff_125c_1.08v`, `fs_-40c_1.20v`.

## Result: the density and the gain are unchanged

`white_out` is the differential output density at 1 MHz (the Phase 1
calibration index), `|Av(1 Hz)|` the absolute gain; `S = white_out /
|Av(1 Hz)|` is the input-referred white density. Row 0 reproduces Phase 1's
measured `ib10_sw20lat6` densities to the printed digits — the measurement
convention is unchanged.

| PVT point | control: white_out / gain / S | same for cadd1f, cadd2f, cadd4f |
|---|---|---|
| `tt_27c_1.20v` | 39.90 nV/√Hz / 1.0849 / **36.78 nV/√Hz** | identical to 10 significant digits |
| `sf_-40c_1.32v` | 34.44 nV/√Hz / 1.1594 / **29.72 nV/√Hz** | identical |
| `ff_125c_1.08v` | 44.62 nV/√Hz / 0.9780 / **45.61 nV/√Hz** | identical |
| `fs_-40c_1.20v` | 35.13 nV/√Hz / 1.1514 / **30.52 nV/√Hz** | identical |

**Adding 1–4 fF at the integration nodes changes neither the white density
at 1 MHz nor the DC gain**: the 1 MHz calibration index sits deep in the
flat band below the node pole (~2 GHz for the ~15 fF node), so the
capacitance is invisible there and at 1 Hz by construction. The
candidate-own-density projection for every setting is therefore the
control's own density — the screen's small noise reduction (see the
[study report](../20261121-issue497.md)) is a pure decision-bandwidth effect
at effectively fixed injected AND own density.

## Mechanism control (parameter application)

Because four identical-looking rows could also mean an ignored parameter,
`mechanism-control/` holds a two-row probe at TT: `c_add = 0` vs `4 nF` —
an absurd capacitance chosen so the 1 MHz density MUST move if `alterparam`
applies `c_add` inside the subckt capacitors. Observed: `white_out`
39.90152 nV/√Hz (0 F) vs 0.79959 nV/√Hz (4 nF), a 49.9× reduction matching
the capacitance ratio, with `gain_dc` unchanged (1.084931 both rows). The
fF-scale rows above are therefore a real null, not a mechanism failure.

## Reproduce

From this directory on a worker with batch-submission credentials and
artifact-broker access (the netlist path is resolved to this directory;
the committed `front-end-cadd.spice` includes the preamp testbench by its
repo-relative path):

```bash
study_dir=$PWD
run_dir=$(mktemp -d)
while read -r process temp supply; do
  python3 - "$process" "$temp" "$supply" "$study_dir" "$run_dir" <<'PY'
import json, sys
process, temp, supply, study_dir, run_dir = sys.argv[1:6]
req = json.load(open(f"{study_dir}/calibration.request.json"))
req["netlist"] = f"{study_dir}/front-end-cadd.spice"
req["corners"]["process"] = [process]
req["corners"]["temperature_c"] = [float(temp)]
req["corners"]["supply_v"]["vsup"] = [float(supply)]
open(f"{run_dir}/{process}.json", "w").write(json.dumps(req, indent=2) + "\n")
PY
done <<'PVT'
mos_tt 27 1.20
mos_sf -40 1.32
mos_ff 125 1.08
mos_fs -40 1.20
PVT
klt sim --batch-set "$run_dir"/mos_*.json --wait-for-capacity 600 \
  --format json -o "$run_dir/artifacts" > "$run_dir/results.json"
```

(The first submission attempt of this run was refused by the batch backend
because the circuit's original `../../testbench/...` include did not resolve
from this directory; the committed circuit carries the corrected
repo-relative path. `batch/` below holds the succeeded attempt.)

## Stored evidence

The bytes of this run are in the fleet artifact store, not in git (issue #318). Manifest: `manifests/artifacts/comparator-integration-capacitance-20261121-issue497-calibration.manifest.json`. Paths above are the manifest `name`s. Fetch one, hash-verified, with:

```
klt artifact get manifests/artifacts/comparator-integration-capacitance-20261121-issue497-calibration.manifest.json#<name> -o <out>
python3 scripts/check_artifact_manifests.py verify manifests/artifacts/comparator-integration-capacitance-20261121-issue497-calibration.manifest.json
```
