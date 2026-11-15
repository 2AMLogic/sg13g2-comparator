* offset-transient-mc: klt-pex body derived from sim/comparator-offset-transient-mc/testbench/ by make_testbenches.py
* Stimulus/probe lines are verbatim from the original fragment.
.include comparator.schematic.sp
.param vdd_val=1.2
.param dut_ib=2e-05
.param dut_vcm=0.6
* comparator_dut wrapper (design/comparator.spice): bias mirror + the core cell.
* The mirror XMB is NOT in the layout; it is the same device on both legs.
.subckt comparator_dut vinp vinn clk ibias dout doutb vdd vss
XMB ibias ibias vss vss sg13_lv_nmos w=10u l=0.5u ng=1 m=1
x1 clk dout doutb ibias vdd vinn vinp vss comparator
.ends comparator_dut
.param c_route=10f
.param tstep_last=48m
vsup vdd 0 dc {vdd_val}
vcm cm 0 dc {dut_vcm}
vd   vd 0 pwl(
+ 0.0000n -0.048 29.8000n -0.048 30.0000n -0.045 59.8000n -0.045
+ 60.0000n -0.042 89.8000n -0.042 90.0000n -0.039 119.8000n -0.039
+ 120.0000n -0.036 149.8000n -0.036 150.0000n -0.033 179.8000n -0.033
+ 180.0000n -0.03 209.8000n -0.03 210.0000n -0.027 239.8000n -0.027
+ 240.0000n -0.024 269.8000n -0.024 270.0000n -0.021 299.8000n -0.021
+ 300.0000n -0.018 329.8000n -0.018 330.0000n -0.015 359.8000n -0.015
+ 360.0000n -0.012 389.8000n -0.012 390.0000n -0.009 419.8000n -0.009
+ 420.0000n -0.006 449.8000n -0.006 450.0000n -0.003 479.8000n -0.003
+ 480.0000n 0 509.8000n 0 510.0000n 0.003 539.8000n 0.003
+ 540.0000n 0.006 569.8000n 0.006 570.0000n 0.009 599.8000n 0.009
+ 600.0000n 0.012 629.8000n 0.012 630.0000n 0.015 659.8000n 0.015
+ 660.0000n 0.018 689.8000n 0.018 690.0000n 0.021 719.8000n 0.021
+ 720.0000n 0.024 749.8000n 0.024 750.0000n 0.027 779.8000n 0.027
+ 780.0000n 0.03 809.8000n 0.03 810.0000n 0.033 839.8000n 0.033
+ 840.0000n 0.036 869.8000n 0.036 870.0000n 0.039 899.8000n 0.039
+ 900.0000n 0.042 929.8000n 0.042 930.0000n 0.045 959.8000n 0.045
+ 960.0000n 0.048 989.8000n 0.048 990.0000n 0.048
+ )
Eap ap cm vd 0 0.5
Ean an cm vd 0 -0.5
vclk clk 0 pulse(0 {vdd_val} 10n 100p 100p 10n 30n)
ib   vdd ibn dc {dut_ib}
Xa   ap an clk ibn dout doutb vdd 0 comparator_dut
Cwd dout 0 {c_route}
Bdoutn doutn 0 v = 'v(dout)/v(vdd)'
.meas tran dlev0 find v(doutn) at=27.0000n
.meas tran dlev1 find v(doutn) at=57.0000n
.meas tran dlev2 find v(doutn) at=87.0000n
.meas tran dlev3 find v(doutn) at=117.0000n
.meas tran dlev4 find v(doutn) at=147.0000n
.meas tran dlev5 find v(doutn) at=177.0000n
.meas tran dlev6 find v(doutn) at=207.0000n
.meas tran dlev7 find v(doutn) at=237.0000n
.meas tran dlev8 find v(doutn) at=267.0000n
.meas tran dlev9 find v(doutn) at=297.0000n
.meas tran dlev10 find v(doutn) at=327.0000n
.meas tran dlev11 find v(doutn) at=357.0000n
.meas tran dlev12 find v(doutn) at=387.0000n
.meas tran dlev13 find v(doutn) at=417.0000n
.meas tran dlev14 find v(doutn) at=447.0000n
.meas tran dlev15 find v(doutn) at=477.0000n
.meas tran dlev16 find v(doutn) at=507.0000n
.meas tran dlev17 find v(doutn) at=537.0000n
.meas tran dlev18 find v(doutn) at=567.0000n
.meas tran dlev19 find v(doutn) at=597.0000n
.meas tran dlev20 find v(doutn) at=627.0000n
.meas tran dlev21 find v(doutn) at=657.0000n
.meas tran dlev22 find v(doutn) at=687.0000n
.meas tran dlev23 find v(doutn) at=717.0000n
.meas tran dlev24 find v(doutn) at=747.0000n
.meas tran dlev25 find v(doutn) at=777.0000n
.meas tran dlev26 find v(doutn) at=807.0000n
.meas tran dlev27 find v(doutn) at=837.0000n
.meas tran dlev28 find v(doutn) at=867.0000n
.meas tran dlev29 find v(doutn) at=897.0000n
.meas tran dlev30 find v(doutn) at=927.0000n
.meas tran dlev31 find v(doutn) at=957.0000n
.meas tran dlev32 find v(doutn) at=987.0000n
