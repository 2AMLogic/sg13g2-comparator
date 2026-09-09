#!/usr/bin/env bash
# Cold-start, single-command reproduction of issue #6's finding: do
# SG13G2's LV MOS models carry per-instance local mismatch?
#
# Usage (from a fresh PDK checkout):
#   export PDK_ROOT=/path/to/ihp-open-pdk PDK=ihp-sg13g2   # or let sim/env.sh
#                                                           # auto-detect it
#   ./sim/device-mismatch-confirm/run_mismatch_check.sh
#
# Runs four cases, each an N-run Monte Carlo sweep of a nominally-identical
# device PAIR (see testbench/tb_lv_mismatch_pair.spice.tmpl for the full
# methodology writeup):
#   nmos-mismatch  -- sg13_lv_nmos pair, mos_tt_mismatch corner (per-instance
#                      local mismatch enabled)
#   nmos-negctrl   -- sg13_lv_nmos pair, mos_tt corner (mismatch NOT modelled
#                      at all -- deterministic negative control)
#   pmos-mismatch  -- sg13_lv_pmos pair, mos_tt_mismatch corner
#   pmos-negctrl   -- sg13_lv_pmos pair, mos_tt corner
#
# Writes one raw per-run CSV and one summary record (mean/std of the
# device-to-device Vgs difference) per case under records/, all sharing one
# timestamp-based run id so they can be cross-referenced.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# shellcheck source=/dev/null
source "${REPO_ROOT}/sim/env.sh"

if [[ -z "${PDK_ROOT:-}" || ! -d "${PDK_ROOT}/${PDK}/libs.tech/ngspice" ]]; then
  echo "FATAL: no usable PDK install resolved (see messages above). Aborting." >&2
  exit 1
fi
if [[ ! -f "${SG13G2_OSDI_DIR}/psp103.osdi" ]]; then
  echo "FATAL: ${SG13G2_OSDI_DIR}/psp103.osdi not found -- build it first (see README.md 'Reproducing')." >&2
  exit 1
fi

if ! command -v ngspice >/dev/null 2>&1; then
  echo "FATAL: ngspice not found on PATH." >&2
  exit 1
fi

RUN_ID="$(date -u +%Y%m%d-%H%M%S)"
SEED=1234
NRUNS=30
IBIAS=10u
L=0.45u
W=1.0u

OUT_DIR="${SCRIPT_DIR}/corners/${RUN_ID}"
RECORDS_DIR="${SCRIPT_DIR}/records"
mkdir -p "${OUT_DIR}" "${RECORDS_DIR}"

TEMPLATE="${SCRIPT_DIR}/testbench/tb_lv_mismatch_pair.spice.tmpl"

NGSPICE_VERSION="$(ngspice -v 2>&1 | head -2 | tail -1)"

# render_and_run <case> <device> <mc_suffix> <corner> <isrc1> <isrc2>
render_and_run() {
  local case="$1" device="$2" mc_suffix="$3" corner="$4" isrc1="$5" isrc2="$6"
  local netlist="${OUT_DIR}/${case}.spice"
  local out_csv="${OUT_DIR}/${case}.csv"

  sed \
    -e "s|@@DEVICE@@|${device}|g" \
    -e "s|@@MC_SUFFIX@@|${mc_suffix}|g" \
    -e "s|@@CORNER@@|${corner}|g" \
    -e "s|@@PDK_ROOT@@|${PDK_ROOT}|g" \
    -e "s|@@PDK@@|${PDK}|g" \
    -e "s|@@OSDI_DIR@@|${SG13G2_OSDI_DIR}|g" \
    -e "s|@@SEED@@|${SEED}|g" \
    -e "s|@@NRUNS@@|${NRUNS}|g" \
    -e "s|@@IBIAS@@|${IBIAS}|g" \
    -e "s|@@L@@|${L}|g" \
    -e "s|@@W@@|${W}|g" \
    -e "s|@@ISRC1_LINE@@|${isrc1}|g" \
    -e "s|@@ISRC2_LINE@@|${isrc2}|g" \
    -e "s|@@OUT_CSV@@|${out_csv}|g" \
    "${TEMPLATE}" > "${netlist}"

  echo "=== running ${case} ===" >&2
  ngspice -b "${netlist}" > "${OUT_DIR}/${case}.log" 2>&1 || {
    echo "FATAL: ngspice failed for ${case} -- see ${OUT_DIR}/${case}.log" >&2
    exit 1
  }
  if [[ ! -s "${out_csv}" ]]; then
    echo "FATAL: ${case} produced no output CSV (${out_csv}) -- see ${OUT_DIR}/${case}.log" >&2
    exit 1
  fi
  echo "${case}: wrote ${out_csv}" >&2
}

# NMOS: current pulled from ground into vgsN, back down through the device.
render_and_run "nmos-mismatch" "sg13_lv_nmos" "nmos" "mos_tt_mismatch" \
  "I1 0 vgs1 ${IBIAS}" "I2 0 vgs2 ${IBIAS}"
render_and_run "nmos-negctrl" "sg13_lv_nmos" "nmos" "mos_tt" \
  "I1 0 vgs1 ${IBIAS}" "I2 0 vgs2 ${IBIAS}"

# PMOS: opposite current-source polarity (device sources current INTO
# ground from vgsN) -- confirmed empirically during issue #6's
# investigation to give a physically sensible (nonzero-magnitude,
# negative-going) Vgs; mirrors the polarity flip between this PDK's own
# mc_lv_nmos_cs_loop.sch and mc_lv_pmos_cs_loop.sch isource orientations.
render_and_run "pmos-mismatch" "sg13_lv_pmos" "pmos" "mos_tt_mismatch" \
  "I1 vgs1 0 ${IBIAS}" "I2 vgs2 0 ${IBIAS}"
render_and_run "pmos-negctrl" "sg13_lv_pmos" "pmos" "mos_tt" \
  "I1 vgs1 0 ${IBIAS}" "I2 vgs2 0 ${IBIAS}"

# --- summarize ---------------------------------------------------------
SUMMARY_MD="${RECORDS_DIR}/${RUN_ID}.md"
{
  echo "# Record ${RUN_ID}"
  echo
  echo "- **Experiment**: device-mismatch-confirm (issue #6, gap-to-T1 tracker"
  echo "  #3 item 6, porting-plan next step 2)"
  echo "- **PDK**: \`${PDK}\` at \`${PDK_ROOT}\` -- pinned release: see \`sim/pdk.json\`"
  echo "- **ngspice**: \`${NGSPICE_VERSION}\`"
  echo "- **Seed**: ${SEED} (fixed once per case; ${NRUNS} runs/case via reset-loop re-draw)"
  echo "- **N runs per case**: ${NRUNS}"
  echo "- **Bias fixture**: diode-connected device, Id=${IBIAS}, l=${L} w=${W} ng=1 m=1"
  echo "  (same single-device fixture as this PDK's own"
  echo "  \`libs.tech/xschem/sg13g2_tests/mc_lv_{nmos,pmos}_cs_loop.sch\`,"
  echo "  instantiated twice per netlist to measure the device-pair Vgs"
  echo "  difference dVgs = Vgs(M2) - Vgs(M1))"
  echo
  echo "| case | corner | mean dVgs (V) | std dVgs (V) | min | max |"
  echo "|---|---|---|---|---|---|"
  for case in nmos-mismatch nmos-negctrl pmos-mismatch pmos-negctrl; do
    stats="$(python3 "${SCRIPT_DIR}/summarize_dvgs.py" "${OUT_DIR}/${case}.csv")"
    corner="mos_tt_mismatch"
    [[ "${case}" == *negctrl ]] && corner="mos_tt"
    echo "| ${case} | ${corner} | ${stats} |"
  done
  echo
  echo "- **Links**:"
  echo "  - Template: \`testbench/tb_lv_mismatch_pair.spice.tmpl\`"
  echo "  - Generated netlists + raw ngspice logs: \`corners/${RUN_ID}/\`"
  echo "  - Per-run raw CSVs: \`corners/${RUN_ID}/*.csv\`"
  echo "- **Timestamp**: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${SUMMARY_MD}"

cp "${OUT_DIR}/nmos-mismatch.csv" "${RECORDS_DIR}/${RUN_ID}-nmos-mismatch.csv"
cp "${OUT_DIR}/nmos-negctrl.csv" "${RECORDS_DIR}/${RUN_ID}-nmos-negctrl.csv"
cp "${OUT_DIR}/pmos-mismatch.csv" "${RECORDS_DIR}/${RUN_ID}-pmos-mismatch.csv"
cp "${OUT_DIR}/pmos-negctrl.csv" "${RECORDS_DIR}/${RUN_ID}-pmos-negctrl.csv"

echo "Wrote summary: ${SUMMARY_MD}" >&2
