"""Unit tests for design_manifest.py — discovery, validation, resolution, overrides."""

import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import design_manifest as dm  # noqa: E402


def write_manifest(directory, body):
    """Write a DESIGN.md with contract sentinels into a temp directory."""
    path = os.path.join(directory, "DESIGN.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# Test manifest\n\n" + dm.START_MARKER + "\n" + body
                     + "\n" + dm.END_MARKER + "\n")
    return path


class DesignManifestTests(unittest.TestCase):
    def setUp(self):
        dm.clear_cache()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.doc = dm.load_design()

    def test_find_design_uses_env_override(self):
        path = write_manifest(self._tmp.name, json.dumps(self.doc))
        with patch.dict(os.environ, {dm.ENV_OVERRIDE: path}):
            self.assertEqual(dm.find_design(), os.path.abspath(path))

    def test_missing_file_raises_actionable_error(self):
        missing = os.path.join(self._tmp.name, "missing", "DESIGN.md")
        with patch.dict(os.environ, {dm.ENV_OVERRIDE: missing}):
            with self.assertRaises(dm.DesignManifestError) as ctx:
                dm.load_design()
        message = str(ctx.exception)
        self.assertIn("not found", message)
        self.assertIn(dm.ENV_OVERRIDE, message)
        self.assertIn("references/DESIGN.md", message)

    def test_missing_sentinels_raise_actionable_error(self):
        path = os.path.join(self._tmp.name, "DESIGN.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# No contract block here\n")
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.load_design(path)
        self.assertIn("sentinels", str(ctx.exception))

    def test_invalid_json_is_reported_with_location(self):
        path = write_manifest(self._tmp.name, "{ this is not json")
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.load_design(path)
        self.assertIn("Invalid JSON", str(ctx.exception))
        self.assertIn("line", str(ctx.exception))

    def test_missing_required_key_is_reported(self):
        broken = copy.deepcopy(self.doc)
        del broken["a11y"]
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.validate(broken)
        self.assertIn("a11y", str(ctx.exception))

    def test_bad_schema_is_rejected(self):
        broken = copy.deepcopy(self.doc)
        broken["$schema"] = "unknown/schema"
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.validate(broken)
        self.assertIn("$schema", str(ctx.exception))

    def test_cycle_detection_is_bounded(self):
        broken = copy.deepcopy(self.doc)
        colors = broken["tokens"]["semantic"]["color"]
        colors["bg"] = "$semantic.color.text"
        colors["text"] = "$semantic.color.bg"
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.validate(broken)
        self.assertIn("cycle", str(ctx.exception).lower())

    def test_missing_theme_pair_is_rejected(self):
        broken = copy.deepcopy(self.doc)
        del broken["tokens"]["primitive"]["color"]["brand"]["light"]
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.validate(broken)
        self.assertIn("light", str(ctx.exception))

    def test_empty_states_are_rejected(self):
        broken = copy.deepcopy(self.doc)
        broken["states"] = []
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.validate(broken)
        self.assertIn("states", str(ctx.exception))

    def test_contrast_below_threshold_is_rejected(self):
        broken = copy.deepcopy(self.doc)
        # Make foreground identical to background in both themes.
        broken["tokens"]["primitive"]["color"]["i0"] = copy.deepcopy(
            broken["tokens"]["primitive"]["color"]["n0"])
        with self.assertRaises(dm.DesignManifestError) as ctx:
            dm.validate(broken)
        self.assertIn("contrast", str(ctx.exception).lower())

    def test_resolve_root_scope_and_theme_pair(self):
        self.assertEqual(dm.resolve("$a11y.minTouchTargetPx", self.doc), 44)
        self.assertEqual(
            dm.resolve("$semantic.color.action-primary", self.doc, "dark"),
            "#ff6b5a",
        )
        self.assertEqual(
            dm.resolve("$semantic.color.action-primary", self.doc, "light"),
            "#c4342a",
        )
        with self.assertRaises(dm.DesignManifestError):
            dm.resolve("$semantic.color.does-not-exist", self.doc, "dark")

    def test_full_override_is_valid_and_described(self):
        override = copy.deepcopy(self.doc)
        override["name"] = "Override Project"
        override["style_direction"] = "editorial"
        override["default_theme"] = "light"
        override["locale"] = "en-GB"
        override["copy_tone"] = "warm, explanatory"
        override["tokens"]["primitive"]["color"]["brand"] = {
            "dark": "#1a73e8", "light": "#0b57d0",
        }
        override["tokens"]["primitive"]["color"]["brandFg"] = {
            "dark": "#ffffff", "light": "#ffffff",
        }
        dm.validate(override)
        tokens = dm.to_builder_tokens(override, "light")
        self.assertEqual(tokens["colors"]["action-primary"], "#0b57d0")
        self.assertEqual(tokens["colors"]["coral"], "#0b57d0")
        self.assertEqual(tokens["style_direction"], "editorial")
        descriptions = dm.describe_overrides(override)
        self.assertTrue(any("action-primary" in line for line in descriptions))
        self.assertTrue(any("style_direction" in line for line in descriptions))
        self.assertLessEqual(len(descriptions), dm.MAX_DESCRIPTIONS)

    def test_cache_invalidates_on_mtime_and_clear_cache(self):
        path = write_manifest(self._tmp.name, json.dumps(self.doc))
        first = dm.load_design(path)
        second = dm.load_design(path)
        self.assertEqual(first, second)
        dm.clear_cache()
        third = dm.load_design(path)
        self.assertEqual(third, first)


if __name__ == "__main__":
    unittest.main()
