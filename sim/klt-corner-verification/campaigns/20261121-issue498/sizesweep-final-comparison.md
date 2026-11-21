# Matched PMOS load-width finalist and 8 µm baseline

The finalist preserves every Target the 8 µm input-pair baseline passed.
This comparison supplements the archived finalist table with both sets of
measurements, all reporting rows and Stretch verdicts.
[Baseline grade](../20261009-issue92/full_w8_l034/grading.md) · [w10 grade](full_w10/grading.md)

Both grades cover 45 PVT points per bench. Row 2 is the mean of the per-point
probit-slope sigmas at the 36.27 nV/√Hz bench injection. Row 1 has 60 offset
draws per point and Row 2 has 80 draws per rung at every point in both
designs. Neither grade has missing draws or an INCOMPLETE row. A dash denotes
an unspecified bound. Row 4c requires reporting only.

| Row | Measurement | 8 µm baseline | w10 | Target / Stretch (both designs) |
|---|---|---:|---:|---|
| 1 | Offset, worst 3σ (mV) | 13.93 | 13.37 | PASS / FAIL |
| 2 | Decision noise, grid mean (mV rms) | 1.33778 | 1.04143 | FAIL / FAIL |
| 3a | Decision time at 50 mV, max (ns) | 0.8664 | 1.188 | PASS / FAIL |
| 3b | Regeneration time constant, max (ps) | 168.7 | 135.6 | PASS / — |
| 3c | Decision time at 0.1 mV, max (ns) | 1.705 | 1.977 | PASS / — |
| 4a | Injected charge per side, max (fC) | 21.2 | 19.76 | PASS / FAIL |
| 4b | Signal-dependent residue, max (µV) | 10.29 | 10.42 | PASS / PASS |
| 4c | Single-ended excursion, max (mV) | 96.03 | 97.95 | REPORTED / — |
| 5a | PVT coverage, all four benches | 45/45 per bench | 45/45 per bench | PASS / — |
| 5b | Average power at 33.3 MHz, max (µW) | 37.61 | 25.67 | — / FAIL |

At its measured 45-point bandwidth, w10's TT-density projection is
**0.96930 mV rms** (1.04143154 × 33.758 / 36.27). Holding the 6 µm
control bandwidth fixed gives **1.02035 mV rms** (1.09627632 × 33.758 /
36.27). The measured w10 mean at 36.27 nV/√Hz is **1.04143 mV rms**, so
Row 2 fails the 1.0 mV Target despite a 5.0% improvement over the control.
The 12 µm screen breached Row 3c at
2.044 ns. Widths between 10 and 12 µm have no timing grade.

[Corrected screen and evidence links](loadwidth-final.md)
