---
name: kuron-design-figcraft
description: Token-driven UI design in FigCraft (.figcraft) with a MANDATORY project DESIGN.md as single source of truth, dynamic style directions (dense operational, bento/modular, editorial, clean utility), primitive→semantic→component token hierarchy, zero-hardcode rules, live terminal editing, and a mandatory 3-5x pixel-verification loop before any design claim.
metadata:
  author: Kuron Studio Team
  license: MIT
  version: "3.2.1"
---

# kuron-design-figcraft — DESIGN.md-Driven Design + FigCraft Visual Verification

A self-contained skill for designing, modifying, and verifying UI screens in
`.figcraft` format. It unifies the design contract, token architecture, four
dynamic style directions, live editing, and the pixel-verification loop into one
inseparable whole with its companion scripts:

- **Yin (contract):** the rules in this `SKILL.md` and `references/`.
- **Yang (execution):** builders, linter, live terminal, and exporter in `scripts/`.

Rules without scripts are never executed; scripts without rules produce *slop*.
Any change on one side must update the other, and the same version must be
locked in `VERSION`, this frontmatter, and `HARNESS_VERSION`.

> **Mandatory motto:** targeted, accurate code that directly solves the
> requirement and its root cause. Maintainer workflow notes are in
> `CONTRIBUTING.md`.

Compatible with Claude Code, Codex, Cursor, Antigravity, and generic harnesses.
It depends on no absolute path, specific repository, credential, or fixed
brand/style. Language tone, colour, and style direction are decided by the
consuming project, not by this skill.

---

## Module Map

| Need | Read | Script |
|---|---|---|
| Mandatory project constitution + machine-readable template | `references/DESIGN.md` | `scripts/design_manifest.py` |
| Product Designer 2026 four pillars | `references/product-designer-2026.md` | — |
| Dynamic style directions and token levers | `references/style-directions.md` | `scripts/quick_design.py` |
| `primitive → semantic → component` hierarchy | `references/token-architecture.md` | `figcraft_tool.py` |
| Layout grammar and anti-hardcode rules | `references/patterns.md` | `figcraft_tool.py`, `quick_design.py` |
| Execution, builders, anti-assumption, 3-5x loop | `references/dark-artifact-rules.md` | `figcraft_tool.py`, `build_artistic_flow.py` |
| Themes, surfaces, glass, parity, accessibility | `references/light-glass-system.md` | `figcraft_tool.py` |
| Live session, port, sync, guardrails | `references/live-editing-workflow.md` | `agent_terminal.py`, `multi_agent_worker.py` |
| Portable colour/size preset | `references/design-tokens.css` | — |
| Objective audit (all boards: utilisation, overlap, overflow, contrast, topology) | `references/dark-artifact-rules.md` | `audit_render.py` |
| Three boards + copy-don't-rebuild smart reuse | this file, §3.1 | `figcraft_tool.py`, `quick_design.py` |

All commands below run from the **skill package root**. Relative paths are
portable. `scripts/agent_terminal.py` supports the global `--port <PORT>` flag,
which must be placed **before** the subcommand.

---

## 0. Product Designer 2026 — Four Pillars (gate before design)

Details: `references/product-designer-2026.md`. In short:

1. **Domain → outcome → style options.** Run the four-question brief (app type,
   target user, main problem, measurable outcome), then offer 2-3 style/layout
   directions (`dense operational`, `bento / modular`, `editorial`,
   `clean utility`, or `custom`) appropriate to the context — the user steers.
   Reject AI slop; prioritise *cognitive clarity*. Write the brief result into
   `DESIGN.md` before building.
2. **Full-spectrum design, zero hollow screens.** UX flow and information
   architecture, functional microcopy (action + object, cause + solution),
   complete states (`empty`, `loading`, `error`, `disabled`/`focus`, `success`,
   long text/data), proportionate and transparent AI-status patterns, and
   accessible, handoff-ready composition.
3. **Component-first: `Duplicate → Refine`, on three boards.** Build base
   components first (input, form, button, icon, card/list item) with clear
   variants and the `primitive → semantic → component → theme/state` hierarchy.
   In FigCraft, duplicate an existing component node and refine it — never
   rebuild every screen from scratch. The three boards below are the mandatory
   container for that work.
4. **Sharp execution.** Measured, decisive calls; short time-boxing; no
   overthinking. The guardrails remain absolute (zero private paths, zero
   secrets, green tests, 3-5x PNG checks).

---

## 1. DESIGN.md — Mandatory and Supreme (gate number one)

**Every consuming project MUST have a `DESIGN.md`.** Without one, the agent
stops with a clear, actionable error — it is forbidden to silently use the
skill preset as if it were a project decision. The full template and machine
specification live in `references/DESIGN.md`.

1. **Single source of truth.** `DESIGN.md` binds colour, typography, spacing,
   radius, motion, style direction, `locale`/`copy_tone`, `a11y`, and `states`.
   `design-tokens.css` is a **portable preset**, not an authority.
2. **Machine-parseable.** One JSON block between the sentinels
   `<!-- design-contract:v1:start -->` / `<!-- design-contract:v1:end -->`
   is read with `json.loads`. `$schema` = `kuron-design-figcraft/design-contract/v1`.
3. **Resolution.** Search upward from the project root (stopping at the repo
   boundary); a custom path is set via `FIGCRAFT_DESIGN_MANIFEST`. Validation
   covers required keys, resolvable `$...` references without cycles, complete
   `dark`/`light` pairs, and passing contrast.
4. **Failure = actionable error**, never a silent fallback.
5. **Silence means `DESIGN.md` wins.** A user request overrides this document
   only where explicitly stated. Violations are recorded in the report rather
   than silently normalised.
6. **Cleanliness.** `DESIGN.md` must contain no private path, secret, CDN URL,
   or internal engine ID.

---

## 2. Token Architecture and Dynamic Style Directions

### 2.1 Hierarchy (see `references/token-architecture.md`)

```text
primitive (raw values)  →  semantic (roles)  →  component (sizes/variants)
                        →  theme/state (dark/light, hover/focus/empty/…)
```

- Components are **forbidden** to call primitives directly.
- **One role = one token.** `action-primary` is not a synonym for "red";
  `data-technical` is not a synonym for "cyan". Colours are freely overridden
  in `DESIGN.md`.
- Tints are always `color-mix(in srgb, var(--token) N%, transparent)` →
  automatic theme parity. At most three elevation levels.
- Scales (space/radius/type/motion) are ordinal ladders, never magic numbers.

### 2.2 Four directions (see `references/style-directions.md`)

| ID | Best for | Character |
|---|---|---|
| `dense_operational` | professional work, dense data | compact rows, dense tables, actions next to data |
| `bento_modular` | multi-module dashboards | asymmetric cards, elevation 2-3 |
| `editorial` | content and long-form reading | typographic rhythm, measured reading width |
| `clean_utility` | narrow tools, setup, forms | one focus, minimal decoration |

These presets are **not a cage**: they may be combined or replaced by `custom`,
as long as `DESIGN.md` records `style_direction` + `style_notes`. Glassmorphism
is **optional** by direction — `editorial`/`clean_utility` may omit it.

---

## 3. Core Philosophy

1. **`DESIGN.md` is the only source of values.** Colour, padding, gap, radius,
   and typography follow the roles mapped there. Inventing "looks good" numbers
   or hex values is forbidden.
2. **One protagonist per screen.** Exactly one `action-primary` action above
   the fold. `data-technical` is reserved for short monospace technical data
   (coordinates, IDs, counters).
3. **Layout grammar, not a frozen template.** The `shell/chrome/rail/canvas/
   inspector/grid/table/article/form/dialog` blocks are assembled per style
   direction — never one wirescreen for every domain. Rhythm comes from
   `semantic.space`.
4. **Pixels > eyes > JSON.** A green lint run is not proof. The only proof of
   visual correctness is an exported PNG that has been opened and inspected.
5. **Every visual claim must be fresh.** Live sessions go stale, IDs shift,
   and `save()` always runs reflow.

### 3.1 Three-Board Standard and Smart Reuse (mandatory)

In multi-page mode the design system uses **one dedicated page per board**:
`pages[0]` is `00_Foundations`, `pages[1]` is `01_Components`, and `pages[2]` is
`02_Screens`; optional exhibits such as `01_Reference` follow at `pages[3]`.
Use `doc.ensure_named_pages([...])` to create/reuse them and
`quick_design.py --preset three-pages` for the offline generator. Each board
keeps a token-derived `SPACE["xl"]` inset and a clean footer at the bottom.

The legacy adjacent layout remains available: three top-level frames on one
selected page of `pages[0..N]`, separated by `BOARD_GAP` (normally `120px`).
`three-board` defaults to `pages[0]` because the live canvas displays that page
first, but every script accepts a `page_index` / `page_name` selector and
preserves later pages untouched:

| Board | Content | Rule |
|---|---|---|
| `00_Foundations` | Semantic colour roles with hex values, typography scale (`Display` / `Heading` / `Body` / `Caption` / `Mono`), spacing and radius tokens | Every value comes from `DESIGN.md` |
| `01_Components` | Reusable bases and variants (`Button`, `Badge`, `NavItem`, `Card`, `Input`, `Row`, …) | Structured for direct duplication |
| `02_Screens` | Final screens | Repeated items are **copies** of nodes from `01_Components` |

**Descriptive labels and card fit (mandatory):** every board, screen,
component, foundation item, and reference section has a descriptive English
name and, where visible, an English caption — never an empty, `Untitled`,
`text`, or other generic placeholder. Wrapper cards contain their children
with clean padding and size around their content; no child escapes its parent
card unless the item is intentionally unboxed. `audit_render.py` enforces both
on every page with rules S-15 (labels) and S-16 (card containment/fit).

**Smart reuse rule — if a component already exists, copy it; do not rebuild
it.** Before creating anything, call `ensure_board()` / `find_or_reuse_component()`
from `figcraft_tool.py`. If the board or component is already present, reuse it
and change only the required properties, text, or coordinates. Use
`duplicate_node()` to deep-clone the full subtree with fresh unique node IDs
(so there are zero ID collisions), then refine the copy. Never rebuild a
repeated component from scratch in a screen. `generate_three_boards()` in
`quick_design.py` implements this end to end and is idempotent.

`find_or_reuse_component()` searches every page by default and
`duplicate_node()` copies templates into a target board on any page, so a
screen on `02_Screens` can reuse a component from `01_Components` without
rebuilding it.

`audit_render.py` audits each top-level board on every page independently and
scopes contrast and layout checks to that board, so neither neighbouring
boards nor other pages can produce false positives. It also verifies
descriptive English labels (S-15) and card containment/fit (S-16) on all pages,
and its PASS line reports how many labels and cards were checked. Use
`--page-index` or `--page-name` to filter the audit or the terminal's `frames`
/ `export-all` commands to one page.

**Engine honesty:** the live FigCraft canvas may display `pages[0]` by default
and its `document.inspect` output can truncate on very large documents. That
is a viewer behaviour, not a file limitation: `.figcraft` documents, offline
builders, reflow, the auditor, and the terminal are all multi-page compatible
and keep `pages[1..N]` intact. `export` / `export-all` with a non-zero page
selector open a read-only temporary projection that promotes the target page
to `pages[0]` for the engine, then reopen the original file and delete the
temporary copy; the multi-page source on disk is never written.

---

## 4. End-to-End Workflow

```text
read DESIGN.md (mandatory) → brief domain → choose style → write/validate DESIGN.md
       ↓
build components (Duplicate → Refine) + complete states
       ↓
build/compile (quick_design.py or figcraft_tool.py)
       ↓
lint_design() → zero warnings
       ↓
agent_terminal.py --port 9880 start --file <file>.figcraft
       ↓
frames → discover real IDs (NEVER guess)
       ↓
edit → watch / reload --soft → export / export-all
       ↓
open PNG → record defects → fix → REPEAT (3 minimum, 5 maximum passes)
       ↓
audit_render.py → stop → report
```

Minimal example:

```bash
python3 scripts/quick_design.py "three-board design system" -p three-board -o out/system.figcraft
python3 scripts/quick_design.py "Project dashboard" -o out/workbench.figcraft --preview
python3 scripts/agent_terminal.py --port 9880 start --file out/workbench.figcraft
python3 scripts/agent_terminal.py --port 9880 frames
python3 scripts/agent_terminal.py --port 9880 export-all -o out/previews/ --scale 2
python3 scripts/audit_render.py out/workbench.figcraft
python3 scripts/agent_terminal.py --port 9880 stop
```

The port is not a sacred constant: pass `--port` on every command, or to
`quick_design.py`. `9880` is only a starting value.

---

## 5. Execution and Artifact Modules

Details: `references/dark-artifact-rules.md` and `references/patterns.md`
(applicable to every theme, not only dark). Operational summary:

- **Mandatory builders** (from `figcraft_tool.py`): `build_button`,
  `build_badge`, `build_connector`, `build_dialog`, `build_empty_state`,
  `build_error_inline`, `build_ledger_row`, `build_pipeline_bar`, `Screen_*`.
  Do not assemble nodes manually.
- **Icon vs connector:** `create_vector` = grid-24 for icons; connectors/arrows
  use `build_connector` (raw pixel network, Manhattan route, automatic arrow
  head). Never mix the two.
- **Multiline text:** one line = one node. The renderer stacks `\n`.
- **Widget gate:** `lint_design()` reports zero warnings AND an exported PNG
  proves glyphs/icons rendered correctly.
- **Documentation canvas** (diagrams, flowcharts, token guides) is exempt from
  the `action-primary` CTA rule — do not paste a fake button.
- **Mandatory states** per `states` in `DESIGN.md`, including `empty/loading/
  error/disabled/focus/success`; the three list states must be distinct.

---

## 6. Theme and Surface Module

Details: `references/light-glass-system.md` (Modal Dialog, Verification
Checklist, Light/Dark parity — complete). Summary:

- Surfaces step through roles `bg → surface → surface-2 → raised`; the warm/
  white preset values may be fully replaced by `DESIGN.md`.
- Frosted glass is **only** for floating chrome/navigation/inspectors — never
  over reading areas, and optional for certain directions.
- One `action-primary` action; `data-technical` only for monospace technical
  data + `tabular-nums`. Both colours come from `DESIGN.md`.
- In `.figcraft`, glass must use the native `effect.add` type `glass`, not a
  translucent fill alone.
- Lucide icons, grid 24, stroke 1.75px, no emoji. Radius/elevation come from
  tokens; a fourth level is forbidden.
- **Light/dark parity:** every colour token has a `dark`/`light` pair; tints
  use `color-mix`, not new hex values. Minimum contrast is AA/AAA.

---

## 7. Live Module — Editing, Generate, Feedback, Audit, Export

Details: `references/live-editing-workflow.md`. **Live capabilities are
mandatory, not optional:**

| Capability | What must happen | Evidence |
|---|---|---|
| **Live Editing** | Change node/properties/**tokens** inside the session and sync to disk: `exec node.set`, `select.set`, `file.save`, `reload --soft/--hard`, `watch` | `diff --id` shows the change + a new PNG |
| **Live Generate** | Create **Components**, **Screen**, **Form**, modal/drawer, list/table, and other elements **inside the live session** using builders + `DESIGN.md` tokens | `frames` shows the new nodes; PNG proves the render |
| **Live Feedback** | `status`, `frames`, `diff`, `watch`, `reload`, `interactive`, `harness-info` | real IDs are readable, never guessed |
| **Live Audit** | `audit_render.py` (utilisation/overflow/contrast/topology) + pixel-by-pixel PNG inspection | audit numbers + PNG, not JSON alone |
| **Live Export** | `export` / `export-all` with `--scale`, relative output folder | PNG opened and inspected |
| **Other live flows** | `start`, `open`, `stop`, parallel work via `multi_agent_worker.py` | clean session, lock released, port changeable |

Cross-capability rules:

- **Live Generate must use `DESIGN.md` tokens**, never values frozen in a
  script. Generated components must expose the same variants/states as the
  existing ones (`duplicate → refine`).
- Every generate/edit is followed by `frames` (new IDs) → `diff` → `export` →
  open the PNG. **JSON is not proof; the PNG is proof.**
- `watch` is read-only and bounded by `--max-events`/`--max-seconds`.

```bash
python3 scripts/agent_terminal.py --port 9880 start --file <file>.figcraft
python3 scripts/agent_terminal.py --port 9880 frames          # discover IDs
python3 scripts/agent_terminal.py --port 9880 exec node.set '{"id": <ID>, "name": "<name>"}'
python3 scripts/agent_terminal.py --port 9880 diff --id <ID>
python3 scripts/agent_terminal.py --port 9880 watch <file>.figcraft -o out/previews/ --scale 2 --max-events 200 --max-seconds 600
python3 scripts/agent_terminal.py --port 9880 export-all -o out/previews/ --scale 2
python3 scripts/agent_terminal.py --port 9880 stop
```

Guardrails:

- Flag `--port` **before** the subcommand; `.figcraft` paths are cwd-tolerant.
- `exec` rejects invalid JSON with a friendly message.
- Run `frames` before `export`/`exec`; repeat after `reload`.
- `reload --soft` is the default; `--hard` only when the structure is stale.
  With no path it uses the file made active by `start`/`open`; a failed reload
  exits non-zero and `watch` never exports a stale document.
- `watch` is always bounded by `--max-events` / `--max-seconds` (cut-loop guard).
  It never modifies the source `.figcraft` file: it triggers a soft reload in
  the live session and writes exported PNGs to the output folder.
- Never run two writers on one file; `watch` is read-only.
- Never make claims from JSON metadata — evidence = PNG.
- A changed `DESIGN.md` is a visual change: reload tokens, reload, verify 3-5x.

For parallel work, `multi_agent_worker.py` partitions ID namespaces
(A `1000–1999`, B `2000–2999`) plus a `.figcraft.lock`.

---

## 8. Mandatory 3-5x Verification Loop

Every result must pass through this closed cycle:

1. **Build** → 2. **`lint_design()`** (zero warnings) → 3. **export PNG** →
4. **open the PNG and inspect pixel by pixel** → 5. **record every defect** →
6. **fix** → back to 1.

**Exit gate:** at least **3 full passes**, stopping only on a clean pass (zero
lint warnings + PNG matches intent). Maximum **5 passes**; if defects remain,
stop and report them — do not ship.

| Excuse | Reality |
|---|---|
| "One export is enough, it is green" | Lint cannot see collisions, giant lines, or typos inside nested nodes. |
| "Pass 1 is good, skip 2-3" | There is always a pass 2; hidden defects appear in the second render. |
| "It is only small text, no re-export" | Editing text = re-export. |
| "5 passes take too long" | Shipping *slop* costs three times more in revisions. |

**Hard checklist before claiming clean:** canvas utilisation ≥60%; no text
overflow; intact connector topology (every node has ≥1 input and ≥1 output
unless terminal); dot/status matches the semantic dictionary; hover/cursor/
selected are three distinct states; `clip: true` on screen frames; contrast
meets `a11y.minContrast`.

### 8.1 Visual Regression Guard — defects that must never pass

| Defect | Symptom | Mandatory detection | Fix |
|---|---|---|---|
| **Text outside a border/frame** | glyphs cross a card/column edge | lint S-08 + inspect the PNG pixel by pixel | fix `width`/`sizing`/Auto-Layout, never truncate the text |
| **Clipped/overlapping text** | line 2+ overlaps the node below; accidental `"..."` | PNG, not JSON | one line = one node; give it room (`width`, not `min-width`) |
| **`clip: false` leaking** | content escapes a 16px-radius screen frame | check `clip` on every screen-level frame | `clip: true` on screen frames; keep content in bounds |
| **Inconsistent auto-layout** | padding/gap "almost equal", random child fill/fixed/hug | compare with the `semantic.space` + `component.*` ladders | align mode/padding/gap/sizing with tokens |
| **Duplicate loses styling/padding** | duplicated node loses fill/stroke/radius/padding | `diff --id` of parent vs duplicate + PNG | copy from the parent component, then `refine` — never rebuild |
| **JSON ≠ real PNG** | metadata looks right but the render is wrong | open the exported PNG; ignore JSON claims | fix structure, `reload`, re-export, look again |

Three hard rules:

1. **Green lint + tidy JSON is not proof.** A freshly opened PNG is proof.
2. **Editing text = re-export.** No "only one letter changed" exception.
3. **Still defective after pass 5 = do not ship.** Keep improving together with
   `Kuron Developer` until it is correct and targeted (see the motto above).

---

## 9. Anti-Assumption and Anti-Illusion Rules

1. **Stale state:** run `frames` each session and after `reload`; visual claims
   require a fresh PNG.
2. **Vectors need both `strokes` and `stroke`:** both are required on
   `create_vector` output.
3. **Schema from live `save_file`, not a guess:** read `document.json` from the
   saved zip as the render contract.
4. **Live canvas shows `pages[0]` by default:** later pages stay in the file
   and are handled by every script with page selectors; verify them with
   `--page-index` / `--page-name`. A non-zero export page is passed to the
   engine via a read-only temporary projection, never by editing the source.
5. **`open_file` is cached per path:** headless edit then reopening the same
   path is stale; force reload via close+open.
6. **`save()` always reflows:** do not tune `y` manually — fix the structure
   (layout/padding/sizing) or it reverts on the next save.
7. **Closed engine binary:** `figcraft-cli` is an optional arbiter; when it is
   unavailable, use the bundled headless fallback. Do not theorise about engine
   behaviour — build a small probe file and measure its pixels.

---

## 10. Name Identity and Living-File Discipline

Numeric node IDs can shift between saves. Before mutating, match the **fresh**
`id + name` pair from load; identify nodes by `name`, not by ID.

Do not write to a file while the user's app has it open — request a pause,
back up, and coordinate the reload. Lint + parity on **every save** catches
stray edits: drift >2px or a new warning versus baseline means revert first,
investigate afterwards.

---

## 11. Anti-Hardcode and Absolute Cleanliness

| Forbidden | Use instead |
|---|---|
| Frozen hex/design-system colours in builders | `action-primary`, `bg`, `data-technical` roles from `DESIGN.md` |
| Free-form spacing/radius/font numbers | `semantic.space/radius/type` ladders, `component.*` |
| One style/brand/project title as "standard" | `style_direction`, `style_notes`, `locale`, `copy_tone` |
| One project's narrative flow as a fixed template | the screen map in the project `DESIGN.md` |
| One UI language as mandatory | project `locale` + `copy_tone` |
| Absolute port/path/binary constants | `--port`, env `FIGCRAFT_APP`, `FIGCRAFT_DESIGN`, `FIGCRAFT_DESIGN_MANIFEST` |
| CDN URL / private path / secret / credential | offline assets, clean values, `.gitignore` |

Every subprocess and socket uses a timeout; every read/polling loop has a hard
cut-loop guard, so an agent can never hang.

---

## 12. Script Contract and Version Lock

| File | Role |
|---|---|
| `scripts/design_manifest.py` | find/parse/validate/resolve `design-contract/v1`, build tokens, describe overrides |
| `scripts/figcraft_tool.py` | builders, manifest-sourced `TOKENS`, `lint_design()`, `save()`, JSON-RPC client |
| `scripts/build_artistic_flow.py` | `resolve_tree_layout()` used by `save()`; full reference-flow generator |
| `scripts/agent_terminal.py` | start/stop/frames/export/export-all/reload/diff/watch/exec/harness-info |
| `scripts/quick_design.py` | rapid generator + Live Generate + PNG preview |
| `scripts/audit_render.py` | utilisation/overflow/clip/contrast/topology audit |
| `scripts/multi_agent_worker.py` | partitioned IDs + lock for parallel work |

**Script obligations toward `DESIGN.md` (implemented across 3.2.x):**

1. Find and parse the `design-contract/v1` JSON block before build/lint/export.
2. Resolve `$...` references, choose the theme, map roles → builders; validate
   contrast, touch targets, and `states`.
3. **No frozen colour/size dictionaries** in `TOKENS`/builders/generators; the
   preset is an explicit file (`DESIGN.md` at the package root), never a silent
   in-code fallback.
4. Report every override and every contract violation; fail with an actionable
   message if `DESIGN.md` is missing or invalid.
5. Preserve existing builder/port/environment names for compatibility.

`design_manifest.py` is the single adapter: `load_design()`, `validate()`,
`resolve()`, `to_builder_tokens()`, and `describe_overrides()`. Builders read
semantic roles (`action-primary`, `data-technical`, …); legacy `TOKENS["colors"]`
aliases remain as compatibility keys but carry manifest-resolved values.

Maintainer-only process notes (including the mandatory real joint trial) live in `CONTRIBUTING.md`.

The FigCraft binary location can be overridden with `FIGCRAFT_APP` (platform
default on macOS), the working file with `FIGCRAFT_DESIGN`, and the design
manifest with `FIGCRAFT_DESIGN_MANIFEST`.

Single version: `VERSION` = frontmatter `metadata.version` =
`HARNESS_VERSION` = `harness-info` manifest = **`3.2.1`**.
`install.sh` refuses installation when versions are out of sync.
