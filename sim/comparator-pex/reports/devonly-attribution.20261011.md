# Extracted-device-only attribution (issue #191) -- DIAGNOSTIC, single corner

Not compliance evidence and not a statistic: tt / 1.20 V / 27 C, deterministic transient, no Monte Carlo, no seeds, no sigma. The original full PEX stays the compliance artifact; DR-0002 bounds are unchanged.

## Extraction scope

lumped model: one series R per net terminal, one ground C per net, vertical-overlap coupling only; no lateral coupling, no distributed RC, quasi-static. The device-only leg keeps all 64 fingers (model, W, L, AS, AD, PS, PD verbatim) and removes 252 terminal R (collapsed to parent nets), 16 ground C and 52 coupling C. The bias mirror XMB is outside the layout and identical on all legs.

## Decision delay (absolute)

| Measure | Schematic | Extracted-device-only | Full PEX | DR-0002 Row 3 |
|---|---|---|---|---|
| td_a (50 mV overdrive) | 0.710 ns | 1.536 ns | 2.040 ns | <= 1.5 ns |
| td_b (1 mV overdrive) | 0.963 ns | 2.005 ns | 2.682 ns | ungraded |
| td_c (0.1 mV overdrive) | 1.106 ns | 2.230 ns | no value | <= 2.0 ns |

## Decision states (v at 18 ns, before the input flip, and at end)

| Row | Schematic | Extracted-device-only | Full PEX |
|---|---|---|---|
| da_first | 3.32e-06 | 2.31e-08 | 3.09e-06 |
| db_first | 3.37e-06 | 2.29e-08 | 3.69e-06 |
| dc_first | 3.32e-06 | 3.81e-06 | 1 |
| da_end | 1 | 1 | 1 |
| db_end | 1 | 1 | 1 |
| dc_end | 1 | 1 | 1 |

## Conditional increments at 50 mV overdrive (td_a)

- schematic -> device-only: +0.826 ns (device representation and junction geometry, routing absent)
- device-only -> full PEX: +0.504 ns (routing RC, conditional on the extracted devices)

These are conditional differences in a nonlinear circuit, not a unique additive decomposition. The device-only leg changes finger count and AS/AD/PS/PD together; they are not separated from each other. One corner cannot size a cause across PVT.

## Missing measurements

- `td_c`: full_pex: measurement produced no value (td_c waits for a rising transition of dcn that never occurs; dc_first already high)

## PVT staging (batch)

`klt sim --backend batch` on the 45-point device-only request: status `error`, 0 pass / 0 fail / 45 error, job `klt-sim-5e70ae964e3a`, batch_job_failed on every corner: batch_runner_version_mismatch (runner klt 0.5.0, client 0.7.0+g39f6da54ae4c). No local grid fallback. All 45 points are retained in `devonly-pvt-batch.20261011.json`. No PVT claim is made.
