"""Verification that refactored scripts contain no frozen colour literals."""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import design_manifest as dm  # noqa: E402
from figcraft_tool import TOKENS  # noqa: E402

SCRIPTS = os.path.join(ROOT, "scripts")
HEX_LITERAL = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
REFACTORED = (
    "design_manifest.py", "figcraft_tool.py", "build_artistic_flow.py",
    "quick_design.py", "multi_agent_worker.py", "agent_terminal.py",
    "audit_render.py",
)
# The historical drift that made ring cyan instead of following the token.
DRIFT_LITERALS = ("38BDF8", "FF6B5A", "ff6b5a", "00e5ff")


class NoFrozenHexTests(unittest.TestCase):
    def test_refactored_scripts_have_no_hex_literals(self):
        offenders = []
        for name in REFACTORED:
            path = os.path.join(SCRIPTS, name)
            with open(path, "r", encoding="utf-8") as handle:
                for lineno, line in enumerate(handle, 1):
                    if HEX_LITERAL.search(line):
                        offenders.append("%s:%d: %s" % (name, lineno, line.strip()))
        self.assertEqual(offenders, [], "Frozen hex found:\n" + "\n".join(offenders))

    def test_historical_drift_literals_are_gone(self):
        offenders = []
        for filename in os.listdir(SCRIPTS):
            if not filename.endswith(".py"):
                continue
            with open(os.path.join(SCRIPTS, filename), "r", encoding="utf-8") as handle:
                text = handle.read()
            for literal in DRIFT_LITERALS:
                if literal in text:
                    offenders.append("%s contains %s" % (filename, literal))
        self.assertEqual(offenders, [], "Drift literals found:\n" + "\n".join(offenders))

    def test_builder_tokens_come_from_manifest_roles(self):
        doc = dm.load_design()
        expected = dm.to_builder_tokens(doc, doc["default_theme"])
        self.assertEqual(TOKENS["colors"]["action-primary"],
                         expected["colors"]["action-primary"])
        self.assertEqual(TOKENS["colors"]["data-technical"],
                         expected["colors"]["data-technical"])
        # Legacy aliases are compatibility keys, not independent values.
        self.assertEqual(TOKENS["colors"]["coral"], TOKENS["colors"]["action-primary"])
        self.assertEqual(TOKENS["colors"]["cyan"], TOKENS["colors"]["data-technical"])

    def test_role_names_are_present_in_builder_tokens(self):
        for role in dm.REQUIRED_COLOR_ROLES:
            if role in ("glass-bg", "glass-toolbar", "glass-floating",
                        "glass-specular", "glass-border", "glass-shadow"):
                continue  # rgba/shadow values are not used as solid paints
            self.assertIn(role, TOKENS["colors"], role)


if __name__ == "__main__":
    unittest.main()
