# kuron-design-figcraft

**Token-driven UI design + visual PNG verification for FigCraft (`.figcraft`).**

A standalone AI-agent skill that turns a design brief into token-compliant UI
screens and then *proves* them with rendered PNGs. It bundles four things that
used to live in separate places: the dark workbench rules, the light
glassmorphism system, the live editing workflow, and a mandatory 3–5x
pixel-verification loop. No private paths, no credentials, no dependency on a
specific repository.

- Core design: every colour, spacing, radius, and type value comes from
  portable `--ks-*` tokens (`references/design-tokens.css`) and
  `references/DESIGN.md`.
- Visual proof: a build is not done until `lint_design()` reports zero warnings
  **and** an exported PNG has been inspected pixel by pixel (minimum 3 clean
  passes, maximum 5).
- Live control: `scripts/agent_terminal.py` drives a running FigCraft instance
  over a configurable TCP port, with timeouts and bounded loops everywhere.

---

## Quick Start

```bash
# 1. Install into any harness skills directory (default: ~/.claude/skills/...)
bash install.sh /path/to/harness/skills/kuron-design-figcraft

# 2. From the installed package root: generate a design + preview PNG
python3 scripts/quick_design.py "Project dashboard" -o out/workbench.figcraft --preview

# 3. Live session: discover IDs, edit, export, inspect, stop
python3 scripts/agent_terminal.py --port 9880 start --file out/workbench.figcraft
python3 scripts/agent_terminal.py --port 9880 frames
python3 scripts/agent_terminal.py --port 9880 export-all -o out/previews/ --scale 2
python3 scripts/agent_terminal.py --port 9880 stop

# 4. Objective render audit + full test suite
python3 scripts/audit_render.py out/workbench.figcraft
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The `--port` flag is global and must appear **before** the subcommand. Defaults
are starting points, not requirements: override the port on every command, and
set `FIGCRAFT_APP` if the FigCraft binary is not at the macOS default location.

---

## Package Structure

```text
kuron-design-figcraft/
├── SKILL.md                       # single contract (name + version 3.0.0)
├── README.md                      # this file
├── LICENSE                        # MIT
├── VERSION                        # 3.0.0 — single source of truth
├── CHANGELOG.md
├── .gitignore
├── install.sh                     # portable installer + version lock
├── references/
│   ├── patterns.md                # --ks-* tokens, geometry, layout patterns
│   ├── dark-artifact-rules.md     # dark rules, builder contract, 3–5x loop
│   ├── light-glass-system.md      # light mode, glass, components, parity
│   ├── live-editing-workflow.md   # agent_terminal.py workflow + guardrails
│   ├── design-tokens.css          # portable dark/light token definitions
│   └── DESIGN.md                  # portable design constitution
├── scripts/
│   ├── figcraft_tool.py           # builders, TOKENS, lint_design(), save()
│   ├── build_artistic_flow.py     # resolve_tree_layout() reflow engine
│   ├── agent_terminal.py          # live TCP bridge (HARNESS_VERSION)
│   ├── quick_design.py            # rapid generator + PNG preview
│   ├── audit_render.py            # numeric render audit
│   └── multi_agent_worker.py      # partitioned-ID parallel work + lock
└── tests/
    ├── test_builders.py
    ├── test_lint_rules.py
    ├── test_save_guard.py
    ├── test_layout_engine.py
    └── test_package_hygiene.py    # zero-leak + frontmatter + version lock
```

`SKILL.md` is the entry point; the `references/` files are the detailed spec so
the main contract stays scannable.

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
  does not need the app.
- Port `9880` may be occupied by another agent. Check `status` first, run
  `stop`, and pass `--port` to use a different control port.
- Only one process may write a given `.figcraft` file at a time; `watch` is
  read-only. Parallel work uses ID namespaces plus a lock file.
- Default UI copy is Indonesian. Treat it as a configurable locale, not a
  hard requirement; substitute neutral copy without changing token values.
- `watch` is intentionally bounded (`--max-events`, `--max-seconds`) so an
  agent session cannot run forever — restart it for a longer session.

---

## License

MIT — see [LICENSE](LICENSE).
