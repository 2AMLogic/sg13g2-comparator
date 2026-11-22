# Matched PMOS load-width characterization (issue #498)

Reduced-model noise measurement for the issue #498 candidate set, using the
Phase 1 method and circuit family ([`20261120-issue477/`](../20261120-issue477/)).

## What this directory holds

| file | role |
|---|---|
| [`front-end.spice`](front-end.spice) | Fresh copy of the loop-broken model. Defaults are the archived `ib10_sw20lat6` control (8 µm / 0.34 µm pair, 20 µm switch, 6 µm XM3–XM6, 10 µA bias). The new `load_w` parameter reaches **only** the diode-connected counterparts XM5A/XM6A; `latch_w` keeps the full-latch wrapper's XM3–XM6 at the control's 6 µm, so one parameter row cannot move any other device (the Phase 1 `latch_w` ties NMOS and PMOS widths together; reusing it would confound the result). |
| [`loadwidth.request.json`](loadwidth.request.json) | One-PVT noise request; each zipped parameter row is one setting: the 6 µm control first, then the declared candidates 4, 8, 10, 12 µm. Measurements: differential output white density at 1 MHz (`white_out`), \|Aᵥ(1 Hz)\| (`gain_dc`), and the per-device output totals. |
| [`density.json`](density.json) | Derived table: per width, per PVT point, `white_out`, `gain_dc`, S = white_out / gain_dc (nV/√Hz), plus the XM5A+XM6A output power share. Generated from the stored batch reports; the numbers below come from it. |

## Result (S, input-referred white density, nV/√Hz)

| load_w | tt 27C/1.20V | sf −40C/1.32V | ff 125C/1.08V | fs −40C/1.20V |
|---|---:|---:|---:|---:|
| 4 µm | 39.41 | 31.73 | 49.43 | 32.50 |
| 6 µm (control) | **36.78** | 29.72 | 45.61 | 30.52 |
| 8 µm | 35.04 | 28.40 | 43.15 | 29.20 |
| 10 µm | 33.76 | 27.42 | 41.35 | 28.22 |
| 12 µm | 32.74 | 26.64 | 39.94 | 27.45 |

The control row reproduces Phase 1's `ib10_sw20lat6` densities at all four
points to the printed digits ([Phase 1 table](../20261120-issue477/pvt-batch.md)),
so the candidate rows sit on the same footing as the ratified calibration.
Wider loads lower S monotonically and lower the DC gain (1.085 → 0.871 V/V
at TT from 6 µm to 12 µm); the load pair's share of output noise power
falls from 86.7 % to 83.3 % at TT. The 10.1 % TT-density reduction the
control's Row 2 projection needs (36.78 → 33.07 nV/√Hz) is crossed between
10 µm (33.76) and 12 µm (32.74).

## Provenance

Submitted 2026-11-21 with `klt sim --batch-set --wait-for-capacity 600`
(four jobs, one per PVT point, five parameter rows each; 20 of 20 cells
`pass`). The raw bytes — derived requests, per-cell decks, ngspice logs,
engine reports, the set result and the broker receipts — are in the fleet
artifact store, not in git: see
[`../20261121-issue498-pvt.md`](../20261121-issue498-pvt.md)
(manifest `manifests/artifacts/comparator-preamp-noise-20261121-issue498-pvt.manifest.json`).

## Reproduce

```bash
run_dir=$(mktemp -d)
while read -r process temp supply; do
  jq --arg netlist "$PWD/front-end.spice" --arg process "$process" \
     --argjson temp "$temp" --argjson supply "$supply" \
     '.netlist = $netlist | .corners.process = [$process] |
      .corners.temperature_c = [$temp] | .corners.supply_v.vsup = [$supply]' \
      loadwidth.request.json > "$run_dir/$process.json"
done <<'PVT'
mos_tt 27 1.20
mos_sf -40 1.32
mos_ff 125 1.08
mos_fs -40 1.20
PVT
klt sim --batch-set "$run_dir"/mos_*.json --wait-for-capacity 600 \
  --format json -o "$run_dir/artifacts" > "$run_dir/results.json"
```

S per row: divide each corner's `white_out` (V/√Hz) by its `gain_dc` (V/V)
and multiply by 10⁹; match corners to rows by the `params` zip order.
