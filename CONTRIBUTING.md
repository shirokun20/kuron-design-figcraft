# Contributing to kuron-design-figcraft

This file is for maintainers of the skill package. Public usage belongs in
`SKILL.md` and `README.md`. All documentation in this repository is English-only.

## Working agreement

> **Motto:** *"Not fancy/clever code, but targeted, accurate code that directly
> solves the requirement and the root cause."*
> If a trial still falls short, keep improving together with the execution side
> (`Kuron Developer`) until the result is correct and targeted — do not stop at
> "good enough". A green test run is not a substitute for a correct result.

Keep changes minimal and surgical. Every subprocess and socket uses a timeout;
every loop and retry has an explicit cut-loop guard. Close every socket, child
process, archive member, and file handle in `with` or `try/finally` so no
resource leaks. Do not hardcode private paths, credentials, CDN URLs, or local
absolute paths in any file.

## Real joint trial (mandatory, Stage 3)

After `Kuron Developer` finishes refactoring `scripts/`, `Kuron Designer` must
run a real trial, not only unit tests:

1. **Real Live Generate:** create Components, Screen, Form, modal/drawer, and
   list/table in a live session from a test `DESIGN.md` (vary theme and style
   direction).
2. **Real Live Edit:** change nodes, properties, and tokens while the session
   runs; check `diff --id`, `reload`, and file sync.
3. **Real pixel audit:** `export-all` → open the PNG → run `audit_render.py` →
   evaluate the six defect classes in `SKILL.md` §8.1 → fix → repeat to at least
   three clean passes (maximum five).
4. **Contract passes only if** no text escapes borders, there is no
   overlap/clipping, `clip: true` is set, sizing is consistent, duplicates keep
   their styling, and JSON matches the PNG.
5. **Failure means keep improving with Developer**, never report "good enough".
   Record findings as new contracts in `references/` when a rule is missing.

## Release checklist

1. Bump `VERSION`, `SKILL.md` frontmatter, `HARNESS_VERSION`, script docstrings,
   `tests/test_package_hygiene.py`, and `CHANGELOG.md` together.
2. Run `python3 -B -W default -m unittest discover -s tests -p 'test_*.py' -v`
   from the repository root; require all tests to pass with no warnings.
3. Verify a clean install into a temporary directory with `install.sh`, then
   check `--help`, fail-closed manifest discovery, and a package-hygiene scan.
4. Sync the clean package (no `.git`, `__pycache__`, `.DS_Store`, `*.pyc`) to
   all maintained copies, then commit, push, and publish the versioned release.
