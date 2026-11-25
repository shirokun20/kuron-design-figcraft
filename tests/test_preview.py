"""--preview reports honestly and cleans up its live bridge."""

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
import quick_design as qd  # noqa: E402


class FakeTerminal:
    instances = []

    def __init__(self, port=9880):
        self.stopped = False
        self.opened = []
        self.instances.append(self)

    def is_port_listening(self):
        return False

    def start_server(self, file_path=None, wait_ready=True):
        return {"ok": True, "pid": 1}

    def open_file(self, path):
        self.opened.append(path)
        return {"ok": True}

    def stop_server(self):
        self.stopped = True
        return {"ok": True}


class FakeClient:
    instances = []
    fail_connect = False

    def __init__(self, port=9880):
        self.closed = False
        self.instances.append(self)

    def connect(self, timeout=2.0):
        return not self.fail_connect

    def document_inspect(self):
        return {"result": {"pages": [{"children": [{"id": 7}]}]}}

    def export_frame(self, node_id, out_path, format="png", scale=1.0):
        with open(out_path, "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n")
        return {"ok": True}

    def close(self):
        self.closed = True


class PreviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.fig = os.path.join(self.tmp, "sample.figcraft")
        self.png = os.path.splitext(self.fig)[0] + "_preview.png"
        self.missing_binary = os.path.join(self.tmp, "no-such-figcraft")
        FakeTerminal.instances = []
        FakeClient.instances = []
        FakeClient.fail_connect = False

    def test_missing_binary_reports_no_png_instead_of_claiming_success(self):
        with mock.patch.object(qd, "preview_app_binary",
                               return_value=self.missing_binary), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            result = qd.export_preview(self.fig)
        self.assertFalse(result)
        self.assertIn("Preview not generated", output.getvalue())
        self.assertNotIn("Preview exported", output.getvalue())
        self.assertFalse(os.path.exists(self.png))

    def test_cli_preview_reports_honest_status_without_a_binary(self):
        with mock.patch.object(qd, "preview_app_binary",
                               return_value=self.missing_binary), \
                mock.patch.object(sys, "argv",
                                  ["quick_design.py", "-o", self.fig, "--preview"]), \
                contextlib.redirect_stdout(io.StringIO()) as output, \
                contextlib.redirect_stderr(io.StringIO()):
            qd.main()
        self.assertIn("Preview not generated", output.getvalue())
        self.assertNotIn("Preview exported:", output.getvalue())

    def test_preview_exports_png_and_closes_every_resource(self):
        with mock.patch.object(at, "FigcraftTerminal", FakeTerminal), \
                mock.patch.object(qd, "FigcraftClient", FakeClient), \
                mock.patch.object(qd, "preview_app_binary",
                                  return_value=sys.executable), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            result = qd.export_preview(self.fig)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.png))
        self.assertIn("Preview exported", output.getvalue())
        self.assertTrue(FakeTerminal.instances[0].stopped)
        self.assertTrue(FakeClient.instances[0].closed)

    def test_preview_failed_launch_stops_the_spawned_process(self):
        class FailingTerminal(FakeTerminal):
            def start_server(self, file_path=None, wait_ready=True):
                return {"ok": False, "error": "port never responded"}

        with mock.patch.object(at, "FigcraftTerminal", FailingTerminal), \
                mock.patch.object(qd, "preview_app_binary",
                                  return_value=sys.executable), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            result = qd.export_preview(self.fig)
        self.assertFalse(result)
        self.assertIn("port never responded", output.getvalue())
        self.assertTrue(FailingTerminal.instances[0].stopped)
        self.assertFalse(os.path.exists(self.png))

    def test_preview_render_error_still_cleans_up(self):
        FakeClient.fail_connect = True
        with mock.patch.object(at, "FigcraftTerminal", FakeTerminal), \
                mock.patch.object(qd, "FigcraftClient", FakeClient), \
                mock.patch.object(qd, "preview_app_binary",
                                  return_value=sys.executable), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            result = qd.export_preview(self.fig)
        self.assertFalse(result)
        self.assertIn("Preview not generated", output.getvalue())
        self.assertTrue(FakeTerminal.instances[0].stopped)
        self.assertTrue(FakeClient.instances[0].closed)


if __name__ == "__main__":
    unittest.main()
