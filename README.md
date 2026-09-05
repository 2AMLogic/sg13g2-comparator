# sg13g2-comparator

A dynamic latched comparator on IHP SG13G2 on
[IHP SG13G2](https://github.com/IHP-GmbH/IHP-Open-PDK), IHP's open-source 130 nm SiGe BiCMOS PDK — designed by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools) and the
open-source xschem + ngspice flow.

**Status: just opened.** Nothing is designed yet. The first work is
the offset and noise measurement methodology — Monte-Carlo mismatch against the PDK's statistical models, if shipped, or a documented sensitivity fallback.

**Built agent-native.** Every specification, decision record, testbench, and
line of documentation here is produced by AI agents working from a ratified
spec and an append-only evidence trail — not human-authored work that agents
merely assisted with. Verification is the product: every claim traces to a
recorded result under PVT corners. Where the agents hit friction with the
open-source tooling — most often
[klayout-tools](https://github.com/2AMLogic/klayout-tools) — that friction is
filed as a public issue against the tool itself, so the fix benefits everyone
using this PDK, not just this repo.

## Why this block, on this PDK

The catalog has SAR ADCs whose comparators live inside them, but no
standalone comparator on any PDK — no block whose spec IS offset, noise,
metastability, and decision time, measured for their own sake. A StrongARM
latch on SG13G2's CMOS devices fills that gap on the thinnest foundry and
becomes the reusable decision element for a future sg13g2 SAR ADC.

The honest centerpiece is **statistical claims from open models**: offset
sigma means Monte-Carlo over the PDK's mismatch models if SG13G2 ships them,
and a documented, clearly-labelled sensitivity-analysis fallback if it does
not. Which of those two worlds this PDK lives in is itself a result worth
committing early. Metastability gets characterized (decision-time vs input
overdrive), not hand-waved.

## Target specification (DRAFT — engineering to ratify)

Offset sigma (with statistical basis stated), input-referred noise,
decision time vs overdrive at the target clock, kickback into a stated
source impedance, supply/power at 1.2 V core (3.3 V I/O flavor only if a
decision record scopes it in).

## License

Apache-2.0.
