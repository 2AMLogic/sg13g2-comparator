* transient-noise: klt-pex body derived from sim/comparator-transient-noise/testbench/ by make_testbenches.py
* Stimulus/probe lines are verbatim from the original fragment.
.include comparator.schematic.sp
.param vdd_val=1.2
.param dut_ib=2e-05
.param dut_vcm=0.6
.param vn_na=0.005735
.param vn_ts=2e-11
.param od_x=0.001
.options reltol=1e-2 abstol=1e-12
* comparator_dut wrapper (design/comparator.spice): bias mirror + the core cell.
* The mirror XMB is NOT in the layout; it is the same device on both legs.
.subckt comparator_dut vinp vinn clk ibias dout doutb vdd vss
XMB ibias ibias vss vss sg13_lv_nmos w=10u l=0.5u ng=1 m=1
x1 clk dout doutb ibias vdd vinn vinp vss comparator
.ends comparator_dut
vsup vdd 0 dc {vdd_val}
vcm  cm 0 dc {dut_vcm}
vd0  vd0 0 dc 0     trnoise({vn_na} {vn_ts} 0 0)
Eap0 ap0 cm vd0 0 0.5
Ean0 an0 cm vd0 0 -0.5
ib0  vdd ibn0 dc {dut_ib}
X0   ap0 an0 clk ibn0 dout0 doutb0 vdd 0 comparator_dut
vd1  vd1 0 dc {od_x} trnoise({vn_na} {vn_ts} 0 0)
Eap1 ap1 cm vd1 0 0.5
Ean1 an1 cm vd1 0 -0.5
ib1  vdd ibn1 dc {dut_ib}
X1   ap1 an1 clk ibn1 dout1 doutb1 vdd 0 comparator_dut
.param od_xn={-1*od_x}
vd2  vd2 0 dc {od_xn} trnoise({vn_na} {vn_ts} 0 0)
Eap2 ap2 cm vd2 0 0.5
Ean2 an2 cm vd2 0 -0.5
ib2  vdd ibn2 dc {dut_ib}
X2   ap2 an2 clk ibn2 dout2 doutb2 vdd 0 comparator_dut
vclk clk 0 pulse(0 {vdd_val} 1n 100p 100p 4n 20n)
