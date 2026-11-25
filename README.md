# kuron-design-figcraft

**Token-driven UI design + visual PNG verification for FigCraft (`.figcraft`).**

A standalone AI-agent skill that turns a design brief into token-compliant UI
screens and then *proves* them with rendered PNGs. It bundles the design
constitution, four dynamic style directions, a layered token architecture, the
live editing workflow, and a mandatory 3–5x pixel-verification loop. No private
paths, no credentials, no dependency on a specific repository, brand, or style.

- **Design first:** every consuming project **must** have a `DESIGN.md` — the
  single source of truth for colour, type, spacing, radius, motion, style
  direction, accessibility, and states. It ships a machine-parseable
  `design-contract/v1` JSON block (`references/DESIGN.md`).
- **Dynamic by default:** choose `dense_operational`, `bento_modular`,
  `editorial`, `clean_utility`, or `custom` from the domain brief. Coral/cyan
  and fixed sizes in the bundled preset are **examples**, not identity.
- **Layered tokens:** `primitive → semantic → component → theme/state`.
  Components never call raw values; one role = one token (`--ks-*` aliases).
- **Visual proof:** a build is not done until `lint_design()` reports zero warnings
  **and** an exported PNG has been inspected pixel by pixel (minimum 3 clean
  passes, maximum 5).
- **Live control:** `scripts/agent_terminal.py` drives a running FigCraft instance
  over a configurable TCP port, with timeouts and bounded loops everywhere.
  Live Editing, Live Generate (Components / Screen / Form / modal-drawer /
  list-table), Live Feedback, Live Audit/Diff/Export are mandatory capabilities.
- **Visual regression guard:** text must never escape its border/frame, clip,
  overlap, or disagree with the rendered PNG.

> **Mandatory motto:** *"Not code that is clever and impressive, but code that is
> targeted, correct, and fits the actual need and root cause."* If a real trial
> shows the result is still lacking, keep fixing it together with
> `Kuron Developer` until it is correct and on-target — never stop at "it runs".

---

## Quick Start

```bash
# 1. Install into any harness skills directory (default: ~/.claude/skills/...)
bash install.sh /path/to/harness/skills/kuron-design-figcraft

# 2. MANDATORY: copy the template into your project root and edit the JSON block
cp <skill>/references/DESIGN.md ./DESIGN.md
#    set style_direction, map action-primary / data-technical, a11y, states
#    keep the two <!-- design-contract:v1:* --> sentinels around the JSON

# 3. From the installed package root: generate a design + preview PNG
python3 scripts/quick_design.py "Project dashboard" -o out/workbench.figcraft --preview
# 3b. Live Generate (Components / Screen / Form), driven by style_direction
python3 scripts/quick_design.py --generate screen --style bento_modular -o out/screen.figcraft
python3 scripts/quick_design.py --generate components -o out/components.figcraft
python3 scripts/quick_design.py --generate form --style clean_utility -o out/form.figcraft

# 4. Live session: discover IDs, edit, export, inspect, stop
python3 scripts/agent_terminal.py --port 9880 start --file out/workbench.figcraft
python3 scripts/agent_terminal.py --port 9880 frames
python3 scripts/agent_terminal.py --port 9880 export-all -o out/previews/ --scale 2
python3 scripts/agent_terminal.py --port 9880 stop

# 5. Objective render audit + full test suite
python3 scripts/audit_render.py out/workbench.figcraft
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The `--port` flag is global and must appear **before** the subcommand. Defaults
are starting points, not requirements: override the port on every command, set
`FIGCRAFT_APP` for a non-default binary, `FIGCRAFT_DESIGN` for the working file,
and `FIGCRAFT_DESIGN_MANIFEST` for a custom `DESIGN.md` location.

---

## Design Approach (2026 standard)

This skill works as a modern product designer, not a screen generator:

1. **Domain first.** Brief on app type, target user, main problem, and intended
   outcome; then offer 2–3 layout/style directions (`dense operational`,
   `bento / modular`, `editorial`, `clean utility`, or `custom`) for the user to
   steer. AI slop and one-size-fits-all layouts are rejected in favour of
   cognitive clarity. The decision is written into `DESIGN.md` before building.
2. **Full-spectrum UX.** Flows and information hierarchy, functional microcopy,
   real `empty`/`loading`/`error`/`disabled`/`focus`/`success` states and
   data-length variants, proportionate AI-status patterns, and accessible
   handoff-ready composition — no "hollow" screens.
3. **Component-first reuse.** Build base components with clear variants and a
   `primitive → semantic → component` token hierarchy, then **duplicate and
   refine** existing nodes for new screens instead of rebuilding from scratch.
4. **Sharp execution.** Measured, decisive calls; short time-boxing; no
   overthinking — with the zero-leak, green-tests, and 3–5x PNG checks intact.

Full spec: `references/product-designer-2026.md`,
`references/style-directions.md`, and `references/token-architecture.md`.

---

## Live capabilities & visual regression guard

| Capability | Contract |
|---|---|
| Live Editing | change node/properties/**tokens** in-session and sync (`exec`, `save`, `reload`, `watch`); prove with `diff` + new PNG |
| Live Generate | create Components, Screen, Form, modal/drawer, list/table in-session using builders + `DESIGN.md` tokens; discover IDs with `frames` |
| Live Feedback / Audit / Diff / Export | `status`, `frames`, `diff`, `watch`, `audit_render.py`, `export/export-all`; PNG is the evidence, never JSON alone |

Six defects must never pass: text outside a border/frame; clipped or overlapping
text; `clip: false` overflow; inconsistent Auto-Layout sizing/padding/gap;
duplicated nodes losing parent styling/padding; and JSON that disagrees with the
real PNG. See `references/live-editing-workflow.md` §1.1 & §5.1,
`references/dark-artifact-rules.md` §4, and `references/patterns.md` §6.1.

**Phase 2 acceptance:** after `Kuron Developer` refactors `scripts/`,
`Kuron Designer` runs a real trial (live generate → live edit → pixel audit) and
the pair keeps fixing until all six guards pass — not until tests merely go green.

---

## DESIGN.md contract (machine-parseable)

`DESIGN.md` is mandatory. The parser extracts only the JSON between
`<!-- design-contract:v1:start -->` and `<!-- design-contract:v1:end -->` and
validates it with the standard library. Key shape:

```json
{
  "$schema": "kuron-design-figcraft/design-contract/v1",
  "style_direction": "dense_operational",
  "default_theme": "dark",
  "locale": "id-ID",
  "tokens": {
    "primitive": { "color": {"brand": {"dark": "#...", "light": "#..."}}, "space": {"2": 8} },
    "semantic": { "color": {"action-primary": "$primitive.color.brand"} },
    "component": { "button": {"height": {"md": 32}} }
  },
  "a11y": { "minContrast": "AA", "minTouchTargetPx": 44 },
  "states": ["default", "hover", "focus", "disabled", "empty", "loading", "error", "success"]
}
```

- Values are literals or `$...` references resolved through
  `primitive → semantic → component`; theme colours always carry `dark`+`light`.
- Roles are stable (`action-primary`, `data-technical`, `status-*`), their
  values are fully overridable. Missing or invalid `DESIGN.md` is an actionable
  error — never a silent fallback to preset.
- Full schema, resolver, and acceptance checklist: `references/DESIGN.md`.

---

## Package Structure

```text
kuron-design-figcraft/
├── DESIGN.md                      # package manifest (explicit preset + extensions)
├── SKILL.md                       # single contract (name + version 3.1.0)
├── README.md                      # this file
├── LICENSE                        # MIT
├── VERSION                        # 3.1.0 — single source of truth
├── CHANGELOG.md
├── .gitignore
├── install.sh                     # portable installer + version lock
├── references/
│   ├── DESIGN.md                  # MANDATORY contract + template (design-contract/v1)
│   ├── design-tokens.css          # portable DEFAULT PRESET, 4 token layers
│   ├── token-architecture.md      # primitive → semantic → component → theme/state
│   ├── style-directions.md        # 4 dynamic directions + token levers
│   ├── product-designer-2026.md   # 4 pillars: domain, full-spectrum UX, reuse, sharp execution
│   ├── patterns.md                # dynamic layout grammar + anti-hardcode
│   ├── dark-artifact-rules.md     # execution, builder, anti-assumption, 3–5x loop
│   ├── light-glass-system.md      # theme/surface, glass, parity, accessibility
│   └── live-editing-workflow.md   # agent_terminal.py workflow + guardrails
├── scripts/
│   ├── design_manifest.py         # find/validate/resolve DESIGN.md, build tokens
│   ├── figcraft_tool.py           # builders, manifest TOKENS, lint_design(), save()
│   ├── build_artistic_flow.py     # resolve_tree_layout() reflow engine
│   ├── agent_terminal.py          # live TCP bridge (HARNESS_VERSION)
│   ├── quick_design.py            # rapid generator + Live Generate + PNG preview
│   ├── audit_render.py            # overflow/clip/contrast/topology audit
│   └── multi_agent_worker.py      # partitioned-ID parallel work + lock
└── tests/
    ├── test_builders.py
    ├── test_lint_rules.py
    ├── test_save_guard.py
    ├── test_layout_engine.py
    ├── test_design_manifest.py    # missing/invalid manifest, cycles, theme pair, overrides
    ├── test_no_frozen_hex.py      # no frozen colour literals in scripts
    ├── test_live_generate.py      # Components/Screen/Form across style directions
    └── test_package_hygiene.py    # zero-leak + frontmatter + version lock
```

`SKILL.md` is the entry point; `references/` files are the detailed spec so the
main contract stays scannable.

---

## Running Tests

From the package root:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
# If pytest is available:
python3 -m pytest -v
```

`test_package_hygiene.py` scans the whole package for absolute private paths
and credential-like strings, validates that `SKILL.md` has valid frontmatter
with `name: kuron-design-figcraft`, and asserts that `VERSION`,
`SKILL.md metadata.version`, and `scripts/HARNESS_VERSION` are all identical.
The remaining tests cover builders, linter rules, multi-page save guards, and
the text-measurement layout helper.

---

## Limitations

- The FigCraft engine is a closed binary. This package talks to it through a
  documented TCP JSON-RPC bridge; it does not include or reverse-engineer the
  engine. `figcraft-cli`, when installed, is an optional headless arbiter.
- PNG preview/export needs the FigCraft app available locally. Set
  `FIGCRAFT_APP` for non-default installs; headless token/lint/builder work
  does not need the app. `quick_design.py --preview` renders through the live
  bridge when it can and otherwise reports "Preview not generated" — it never
  claims a PNG that was not written.
- Port `9880` may be occupied by another agent. Check `status` first, run
  `stop`, and pass `--port` to use a different control port.
- Only one process may write a given `.figcraft` file at a time; `watch` is
  read-only. Parallel work uses ID namespaces plus a lock file.
- The bundled preset copy and colours are neutral English defaults. Treat
  them as a configurable starting point via `locale`, `copy_tone`, and
  `DESIGN.md` — not a hard requirement.
- `watch` is intentionally bounded (`--max-events`, `--max-seconds`) so an
  agent session cannot run forever — restart it for a longer session.
- Scripts resolve all values from `DESIGN.md` through `design_manifest.py`.
  A consuming project without a manifest fails with an actionable error; the
  skill package ships its own explicit `DESIGN.md` for internal tooling.

---

## License

MIT — see [LICENSE](LICENSE).
