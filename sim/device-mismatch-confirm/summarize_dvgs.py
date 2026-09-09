#!/usr/bin/env python3
"""Summarize a device-mismatch-confirm ngspice `wrdata` CSV.

Usage: summarize_dvgs.py <csv-path>

Prints one markdown-table-row-fragment: "mean | std | min | max" (in volts)
for the dVgs column ngspice's own `wrdata` emits as the third pair of
columns (index, value repeated per vector -- see
testbench/tb_lv_mismatch_pair.spice.tmpl's `wrdata` line: vgs1_arr,
vgs2_arr, dvgs_arr in that order, each as an "index value" column pair).

Pure stdlib -- no third-party dependency, so this stays runnable in the
same sandbox the ngspice run itself uses.
"""
import statistics
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize_dvgs.py <csv-path>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    dvgs = []
    with open(path) as f:
        for line in f:
            fields = line.split()
            if not fields:
                continue
            # wrdata writes N vectors as consecutive (index, value) column
            # pairs on one row per sample: idx1 vgs1 idx2 vgs2 idx3 dvgs.
            if len(fields) < 6:
                continue
            try:
                dvgs.append(float(fields[5]))
            except ValueError:
                continue
    if not dvgs:
        print("nan | nan | nan | nan")
        return 1
    mean = statistics.fmean(dvgs)
    std = statistics.stdev(dvgs) if len(dvgs) > 1 else 0.0
    print(f"{mean:.6e} | {std:.6e} | {min(dvgs):.6e} | {max(dvgs):.6e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
