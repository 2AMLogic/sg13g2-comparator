# Stored Monte-Carlo evidence for the #92 bias/latch finalists (campaign `20261115-issue92-bias`)

The committed campaign directory
`sim/klt-corner-verification/campaigns/20261115-issue92-bias/` carries, for each
finalist (`full_ib10_sw20`, `full_ib10_sw20lat6`, `full_ib12p5_sw20`), the full
request/body/invocation/attempts chain, the deterministic 45-point envelopes
(kickback, regeneration), the grading outputs and the campaign report. The
bulky Monte-Carlo evidence is stored here instead of committed, under the
evidence-size budget (issue #318): this run id holds each finalist's five
offset_mc envelopes (MC N = 60 per point, seeds = bench defaults committed in
each request) and five transient_noise envelopes (N = 80 per rung), plus one
`artifacts-mc.tar.gz` with the per-corner ngspice artifacts of those ten
benches. Every stored `name` maps 1:1 onto the committed campaign directory
of the same finalist: `full_<name>/` here is
`20261115-issue92-bias/full_<name>/` there.

Headline graded results (full 45-point grid, `kltsim.grade`, seeds committed):

| finalist | Row 1 offset 3 sigma worst (MC N=60) | Row 2 noise grid mean (probit, N=80) | Rows 3a/3b/3c/4a/4b |
|---|---|---|---|
| ib10_sw20 | INCOMPLETE (44/45 valid; worst valid 13.69 mV @ tt_125c_1.08v) | 1.192 mV rms (FAIL vs <= 1.0) | all PASS |
| ib10_sw20lat6 | INCOMPLETE (43/45 valid; worst valid 13.37 mV @ ff_125c_1.08v) | 1.096 mV rms (FAIL vs <= 1.0) | all PASS |
| ib12p5_sw20 | INCOMPLETE (44/45 valid; worst valid 13.78 mV @ fs_125c_1.08v) | 1.255 mV rms (FAIL vs <= 1.0) | all PASS |

Row 1 is incomplete because one mismatch draw per finalist aborted in ngspice
(`timestep_too_small` -> `analysis_aborted`) at a fixed committed seed; the
affected PVT point is reported invalid, not silently dropped. No candidate in
the DR-0001 topology closes Row 2; see
`20261115-issue92-bias/sizesweep-final.md` for the full tables and the
baseline comparison. This store proposes no bound, adopts no candidate and
relaxes no row.

## Stored evidence

The bytes of this run are in the fleet artifact store, not in git (issue #318). Manifest: `manifests/artifacts/klt-corner-verification-20261115-issue92-bias-mc.manifest.json` (33 objects, 94823025 B). Paths above are the manifest `name`s. Fetch one, hash-verified, with:

```
klt artifact get manifests/artifacts/klt-corner-verification-20261115-issue92-bias-mc.manifest.json#<name> -o <out>
python3 scripts/check_artifact_manifests.py verify manifests/artifacts/klt-corner-verification-20261115-issue92-bias-mc.manifest.json
```

| name | size (B) | sha256 |
|---|---:|---|
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/artifacts-mc.tar.gz` | 1750963 | `36aa8604e0ecb91498401ac0a4803ba6f2420969dd98bb18473ca9c65c55f022` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/offset_mc.mos_ff_mismatch.envelope.json` | 1603291 | `6a17596dfd677b56e80099781014bb4b77f8625a4fced30653b091783daa974f` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/offset_mc.mos_fs_mismatch.envelope.json` | 1603652 | `23c122c00381bed39fdeffc166ad832ad2468d3ad3b6fe64bb615d803f91fa56` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/offset_mc.mos_sf_mismatch.envelope.json` | 1605341 | `784336016b71233e640b78e31f0c0424ad74525b3ab6270101f2befed096e464` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/offset_mc.mos_ss_mismatch.envelope.json` | 1602762 | `83264f5723ed7366454e7900e41538bb006849d1f624a5523e9670d4ff0b6acc` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/offset_mc.mos_tt_mismatch.envelope.json` | 1600820 | `f15f856fc995d157b3d7a7b2d574c1bf346cd7675c90771ffd23b9bb9a1419df` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/transient_noise.mos_ff.envelope.json` | 4363774 | `5fcd900cbb743b25b81481760071d79c67401139aff2e6d5d4c4ed4fbeaf832e` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/transient_noise.mos_fs.envelope.json` | 4361724 | `84e5b679df600e5da25fb6c4cb864646e0aa803386fd1ff23724f20ade4c03c1` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/transient_noise.mos_sf.envelope.json` | 4363032 | `c9b065b8cd4704428ab6ffdcc8c5b1e62b56259841df3bca1b7ac5fb1f2affb8` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/transient_noise.mos_ss.envelope.json` | 4361534 | `303f4b6c3773f966f7a7807b7d4b01d0fd28d64614b23dd01f4a1d18a9c3e1d0` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20/transient_noise.mos_tt.envelope.json` | 4362608 | `891ca31784e6dc7bf8364ff0c9a0aacc9038fe1ef7c80a06ab9c48bff4b0c809` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/artifacts-mc.tar.gz` | 1758137 | `b7aa270c1b1fe8e0bfc1492985e50b470af195cb341ec8997613f0b392c37a28` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/offset_mc.mos_ff_mismatch.envelope.json` | 1609600 | `77cc7fe269a53179f843a3ab249c6af20f534abead18e77957b442000479752f` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/offset_mc.mos_fs_mismatch.envelope.json` | 1607880 | `d0c1d94e54ace24f687077dae84b8c25ff4de721d6a5ab8dd990f4fa2147b265` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/offset_mc.mos_sf_mismatch.envelope.json` | 1610936 | `bab6563fe160ac2cc0f15c58f73e1353b3de13a191bceed752b237172b0afa34` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/offset_mc.mos_ss_mismatch.envelope.json` | 1605791 | `4a080d469bd071a915c89c2ee062ccd3fa0429492dea60ae685555e4f2c1fdea` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/offset_mc.mos_tt_mismatch.envelope.json` | 1606714 | `be19ae9c25becd58a7eb84dd7981c6568a3a49c6139579177a705ca2f7d5a355` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/transient_noise.mos_ff.envelope.json` | 4369621 | `0f03619c10a050f9d6d1acec5b13772f2168d0ff3068f6fc34089688e03a0f4c` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/transient_noise.mos_fs.envelope.json` | 4366296 | `d6209752d125d399ea2e7e1e3213ffec49937eecdc281821e75061e225e90b7f` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/transient_noise.mos_sf.envelope.json` | 4368074 | `80b5d5717a059ae3921d3a0bdb2c3fa5a1720977f72b9b5c51635e776d6b92c3` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/transient_noise.mos_ss.envelope.json` | 4368047 | `1976580fb8e95b0dcfcb4945478c8d01d03262c0616024cd4c13f4a45297cc66` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib10_sw20lat6/transient_noise.mos_tt.envelope.json` | 4368002 | `ecf3c6a20f5ea26d7c82f118599adb63a9b8c09f59a22b68162367273d2c686f` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/artifacts-mc.tar.gz` | 1750686 | `40f672371372f137e8532df14c484dea917133d7cf7b4da0948c19f803db3bfd` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/offset_mc.mos_ff_mismatch.envelope.json` | 1604946 | `13d4fd865b4203e49249f094333ce57b9afc67c96d29172ecb0f82edd137fb41` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/offset_mc.mos_fs_mismatch.envelope.json` | 1604301 | `6099dce4461ff09d521768b9207c0f25124812951bfe4e670047d6c01325a506` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/offset_mc.mos_sf_mismatch.envelope.json` | 1607765 | `a64ba5b52e5eff48010939d56fd9f352f92170c42cf5a852cf598c5c9d9cccfd` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/offset_mc.mos_ss_mismatch.envelope.json` | 1604970 | `8fe7662e502cf030b6fa9b94b22669ca63c62d67e7c802f1c8286fb1d19bbaa3` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/offset_mc.mos_tt_mismatch.envelope.json` | 1603718 | `b4949e1df663b0a0309948b6050cc11f8884b630726d2c359c20b958f41c437c` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/transient_noise.mos_ff.envelope.json` | 4367321 | `3a21d38ba24e3c71a5f0c2438ff574d1329f2efa5ce1ca1660ee9c41084f45a4` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/transient_noise.mos_fs.envelope.json` | 4364917 | `8fc67084d6e5e67bbf1a7b985fa59f9b1d85866f69516762048e9c674956ac23` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/transient_noise.mos_sf.envelope.json` | 4364909 | `c5a9ade6e4706c55c4a38224e07f0ab5c0d041056a4cbcbd6abeea3498e82d00` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/transient_noise.mos_ss.envelope.json` | 4364302 | `1ef4bedc15f1010c2af165758f9064e20edecbf673dca37f9fea2ba03e6650ca` |
| `sim/klt-corner-verification/campaigns/20261115-issue92-bias-mc/full_ib12p5_sw20/transient_noise.mos_tt.envelope.json` | 4366591 | `cb5c2c6daf3394daae31a373280536aaf288fcc8d6c507b3b174231616dc0e93` |
