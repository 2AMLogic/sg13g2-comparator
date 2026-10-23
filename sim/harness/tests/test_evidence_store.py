"""Issue #318: the evidence writer stores bytes through ``klt artifact put``
and commits only a manifest and a summary. Every failure is fail closed.

Stdlib only. ``klt`` is emulated by an injected ``run`` (the writer's only
contact with it is argv + exit status + the manifest file it merges into), and
the broker probe runs against a throwaway local HTTP server.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from harness import evidence_store as es

REPO = "owner/repo"


def fake_klt(store: dict, *, fail=None, corrupt=False):
    """Emulate ``klt artifact put FILE --name N --manifest M --format json``."""

    def run(cmd, **kw):
        assert cmd[:3] == ["klt", "artifact", "put"], cmd
        path, name, manifest = cmd[3], cmd[cmd.index("--name") + 1], cmd[cmd.index("--manifest") + 1]
        assert "--broker" not in cmd  # the broker URL never goes in argv
        if fail is not None:
            err = {"schema_version": 1, "error": {"command": "artifact put",
                                                  "message": "cannot reach the artifact broker",
                                                  "code": fail}}
            return subprocess.CompletedProcess(cmd, 1, "", json.dumps(err))
        data = Path(path).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        store[sha] = data
        entry = {"sha256": "0" * 64 if corrupt else sha, "size": len(data), "kind": "evidence",
                 "producer": {"tool": "klt", "version": "t", "loom.repo": REPO, "commit": None},
                 "uri": f"s3://bucket/evidence/owner__repo/{sha[:2]}/{'0' * 64 if corrupt else sha}",
                 "name": name}
        p = Path(manifest)
        m = json.loads(p.read_text()) if p.exists() else {"schema_version": 1, "entries": []}
        m["entries"].append(entry)
        p.write_text(json.dumps(m))
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"status": "stored"}), "")

    return run


class Base(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        self.stage = self.root / "sim/.work/.stage/b"
        (self.stage / "corners/r1").mkdir(parents=True)
        (self.stage / "corners/r1/tt.log").write_text("log tt\n")
        (self.stage / "corners/r1/ff.log").write_text("log ff\n")
        (self.stage / "corners/r1/empty.log").write_text("")
        (self.stage / "r1.json").write_text('{"x": 1}\n')
        self.files = [(self.stage / "r1.json", "sim/b/records/r1.json")]
        self.files += es.stage_files(self.stage / "corners/r1", "sim/b/corners/r1")
        self.summary = self.root / "sim/b/records/r1.md"
        self.mpath = self.root / "manifests/artifacts/b-r1.manifest.json"
        self.store = {}

    def put(self, **kw):
        return lambda files, root: es.put_files(files, root, run=fake_klt(self.store, **kw))

    def store_files(self, **kw):
        return es.store_files(self.files, repo_root=self.root, bench="b", rid="r1",
                              summary_text="# record\n", summary_path=self.summary,
                              put=self.put(**kw))

    def assert_nothing_committed(self):
        self.assertFalse(self.mpath.exists())
        self.assertFalse(self.summary.exists())
        self.assertFalse((self.root / "sim/b").exists())


class Writer(Base):
    def test_stores_bytes_commits_manifest_and_summary_only(self):
        path = self.store_files()
        self.assertEqual(path, self.mpath)
        m = json.loads(self.mpath.read_text())
        names = [e["name"] for e in m["entries"]]
        self.assertEqual(names, ["sim/b/corners/r1/ff.log", "sim/b/corners/r1/tt.log",
                                 "sim/b/records/r1.json"])
        for e in m["entries"]:
            self.assertEqual(hashlib.sha256(self.store[e["sha256"]]).hexdigest(), e["sha256"])
        text = self.summary.read_text()
        self.assertTrue(text.startswith("# record\n"))
        self.assertIn("## Stored evidence", text)
        self.assertIn("manifests/artifacts/b-r1.manifest.json", text)
        self.assertIn("`sim/b/corners/r1/empty.log` | 0 |", text)  # listed, not stored
        # Only the summary landed under sim/b: no evidence blob.
        self.assertEqual([p.relative_to(self.root).as_posix()
                          for p in (self.root / "sim/b").rglob("*") if p.is_file()],
                         ["sim/b/records/r1.md"])

    def test_broker_unreachable_is_fail_closed(self):
        with self.assertRaises(es.StoreError) as cm:
            self.store_files(fail="broker_unreachable")
        self.assertIn("broker_unreachable", str(cm.exception))
        self.assert_nothing_committed()
        self.assertTrue((self.stage / "r1.json").exists())  # staged bytes kept

    def test_manifest_not_matching_bytes_is_refused(self):
        with self.assertRaises(es.StoreError):
            self.store_files(corrupt=True)
        self.assert_nothing_committed()

    def test_existing_manifest_or_summary_is_never_overwritten(self):
        self.mpath.parent.mkdir(parents=True)
        self.mpath.write_text("{}")
        with self.assertRaises(es.StoreError):
            self.store_files()
        self.assertEqual(self.mpath.read_text(), "{}")
        self.assertEqual(self.store, {})  # refused before any put

    def test_nothing_but_empty_files_is_refused(self):
        self.files = [(self.stage / "corners/r1/empty.log", "sim/b/corners/r1/empty.log")]
        with self.assertRaises(es.StoreError):
            self.store_files()
        self.assert_nothing_committed()

    def test_duplicate_names_refused(self):
        self.files.append((self.stage / "r1.json", "sim/b/records/r1.json"))
        with self.assertRaises(es.StoreError):
            self.store_files()

    def test_symlink_in_stage_refused(self):
        (self.stage / "corners/r1/link.log").symlink_to(self.stage / "r1.json")
        with self.assertRaises(es.StoreError):
            es.stage_files(self.stage / "corners/r1", "sim/b/corners/r1")


class Preflight(unittest.TestCase):
    def which(self, name):
        return f"/bin/{name}"

    def run_ok(self, cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "usage", "")

    def test_no_broker_configured(self):
        with self.assertRaisesRegex(es.StoreError, "KLT_ARTIFACT_BROKER"):
            es.preflight(Path("."), env={}, which=self.which, run=self.run_ok,
                         probe=lambda *a: None)

    def test_klt_missing_or_without_artifact_verb(self):
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        with self.assertRaisesRegex(es.StoreError, "not on PATH"):
            es.preflight(Path("."), env=env, which=lambda n: None, run=self.run_ok,
                         probe=lambda *a: None)
        with self.assertRaisesRegex(es.StoreError, "no `artifact put` verb"):
            es.preflight(Path("."), env=env, which=self.which,
                         run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 2, "", ""),
                         probe=lambda *a: None)

    def test_probe_gets_repo_and_broker(self):
        seen = []
        env = {es.ENV_BROKER: "http://broker.invalid", es.ENV_REPO: REPO}
        es.preflight(Path("."), env=env, which=self.which, run=self.run_ok,
                     probe=lambda base, repo: seen.append((base, repo)))
        self.assertEqual(seen, [("http://broker.invalid", REPO)])


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, body))
        payload = ({"key": "k", "exists": False} if self.status == 200
                   else {"error": "not_granted", "message": "no"})
        raw = json.dumps(payload).encode()
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class Probe(unittest.TestCase):
    def serve(self, status):
        handler = type("H", (_Handler,), {"status": status, "seen": []})
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}", handler

    def test_reachable_broker_passes(self):
        for status in (200, 404):
            base, handler = self.serve(status)
            es.probe_broker(base, REPO)
            (path, body), = handler.seen
            self.assertEqual(path, "/v1/stat")
            self.assertEqual(body["repo"], REPO)

    def test_refusal_fails_closed(self):
        base, _ = self.serve(403)
        with self.assertRaisesRegex(es.StoreError, "HTTP 403: not_granted"):
            es.probe_broker(base, REPO)

    def test_unreachable_fails_closed(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaisesRegex(es.StoreError, "unreachable"):
            es.probe_broker(f"http://127.0.0.1:{port}", REPO, timeout=5)

    def test_url_with_credentials_refused(self):
        with self.assertRaises(es.StoreError):
            es.probe_broker("http://u:p@127.0.0.1:1", REPO)


class CampaignCli(unittest.TestCase):
    """``sim/run_store_evidence.py``: the store path for campaign outputs."""

    def setUp(self):
        import importlib.util
        path = Path(__file__).resolve().parents[2] / "run_store_evidence.py"
        spec = importlib.util.spec_from_file_location("run_store_evidence", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name).resolve()
        (self.root / "sim/bench").mkdir(parents=True)
        self.staged = self.root / "sim/.work/camp"
        self.staged.mkdir(parents=True)
        (self.staged / "a.json").write_text("{}\n")
        self.summary = self.root / "summary.md"
        self.summary.write_text("# campaign\n")
        self.mod.REPO_ROOT = self.root

    def main(self, staged=None, preflight_exc=None):
        from unittest import mock
        store = {}
        real_put = es.put_files
        with mock.patch.object(es, "preflight", side_effect=preflight_exc), \
             mock.patch.object(es, "put_files",
                               side_effect=lambda f, r: real_put(f, r, run=fake_klt(store))), \
             mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            return self.mod.main(["bench", "20261022-abc", str(staged or self.staged),
                                  "--summary", str(self.summary)])

    def test_stores_and_commits_manifest_and_summary(self):
        self.assertEqual(self.main(), 0)
        m = json.loads((self.root / "manifests/artifacts/bench-20261022-abc.manifest.json")
                       .read_text())
        self.assertEqual([e["name"] for e in m["entries"]],
                         ["sim/bench/campaigns/20261022-abc/a.json"])
        self.assertTrue((self.root / "sim/bench/campaigns/20261022-abc.md").is_file())
        self.assertFalse((self.root / "sim/bench/campaigns/20261022-abc").exists())

    def test_store_unavailable_commits_nothing(self):
        self.assertEqual(self.main(preflight_exc=es.StoreError("no broker")), 10)
        self.assertFalse((self.root / "manifests").exists())
        self.assertFalse((self.root / "sim/bench/campaigns").exists())

    def test_staged_dir_inside_tracked_tree_refused(self):
        inside = self.root / "sim/bench/campaigns/x"
        inside.mkdir(parents=True)
        (inside / "a.json").write_text("{}\n")
        self.assertEqual(self.main(staged=inside), 1)
        self.assertFalse((self.root / "manifests").exists())


if __name__ == "__main__":
    unittest.main()
