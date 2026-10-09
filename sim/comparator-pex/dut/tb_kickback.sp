* kickback: klt-pex body derived from sim/comparator-kickback/testbench/ by make_testbenches.py
* Stimulus/probe lines are verbatim from the original fragment.
.include comparator.schematic.sp
.param vdd_val=1.2
.param dut_ib=2e-05
.param dut_vcm=0.6
.options reltol=1e-4 vntol=1e-9 abstol=1e-15 chgtol=1e-16
* comparator_dut wrapper (design/comparator.spice): bias mirror + the core cell.
* The mirror XMB is NOT in the layout; it is the same device on both legs.
.subckt comparator_dut vinp vinn clk ibias dout doutb vdd vss
XMB ibias ibias vss vss sg13_lv_nmos w=10u l=0.5u ng=1 m=1
x1 clk dout doutb ibias vdd vinn vinp vss comparator
.ends comparator_dut
.param rsrc=1k
.param cin=100f
.param rfloat=1G
.param cfloat=1p
.param dv_small=1m
.param dv_big=100m
.param t_pre=29n
.param t_post=55n
vsup vdd 0 dc {vdd_val}
vcm  cm 0 dc {dut_vcm}
vclk clk 0 pulse(0 {vdd_val} 30n 100p 100p 10n 30n)
vsa  sa 0 dc {dv_small}
Easp asp cm sa 0 0.5
Easn asn cm sa 0 -0.5
Rap  asp apa {rsrc}
Ran  asn ana {rsrc}
Cap  apa 0 {cin}
Can  ana 0 {cin}
iba  vdd ibna dc {dut_ib}
Xa   apa ana clk ibna douta doutba vdd 0 comparator_dut
vsb  sb 0 dc {dv_small}
Ebsp bsp cm sb 0 0.5
Ebsn bsn cm sb 0 -0.5
Rbp  bsp bpp {rfloat}
Rbn  bsn bpn {rfloat}
Cbp  bpp 0 {cfloat}
Cbn  bpn 0 {cfloat}
ibb  vdd ibnb dc {dut_ib}
Xb   bpp bpn clk ibnb doutb doutbb vdd 0 comparator_dut
vsc  sc 0 dc {dv_big}
Ecsp csp cm sc 0 0.5
Ecsn csn cm sc 0 -0.5
Rcp  csp cpp {rfloat}
Rcn  csn cpn {rfloat}
Ccp  cpp 0 {cfloat}
Ccn  cpn 0 {cfloat}
ibc  vdd ibnc dc {dut_ib}
Xc   cpp cpn clk ibnc doutc doutbc vdd 0 comparator_dut
Bad ad 0 v = 'v(apa)-v(asp)'
Bbd bd 0 v = 'v(bpp)-v(bpn)'
Bcd cd 0 v = 'v(cpp)-v(cpn)'
Bbc bc 0 v = '(v(bpp)+v(bpn))/2-v(cm)'
Bdan dan 0 v = 'v(douta)/v(vdd)'
Bdbn dbn 0 v = 'v(doutb)/v(vdd)'
Bdcn dcn 0 v = 'v(doutc)/v(vdd)'
