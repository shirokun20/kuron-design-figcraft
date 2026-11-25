"""Multi-page save guard tests — converted to unittest."""
import contextlib
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from figcraft_tool import FigcraftDocument  # noqa: E402


def temp_path():
    fd, path = tempfile.mkstemp(suffix=".figcraft")
    os.close(fd)
    return path


class SaveGuardTests(unittest.TestCase):
    def test_two_pages_warns(self):
        doc = FigcraftDocument("mp")
        doc.doc["pages"] = [1, 1794]
        err = io.StringIO()
        path = temp_path()
        try:
            with contextlib.redirect_stderr(err):
                doc.save(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        self.assertIn("multi-page", err.getvalue())

    def test_single_page_no_warning(self):
        doc = FigcraftDocument("sp")
        err = io.StringIO()
        path = temp_path()
        try:
            with contextlib.redirect_stderr(err):
                doc.save(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
        self.assertNotIn("multi-page", err.getvalue())


if __name__ == "__main__":
    unittest.main()
