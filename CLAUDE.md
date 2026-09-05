# sg13g2-comparator — agent instructions

Open-source canary block: a dynamic latched comparator on ihp sg13g2,
on IHP SG13G2, IHP's open-source 130 nm SiGe BiCMOS PDK, designed and verified by AI agents.

- **PDK**: IHP SG13G2 (https://github.com/IHP-GmbH/IHP-Open-PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout work.
- **New block on this PDK; the topology is textbook.** StrongARM latch plus
  optional continuous-time preamp. Start from the literature (Razavi's
  StrongARM tutorial is canonical) and the PDK models, not from the SAR
  canaries' embedded comparators.
- **Offset claims state their statistical basis.** Monte-Carlo over shipped
  mismatch models when the PDK provides them; otherwise a labelled
  sensitivity fallback. Never present a single-corner offset as a sigma.
- **Metastability is a first-class spec row**: decision time vs overdrive,
  and the input-referred noise floor from transient-noise runs with seeds
  and run counts committed.
- **Kickback is measured**, not assumed: the bench drives realistic source
  impedances and records disturbance at the inputs.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue at
  `2AMLogic/klayout-tools` describing the tool gap generically — that tracker
  is scoped to the tool, so keep design-specific detail out of it and
  describe the gap, not the design.
- **Verification is the product**: no claim without a testbench; PVT corners
  on every recorded result; `sim/` results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not
  relax the ratified spec to make results pass.
