"""Concurrency hardening tests: atomic saves, scoped locks/state, harness detection."""

import concurrent.futures
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import agent_terminal as at  # noqa: E402
import harness_detect as hd  # noqa: E402
import multi_agent_worker as mw  # noqa: E402
from figcraft_tool import FigcraftDocument  # noqa: E402


class SaveRaceTests(unittest.TestCase):
    """Concurrent saves must publish one valid archive and leak no temp files."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(self.dir, "race.figcraft")

    @staticmethod
    def _doc():
        doc = FigcraftDocument("Race")
        doc.doc["pages"] = [1]
        return doc

    @staticmethod
    def _leftovers(directory):
        return [name for name in os.listdir(directory) if name.endswith(".tmp")]

    def test_concurrent_saves_leave_one_valid_archive_and_no_tmp_files(self):
        doc = self._doc()
        barrier = threading.Barrier(8)

        def save(index):
            doc.doc["name"] = "Race-%d" % index
            barrier.wait(timeout=5)
            doc.save(self.path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(save, range(8)))

        with zipfile.ZipFile(self.path) as archive:
            self.assertEqual(sorted(archive.namelist()),
                             ["document.json", "thumbnail.png"])
            payload = json.loads(archive.read("document.json"))
        self.assertIn(payload["name"], ["Race-%d" % i for i in range(8)])
        self.assertEqual(self._leftovers(self.dir), [])

    def test_two_saves_use_distinct_temp_files(self):
        doc = self._doc()
        seen = []
        guard = threading.Lock()
        real_replace = os.replace

        def capture(src, dst):
            with guard:
                seen.append(src)
            return real_replace(src, dst)

        with mock.patch.object(os, "replace", side_effect=capture):
            threads = [threading.Thread(target=doc.save, args=(self.path,))
                       for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertTrue(all(not thread.is_alive() for thread in threads))

        self.assertEqual(len(seen), 2)
        self.assertNotEqual(seen[0], seen[1])
        self.assertEqual(self._leftovers(self.dir), [])

    def test_failed_replace_removes_its_temp_file(self):
        doc = self._doc()
        real_replace = os.replace
        calls = []

        def flaky(src, dst):
            calls.append(src)
            if len(calls) == 1:
                raise OSError("simulated replace failure")
            return real_replace(src, dst)

        with mock.patch.object(os, "replace", side_effect=flaky):
            with self.assertRaises(OSError):
                doc.save(self.path)
        self.assertEqual(self._leftovers(self.dir), [])

        doc.save(self.path)
        self.assertTrue(zipfile.is_zipfile(self.path))
        self.assertEqual(self._leftovers(self.dir), [])


class MergerTests(unittest.TestCase):
    """Multi-page, ZIP-safe, collision-checked, bounded-lock merging."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.path = os.path.join(self.dir, "master.figcraft")
        self._write_master()

    def _write_master(self):
        doc = {
            "name": "Master",
            "pages": [1, 2],
            "nodes": {
                "1": {"id": 1, "name": "Page One", "type": "page", "children": []},
                "2": {"id": 2, "name": "Page Two", "type": "page", "children": []},
            },
            "next_id": 10,
        }
        with zipfile.ZipFile(self.path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("document.json", json.dumps(doc))
            archive.writestr("thumbnail.png", b"thumbnail")
            archive.writestr("meta.json", '{"kept": true}')

    @staticmethod
    def _subtree(nid, page, name):
        return {"page": page, "root_id": nid,
                "nodes": {str(nid): {"id": nid, "name": name,
                                     "type": "frame", "children": []}}}

    @staticmethod
    def _merge(merger, subtrees, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return merger.merge_subtrees(subtrees, **kwargs)

    def _read(self):
        with zipfile.ZipFile(self.path) as archive:
            return {info.filename: archive.read(info.filename)
                    for info in archive.infolist()}

    def test_multi_page_merge_preserves_siblings_and_all_zip_entries(self):
        merger = mw.ASTPartitionMerger(self.path)
        self.assertTrue(self._merge(merger, [
            self._subtree(1000, 1, "Screen A"),
            self._subtree(2000, 2, "Screen B"),
        ]))

        payload = self._read()
        self.assertEqual(sorted(payload), ["document.json", "meta.json", "thumbnail.png"])
        self.assertEqual(payload["thumbnail.png"], b"thumbnail")
        self.assertEqual(json.loads(payload["meta.json"]), {"kept": True})
        doc = json.loads(payload["document.json"])
        self.assertEqual(doc["pages"], [1, 2])
        self.assertEqual(doc["nodes"]["1"]["children"], [1000])
        self.assertEqual(doc["nodes"]["2"]["children"], [2000])
        self.assertEqual(doc["nodes"]["1000"]["name"], "Screen A")
        self.assertEqual(doc["nodes"]["2000"]["name"], "Screen B")
        self.assertEqual([n for n in os.listdir(self.dir)
                          if n.endswith(".lock") or n.endswith(".tmp")], [])

    def test_duplicate_ids_are_rejected_deterministically_without_writes(self):
        merger = mw.ASTPartitionMerger(self.path)
        duplicate = [self._subtree(3000, 1, "First"),
                     self._subtree(3000, 2, "Second")]
        with self.assertRaises(ValueError) as first:
            self._merge(merger, duplicate)
        with self.assertRaises(ValueError) as second:
            self._merge(merger, duplicate)
        self.assertEqual(str(first.exception), str(second.exception))
        self.assertIn("node ID collision", str(first.exception))
        self.assertIn("3000", str(first.exception))

        doc = json.loads(self._read()["document.json"])
        self.assertNotIn("3000", doc["nodes"])
        self.assertEqual(doc["nodes"]["1"]["children"], [])
        self.assertFalse(os.path.exists(self.path + ".lock"))

    def test_collision_with_existing_node_is_rejected(self):
        merger = mw.ASTPartitionMerger(self.path)
        with self.assertRaisesRegex(ValueError, "already in document"):
            self._merge(merger, [self._subtree(1, 1, "Clashes")])
        self.assertFalse(os.path.exists(self.path + ".lock"))

    @staticmethod
    def _dead_pid():
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=5)
        return child.pid

    def test_stale_lock_with_dead_owner_is_recovered(self):
        lock_path = self.path + ".lock"
        with open(lock_path, "w", encoding="utf-8") as handle:
            handle.write("%d:stale" % self._dead_pid())
        merger = mw.ASTPartitionMerger(self.path)
        self.assertTrue(self._merge(merger,
            [self._subtree(4000, 1, "Recovered")], timeout=1.0))
        self.assertFalse(os.path.exists(lock_path))
        doc = json.loads(self._read()["document.json"])
        self.assertEqual(doc["nodes"]["1"]["children"], [4000])

    def test_old_unreadable_lock_is_recovered(self):
        lock_path = self.path + ".lock"
        with open(lock_path, "w", encoding="utf-8") as handle:
            handle.write("malformed")
        old = time.time() - (mw.LOCK_STALE_SECONDS + 10)
        os.utime(lock_path, (old, old))
        merger = mw.ASTPartitionMerger(self.path)
        self.assertTrue(self._merge(merger,
            [self._subtree(5000, 2, "Recovered")], timeout=1.0))
        self.assertFalse(os.path.exists(lock_path))

    def test_live_lock_times_out_bounded_and_is_not_deleted(self):
        lock_path = self.path + ".lock"
        owner = "%d:live" % os.getpid()
        with open(lock_path, "w", encoding="utf-8") as handle:
            handle.write(owner)
        merger = mw.ASTPartitionMerger(self.path)
        with mock.patch.object(mw.time, "sleep", lambda _seconds: None):
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                self._merge(merger,
                    [self._subtree(6000, 1, "Blocked")], timeout=0.2)
            self.assertLess(time.monotonic() - started, 2.0)
        with open(lock_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), owner)
        self.assertNotIn("6000", json.loads(self._read()["document.json"])["nodes"])


class ScopedStateTests(unittest.TestCase):
    """Parallel terminal instances must not share PID/active/port state."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        base = os.path.join(self.dir, ".figcraft")
        for name, value in (("PID_FILE", base + ".pid"),
                            ("PORT_FILE", base + ".port"),
                            ("ACTIVE_FILE", base + ".active.json")):
            patcher = mock.patch.object(at, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.first = os.path.join(self.dir, "first.figcraft")
        self.second = os.path.join(self.dir, "second.figcraft")
        for path in (self.first, self.second):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{}")

    def test_paths_are_distinct_per_scope_and_sanitized(self):
        a = at.scoped_state_paths("9881")
        b = at.scoped_state_paths("9882")
        self.assertEqual(len(a), 3)
        for left, right in zip(a, b):
            self.assertNotEqual(left, right)
        self.assertEqual(at.scoped_state_paths(None),
                         (at.PID_FILE, at.PORT_FILE, at.ACTIVE_FILE))
        sanitized = at.scoped_state_paths("worker/one")[0]
        self.assertNotIn("/", os.path.basename(sanitized))

    def test_two_ports_write_and_clear_independent_state(self):
        first = at.FigcraftTerminal(port=9881, state_scope="9881")
        second = at.FigcraftTerminal(port=9882, state_scope="9882")
        self.assertNotEqual(first.pid_file, second.pid_file)
        self.assertNotEqual(first.active_file, second.active_file)

        procs = [mock.Mock(pid=7001), mock.Mock(pid=7002)]
        with mock.patch.object(at, "DEFAULT_APP_PATH", sys.executable), \
                mock.patch.object(at.subprocess, "Popen", side_effect=procs), \
                mock.patch.object(first, "is_port_listening", return_value=False), \
                mock.patch.object(second, "is_port_listening", return_value=False):
            first.start_server(file_path=self.first, wait_ready=False)
            second.start_server(file_path=self.second, wait_ready=False)

        self.assertEqual(at.read_active_file("9881"), os.path.abspath(self.first))
        self.assertEqual(at.read_active_file("9882"), os.path.abspath(self.second))
        self.assertIsNone(at.read_active_file())
        for terminal in (first, second):
            self.assertTrue(os.path.exists(terminal.pid_file))
            self.assertTrue(os.path.exists(terminal.port_file))

        with mock.patch.object(at.os, "kill"):
            first.stop_server()
        self.assertFalse(os.path.exists(first.pid_file))
        self.assertFalse(os.path.exists(first.port_file))
        self.assertIsNone(at.read_active_file("9881"))
        self.assertTrue(os.path.exists(second.pid_file))
        self.assertEqual(at.read_active_file("9882"), os.path.abspath(self.second))
        with mock.patch.object(at.os, "kill"):
            second.stop_server()

    def test_cli_derives_state_scope_from_explicit_port(self):
        fake = mock.Mock()
        fake.status.return_value = {"ok": True}
        with mock.patch.object(sys, "argv",
                               ["agent_terminal.py", "--port", "9883", "status"]), \
                mock.patch.object(at, "FigcraftTerminal", return_value=fake) as ctor, \
                contextlib.redirect_stdout(io.StringIO()):
            at.main()
        self.assertEqual(ctor.call_args.kwargs["state_scope"], "9883")


class HarnessDetectionTests(unittest.TestCase):
    """Runtime detection is deterministic, stdlib-only, and CLI-visible."""

    def test_known_harness_markers(self):
        cases = {
            "ANTIGRAVITY": "antigravity",
            "CLAUDECODE": "claude-code",
            "OPENCODE_SESSION_ID": "opencode",
            "CODEX_HOME": "codex",
        }
        for key, expected in cases.items():
            with self.subTest(marker=key):
                self.assertEqual(hd.detect_harness({key: "1"}), expected)

    def test_generic_and_unknown_fallbacks(self):
        self.assertEqual(hd.detect_harness({"AI_AGENT": "1"}), "generic")
        self.assertEqual(hd.detect_harness({}), "unknown")
        self.assertEqual(hd.detect_harness({"CLAUDECODE": "0"}), "unknown")
        self.assertEqual(hd.detect_harness({"TERM_PROGRAM": "Claude Code"}),
                         "claude-code")

    def test_override_wins_and_priority_is_fixed(self):
        env = {"FIGCRAFT_HARNESS": "codex", "CLAUDECODE": "1",
               "OPENCODE_SESSION_ID": "1"}
        self.assertEqual(hd.detect_harness(env), "codex")
        self.assertEqual(hd.detect_harness(
            {"ANTIGRAVITY": "1", "CLAUDECODE": "1"}), "antigravity")
        self.assertIn("unknown", hd.SUPPORTED_HARNESSES)
        with mock.patch.dict(os.environ, {"OPENCODE_SESSION_ID": "session"},
                             clear=True):
            self.assertEqual(hd.detect_harness(), "opencode")

    def test_show_harness_cli_uses_detection(self):
        output = io.StringIO()
        with mock.patch.object(sys, "argv",
                               ["multi_agent_worker.py", "--show-harness"]), \
                contextlib.redirect_stdout(output):
            mw.main()
        self.assertEqual(json.loads(output.getvalue())["harness"],
                         hd.detect_harness())


if __name__ == "__main__":
    unittest.main()
