"""Package hygiene: zero leaks, valid frontmatter, locked versions.

Run with `python3 -m unittest discover -s tests -p 'test_*.py' -v`.
Search patterns are assembled from fragments so this test file itself does
not contain the literals it searches for (self-detection).
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "SKILL.md")
VERSION_FILE = os.path.join(ROOT, "VERSION")
HARNESS = os.path.join(ROOT, "scripts", "agent_terminal.py")

# Build forbidden literals from parts — the source of this test stays clean.
FORBIDDEN = [
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "gh" + "p_",
    "github" + "_pat_",
    "s" + "k-",
    "AI" + "za",
    "AK" + "IA",
    "Bearer" + " ",
]
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
TEXT_SUFFIXES = {".py", ".md", ".css", ".sh", ".txt", ".json", ".yml", ".yaml", ""}


def iter_package_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.splitext(name)[1].lower() not in TEXT_SUFFIXES:
                continue
            yield path


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index])
    return None


def frontmatter_version(block):
    match = re.search(r'^\s+version:\s*["\']?([0-9][^"\'\s]*)', block, re.M)
    return match.group(1) if match else None


class HygieneTests(unittest.TestCase):
    def test_zero_forbidden_paths_and_credentials(self):
        offenders = []
        for path in iter_package_files():
            rel = os.path.relpath(path, ROOT)
            for lineno, line in enumerate(read_text(path).splitlines(), 1):
                for needle in FORBIDDEN:
                    if needle in line:
                        offenders.append(f"{rel}:{lineno}: {needle!r}")
                        break
        self.assertEqual(offenders, [], "Found forbidden content:\n" + "\n".join(offenders))

    def test_skill_frontmatter_is_valid(self):
        block = frontmatter(read_text(SKILL))
        self.assertIsNotNone(block, "SKILL.md has no closing frontmatter delimiter")
        name = re.search(r'^name:\s*(\S+)', block, re.M)
        self.assertIsNotNone(name, "SKILL.md frontmatter has no name field")
        self.assertEqual(name.group(1), "kuron-design-figcraft")
        self.assertIsNotNone(frontmatter_version(block), "no metadata.version in SKILL.md")

    def test_version_lock_across_package(self):
        version = read_text(VERSION_FILE).strip()
        block = frontmatter(read_text(SKILL))
        skill_version = frontmatter_version(block)
        harness_match = re.search(r'^HARNESS_VERSION\s*=\s*["\']([^"\']+)',
                                  read_text(HARNESS), re.M)
        harness_version = harness_match.group(1) if harness_match else None
        self.assertEqual(version, "3.2.3")
        self.assertEqual(skill_version, version)
        self.assertEqual(harness_version, version)

    def test_harness_name_is_package_name(self):
        harness_text = read_text(HARNESS)
        self.assertIn('HARNESS_NAME = "kuron-design-figcraft"', harness_text)
        self.assertNotIn("kuron_design_crafting", harness_text)

    def test_no_build_notification_script_bundled(self):
        scripts = os.listdir(os.path.join(ROOT, "scripts"))
        self.assertNotIn("build_notification_design.py", scripts)

    def test_2026_pillars_documented(self):
        skill = read_text(SKILL)
        readme = read_text(os.path.join(ROOT, "README.md"))
        reference = os.path.join(ROOT, "references", "product-designer-2026.md")
        self.assertTrue(os.path.isfile(reference))
        body = read_text(reference)
        self.assertIn("Product Designer 2026", skill)
        self.assertIn("Design Approach (2026 standard)", readme)
        for needle in ("cognitive clarity", "Duplicate", "Zero Hollow Screens",
                       "Anti-Overthinking", "handoff", "bento"):
            self.assertIn(needle, body, f"missing pillar content: {needle}")


if __name__ == "__main__":
    unittest.main()
