| row | corner | schematic | extracted | delta % | klt status |
|---|---|---|---|---|---|
| regeneration.nominal.vsup_v | tt/1.200V/27C | 1.2 | 1.2 | +0.000 | pass |
| regeneration.nominal.td_a | tt/1.200V/27C | 7.09689e-10 | 2.03961e-09 | +187.395 | pass |
| regeneration.nominal.td_b | tt/1.200V/27C | 9.63272e-10 | 2.68174e-09 | +178.399 | pass |
| regeneration.nominal.td_c | tt/1.200V/27C | 1.10599e-09 | n/a (no value) | n/a | error |
| regeneration.nominal.da_first | tt/1.200V/27C | 3.32417e-06 | 3.09229e-06 | -6.976 | pass |
| regeneration.nominal.db_first | tt/1.200V/27C | 3.3668e-06 | 3.69232e-06 | +9.669 | pass |
| regeneration.nominal.dc_first | tt/1.200V/27C | 3.31935e-06 | 0.999993 | +30126069.280 | pass |
| regeneration.nominal.da_end | tt/1.200V/27C | 1 | 1 | +0.000 | pass |
| regeneration.nominal.db_end | tt/1.200V/27C | 1 | 1 | +0.000 | pass |
| regeneration.nominal.dc_end | tt/1.200V/27C | 1 | 1 | +0.000 | pass |
| regeneration.nominal.i_stat | tt/1.200V/27C | -2.02726e-05 | -2.02878e-05 | -0.075 | pass |
| regeneration.nominal.q_dec | tt/1.200V/27C | -1.97023e-13 | -2.20685e-13 | -12.010 | pass |
| kickback.nominal.ad_pos | tt/1.200V/27C | 0.115818 | 0.106602 | -7.957 | pass |
| kickback.nominal.ad_neg | tt/1.200V/27C | -0.0358128 | -0.0408724 | -14.128 | pass |
| kickback.nominal.ap0 | tt/1.200V/27C | 0.6005 | 0.6005 | +0.000 | pass |
| kickback.nominal.apmax | tt/1.200V/27C | 0.716318 | 0.707102 | -1.287 | pass |
| kickback.nominal.apmin | tt/1.200V/27C | 0.564687 | 0.559628 | -0.896 | pass |
| kickback.nominal.bd0 | tt/1.200V/27C | 0.000994567 | 0.000994463 | -0.010 | pass |
| kickback.nominal.bd1 | tt/1.200V/27C | 0.00099492 | 0.000995526 | +0.061 | pass |
| kickback.nominal.cd0 | tt/1.200V/27C | 0.0994542 | 0.0994514 | -0.003 | pass |
| kickback.nominal.cd1 | tt/1.200V/27C | 0.0994455 | 0.0994416 | -0.004 | pass |
| kickback.nominal.bc0 | tt/1.200V/27C | 0.00105558 | 0.00105652 | +0.089 | pass |
| kickback.nominal.bc1 | tt/1.200V/27C | 0.000311667 | 6.36712e-05 | -79.571 | pass |
| kickback.nominal.bp0 | tt/1.200V/27C | 0.601553 | 0.601554 | +0.000 | pass |
| kickback.nominal.bn0 | tt/1.200V/27C | 0.600558 | 0.600559 | +0.000 | pass |
| kickback.nominal.bp1 | tt/1.200V/27C | 0.600809 | 0.600561 | -0.041 | pass |
| kickback.nominal.bn1 | tt/1.200V/27C | 0.599814 | 0.599566 | -0.041 | pass |
| kickback.nominal.da_end | tt/1.200V/27C | 1 | 1 | +0.000 | pass |
| kickback.nominal.db_end | tt/1.200V/27C | 1 | 1 | +0.000 | pass |
| kickback.nominal.dc_end | tt/1.200V/27C | 1 | 1 | +0.000 | pass |

Note (hand-added after generation, PR #113 review): the `dc_first` row is **not
a meaningful delta and is not a pass**. It samples `v(dcn)` at 18 ns, before
the input flip. The extracted latch has already resolved to the opposite side
(0.99999 vs the schematic's ~0). That is the same flipped decision that leaves
`td_c` with no value. The `pass` status only records that both legs produced
a value (no limit is set on the row). See `../README.md`, "Findings".
