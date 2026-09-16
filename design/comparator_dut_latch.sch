v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} -400 0 0 0 {name=P1 lab=inp}
C {devices/iopin.sym} -400 40 0 0 {name=P2 lab=inn}
C {devices/iopin.sym} -400 80 0 0 {name=P3 lab=clk}
C {devices/iopin.sym} -400 120 0 0 {name=P4 lab=dout}
C {devices/iopin.sym} -400 160 0 0 {name=P5 lab=doutb}
C {devices/iopin.sym} -400 200 0 0 {name=P6 lab=vdd}
C {devices/iopin.sym} -400 240 0 0 {name=P7 lab=vss}
T {comparator_dut_latch -- StrongARM core, tail-bias node tied to vdd (see design/README.md)} -400 -80 0 0 0.6 0.6 {}
C {comparator.sym} 200 240 0 0 {name=x1}
C {devices/lab_pin.sym} 150 170 0 0 {name=x1_vinp lab=inp}
C {devices/lab_pin.sym} 150 190 0 0 {name=x1_vinn lab=inn}
C {devices/lab_pin.sym} 150 210 0 0 {name=x1_clk lab=clk}
C {devices/lab_pin.sym} 150 230 0 0 {name=x1_vbias lab=vdd}
C {devices/lab_pin.sym} 150 250 0 0 {name=x1_dout lab=dout}
C {devices/lab_pin.sym} 150 270 0 0 {name=x1_doutb lab=doutb}
C {devices/lab_pin.sym} 150 290 0 0 {name=x1_vdd lab=vdd}
C {devices/lab_pin.sym} 150 310 0 0 {name=x1_vss lab=vss}
