# Nominal front-end density for the six #92 finalists and the committed control

The single-PVT run from PR #486 measured each design at TT, 27 °C, 1.20 V
on 2026-11-20. All seven parameter rows passed with ngspice 47, klt
`75c6350d487d` and IHP SG13G2 v0.3.0. Repeating the committed request
reproduced all seven rows' output densities and gains. The Row 2 projections
use these nominal densities to rescale the archived 45-point grid means.
[Density and projection table](20261120-issue477/pvt-batch.md#nominal-recalibration-for-the-six-92-finalists)

To reproduce the nominal measurements, run the full request from its directory
with `PDK_ROOT` pointing to the SG13G2 installation.

```bash
run_dir=$(mktemp -d)
klt sim nominal.request.json --backend local --format json -o "$run_dir/artifacts"
```

In `artifacts/report.json`, match each corner's `params` to the zipped parameter
row in the request. Divide its `white_out` at 1 MHz (V/√Hz) by `gain_dc`
at 1 Hz (V/V) and multiply by 10⁹ to obtain the input density in nV/√Hz.
The stored decks and ngspice logs give the per-row simulator inputs and
measurements. [Measurement request](20261120-issue477/nominal.request.json)

## Stored evidence

The bytes of this run are in the fleet artifact store, not in git (issue #318). Manifest: `manifests/artifacts/comparator-preamp-noise-20261120-issue477-nominal.manifest.json` (25 objects, 80977 B). Paths above are the manifest `name`s. Fetch one, hash-verified, with:

```
klt artifact get manifests/artifacts/comparator-preamp-noise-20261120-issue477-nominal.manifest.json#<name> -o <out>
python3 scripts/check_artifact_manifests.py verify manifests/artifacts/comparator-preamp-noise-20261120-issue477-nominal.manifest.json
```

| name | size (B) | sha256 |
|---|---:|---|
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_251f4d057b63b8c254c634887e45c322fc29ec3b34248a4cb097579216bd7ae8/corner.cir` | 2331 | `7e4ad7f498e8dc34cd9d78a96aecbcad4e6cd2ce5b512f90258a09ae65951b8f` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_251f4d057b63b8c254c634887e45c322fc29ec3b34248a4cb097579216bd7ae8/corner.json` | 231 | `ae86624a986674b1888fdbfc5462604ddf7d616343fdc76efd3b3ad9ba2844ef` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_251f4d057b63b8c254c634887e45c322fc29ec3b34248a4cb097579216bd7ae8/ngspice.log` | 578 | `8a22c28f176cf3af846848f06622d9406d30b3b25c3c8930332be20f6ef70207` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_3eaefa1d19e565605f4604ccfa62eb8a653e28dc2c827cf3dc14a31ef0b133e0/corner.cir` | 2329 | `efb3b237c831d2d1993d53b105cef3b334fd2dc977093f6feea2bc2e0cab365d` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_3eaefa1d19e565605f4604ccfa62eb8a653e28dc2c827cf3dc14a31ef0b133e0/corner.json` | 227 | `4233c8e386f44e9e0b2e744d0df137787e16fb870bf0a6d127441c90a08bea96` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_3eaefa1d19e565605f4604ccfa62eb8a653e28dc2c827cf3dc14a31ef0b133e0/ngspice.log` | 578 | `805ba2d64677942f20224ba56cb9309f012be74d406cae32f56aa26f5aa86d10` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_5071bf0dcd1c4b34d2855fb0f002a43ef83a402df4804bda37fbb537e49df71e/corner.cir` | 2329 | `8017007c8872d8e90243aa16084dd12ffca8a6e2fba80d65954db0bda2844159` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_5071bf0dcd1c4b34d2855fb0f002a43ef83a402df4804bda37fbb537e49df71e/corner.json` | 227 | `bf6700e61227bd87caeffeba1d3aba6b9959856018f7820b82997824b47085b9` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_5071bf0dcd1c4b34d2855fb0f002a43ef83a402df4804bda37fbb537e49df71e/ngspice.log` | 578 | `b41b3e3a552ba95032f9b3df754071511845c5d38c9b4322e585c5bee77d9864` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_bc0a2812900badadd5f3fd4a3cd74d831bf8bef6b6e961478c97b69ea9cb02df/corner.cir` | 2327 | `aa60fcb261a45154e57c56a098c618af06e989ce56f657994e7aca75c353b4e8` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_bc0a2812900badadd5f3fd4a3cd74d831bf8bef6b6e961478c97b69ea9cb02df/corner.json` | 223 | `78db8f979246c30014c239384960b28619aad058c599ef0a4749bda13dd04215` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_bc0a2812900badadd5f3fd4a3cd74d831bf8bef6b6e961478c97b69ea9cb02df/ngspice.log` | 578 | `4379e8af73eb7bf8e26863425baa409392232fbef978d2620a2cf5a22985f7e4` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_bcf29c23dedd3b6472a8010025070f5b8e29625bf8b71048b374ba44b674afdf/corner.cir` | 2332 | `7720162c38caec74a1f54fe92c27882f8b83e686d3ac4dfa8925bf839ec6cde2` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_bcf29c23dedd3b6472a8010025070f5b8e29625bf8b71048b374ba44b674afdf/corner.json` | 233 | `6d44c8823d5608860c1bbb31560b3fb06e08ec5f18d0adaddfa7b42706375432` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_bcf29c23dedd3b6472a8010025070f5b8e29625bf8b71048b374ba44b674afdf/ngspice.log` | 578 | `755114f2306bf304884fbd88a2961f25cac4203b1439b84fefc5c1472947a9b2` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_e0b4efe59f779eeba0cdf40423b77aebc20362ff6f9dad2d908a1a995dd635c6/corner.cir` | 2329 | `368cb411c038820895cf4cd83c4fa399a5a9135c71543bebeb3bc4942313801a` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_e0b4efe59f779eeba0cdf40423b77aebc20362ff6f9dad2d908a1a995dd635c6/corner.json` | 227 | `d2c89d63115a804d1da4d786d2880afe8e4e56c616c95d2f2c3039682b1ef21e` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_e0b4efe59f779eeba0cdf40423b77aebc20362ff6f9dad2d908a1a995dd635c6/ngspice.log` | 578 | `1355b55a07ad16ba58a1096f30ab6343c383f986d95d3effe97675b7b0ec2551` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_e577210fed33d9c5dc2c6f74fd365436d06487577068e15e4f637e5d3e879ddb/corner.cir` | 2329 | `e00ec8b8e89511ea2bb9420b97adbeb8db1d93be6210a24e5ea8cbbda8742639` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_e577210fed33d9c5dc2c6f74fd365436d06487577068e15e4f637e5d3e879ddb/corner.json` | 227 | `033c2c236365079f9155e4a0166bf676807cc29f800eedcee45c163673b87c34` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/mos_tt_1p200V_27C_params_e577210fed33d9c5dc2c6f74fd365436d06487577068e15e4f637e5d3e879ddb/ngspice.log` | 578 | `c66b9427bfe4466157f39d4b63c52617cf8ebe9f280402d0caaa818c71650982` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/artifacts/report.json` | 50253 | `73b059bdff520e341af2fb51b928e4931cbcf1c5d00b1c877bbbdbd780aac542` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/front-end.spice` | 2672 | `70a814d6e22b94b727b0c28b046d8cba14d2d4a3e7afed582eab1eb9991acebc` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/nominal.request.json` | 2762 | `7098c88d2d9f93d7173ad16263940604336102f7ebf98dbc9d80d6deaf1fa1c3` |
| `sim/comparator-preamp-noise/reports/20261120-issue477-nominal/tb_preamp_noise.spice` | 3343 | `16cb64f2711e37101a909c16fed05f5d72341b06c67cfeb8429a8773a5ce97ae` |
