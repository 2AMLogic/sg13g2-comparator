#!/usr/bin/env bash
# One-command layout flow for the comparator (issue #58, T1 item 2).
#
#   layout/run_flow.sh            regenerate layout/comparator/comparator.gds,
#                                 then run every check below against it
#   layout/run_flow.sh --check    leave the committed GDS alone: regenerate into
#                                 a temp dir and require it to be byte-identical
#                                 to the committed one, then run the checks
#
# Stages:
#   1. generate      layout/comparator/generate.py -> comparator.gds. The
#                    generator first reconciles its device table with the
#                    `.subckt comparator` block of design/comparator.spice
#                    (24 devices, LV flavour, nets, W, L, pins, matched-pair
#                    geometry) and refuses to draw on any disagreement.
#   2. reproduce     generate a second time from scratch into a temp dir;
#                    the two streams must be byte-identical (`cmp`).
#   3. stream        layout/comparator/check_stream.py: one top cell named
#                    `comparator`, non-empty, all eight ports pinned on Metal3,
#                    no host paths, boxes only.
#   4. connectivity  `klt extract --deck sg13g2` + `klt lvs` against the
#                    schematic. A SELF-CHECK of the generator, written only to
#                    a temp dir -- it is not the LVS signoff evidence of issue
#                    #60, and nothing from it is committed.
#   5. controls      two mutated references (one topology, one W) that MUST
#                    mismatch, so a `match` in stage 4 is known to mean
#                    something.
#   6. drc           `klt drc --deck sg13g2 --top comparator` on the GDS, run
#                    from the repo root with the repo-relative path so the
#                    envelope records no host path. Writes the COMMITTED
#                    layout/comparator/drc_report.json (issue #59, T1 item 3);
#                    with --check, instead requires the committed envelope to
#                    be fresh (`klt drc --check`) and `status: clean`. The
#                    deck's coverage gaps are printed, and are quoted in
#                    manifests/README.md.
#
# Tooling: everything runs on the klayout-tools build this repo pins (see
# manifests/README.md and .github/workflows/ci.yml), and on the KLayout
# Python module that build installs; no PDK install is read. By default the
# pinned build is fetched into an isolated uv cache via `uvx`; set
# KLT_NATIVE=1 to use `python3`/`klt` from PATH instead (CI does, after
# `pip install`-ing the same pin).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
CELL_DIR="${HERE}/comparator"
GDS="${CELL_DIR}/comparator.gds"
TOP="comparator"
PORTS="vinp,vinn,clk,vbias,dout,doutb,vdd,vss"

KLT_PIN="e8ca621a6961879cec1af60cc932c3b3d58ddcaa"
KLAYOUT_PIN="0.30.10"  # the KLayout this klt build was tested against

MODE="run"
case "${1:-}" in
  "") ;;
  --check) MODE="check" ;;
  -h|--help) sed -n '2,45p' "${BASH_SOURCE[0]}"; exit 0 ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

if [[ "${KLT_NATIVE:-0}" == "1" ]]; then
  PY=(python3)
  KLT=(klt)
else
  command -v uvx >/dev/null || {
    echo "uvx not found: install uv, or set KLT_NATIVE=1 with the pinned klt on PATH" >&2
    exit 1
  }
  SRC="klayout-tools @ git+https://github.com/2AMLogic/klayout-tools@${KLT_PIN}"
  PY=(uvx --quiet --with "klayout==${KLAYOUT_PIN}" --from "${SRC}" python)
  KLT=(uvx --quiet --with "klayout==${KLAYOUT_PIN}" --from "${SRC}" klt)
fi

say() { printf '\n=== %s\n' "$*"; }

say "tools"
echo "  klt: $("${KLT[@]}" --version)"
echo "  klayout: $("${PY[@]}" -c 'import klayout.db as k; print(k.__version__)' 2>/dev/null || echo unknown)"

say "1. generate"
if [[ "${MODE}" == "check" ]]; then
  "${PY[@]}" "${CELL_DIR}/generate.py" -o "${WORK}/first.gds"
  cmp "${WORK}/first.gds" "${GDS}" || {
    echo "  FAIL: regenerated stream differs from the committed ${GDS#"${REPO}/"}" >&2
    echo "        run layout/run_flow.sh (no --check) and commit the result" >&2
    exit 1
  }
  echo "  committed ${GDS#"${REPO}/"} reproduces byte-for-byte"
  TARGET="${GDS}"
else
  "${PY[@]}" "${CELL_DIR}/generate.py" -o "${GDS}"
  TARGET="${GDS}"
fi

say "2. reproduce"
"${PY[@]}" "${CELL_DIR}/generate.py" -o "${WORK}/second.gds" > /dev/null
cmp "${WORK}/second.gds" "${TARGET}"
echo "  two independent runs are byte-identical ($(sha256sum "${TARGET}" | cut -c1-16)...)"

say "3. stream"
"${PY[@]}" "${CELL_DIR}/check_stream.py" "${TARGET}"

say "4. connectivity self-check (klt extract + klt lvs; temp dir only)"
"${KLT[@]}" extract --deck sg13g2 --top "${TOP}" --pins "${PORTS}" \
  -o "${WORK}/extracted.spice" --format json "${TARGET}" > "${WORK}/extract.json"
# Workaround for 2AMLogic/klayout-tools#2852: `klt lvs` crashes when the
# reference file also holds subcircuits that instantiate the selected top
# (design/comparator.spice does: comparator_dut, comparator_dut_latch). Cut
# the one `.subckt comparator ... .ends` block into its own file.
awk '/^\.subckt comparator /{on=1} on{print} on && /^\.ends/{exit}' \
  "${REPO}/design/comparator.spice" > "${WORK}/reference.spice"
cat > "${WORK}/lvs_request.json" <<EOF
{"schema": "klt.lvs.request/1", "engine": "klayout",
 "layout": {"netlist": "${WORK}/extracted.spice", "top": "${TOP}"},
 "reference": {"netlist": "${WORK}/reference.spice", "top": "${TOP}",
               "form": "subckt-call", "deck": "sg13g2"},
 "options": {"combine_devices": true}}
EOF
"${KLT[@]}" lvs "${WORK}/lvs_request.json" --format json > "${WORK}/lvs.json" 2> "${WORK}/lvs.err" || true
"${PY[@]}" - "${WORK}/extract.json" "${WORK}/lvs.json" "${WORK}/lvs.err" <<'PY'
import json, pathlib, sys
ext = json.load(open(sys.argv[1]))
raw = pathlib.Path(sys.argv[2]).read_text()
if not raw.strip():
    print("  FAIL: klt lvs produced no report:\n" + pathlib.Path(sys.argv[3]).read_text(), file=sys.stderr)
    sys.exit(1)
lvs = json.loads(raw)
print(f"  extracted fingers: {ext['device_counts']}")
print(f"  lvs status: {lvs['status']}  counts: {lvs.get('counts')}")
for m in lvs.get("mismatches", []):
    print(f"    {m['severity']}: {m['category']}: {m['description']}")
sys.exit(0 if lvs["status"] == "match" else 1)
PY

say "5. connectivity negative controls (each mutated reference MUST mismatch)"
control() {  # <name> <sed expression> <what it breaks>
  local name="$1" expr="$2" what="$3"
  sed "${expr}" "${WORK}/reference.spice" > "${WORK}/${name}.spice"
  if cmp -s "${WORK}/reference.spice" "${WORK}/${name}.spice"; then
    echo "  ${name}: mutation did not change the reference -- control is void" >&2
    exit 1
  fi
  sed "s#${WORK}/reference.spice#${WORK}/${name}.spice#" "${WORK}/lvs_request.json" \
    > "${WORK}/${name}.json"
  "${KLT[@]}" lvs "${WORK}/${name}.json" --format json > "${WORK}/${name}.out" 2>/dev/null || true
  "${PY[@]}" - "${WORK}/${name}.out" "${name}" "${what}" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
cats = sorted({m["category"] for m in d.get("mismatches", []) if m["severity"] == "error"})
print(f"  {sys.argv[2]} ({sys.argv[3]}): status={d['status']} {cats}")
sys.exit(0 if d["status"] != "match" else 1)
PY
}
# Topology: rewire one latch device's gate. Nothing in the drawn geometry
# changes -- only the reference's claim about it.
control topology-control 's/^XM3 ln lp np vss/XM3 ln ln np vss/' "M3 gate lp -> ln"
# Parameter: input-device W 12u -> 11.5u, less than one 3u finger, so a
# compare that tolerated or mis-summed fingers would not see it.
control parameter-control \
  's/^XM1 np vinp tail vss sg13_lv_nmos w=12u/XM1 np vinp tail vss sg13_lv_nmos w=11.5u/' \
  "M1 W 12u -> 11.5u"


say "6. drc (klt drc --deck sg13g2; T1 item 3 evidence)"
REPORT="${CELL_DIR}/drc_report.json"
REL_GDS="${GDS#"${REPO}/"}"
REL_REPORT="${REPORT#"${REPO}/"}"
cd "${REPO}"  # klt records the input path as given: keep it repo-relative
if [[ "${MODE}" == "check" ]]; then
  "${KLT[@]}" drc --check "${REL_REPORT}" > /dev/null
  echo "  committed ${REL_REPORT} is fresh for ${REL_GDS}"
else
  # exit 3 = violations found; the report is still written, then judged below
  "${KLT[@]}" drc --deck sg13g2 --top "${TOP}" --format json "${REL_GDS}" \
    > "${WORK}/drc_report.json" || [[ $? -eq 3 ]]
  cp "${WORK}/drc_report.json" "${REPORT}"
fi
"${PY[@]}" - "${REPORT}" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d["coverage"]
print(f"  status: {d['status']}  violations: {d['violation_count']}  deck: {d['provenance']['deck']['content_hash'][:23]}...")
print(f"  rules checked: {len(c['rules_checked'])}  skipped: {len(c['rules_skipped'])}")
print(f"  layers in stream without rules: {', '.join(c['layers_in_stream_without_rules'])}")
if d["file"].startswith("/"):
    print(f"  FAIL: envelope embeds a host-absolute path: {d['file']}", file=sys.stderr); sys.exit(1)
sys.exit(0 if d["status"] == "clean" else 1)
PY

say "done (${MODE})"
