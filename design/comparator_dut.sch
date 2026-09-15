v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} -400 0 0 0 {name=P1 lab=vinp}
C {devices/iopin.sym} -400 40 0 0 {name=P2 lab=vinn}
C {devices/iopin.sym} -400 80 0 0 {name=P3 lab=clk}
C {devices/iopin.sym} -400 120 0 0 {name=P4 lab=ibias}
C {devices/iopin.sym} -400 160 0 0 {name=P5 lab=dout}
C {devices/iopin.sym} -400 200 0 0 {name=P6 lab=doutb}
C {devices/iopin.sym} -400 240 0 0 {name=P7 lab=vdd}
C {devices/iopin.sym} -400 280 0 0 {name=P8 lab=vss}
T {comparator_dut -- tail-bias reference + StrongARM core (sim/dut/README.md contract)} -400 -80 0 0 0.6 0.6 {}
C {sg13g2_pr/sg13_lv_nmos.sym} 0 200 0 0 {name=MB model=sg13_lv_nmos w=10u l=0.5u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 20 170 2 0 {name=MB_d lab=ibias}
C {devices/lab_pin.sym} -20 200 0 0 {name=MB_g lab=ibias}
C {devices/lab_pin.sym} 20 230 2 0 {name=MB_s lab=vss}
C {devices/lab_pin.sym} 20 200 2 0 {name=MB_b lab=vss}
C {comparator.sym} 200 500 0 0 {name=x1}
C {devices/lab_pin.sym} 150 430 0 0 {name=x1_vinp lab=vinp}
C {devices/lab_pin.sym} 150 450 0 0 {name=x1_vinn lab=vinn}
C {devices/lab_pin.sym} 150 470 0 0 {name=x1_clk lab=clk}
C {devices/lab_pin.sym} 150 490 0 0 {name=x1_vbias lab=ibias}
C {devices/lab_pin.sym} 150 510 0 0 {name=x1_dout lab=dout}
C {devices/lab_pin.sym} 150 530 0 0 {name=x1_doutb lab=doutb}
C {devices/lab_pin.sym} 150 550 0 0 {name=x1_vdd lab=vdd}
C {devices/lab_pin.sym} 150 570 0 0 {name=x1_vss lab=vss}
