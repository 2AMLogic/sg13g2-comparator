"""Regression tests for the issue #92 sizing-study helpers (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import unittest

from kltsim import build, grade, sizesweep
from kltsim.benches import KICKBACK, REGENERATION


class GeometryTests(unittest.TestCase):
    def body(self, **kw):
        return build.compose_body(KICKBACK, build.BATCH_OSDI_DIR, **kw)

    def test_no_override_body_has_no_geometry_marker(self):
        self.assertEqual(build.extract_geometry(self.body()), {})
        self.assertNotIn("GEOMETRY OVERRIDE", self.body())

    def test_override_changes_only_named_instances(self):
        text = self.body(geometry_overrides={"XM1.w": "8u", "XM2.w": "8u"})
        _p, _s, embedded = build.extract_dut_block(text)
        self.assertIn("XM1 np vinp tail vss sg13_lv_nmos w=8u l=0.34u", embedded)
        self.assertIn("XM2 nn vinn tail vss sg13_lv_nmos w=8u l=0.34u", embedded)
        base = build.extract_dut_block(self.body())[2].split("\n")
        new = embedded.split("\n")
        self.assertEqual([a for a, b in zip(base, new) if a != b].__len__(), 2)
        self.assertEqual(build.extract_geometry(text), {"XM1.w": "8u", "XM2.w": "8u"})

    def test_declared_sha_matches_embedded_and_base_is_recorded(self):
        text = self.body(geometry_overrides={"XM1.l": "0.5u"})
        _p, declared, embedded = build.extract_dut_block(text)
        self.assertEqual(declared, hashlib.sha256(embedded.encode()).hexdigest())
        base = build.load_dut_binding()["_netlist_path"].read_bytes()
        self.assertIn(f"base DUT (unmodified) sha256={hashlib.sha256(base).hexdigest()}", text)

    def test_unknown_instance_or_field_refused(self):
        for bad in ({"XNOPE.w": "1u"}, {"XM1.m": "2"}, {"XMBA.w": "1u"}):
            with self.assertRaises(build.BuildError):
                self.body(geometry_overrides=bad)

    def test_parse_geometry(self):
        self.assertEqual(build.parse_geometry(["XM1.w=8u"]), {"XM1.w": "8u"})
        with self.assertRaises(build.BuildError):
            build.parse_geometry(["XM1=8u"])

    def test_grade_accepts_declared_geometry_and_refuses_undeclared_edit(self):
        dut = grade.load_dut_reference() if hasattr(grade, "load_dut_reference") else None
        if dut is None:
            self.skipTest("no DutReference loader")
        text = self.body(geometry_overrides={"XM1.w": "8u"})
        ev = grade.BenchEvidence(name="kickback", body_text=text, envelopes=[])
        self.assertEqual(grade.check_dut(ev, dut), [])
        tampered = text.replace("XM1 np vinp tail vss sg13_lv_nmos w=8u", "XM1 np vinp tail vss sg13_lv_nmos w=9u")
        ev2 = grade.BenchEvidence(name="kickback", body_text=tampered, envelopes=[])
        self.assertTrue(grade.check_dut(ev2, dut))


class ScreenRequestTests(unittest.TestCase):
    def test_screen_grid_contains_binding_corner(self):
        req = build.compose_request(KICKBACK, "k.body.spice", "batch")
        out = json.loads(sizesweep.screen_request((json.dumps(req)).encode()))
        c = out["corners"]
        self.assertIn("mos_ff", c["process"])
        self.assertIn(1.32, c["supply_v"]["vsup"])
        self.assertIn(125, c["temperature_c"])
        self.assertEqual(len(c["process"]) * len(c["supply_v"]["vsup"]) * len(c["temperature_c"]), 18)

    def test_regeneration_screen_keeps_all_supply_keys(self):
        req = build.compose_request(REGENERATION, "r.body.spice", "batch")
        out = json.loads(sizesweep.screen_request(json.dumps(req).encode()))
        self.assertEqual(set(out["corners"]["supply_v"]), set(req["corners"]["supply_v"]))


if __name__ == "__main__":
    unittest.main()
