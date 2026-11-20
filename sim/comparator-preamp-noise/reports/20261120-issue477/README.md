# Row 2 front-end density and decision bandwidth

**Characterization, Phase 1 of #477.** Every #92 finalist used the same
36.27 nV/√Hz injection. At that density the best grid mean, 1.096 mV for
`ib10_sw20lat6`, would need an 8.8% reduction in amplitude to reach
1.0 mV. At fixed bandwidth this corresponds to 33.09 nV/√Hz. At fixed
density it corresponds to multiplying every point's bandwidth by 0.832
(a 16.8% reduction). The reduced-model measurements across PVT are pending.

## What #92 measured

The W/L campaign has three `full_*` finalists (`w6_l034`, `w8_l020`,
`w8_l034`). The bias campaign has three more (`ib10_sw20`, `ib10_sw20lat6`,
`ib12p5_sw20`). All 30 `transient_noise.mos_*.request.json` files name
the adjacent `transient_noise.body.spice`. In all six bodies the three rung
sources `vd0`, `vd1`, `vd2` use `trnoise({vn_na} {vn_ts} 0 0)` with
`vn_na=5.735e-3` and `vn_ts=2e-11`. The one-sided low-frequency density
is `NA × √(2 TS)`. The nine W/L screens and thirteen bias screens contain
only kickback and regeneration requests. They have no Row 2 result.
[W/L requests](../../../klt-corner-verification/campaigns/20261009-issue92/) ·
[Bias requests](../../../klt-corner-verification/campaigns/20261115-issue92-bias/) ·
[Injection calibration](../../../comparator-transient-noise/README.md#calibration-a-spectral-density-not-a-band-limited-total)

The earlier injection split gives a grid mean of 1.356 mV for the front end
alone and 1.305 mV with front-end, regenerative-pair and reset sources
together. The internal-only 8× run implies 0.177 mV at 1×, about 2% of
the power. These figures come from the existing campaign.
[20261009-issue81](../../../comparator-transient-noise-full/README.md)

## Bandwidth implied by the probit slope

Each cell gives **sigma in mV rms / effective decision bandwidth in GHz**.
For injection density `S₀ = 36.27 nV/√Hz`, `B = (σ/S₀)²` in SI units.
The source is the Row 2 `monte_carlo_per_point[].sigma` field, with 80
trials per rung at each point. Bandwidth inferred this way inherits the
sampling uncertainty of the slope. The four points bracket each design's
45-point mean. SF is the committed minimum, TT is the calibration point,
FF is the maximum for both the committed and 8 µm designs, and FS is the
maximum for the 10 µA finalist.
[Implied aperture](../../../comparator-transient-noise/README.md) ·
[Committed grading](../../../klt-corner-verification/campaigns/20261009-d73a9ac/grading.json) ·
[8 µm grading](../../../klt-corner-verification/campaigns/20261009-issue92/full_w8_l034/grading.json) ·
[10 µA grading](../../../klt-corner-verification/campaigns/20261115-issue92-bias/full_ib10_sw20lat6/grading.json)

| PVT point | 12 µm committed | 8 µm baseline | `ib10_sw20lat6` |
|---|---:|---:|---:|
| `sf_-40c_1.32v` | 0.846 / 0.544 | 1.024 / 0.796 | 1.059 / 0.852 |
| `tt_27c_1.20v` | 1.361 / 1.408 | 1.107 / 0.932 | 1.157 / 1.017 |
| `ff_125c_1.08v` | 1.843 / 2.582 | 1.764 / 2.366 | 1.065 / 0.862 |
| `fs_-40c_1.20v` | 1.069 / 0.868 | 1.673 / 2.127 | 1.438 / 1.571 |
| **45-point mean sigma (mV)** | **1.289** | **1.338** | **1.096** |

The published 12 µm reduced-model record already gives the corner density
`S = white_nv_rthz / av_dc`. At the four points above, in table order, it
gives 29.02, 36.27, 47.13 and 29.53 nV/√Hz. Multiplying each corner's
density by its own `√B` gives 0.677, 1.361, 2.395 and 0.870 mV. The
same calculation over **all 45 matched points** gives a mean of **1.353 mV**
for the committed design. This assumes that the decision response scales
linearly with source amplitude. A candidate-specific nominal calibration
would instead multiply its published grid mean by `S_nominal / S₀`.
[Reduced-model record](../../records/20260916-113303-180cca7.json)

## Measuring the candidate density

The #92 override changes the full latch's device cards. Its archived bodies
still give the reduced model a 12 µm input pair. The characterization copy
applies the same W/L to XM1/XM2 and XM1A/XM2A, the same switch width to
XMSW/XMSWA, and the latch width to XM3–XM6 and their diode-connected
load counterparts XM5A/XM6A. It reuses the original differential stimulus,
reset-latch load, 10 fF routing load, and 0.6 V common mode.
[Characterization circuit](front-end.spice) · [Preamp bench](../../testbench/tb_preamp_noise.spice)

The request reproduces the calibration convention. It samples differential
output noise at 1 MHz (index 120 on a 20 point/decade sweep from 1 Hz)
and divides by `|Aᵥ(1 Hz)|`. At 1 Hz the ratio of ngspice's output and
input spectra gives that gain. The resulting density includes all device
noise at the calibration frequency.

For each device, the request reads ngspice's **device-total** output
amplitude at the same index. Divide its square by `white_out²` to obtain
its power share. Group XM1A+XM2A as input pair and XMTA+XMSWA as tail
and switch. Everything else is the remaining power, including the
diode-connected loads. XMBA and both loads are measured separately to
check power closure. Individual PSP103 generators can have duplicate
names in the ranked contributor list.
[Measurement request](nominal.request.json) · [KLT contributor issue](https://github.com/2AMLogic/klayout-tools/issues/6978)

The nominal request contains the committed design and all six measured
finalists. Its first three parameter rows select the three designs in
the table. To reproduce the bounded batch run, start in this directory
with the fleet submit profile and artifact broker configured.

```bash
study_dir=$PWD
run_dir=$(mktemp -d)
while read -r process temp supply; do
  jq --arg netlist "$study_dir/front-end.spice" --arg process "$process" \
     --argjson temp "$temp" --argjson supply "$supply" \
     '.netlist = $netlist | .corners.process = [$process] |
      .corners.temperature_c = [$temp] | .corners.supply_v.vsup = [$supply] |
      .corners.params |= with_entries(.value |= .[:3]) |
      ._comment = ["Committed 12u, w8_l034 and ib10_sw20lat6 in parameter-row order."]' \
     nominal.request.json > "$run_dir/$process.json"
done <<'PVT'
mos_tt 27 1.20
mos_sf -40 1.32
mos_ff 125 1.08
mos_fs -40 1.20
PVT
klt sim --batch-set "$run_dir"/mos_*.json --wait-for-capacity 600 \
  --format json -o "$run_dir/artifacts" > "$run_dir/results.json"
```

**Outstanding evidence.** The batch submission stopped before upload because
the submit profile could not obtain credentials on this host. The artifact
broker was also unreachable. The single-corner exploratory measurements
await storage. Per-candidate PVT densities, device shares and recalibrated
projections remain open in [#477](https://github.com/2AMLogic/sg13g2-comparator/issues/477).
