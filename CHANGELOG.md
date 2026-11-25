# Changelog — kuron-design-figcraft

One version for the whole package: `VERSION`, the `SKILL.md` frontmatter, and
`HARNESS_VERSION` are always identical.

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
