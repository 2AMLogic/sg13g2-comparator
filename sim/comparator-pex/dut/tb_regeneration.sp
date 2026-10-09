* regeneration: klt-pex body derived from sim/comparator-regeneration/testbench/ by make_testbenches.py
* Stimulus/probe lines are verbatim from the original fragment.
.include comparator.schematic.sp
.param vdd_val=1.2
.param dut_ib=2e-05
.param dut_vcm=0.6
.options reltol=1e-4 vntol=1e-9 abstol=1e-13
* comparator_dut wrapper (design/comparator.spice): bias mirror + the core cell.
* The mirror XMB is NOT in the layout; it is the same device on both legs.
.subckt comparator_dut vinp vinn clk ibias dout doutb vdd vss
XMB ibias ibias vss vss sg13_lv_nmos w=10u l=0.5u ng=1 m=1
x1 clk dout doutb ibias vdd vinn vinp vss comparator
.ends comparator_dut
.param dv_big=50m
.param dv_mid=1m
.param dv_tiny=0.1m
.param t_flip=20n
.param c_route=10f
vsup  vdd  0 dc {vdd_val}
vsupa vdda 0 dc {vdd_val}
vclk clk 0 pulse(0 {vdd_val} 10n 100p 100p 10n 30n)
vcm cm 0 dc {dut_vcm}
vsa  sa 0 pwl(0 {-dv_big} {t_flip} {-dv_big} {t_flip+1n} {dv_big})
Eapa apa cm sa 0 0.5
Eana ana cm sa 0 -0.5
iba  vdda ibna dc {dut_ib}
Xa   apa ana clk ibna douta doutba vdda 0 comparator_dut
vsb  sb 0 pwl(0 {-dv_mid} {t_flip} {-dv_mid} {t_flip+1n} {dv_mid})
Eapb apb cm sb 0 0.5
Eanb anb cm sb 0 -0.5
ibb  vdd ibnb dc {dut_ib}
Xb   apb anb clk ibnb doutb doutbb vdd 0 comparator_dut
vsc  sc 0 pwl(0 {-dv_tiny} {t_flip} {-dv_tiny} {t_flip+1n} {dv_tiny})
Eapc apc cm sc 0 0.5
Eanc anc cm sc 0 -0.5
ibc  vdd ibnc dc {dut_ib}
Xc   apc anc clk ibnc doutc doutbc vdd 0 comparator_dut
Bclkn clkn 0 v = 'v(clk)/v(vdd)'
Bdan  dan  0 v = 'v(douta)/v(vdda)'
Bdbn  dbn  0 v = 'v(doutb)/v(vdd)'
Bdcn  dcn  0 v = 'v(doutc)/v(vdd)'
