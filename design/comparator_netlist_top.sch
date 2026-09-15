v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
T {NETLIST-ASSEMBLY CELL -- instantiates the three sim/dut/README.md contract
subcircuits so one xschem run emits all of them. design/netlist.sh keeps only
the .subckt blocks; the three instances below are never simulated.} -400 -160 0 0 0.4 0.4 {}
C {comparator_dut.sym} 0 200 0 0 {name=x1}
C {devices/lab_pin.sym} -50 130 0 0 {name=x1_vinp lab=comparator_dut_vinp}
C {devices/lab_pin.sym} -50 150 0 0 {name=x1_vinn lab=comparator_dut_vinn}
C {devices/lab_pin.sym} -50 170 0 0 {name=x1_clk lab=comparator_dut_clk}
C {devices/lab_pin.sym} -50 190 0 0 {name=x1_ibias lab=comparator_dut_ibias}
C {devices/lab_pin.sym} -50 210 0 0 {name=x1_dout lab=comparator_dut_dout}
C {devices/lab_pin.sym} -50 230 0 0 {name=x1_doutb lab=comparator_dut_doutb}
C {devices/lab_pin.sym} -50 250 0 0 {name=x1_vdd lab=comparator_dut_vdd}
C {devices/lab_pin.sym} -50 270 0 0 {name=x1_vss lab=comparator_dut_vss}
C {comparator_dut_analog.sym} 300 200 0 0 {name=x2}
C {devices/lab_pin.sym} 250 140 0 0 {name=x2_vinp lab=comparator_dut_analog_vinp}
C {devices/lab_pin.sym} 250 160 0 0 {name=x2_vinn lab=comparator_dut_analog_vinn}
C {devices/lab_pin.sym} 250 180 0 0 {name=x2_ibias lab=comparator_dut_analog_ibias}
C {devices/lab_pin.sym} 250 200 0 0 {name=x2_aop lab=comparator_dut_analog_aop}
C {devices/lab_pin.sym} 250 220 0 0 {name=x2_aon lab=comparator_dut_analog_aon}
C {devices/lab_pin.sym} 250 240 0 0 {name=x2_vdd lab=comparator_dut_analog_vdd}
C {devices/lab_pin.sym} 250 260 0 0 {name=x2_vss lab=comparator_dut_analog_vss}
C {comparator_dut_latch.sym} 600 200 0 0 {name=x3}
C {devices/lab_pin.sym} 550 140 0 0 {name=x3_inp lab=comparator_dut_latch_inp}
C {devices/lab_pin.sym} 550 160 0 0 {name=x3_inn lab=comparator_dut_latch_inn}
C {devices/lab_pin.sym} 550 180 0 0 {name=x3_clk lab=comparator_dut_latch_clk}
C {devices/lab_pin.sym} 550 200 0 0 {name=x3_dout lab=comparator_dut_latch_dout}
C {devices/lab_pin.sym} 550 220 0 0 {name=x3_doutb lab=comparator_dut_latch_doutb}
C {devices/lab_pin.sym} 550 240 0 0 {name=x3_vdd lab=comparator_dut_latch_vdd}
C {devices/lab_pin.sym} 550 260 0 0 {name=x3_vss lab=comparator_dut_latch_vss}
