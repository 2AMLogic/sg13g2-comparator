v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} -400 0 0 0 {name=P1 lab=vinp}
C {devices/iopin.sym} -400 40 0 0 {name=P2 lab=vinn}
C {devices/iopin.sym} -400 80 0 0 {name=P3 lab=clk}
C {devices/iopin.sym} -400 120 0 0 {name=P4 lab=vbias}
C {devices/iopin.sym} -400 160 0 0 {name=P5 lab=dout}
C {devices/iopin.sym} -400 200 0 0 {name=P6 lab=doutb}
C {devices/iopin.sym} -400 240 0 0 {name=P7 lab=vdd}
C {devices/iopin.sym} -400 280 0 0 {name=P8 lab=vss}
T {comparator -- single-tail StrongARM latch + isolation inverters + NOR SR output latch (DR-0001)} -400 -80 0 0 0.6 0.6 {}
C {sg13g2_pr/sg13_lv_nmos.sym} 0 200 0 0 {name=MT model=sg13_lv_nmos w=40u l=0.5u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 20 170 2 0 {name=MT_d lab=tmid}
C {devices/lab_pin.sym} -20 200 0 0 {name=MT_g lab=vbias}
C {devices/lab_pin.sym} 20 230 2 0 {name=MT_s lab=vss}
C {devices/lab_pin.sym} 20 200 2 0 {name=MT_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 200 200 0 0 {name=MSW model=sg13_lv_nmos w=40u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 220 170 2 0 {name=MSW_d lab=tail}
C {devices/lab_pin.sym} 180 200 0 0 {name=MSW_g lab=clk}
C {devices/lab_pin.sym} 220 230 2 0 {name=MSW_s lab=tmid}
C {devices/lab_pin.sym} 220 200 2 0 {name=MSW_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 400 200 0 0 {name=M1 model=sg13_lv_nmos w=12u l=0.34u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 420 170 2 0 {name=M1_d lab=np}
C {devices/lab_pin.sym} 380 200 0 0 {name=M1_g lab=vinp}
C {devices/lab_pin.sym} 420 230 2 0 {name=M1_s lab=tail}
C {devices/lab_pin.sym} 420 200 2 0 {name=M1_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 600 200 0 0 {name=M2 model=sg13_lv_nmos w=12u l=0.34u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 620 170 2 0 {name=M2_d lab=nn}
C {devices/lab_pin.sym} 580 200 0 0 {name=M2_g lab=vinn}
C {devices/lab_pin.sym} 620 230 2 0 {name=M2_s lab=tail}
C {devices/lab_pin.sym} 620 200 2 0 {name=M2_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 800 200 0 0 {name=M3 model=sg13_lv_nmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 820 170 2 0 {name=M3_d lab=ln}
C {devices/lab_pin.sym} 780 200 0 0 {name=M3_g lab=lp}
C {devices/lab_pin.sym} 820 230 2 0 {name=M3_s lab=np}
C {devices/lab_pin.sym} 820 200 2 0 {name=M3_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 1000 200 0 0 {name=M4 model=sg13_lv_nmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1020 170 2 0 {name=M4_d lab=lp}
C {devices/lab_pin.sym} 980 200 0 0 {name=M4_g lab=ln}
C {devices/lab_pin.sym} 1020 230 2 0 {name=M4_s lab=nn}
C {devices/lab_pin.sym} 1020 200 2 0 {name=M4_b lab=vss}
C {sg13g2_pr/sg13_lv_pmos.sym} 1200 200 0 0 {name=M5 model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1220 230 2 0 {name=M5_d lab=ln}
C {devices/lab_pin.sym} 1180 200 0 0 {name=M5_g lab=lp}
C {devices/lab_pin.sym} 1220 170 2 0 {name=M5_s lab=vdd}
C {devices/lab_pin.sym} 1220 200 2 0 {name=M5_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 1400 200 0 0 {name=M6 model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1420 230 2 0 {name=M6_d lab=lp}
C {devices/lab_pin.sym} 1380 200 0 0 {name=M6_g lab=ln}
C {devices/lab_pin.sym} 1420 170 2 0 {name=M6_s lab=vdd}
C {devices/lab_pin.sym} 1420 200 2 0 {name=M6_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 0 460 0 0 {name=M7 model=sg13_lv_pmos w=6u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 20 490 2 0 {name=M7_d lab=ln}
C {devices/lab_pin.sym} -20 460 0 0 {name=M7_g lab=clk}
C {devices/lab_pin.sym} 20 430 2 0 {name=M7_s lab=vdd}
C {devices/lab_pin.sym} 20 460 2 0 {name=M7_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 200 460 0 0 {name=M8 model=sg13_lv_pmos w=6u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 220 490 2 0 {name=M8_d lab=lp}
C {devices/lab_pin.sym} 180 460 0 0 {name=M8_g lab=clk}
C {devices/lab_pin.sym} 220 430 2 0 {name=M8_s lab=vdd}
C {devices/lab_pin.sym} 220 460 2 0 {name=M8_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 400 460 0 0 {name=M9 model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 420 490 2 0 {name=M9_d lab=np}
C {devices/lab_pin.sym} 380 460 0 0 {name=M9_g lab=clk}
C {devices/lab_pin.sym} 420 430 2 0 {name=M9_s lab=vdd}
C {devices/lab_pin.sym} 420 460 2 0 {name=M9_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 600 460 0 0 {name=M10 model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 620 490 2 0 {name=M10_d lab=nn}
C {devices/lab_pin.sym} 580 460 0 0 {name=M10_g lab=clk}
C {devices/lab_pin.sym} 620 430 2 0 {name=M10_s lab=vdd}
C {devices/lab_pin.sym} 620 460 2 0 {name=M10_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 800 460 0 0 {name=MIAP model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 820 490 2 0 {name=MIAP_d lab=lnb}
C {devices/lab_pin.sym} 780 460 0 0 {name=MIAP_g lab=ln}
C {devices/lab_pin.sym} 820 430 2 0 {name=MIAP_s lab=vdd}
C {devices/lab_pin.sym} 820 460 2 0 {name=MIAP_b lab=vdd}
C {sg13g2_pr/sg13_lv_nmos.sym} 1000 460 0 0 {name=MIAN model=sg13_lv_nmos w=1.5u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1020 430 2 0 {name=MIAN_d lab=lnb}
C {devices/lab_pin.sym} 980 460 0 0 {name=MIAN_g lab=ln}
C {devices/lab_pin.sym} 1020 490 2 0 {name=MIAN_s lab=vss}
C {devices/lab_pin.sym} 1020 460 2 0 {name=MIAN_b lab=vss}
C {sg13g2_pr/sg13_lv_pmos.sym} 1200 460 0 0 {name=MIBP model=sg13_lv_pmos w=3u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1220 490 2 0 {name=MIBP_d lab=lpb}
C {devices/lab_pin.sym} 1180 460 0 0 {name=MIBP_g lab=lp}
C {devices/lab_pin.sym} 1220 430 2 0 {name=MIBP_s lab=vdd}
C {devices/lab_pin.sym} 1220 460 2 0 {name=MIBP_b lab=vdd}
C {sg13g2_pr/sg13_lv_nmos.sym} 1400 460 0 0 {name=MIBN model=sg13_lv_nmos w=1.5u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1420 430 2 0 {name=MIBN_d lab=lpb}
C {devices/lab_pin.sym} 1380 460 0 0 {name=MIBN_g lab=lp}
C {devices/lab_pin.sym} 1420 490 2 0 {name=MIBN_s lab=vss}
C {devices/lab_pin.sym} 1420 460 2 0 {name=MIBN_b lab=vss}
C {sg13g2_pr/sg13_lv_pmos.sym} 0 720 0 0 {name=MNAP1 model=sg13_lv_pmos w=4u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 20 750 2 0 {name=MNAP1_d lab=na}
C {devices/lab_pin.sym} -20 720 0 0 {name=MNAP1_g lab=lnb}
C {devices/lab_pin.sym} 20 690 2 0 {name=MNAP1_s lab=vdd}
C {devices/lab_pin.sym} 20 720 2 0 {name=MNAP1_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 200 720 0 0 {name=MNAP2 model=sg13_lv_pmos w=4u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 220 750 2 0 {name=MNAP2_d lab=doutb}
C {devices/lab_pin.sym} 180 720 0 0 {name=MNAP2_g lab=dout}
C {devices/lab_pin.sym} 220 690 2 0 {name=MNAP2_s lab=na}
C {devices/lab_pin.sym} 220 720 2 0 {name=MNAP2_b lab=vdd}
C {sg13g2_pr/sg13_lv_nmos.sym} 400 720 0 0 {name=MNAN1 model=sg13_lv_nmos w=1.5u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 420 690 2 0 {name=MNAN1_d lab=doutb}
C {devices/lab_pin.sym} 380 720 0 0 {name=MNAN1_g lab=lnb}
C {devices/lab_pin.sym} 420 750 2 0 {name=MNAN1_s lab=vss}
C {devices/lab_pin.sym} 420 720 2 0 {name=MNAN1_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 600 720 0 0 {name=MNAN2 model=sg13_lv_nmos w=1.5u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 620 690 2 0 {name=MNAN2_d lab=doutb}
C {devices/lab_pin.sym} 580 720 0 0 {name=MNAN2_g lab=dout}
C {devices/lab_pin.sym} 620 750 2 0 {name=MNAN2_s lab=vss}
C {devices/lab_pin.sym} 620 720 2 0 {name=MNAN2_b lab=vss}
C {sg13g2_pr/sg13_lv_pmos.sym} 800 720 0 0 {name=MNBP1 model=sg13_lv_pmos w=4u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 820 750 2 0 {name=MNBP1_d lab=nb}
C {devices/lab_pin.sym} 780 720 0 0 {name=MNBP1_g lab=lpb}
C {devices/lab_pin.sym} 820 690 2 0 {name=MNBP1_s lab=vdd}
C {devices/lab_pin.sym} 820 720 2 0 {name=MNBP1_b lab=vdd}
C {sg13g2_pr/sg13_lv_pmos.sym} 1000 720 0 0 {name=MNBP2 model=sg13_lv_pmos w=4u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1020 750 2 0 {name=MNBP2_d lab=dout}
C {devices/lab_pin.sym} 980 720 0 0 {name=MNBP2_g lab=doutb}
C {devices/lab_pin.sym} 1020 690 2 0 {name=MNBP2_s lab=nb}
C {devices/lab_pin.sym} 1020 720 2 0 {name=MNBP2_b lab=vdd}
C {sg13g2_pr/sg13_lv_nmos.sym} 1200 720 0 0 {name=MNBN1 model=sg13_lv_nmos w=1.5u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1220 690 2 0 {name=MNBN1_d lab=dout}
C {devices/lab_pin.sym} 1180 720 0 0 {name=MNBN1_g lab=lpb}
C {devices/lab_pin.sym} 1220 750 2 0 {name=MNBN1_s lab=vss}
C {devices/lab_pin.sym} 1220 720 2 0 {name=MNBN1_b lab=vss}
C {sg13g2_pr/sg13_lv_nmos.sym} 1400 720 0 0 {name=MNBN2 model=sg13_lv_nmos w=1.5u l=0.13u ng=1 m=1 spiceprefix=X}
C {devices/lab_pin.sym} 1420 690 2 0 {name=MNBN2_d lab=dout}
C {devices/lab_pin.sym} 1380 720 0 0 {name=MNBN2_g lab=doutb}
C {devices/lab_pin.sym} 1420 750 2 0 {name=MNBN2_s lab=vss}
C {devices/lab_pin.sym} 1420 720 2 0 {name=MNBN2_b lab=vss}
