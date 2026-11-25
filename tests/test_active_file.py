"""Active-file persistence and fatal reload/watch behavior."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import agent_terminal as at  # noqa: E402


class ActiveFileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.active = os.path.join(self.tmp, ".figcraft.active.json")
        self.pid = os.path.join(self.tmp, ".figcraft.pid")
        self.port = os.path.join(self.tmp, ".figcraft.port")
        for name, value in (("ACTIVE_FILE", self.active),
                            ("PID_FILE", self.pid), ("PORT_FILE", self.port)):
            patcher = mock.patch.object(at, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.fig = os.path.join(self.tmp, "design.figcraft")
        with open(self.fig, "w", encoding="utf-8") as handle:
            handle.write("{}")

    def term(self):
        return at.FigcraftTerminal(port=9921)

    def test_start_persists_active_file_and_reload_uses_it(self):
        term = self.term()
        proc = mock.Mock(pid=4242)
        with mock.patch.object(at, "DEFAULT_APP_PATH", sys.executable), \
                mock.patch.object(at.subprocess, "Popen", return_value=proc), \
                mock.patch.object(term, "is_port_listening", return_value=False):
            result = term.start_server(file_path=self.fig, wait_ready=False)
        self.assertTrue(result["ok"])
        self.assertEqual(at.read_active_file(), os.path.abspath(self.fig))

        calls = []

        def fake_execute(command, params=None):
            calls.append((command, params or {}))
            return {"ok": True, "result": {}}

        with mock.patch.object(term, "execute_command", side_effect=fake_execute):
            out = term.reload_file()
        self.assertEqual(out["file"], os.path.abspath(self.fig))
        self.assertTrue(any(command == "file.reload"
                            and params.get("path") == os.path.abspath(self.fig)
                            for command, params in calls))

    def test_open_updates_active_file_and_watch_uses_it(self):
        term = self.term()
        with mock.patch.object(term, "execute_command", return_value={"ok": True}):
            opened = term.open_file(self.fig)
        self.assertTrue(opened["ok"])
        self.assertEqual(at.read_active_file(), os.path.abspath(self.fig))

        reloads = []

        def fake_reload(path=None, mode="soft"):
            reloads.append((path, mode))
            return {"ok": True}

        with mock.patch.object(term, "reload_file", side_effect=fake_reload), \
                mock.patch.object(term, "export_all", return_value={"ok": True}), \
                mock.patch.object(at.time, "sleep", lambda _seconds: None), \
                mock.patch.object(at.os.path, "getmtime",
                                  side_effect=[100.0, 101.0, 101.0]), \
                contextlib.redirect_stdout(io.StringIO()):
            summary = term.watch_file(out_dir=self.tmp, debounce=0.01,
                                      max_events=1, max_seconds=1.0)
        self.assertEqual(reloads[0][0], os.path.abspath(self.fig))
        self.assertEqual(summary["file"], os.path.abspath(self.fig))
        self.assertTrue(summary["ok"])

    def test_reload_or_watch_without_active_file_fails_explicitly(self):
        term = self.term()
        self.assertIsNone(at.read_active_file())
        out = term.reload_file()
        self.assertFalse(out["ok"])
        self.assertIn("No active", out["error"])
        watched = term.watch_file(out_dir=self.tmp)
        self.assertFalse(watched["ok"])
        self.assertEqual(watched["stop"], "no_active_file")

    def test_failed_reload_returns_not_ok_and_cli_exits_one(self):
        term = self.term()
        failure = {"ok": False, "error": "engine rejected the target"}
        with mock.patch.object(term, "execute_command", return_value=failure):
            out = term.reload_file(self.fig)
        self.assertFalse(out["ok"])
        self.assertTrue(out["fallback"])

        fake_term = mock.Mock()
        fake_term.reload_file.return_value = failure
        with mock.patch.object(sys, "argv", ["agent_terminal.py", "reload", self.fig]), \
                mock.patch.object(at, "FigcraftTerminal", return_value=fake_term), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                at.main()
        self.assertEqual(caught.exception.code, 1)

    def test_watch_never_exports_after_a_failed_reload(self):
        term = self.term()
        with mock.patch.object(term, "execute_command", return_value={"ok": True}):
            term.open_file(self.fig)
        exported = []

        def fake_reload(path=None, mode="soft"):
            return {"ok": False, "error": "stale document"}

        def fake_export(*_args, **_kwargs):
            exported.append(True)
            return {"ok": True}

        with mock.patch.object(term, "reload_file", side_effect=fake_reload), \
                mock.patch.object(term, "export_all", side_effect=fake_export), \
                mock.patch.object(at.time, "sleep", lambda _seconds: None), \
                mock.patch.object(at.os.path, "getmtime", side_effect=[100.0, 101.0]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            summary = term.watch_file(out_dir=self.tmp)
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["stop"], "reload_failed")
        self.assertEqual(exported, [])
        self.assertIn("stale document", output.getvalue())


if __name__ == "__main__":
    unittest.main()
