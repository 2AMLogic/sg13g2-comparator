"""Tests for design/netlist.py (issues #117, #489).

stdlib only. ``_run_klt_netlist`` is always mocked in the build/contract
tests: klt, xschem and the PDK are never needed there. The fixture netlist
is built from the harness's own REQUIRED_SUBCKTS so the test cannot drift
from the pin-order contract. ``TestRunKltNetlist`` mocks the ``subprocess``
boundary to exercise the real ``klt netlist`` command shape and its failure
paths -- still no klt, xschem or PDK required.
"""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "netlist.py"
spec = importlib.util.spec_from_file_location("netlist_under_test", SCRIPT)
nl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nl)


def block(name, pins, extra=""):
    return [f".subckt {name} {' '.join(pins)}{extra}", "R1 a b 1k", f".ends {name}"]


def fixture_text(skip=(), swap=None, extra_blocks=(), forbidden_line=None):
    lines = ["** sch_path: top.sch", "**.subckt top", "* expanding symbol: x"]
    pins_by = dict(nl.REQUIRED_SUBCKTS)
    pins_by.setdefault("comparator", ("a", "b"))
    for name in reversed(nl.SUBCKT_ORDER):  # deliberately not the output order
        if name in skip:
            continue
        pins = pins_by[name]
        if swap == name:
            pins = (pins[1], pins[0]) + tuple(pins[2:])
        lines += block(name, pins)
        if forbidden_line and name == "comparator":
            lines.insert(-1, forbidden_line)
    for extra in extra_blocks:
        lines += block(extra, ("p", "q"))
    lines += ["**.ends", ".end"]
    return "\n".join(lines) + "\n"


def build_from(text):
    with mock.patch.object(nl, "_run_klt_netlist", return_value=text):
        return nl.build()


class TestExtract(unittest.TestCase):
    def test_unterminated_block(self):
        with self.assertRaises(SystemExit) as cm:
            nl._extract_subckts(".subckt foo a b\nR1 a b 1\n")
        self.assertIn("unterminated", str(cm.exception))

    def test_outside_text_dropped_and_ends_closes(self):
        text = "\n".join([
            "** banner", "**.subckt top a", "X1 a b foo", ".end",
            ".subckt foo a b", "R1 a b 1", ".ends", "R9 junk 0 1", "**.ends",
        ])
        blocks = nl._extract_subckts(text)
        self.assertEqual(list(blocks), ["foo"])
        self.assertEqual(blocks["foo"], [".subckt foo a b", "R1 a b 1", ".ends"])

    def test_names_keyed_correctly(self):
        text = ".subckt a x\n.ends\n.subckt b y\n.ends\n"
        self.assertEqual(sorted(nl._extract_subckts(text)), ["a", "b"])


class TestContract(unittest.TestCase):
    def good_blocks(self):
        return {n: block(n, p) for n, p in nl.REQUIRED_SUBCKTS.items()}

    def test_good_passes(self):
        nl._assert_contract(self.good_blocks())

    def test_missing_subckt_named(self):
        b = self.good_blocks()
        victim = sorted(b)[0]
        del b[victim]
        with self.assertRaises(SystemExit) as cm:
            nl._assert_contract(b)
        self.assertIn(victim, str(cm.exception))

    def test_wrong_pin_order(self):
        b = self.good_blocks()
        name = "comparator_dut"
        pins = nl.REQUIRED_SUBCKTS[name]
        b[name] = block(name, (pins[1], pins[0]) + tuple(pins[2:]))
        with self.assertRaises(SystemExit) as cm:
            nl._assert_contract(b)
        self.assertIn("pin order", str(cm.exception))

    def test_params_ignored_in_pin_compare(self):
        b = self.good_blocks()
        name = "comparator_dut"
        b[name] = block(name, nl.REQUIRED_SUBCKTS[name], extra=" w=1u l=0.13u")
        nl._assert_contract(b)


class TestForbidden(unittest.TestCase):
    def test_each_forbidden_rejected(self):
        for tok in nl.FORBIDDEN:
            with self.subTest(tok=tok):
                with self.assertRaises(SystemExit):
                    nl._assert_no_forbidden(["R1 a b 1", f"  {tok.upper()} foo"])

    def test_ends_and_param_allowed(self):
        nl._assert_no_forbidden([".ends foo", ".param x=1", "* .end comment"])

    def test_forbidden_set_is_expected(self):
        self.assertEqual(set(nl.FORBIDDEN),
                         {".control", ".endc", ".end", ".lib", ".temp", ".include"})


class TestBuild(unittest.TestCase):
    def test_order_header_and_trailing_newline(self):
        out = build_from(fixture_text())
        self.assertTrue(out.startswith(nl.HEADER))
        self.assertTrue(out.endswith("\n"))
        self.assertFalse(out.endswith("\n\n"))
        names = [l.split()[1] for l in out.splitlines() if l.startswith(".subckt ")]
        self.assertEqual(names, list(nl.SUBCKT_ORDER))
        self.assertNotIn("\n.end\n", out)

    def test_deterministic(self):
        text = fixture_text()
        self.assertEqual(build_from(text), build_from(text))

    def test_independent_of_tempdir_name(self):
        seen = []

        def fake(outdir):
            seen.append(str(outdir))
            return fixture_text()

        with mock.patch.object(nl, "_run_klt_netlist", side_effect=fake):
            a, b = nl.build(), nl.build()
        self.assertNotEqual(seen[0], seen[1])
        self.assertEqual(a, b)

    def test_unexpected_extra_subckt(self):
        with self.assertRaises(SystemExit) as cm:
            build_from(fixture_text(extra_blocks=("rogue",)))
        self.assertIn("rogue", str(cm.exception))

    def test_missing_ordered_subckt(self):
        # "comparator" is in SUBCKT_ORDER but not in REQUIRED_SUBCKTS
        self.assertNotIn("comparator", nl.REQUIRED_SUBCKTS)
        with self.assertRaises(SystemExit) as cm:
            build_from(fixture_text(skip=("comparator",)))
        self.assertIn("missing", str(cm.exception))

    def test_missing_required_subckt(self):
        with self.assertRaises(SystemExit):
            build_from(fixture_text(skip=("comparator_dut",)))

    def test_pin_order_rejected(self):
        with self.assertRaises(SystemExit):
            build_from(fixture_text(swap="comparator_dut_latch"))

    def test_forbidden_inside_block_rejected(self):
        with self.assertRaises(SystemExit):
            build_from(fixture_text(forbidden_line=".include foo.lib"))


class RunResult:
    """Stand-in for subprocess.run's return value."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestRunKltNetlist(unittest.TestCase):
    """The klt tool boundary, with subprocess.run and _xschemrc mocked."""

    def run_klt(self, result, produced_text=None):
        """Capture the invocation; write `produced_text` to -o on exit 0."""
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs.get("env")
            if produced_text is not None:
                out = cmd[cmd.index("--output") + 1]
                Path(out).write_text(produced_text)
            return result

        with tempfile.TemporaryDirectory() as outdir:
            seen["outdir"] = outdir
            with mock.patch.object(nl.shutil, "which", return_value="/usr/bin/klt"), \
                    mock.patch.object(nl.subprocess, "run", side_effect=fake_run), \
                    mock.patch.object(nl, "_xschemrc",
                                      return_value=Path("/pdk/xschemrc")):
                with contextlib.redirect_stderr(io.StringIO()):
                    nl._run_klt_netlist(Path(outdir))
        return seen

    def test_command_shape(self):
        seen = self.run_klt(RunResult(), produced_text="netlist\n")
        cmd = seen["cmd"]
        self.assertEqual(cmd[0:2], ["klt", "netlist"])
        for flag in ("--rcfile", "--symbol-path", "--timeout-s",
                     "--no-provenance-header", "--output"):
            self.assertIn(flag, cmd, f"missing {flag}")
        self.assertEqual(cmd[cmd.index("--rcfile") + 1], "/pdk/xschemrc")
        self.assertEqual(cmd[cmd.index("--symbol-path") + 1], str(nl.DESIGN_DIR))
        self.assertEqual(cmd[cmd.index("--timeout-s") + 1], str(nl.KLT_TIMEOUT_S))
        self.assertEqual(cmd[-1], str(nl.TOP_CELL))
        # output lands inside the caller's temp dir, not the repo
        out = Path(cmd[cmd.index("--output") + 1])
        self.assertEqual(str(out.parent), seen["outdir"])

    def test_no_ambient_user_library_leaks_into_child_env(self):
        # Seed the parent environment so a filter regression is observable.
        with mock.patch.dict(os.environ, {"XSCHEM_USER_LIBRARY_PATH": "/ambient/sentinel"}):
            seen = self.run_klt(RunResult(), produced_text="netlist\n")
        env = seen["env"]
        self.assertIsNotNone(env)
        self.assertNotIn("XSCHEM_USER_LIBRARY_PATH", env)
        # the rest of the ambient environment is passed through
        for key in ("PATH", "HOME"):
            self.assertIn(key, env)

    def test_klt_failure_dumps_output_and_raises(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_klt(RunResult(returncode=7, stdout="boom-out", stderr="boom-err"))
        self.assertIn("klt netlist failed", str(cm.exception))
        self.assertIn("exit 7", str(cm.exception))

    def test_missing_output_file_is_a_failure(self):
        # exit 0 but no freshly written netlist: klt's contract broken
        with self.assertRaises(SystemExit) as cm:
            self.run_klt(RunResult(returncode=0))
        msg = str(cm.exception)
        self.assertIn("exited 0 but did not write the expected output file", msg)
        self.assertIn("missing netlist", msg)
        self.assertIn(nl.TOP_CELL.stem + ".spice", msg)

    def test_missing_tool(self):
        with mock.patch.object(nl.shutil, "which", return_value=None):
            with self.assertRaises(SystemExit) as cm:
                nl._run_klt_netlist(Path("/nonexistent"))
        self.assertIn("klt not found", str(cm.exception))
        self.assertIn("klt-pin.json", str(cm.exception))


class TestMainCheck(unittest.TestCase):
    def run_check(self, existing, generated):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "comparator.spice"
            if existing is not None:
                out.write_text(existing)
            o, e = io.StringIO(), io.StringIO()
            with mock.patch.object(nl, "OUTPUT", out), \
                    mock.patch.object(nl, "REPO_ROOT", root), \
                    mock.patch.object(nl, "build", return_value=generated), \
                    mock.patch("sys.argv", ["netlist.py", "--check"]), \
                    contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = nl.main()
            return rc, o.getvalue(), e.getvalue()

    def test_up_to_date(self):
        rc, out, _ = self.run_check("x\n", "x\n")
        self.assertEqual(rc, 0)
        self.assertIn("up to date", out)

    def test_stale(self):
        rc, _, err = self.run_check("old\n", "new\n")
        self.assertEqual(rc, 1)
        self.assertIn("stale", err)

    def test_missing_file(self):
        rc, _, err = self.run_check(None, "new\n")
        self.assertEqual(rc, 1)
        self.assertIn("stale", err)


if __name__ == "__main__":
    unittest.main()
