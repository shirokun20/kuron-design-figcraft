# Changelog — kuron-design-figcraft

One version for the whole package: `VERSION`, the `SKILL.md` frontmatter, and
`HARNESS_VERSION` are always identical.

## 3.2.2 — Concurrency hardening and multi-agent harness support

- **Race-free atomic saves:** `FigcraftDocument.save()` now writes to a unique
  temp file in the target directory, flushes and `fsync`s the completed archive,
  and publishes it with `os.replace()`. Concurrent writers never share a
  `.tmp` path, and a failed write or replace always removes its own temp file.
- **Hardened `ASTPartitionMerger` (`scripts/multi_agent_worker.py`):** merges
  multiple pages, preserves every ZIP container entry verbatim, rejects
  duplicate node IDs deterministically before any write, recovers stale locks
  from dead PIDs or old mtimes, retries under a bounded monotonic deadline, and
  releases only a lock it still owns.
- **Instance-scoped terminal state:** `scripts/agent_terminal.py` scopes PID,
  active-file, and port metadata per port/instance with ownership-checked
  `atexit` cleanup, so parallel subagents and workers never clobber one another.
- **Runtime harness detection:** new stdlib-only `scripts/harness_detect.py`,
  wired into `multi_agent_worker.py` and `agent_terminal.py harness-info`.
  `SKILL.md` adds concise Antigravity (`swarm`, `run_workflow`,
  `invoke_subagent`) and Claude Code (`Agent`) freeze-before-fanout and
  page/board sharding guidance.
- **Tests and version lock:** 16 new concurrency and harness unit tests in
  `tests/test_concurrency_hardening.py`; all version markers move to `3.2.2`.

## 3.2.1 — Fail-closed discovery, core layout, and release hygiene

- **Fail-closed `find_design()`:** removed the automatic fallback to the skill
  package's `DESIGN.md`. Running a script from a project without a manifest now
  raises an actionable `DesignManifestError` that suggests copying the starter
  (`cp <skill>/references/DESIGN.md ./DESIGN.md`) or setting
  `FIGCRAFT_DESIGN_MANIFEST`. The package manifest is available only through an
  explicit internal opt-in (`allow_package_fallback=True` or
  `FIGCRAFT_ALLOW_PACKAGE_DESIGN=1`) for the bundled demo and self-tests. Added
  tests that prove external-directory calls fail closed and that the opt-in is
  strictly explicit.
- **Valid starter template:** `references/DESIGN.md` now carries a compact but
  complete `design-contract/v1` JSON block that passes `json.loads()` and
  `validate()` on first run; the README Quick Start points to it.
- **Installer:** `--help` and `--dry-run`, `pwd -P` source resolution, `with`
  handlers in both version-check heredocs, explicit copy of `DESIGN.md`,
  `CONTRIBUTING.md`, and `docs/assets/showcase/`, harness verification from
  inside `DEST` with visible stderr on failure, and `python3 -B` for a
  cache-free test run. Re-running is idempotent and touches nothing outside the
  target directory.
- **Core layout decoupled:** `resolve_tree_layout()` moved into
  `figcraft_tool.py`, so `FigcraftDocument.save()` no longer imports the
  reference demo. `build_artistic_flow.py` is an explicitly invoked demo with
  `--help` / `--out-dir` and lazy manifest loading.
- **Resource and code hygiene:** worker sockets are closed and reset on connect
  failure and in `close()`; the worker has `--help` / `--out` and no dead import;
  relative design paths resolve against cwd first; all `archive.open()` calls
  and `ZipFile` temp files are cleaned up; child processes are reaped on stop or
  failed startup; every polling loop has an explicit cut-loop guard; dead
  imports and the unused auditor `root_id` parameter are gone. Docstrings now
  report `3.2.1`.
- **Documentation:** `SKILL.md` is under 500 lines and public-facing; maintainer
  process notes moved to `CONTRIBUTING.md`. Corrected the `watch`, parallel ID
  namespace (`A 1000–1999`, `B 2000–2999`), and `frames --json` descriptions;
  added Troubleshooting and Linux `FIGCRAFT_APP` guidance.
- **Demo GIF:** `docs/assets/demo.gif` records a real Generate → Live Terminal
  → Live Editing → Live Audit & Export run (12 seconds, 1100x620, under 2.5 MB)
  with generic prompts and no private paths; the README and installer include
  it alongside the showcase PNGs.
- **Version lock:** `VERSION`, `SKILL.md` frontmatter, `HARNESS_VERSION`, script
  docstrings, hygiene tests, and this changelog all move to `3.2.1`.

## 3.2.0 — Three boards, smart reuse, and a board-scoped audit

- **Mandatory 3-board standard:** generators now place three adjacent
  top-level frames on `pages[0]`: `00_Foundations` (semantic colour roles,
  typography scale, spacing and radius tokens from `DESIGN.md`),
  `01_Components` (reusable bases and variants), and `02_Screens` (final
  screens). `ensure_board()` reuses an existing board and never rebuilds it.
- **Smart reuse ("copy, do not rebuild"):** `find_or_reuse_component()`
  locates an existing component in a bounded search and returns it untouched;
  `duplicate_node()` deep-clones the whole subtree with fresh unique ids and
  applies only the requested overrides. `alloc_id()` probes against the real
  node map, so a stale `next_id` in a loaded file cannot cause a collision.
  Screen instances are created by duplicating nodes from `01_Components`.
- **`quick_design.py`:** added the `three-board` preset (also routed from a
  "design system" / "foundations" brief). It fills Foundations from the
  manifest, populates Components with Button, Badge, Card, Input, Row, and
  variants, and builds Screens by duplicating those components. All existing
  presets and flags remain compatible.
- **`audit_render.py`:** audits every top-level board, not only frames wider
  than 1000px. Contrast ancestry, traversal, and layout checks are scoped to
  the board root, eliminating cross-board false positives; rule S-14 reports
  overlapping sibling boards.
- **Full multi-page support:** `ensure_board()`, `find_or_reuse_component()`,
  `duplicate_node()`, the preset generator, the auditor, and the terminal now
  accept `page_index` / `page_name` selectors and work across `pages[0..N]`.
  Save/reflow preserves later pages; the auditor checks every page and can be
  filtered by page; documentation describes the live canvas's page-0 default
  honestly.
- **Tests:** added `test_three_boards.py` and `test_multi_page.py` covering
  3-board layout, smart reuse with unique ids, page selection and cross-page
  duplication, save/reflow preservation of `pages[1..N]`, and multi-page audit
  detection and cleanliness.
- **Separate-page standard:** `ensure_named_pages()` and the `three-pages`
  preset put `00_Foundations`, `01_Components`, and `02_Screens` on dedicated
  pages; cross-page `find_or_reuse_component()` / `duplicate_node()` still copy
  templates without rebuilding them.
- **Foundations and component composition:** semantic swatches now carry a
  1px `line` stroke so light roles stay crisp, Foundations fills two columns,
  and stereo's `01_Components` uses a balanced 2x2 specimen grid.
- **Page-safe export:** `export` / `export-all` accept `--page-index` /
  `--page-name`; a non-zero page is exported through a read-only temporary
  projection that promotes it to `pages[0]` for the live engine and restores
  the original file, which is never written.
- **Descriptive labels and card fit:** all generated nodes use descriptive
  English names (`build_badge` no longer emits a node named `text`), component
  specimens in stereo carry visible English captions, and `audit_render.py`
  adds S-15 (label completeness) and S-16 (card containment/fit) across every
  page with counts in its PASS output.
- **Tests:** `test_stage5_remediation.py` covers the swatch stroke, two-column
  coverage, dedicated pages and cross-page reuse, no-mutation projection, and
  positive/negative label and card-fit cases on later pages.
- **Version lock:** `VERSION`, `SKILL.md` metadata, `HARNESS_VERSION`, and
  `tests/test_package_hygiene.py` all move to `3.2.0`.

## 3.1.0 — Manifest-driven scripts, Live Generate, and stronger audit

- **New `scripts/design_manifest.py`:** locates `DESIGN.md` upward from the
  working directory (repo/package boundary, override via
  `FIGCRAFT_DESIGN_MANIFEST`), extracts the `design-contract/v1` block, parses
  it with `json.loads`, and validates `$schema`, required keys, paired
  `dark`/`light` colours, `$...` references with bounded cycle detection,
  `a11y.minContrast` ratios, and non-empty `states`. Missing or invalid input
  now raises an actionable error — there is no silent preset fallback.
  `resolve()`, `to_builder_tokens()` (preserving legacy `TOKENS["colors"]`
  aliases), and `describe_overrides()` are the single adapter for all builders.
  Parsed manifests are cached by `(path, mtime_ns)` to avoid repeated reads.
- **`figcraft_tool.py`:** `TOKENS` is now derived from `DESIGN.md`; no frozen
  colour/size dictionary or hex literal remains. Lint rules S-01/S-02/S-09
  refer to the `action-primary` and `data-technical` roles instead of coral/
  cyan literals; S-11 detects screen frames with `clip: false`. Added
  `duplicate_node()`, `component_first()`, and `prevent_clipping()` for
  component-first reuse and overflow prevention.
- **`build_artistic_flow.py`:** removed the hardcoded `C` palette (including
  the real `ring` drift), sourced colours/fonts and the screen map from the
  manifest, and removed all frozen hex values.
- **`quick_design.py`:** colours, type, spacing, component sizes, and microcopy
  come from tokens plus `locale`/`copy_tone`. Added **Live Generate** for
  Components, Screen, and Form, with layout driven by `style_direction`
  (`dense_operational`, `bento_modular`, `editorial`, `clean_utility`,
  `custom`); `--style` and `--theme` overrides are supported.
- **`multi_agent_worker.py`:** demo node colours now use the `action-primary`
  role token instead of a fixed hex value.
- **`agent_terminal.py`:** keeps the global `--port` flag (default `9880`) and
  adds `design_contract`, `style_direction`, and `theme` to `harness-info`.
- **`audit_render.py`:** sources tokens from the manifest, audits WCAG contrast
  in both themes using `a11y.minContrast`, and strengthens detection of text
  overflowing frames, content escaping parent bounds, and `clip: false`.
- **Version lock:** `VERSION`, `SKILL.md` metadata, `HARNESS_VERSION`, the
  `harness-info` manifest, and `tests/test_package_hygiene.py` all moved to
  `3.1.0`.
- **English policy:** all skill documentation, comments, and docstrings are
  clean English; the `design-contract/v1` schema is unchanged.
- **Tests:** added `test_design_manifest.py`, `test_no_frozen_hex.py`, and
  `test_live_generate.py`; lint/builder tests now assert semantic role mapping
  rather than literal coral/cyan values.

## Stage 1 documentation upgrade (released as part of 3.1.0)

- **DESIGN.md upgraded:** a mandatory template + `design-contract/v1` contract
  for consuming projects, with a delimited JSON block, `$...` resolver, theme
  pairs, contrast/state validation, and actionable errors — no silent fallback.
- **Dynamic, not one style:** added `style-directions.md` (four directions +
  `custom`) and `token-architecture.md`
  (`primitive → semantic → component → theme/state`). Rewrote
  `design-tokens.css` in layers with `[data-style]` hooks;
  `action-primary`/`data-technical` are roles, not colours.
- **Module reframing:** `patterns.md` is a generic layout grammar;
  `dark-artifact-rules.md` is a cross-theme execution contract;
  `light-glass-system.md` is a theme/surface system with optional glass.
- **2026 standards strengthened:** action+object / cause+solution microcopy,
  zero-state matrix, AI-status ladder, AA/AAA, touch targets, reduced motion,
  and `duplicate → refine`.
- **Cleanliness:** zero private paths, secrets, CDN URLs, or engine IDs in
  documentation; the preset is explicitly labelled as an overridable example.

## 3.0.0 — Self-contained package, safe to publish

- Merged three skills (`kuron_design_crafting` 2.5.1,
  `kuron_glass_light_design` 1.0.0, `figcraft_live_editing` 1.0.0) into one
  `SKILL.md` plus `references/` modules: dark workbench, light glassmorphism,
  live terminal editing, and the 3-5x pixel-verification loop.
- Completed the light module: repaired the truncated Modal Dialog table, added
  a 14-item Verification Checklist and eight Light/Dark parity rules.
- Portability: removed all private absolute paths; bundled tokens and
  `DESIGN.md` in `references/`; documented the `--ks-*` prefix as a skill
  convention; made `--port`, `FIGCRAFT_APP`, and `FIGCRAFT_DESIGN` configurable.
- Bundled scripts in `scripts/` (with no one-off build containing private
  paths): `figcraft_tool.py`, `build_artistic_flow.py`, `agent_terminal.py`,
  `quick_design.py`, `audit_render.py`, `multi_agent_worker.py`.
- Guardrails: every subprocess/socket uses timeouts; every read/poll/REPL loop
  has a cut-loop guard (`--max-events`, `--max-seconds`, bounded `recv()`
  chunks, bounded REPL lines).
- Unified harness: `harness-info` reports the name `kuron-design-figcraft` and
  version `3.0.0` (previously `kuron_design_crafting` 2.5.1).
- Tests: converted four test scripts to `unittest.TestCase` and added
  `test_package_hygiene.py` (zero-leak, frontmatter, version lock).
- Distribution: `install.sh` installs into
  `<target>/skills/kuron-design-figcraft/` and verifies versions + tests.

## Legacy history (condensed)

- 2.5.1 — name identity (name ≠ ID) + living-file discipline.
- 2.5.0 — machine map & anti-illusion (pixels > eyes > JSON).
- 2.4.0 — yin-yang + version lock + dialog/empty/error/ledger builders.
- 2.3.0 — red-team integration, `build_connector`, lint S-01/S-02/S-08.
- 2.2.0 — 3-5x verification loop + `DESIGN.md` supremacy.
