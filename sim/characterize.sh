#!/usr/bin/env bash
#
# sim/characterize.sh -- THE one-command entry point for this block.
#
# Ported in shape from gf180-comparator/sim/characterize.sh: two modes, one
# campaign per spec row, every campaign run through the same run_corners.py
# harness, a pass/fail summary printed at the end regardless of where a
# failure happened (one bad campaign does not stop the rest -- a reviewer
# gets one full report per invocation instead of bisecting failures one
# re-run at a time).
#
#   sim/characterize.sh smoke
#       One nominal PVT point (tt / 27 C / nominal supply) per campaign,
#       writing NO evidence. Seconds, not minutes -- proof that the whole
#       command surface runs from a clean checkout, nothing more.
#
#   sim/characterize.sh characterize
#       The full PVT campaign behind every spec row: 5 process corners x
#       (-40, 27, 125) C x (1.08, 1.20, 1.32) V = 45 points per campaign.
#       Mints a new, dated, append-only record per campaign under
#       sim/<experiment>/records/ (sim/README.md's format -- a genuinely new
#       record, never an overwrite of one already committed).
#
#   sim/characterize.sh selftest
#       Delegates to sim/selftest.sh -- the harness's own acceptance test,
#       including the sabotaged-corner negative control. This is a DIFFERENT
#       thing from the two modes above: it proves the HARNESS works, not that
#       the circuit does.
#
# Exit status: 0 if every campaign that ran exited 0; otherwise the number of
# failing campaigns.

set -uo pipefail

SIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SIM_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:-}"
case "${MODE}" in
  smoke|characterize) ;;
  selftest) exec "${SIM_DIR}/selftest.sh" ;;
  *)
    echo "usage: $(basename "$0") {smoke|characterize|selftest}" >&2
    echo "  smoke         one nominal point per campaign, writes no evidence (seconds)" >&2
    echo "  characterize  full 45-point PVT campaign, mints sim/ evidence records" >&2
    echo "  selftest      harness acceptance test incl. the sabotage negative control" >&2
    exit 1
    ;;
esac

JOBS="${JOBS:-}"
if [ -z "${JOBS}" ]; then
  JOBS="$(command -v nproc >/dev/null 2>&1 && nproc || echo 4)"
fi

RUNNER=(python3 "${SIM_DIR}/run_corners.py")

# Every campaign names, in its comment, which README.md target-specification
# row it backs. Cross-reference against that table.
#   comparator-offset-mc      -> Offset sigma
#   comparator-preamp-noise   -> Input-referred noise
#   comparator-regeneration   -> Decision time vs. overdrive (+ metastability)
#   comparator-kickback       -> Kickback
CAMPAIGNS=(
  comparator-offset-mc
  comparator-preamp-noise
  comparator-regeneration
  comparator-kickback
)

echo "=============================================================================="
echo "  sg13g2-comparator characterization -- mode=${MODE}  jobs=${JOBS}"
echo "=============================================================================="
"${RUNNER[@]}" --check-env || {
  echo "environment check failed; see sim/README.md 'Cold start'" >&2
  exit 1
}
echo

FAILED=0
declare -a RESULTS=()

for campaign in "${CAMPAIGNS[@]}"; do
  echo
  echo "######################## ${campaign} ########################"
  if [ "${MODE}" = "smoke" ]; then
    # comparator-offset-mc's 200-draw loop measures a Monte-Carlo SIGMA, and
    # SG13G2 ties local mismatch to which mos_*_mismatch corner section is
    # loaded (sim/harness/corners.py) rather than to a separable global
    # switch -- plain `tt` (mismatch OFF) would give this bench a
    # mathematically-zero-variance smoke point, which is a degenerate,
    # not-representative single-point run for it specifically (issue #8;
    # see sim/comparator-offset-mc/testbench/tb.json's evidence.notes for the
    # sqrt()/abs() numerical-precision trap that a zero-variance draw set
    # can otherwise trip). Every other bench is corner-invariant enough for
    # plain `tt` to be a fine quick smoke point.
    smoke_corner="tt"
    if [ "${campaign}" = "comparator-offset-mc" ]; then
      smoke_corner="tt_mismatch"
    fi
    "${RUNNER[@]}" "${campaign}" \
      --corners "${smoke_corner}" --temps 27 --supply-tolerance 0 --no-write -j 1
  else
    "${RUNNER[@]}" "${campaign}" -j "${JOBS}"
  fi
  status=$?
  if [ "${status}" -eq 0 ]; then
    RESULTS+=("PASS  ${campaign}")
  else
    RESULTS+=("FAIL  ${campaign}  (exit ${status})")
    FAILED=$((FAILED + 1))
  fi
done

echo
echo "=============================================================================="
echo "  SUMMARY (${MODE})"
for line in "${RESULTS[@]}"; do
  echo "    ${line}"
done
echo "  ${FAILED} of ${#CAMPAIGNS[@]} campaigns failed"
echo "=============================================================================="
exit "${FAILED}"
