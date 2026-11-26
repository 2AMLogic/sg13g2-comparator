# Issue #497 Phase 1 calibration: stored run bytes

The four-point `.noise` batch (control + `cadd1f`/`cadd2f`/`cadd4f` rows at
the archived `ib10_sw20lat6` geometry, 10 µA bias) and the two-row
mechanism control that proves `c_add` applies in the subckt capacitors.
Method, mapping, results table and the reproduce invocation live in
[`20261121-issue497-calibration/README.md`](20261121-issue497-calibration/README.md);
the study conclusion is in
[`20261121-issue497.md`](20261121-issue497.md).

Runner klt 0.9.x / ngspice 47, submitted 2026-11-21 with
`--batch-set --wait-for-capacity 600`; 16 of 16 calibration cells `pass`,
both mechanism-control cells `pass`. Job ids (calibration): `mos_tt` =
`klt-sim-b68be702f469`, `mos_sf` = `klt-sim-0136489d2422`, `mos_ff` =
`klt-sim-67b2d74beabc`, `mos_fs` = `klt-sim-2e9c5d8ab78a`.

## Stored evidence

The bytes of this run are in the fleet artifact store, not in git (issue #318). Manifest: `manifests/artifacts/comparator-integration-capacitance-20261121-issue497-calibration.manifest.json`. Paths above are the manifest `name`s. Fetch one, hash-verified, with:

```
klt artifact get manifests/artifacts/comparator-integration-capacitance-20261121-issue497-calibration.manifest.json#<name> -o <out>
python3 scripts/check_artifact_manifests.py verify manifests/artifacts/comparator-integration-capacitance-20261121-issue497-calibration.manifest.json
```
