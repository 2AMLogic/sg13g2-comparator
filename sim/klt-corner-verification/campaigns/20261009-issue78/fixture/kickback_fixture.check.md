| case | injected | expected Q (fC) | measured Q (fC) | expected net (fC) | measured net (fC) | sign | end-window estimator (fC) | ok |
|---|---|---|---|---|---|---|---|---|
| a | unipolar +10 fC (+7 fC before 29 ns and +4 fC after 45 ns excluded) | 10.000 | 9.9999 | -10.000 | -9.9998 | - (exp -) | 9.9998 | PASS |
| b | unipolar -10 fC | 10.000 | 10.0000 | 10.000 | 9.9999 | + (exp +) | 9.9999 | PASS |
| c | bipolar +20 fC then -20 fC, net 0 | 20.000 | 19.9999 | 0.000 | 0.0001 | - (exp -) | 0.0001 | PASS |
| d | +10 fC through a restoring 1 kohm / 100 fF node (V x C_in reads ~0.1 fC) | 10.000 | 10.0000 | -10.000 | -9.9999 | - (exp -) | 9.9999 | PASS |

Case d restoration: peak node volts x C_in reads 0.1000 fC for the 10.0 fC actually delivered; the instrument reads 10.0000 fC.

Tolerance 0.02 fC. End-window estimator fails the bipolar case (negative control): True. Overall: PASS.
