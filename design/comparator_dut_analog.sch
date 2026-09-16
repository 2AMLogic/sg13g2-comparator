v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} -400 0 0 0 {name=P1 lab=vinp}
C {devices/iopin.sym} -400 40 0 0 {name=P2 lab=vinn}
C {devices/iopin.sym} -400 80 0 0 {name=P3 lab=ibias}
C {devices/iopin.sym} -400 120 0 0 {name=P4 lab=aop}
C {devices/iopin.sym} -400 160 0 0 {name=P5 lab=aon}
C {devices/iopin.sym} -400 200 0 0 {name=P6 lab=vdd}
C {devices/iopin.sym} -400 240 0 0 {name=P7 lab=vss}
T {comparator_dut_analog -- LOOP-BROKEN reduced sub-model, offset/noise LOWER BOUND (design/README.md)} -400 -80 0 0 0.6 0.6 {}
C {sg13g2_pr/sg13_lv_nmos.sym} 0 200 0 0 {name=MBA model=sg13_lv_nmos w=10u l=0.5u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 20 170 2 0 {name=MBA_d lab=ibias}
C {devices/lab_pin.sym} -20 200 0 0 {name=MBA_g lab=ibias}
C {devices/lab_pin.sym} 20 230 2 0 {name=MBA_s lab=vss}
C {devices/lab_pin.sym} 20 200 2 0 {name=MBA_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 200 200 0 0 {name=MTA model=sg13_lv_nmos w=40u l=0.5u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 220 170 2 0 {name=MTA_d lab=tmid}
C {devices/lab_pin.sym} 180 200 0 0 {name=MTA_g lab=ibias}
C {devices/lab_pin.sym} 220 230 2 0 {name=MTA_s lab=vss}
C {devices/lab_pin.sym} 220 200 2 0 {name=MTA_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 400 200 0 0 {name=MSWA model=sg13_lv_nmos w=40u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 420 170 2 0 {name=MSWA_d lab=tail}
C {devices/lab_pin.sym} 380 200 0 0 {name=MSWA_g lab=vdd}
C {devices/lab_pin.sym} 420 230 2 0 {name=MSWA_s lab=tmid}
C {devices/lab_pin.sym} 420 200 2 0 {name=MSWA_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 600 200 0 0 {name=M1A model=sg13_lv_nmos w=12u l=0.34u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 620 170 2 0 {name=M1A_d lab=aon}
C {devices/lab_pin.sym} 580 200 0 0 {name=M1A_g lab=vinp}
C {devices/lab_pin.sym} 620 230 2 0 {name=M1A_s lab=tail}
C {devices/lab_pin.sym} 620 200 2 0 {name=M1A_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 800 200 0 0 {name=M2A model=sg13_lv_nmos w=12u l=0.34u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 820 170 2 0 {name=M2A_d lab=aop}
C {devices/lab_pin.sym} 780 200 0 0 {name=M2A_g lab=vinn}
C {devices/lab_pin.sym} 820 230 2 0 {name=M2A_s lab=tail}
C {devices/lab_pin.sym} 820 200 2 0 {name=M2A_b lab=vss}
C {sg13g2_pr/sg13_lv_pmos.sym} 1000 200 0 0 {name=M5A model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1020 230 2 0 {name=M5A_d lab=aon}
C {devices/lab_pin.sym} 980 200 0 0 {name=M5A_g lab=aon}
C {devices/lab_pin.sym} 1020 170 2 0 {name=M5A_s lab=vdd}
C {devices/lab_pin.sym} 1020 200 2 0 {name=M5A_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 1200 200 0 0 {name=M6A model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1220 230 2 0 {name=M6A_d lab=aop}
C {devices/lab_pin.sym} 1180 200 0 0 {name=M6A_g lab=aop}
C {devices/lab_pin.sym} 1220 170 2 0 {name=M6A_s lab=vdd}
C {devices/lab_pin.sym} 1220 200 2 0 {name=M6A_b lab=vdd}
