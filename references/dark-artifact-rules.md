# Artifact Rules — Execution, Builder, and Verification Contract

> The filename is kept for compatibility. The content applies to **every theme
> and every style direction**, not only dark. Themes differ only in the token
> values in `DESIGN.md`.

This module binds the artistic rules, builder contract, and verification loop.
Companions: `patterns.md` (layout grammar), `DESIGN.md` (source of values),
`light-glass-system.md` (theme/surface), `live-editing-workflow.md` (terminal).

---

## 1. Supremacy of DESIGN.md

Every colour, padding, margin, gap, radius, type value, and layout **MUST**
follow the project's `DESIGN.md` and the roles mapped there. No values outside
the contract, no "roughly nice" numbers.

- **Roles, not colours.** `action-primary` = one main action; `data-technical` =
  coordinates/IDs/counters in mono; `status-*` = status. Colours are freely
  overridable.
- A custom user request overrides `DESIGN.md` **only on what is stated
  explicitly**. Silence means `DESIGN.md` wins.
- If a request conflicts with a role or contrast, follow the user but **report
  it** — never normalise it silently.
- Bundled presets are used only when a project copies them into its own
  `DESIGN.md`.

---

## 2. Artistic Rules Above Tokens

> **Documentation canvas exception:** architecture diagrams, flowcharts, and
> token guides are NOT working screens — they are exempt from the
> `action-primary` CTA requirement. Do not paste fake action buttons there.

1. **One protagonist per screen.** Within three seconds it is clear what to
   click. Exactly one main action above the fold; the active card gets a 2px
   `action-primary` outline, others a neutral `line` hairline.
2. **Spacing rhythm from `semantic.space`.** No "almost the same but different"
   gaps.
3. **Three-sweep hierarchy.** Heading (`display`/`heading`) → body (`body`) →
   meta (`mono`, `tabular-nums`).
4. **`data-technical` only for technical data.** Never for headings or
   decoration; `action-primary` only for the main action and active selection
   outline.
5. **Badges/chips have no border** and sit on token-derived soft tints. Progress
   bars are 3–6px; fill uses `action-primary` only at 100%, otherwise
   `data-technical`.
6. **Real microcopy.** Buttons name action + object; errors give cause + way
   out; empty states offer an action. No lorem/placeholder text.
7. **Keyboard and motion.** `ring` focus is always visible; shortcuts are shown;
   `prefers-reduced-motion` is respected; touch targets are ≥
   `a11y.minTouchTargetPx`.
8. **1px detail.** Window bar height comes from `component` presets, single
   hairlines, no gradients, decorative shadows, or emoji as icons.

---

## 3. Builder Contract (use `figcraft_tool.py`)

| Component | Builder | Required anatomy |
|---|---|---|
| Button | `build_button` (+`icon_name`) | frame + vector icon + label; one main action per screen |
| Badge/chip | `build_badge` | pill frame + mono text; no border, on soft tint |
| Toggle | frame + knob | `status-success` track when ON; full pill radius |
| Input | frame + text | masked credentials (`••••`), mono font |
| Screen | `Screen_*` | chrome + body |
| Dialog/modal | `build_dialog` | scrim + `card`-radius frame + header + body + footer (one primary + Cancel) |
| Empty state | `build_empty_state` | heading + description + action; no illustration |
| Error inline | `build_error_inline` | borderless badge + cause + way out + [Retry] |
| Ledger row | `build_ledger_row` | `#/Page/Original/Result/Load/Check`; 1px separator; three states |
| Pipeline bar | `build_pipeline_bar` | flow stages, arrow `→`, active stage in `action-primary` on soft tint |
| Connector | `build_connector` | raw pixel network, Manhattan routing, automatic arrowheads |

> **Script contract (active in `3.2.2`):** builders must not carry a frozen
> colour/size dictionary. `TOKENS` must be resolved from the project's
> `DESIGN.md` at build time. Builder names above stay stable; values are dynamic.

**Icons vs lines — two different machines.** `create_vector` multiplies a path
as a 24-grid icon; do **not** use it for lines/connectors/arrows (coordinates
explode 4–8x). Connectors use a raw pixel network with `strokes` + `stroke`.
One network per arrow may have multiple subpaths (line + arrowhead); elbows are
orthogonal, not diagonal.

**Flow topology:** every node must have ≥1 incoming and ≥1 outgoing edge
(except terminals). Orphan arrows are defects.

**Multiline text:** one line = one node (`D1`/`D2`). The renderer stacks `\n`,
so lines 2+ overwrite the node below.

Verify every build: `lint_design()` with **0 warnings** AND an exported PNG
showing glyphs/icons rendered correctly (reading JSON is not enough).

**Reuse (Duplicate → Refine):** before building a screen, copy an existing
component node, then adjust what is off. Include real states — `empty`,
`loading/skeleton`, `error`, `disabled/focus`, and text/data length variants —
so no screen is hollow. Details: `product-designer-2026.md`.

---

## 4. Mandatory 3–5x Verification Loop

One pass is never enough — visual defects slip past lint (giant lines, text
collisions, typos inside nodes). Every result MUST pass this cycle:

```text
Build → lint_design (0 warnings) → export PNG → inspect the PNG pixel by pixel
     → record every defect → fix → (back to Build)
```

**Exit gate:** at least **3 full passes**; stop only on one fully clean pass
(lint 0 + PNG matches intent). Maximum **5 passes** — if defects remain, stop,
report them, do not ship.

| Excuse | Reality |
|---|---|
| "One export is enough, lint is green" | Lint cannot see collisions/line weight/slop. The PNG is the only proof. |
| "Pass 1 looks good, skip 2–3" | There is always a pass 2; hidden defects appear on the second render. |
| "It is only small text" | Editing text = re-export. |
| "Five passes take too long" | Shipping slop costs three times more in revisions. |

**Red flags — repeat the pass:** claiming "it looks good" without a new PNG;
fixing without re-exporting; reading JSON instead of looking at the image.

**Hard checklist before claiming clean:**
1. Canvas utilisation ≥60% (content bounding box vs frame area; >150px dead
   space at the bottom = reject).
2. No text overflow (lint S-08 silent + the eye: no glyph overlaps).
3. Graph topology intact (every node has ≥1 incoming and ≥1 outgoing, except
   terminals).
4. Dots/statuses match the semantic dictionary (success/warn/muted/info carry
   the right meaning).
5. Three distinct list states: hover / keyboard cursor / persistent selection.
6. `clip: true` on screen frames.
7. Text/layer contrast meets `a11y.minContrast` in both themes.

**Visual Regression Guard (must never pass):** text outside a border/frame;
clipped or overlapping text; `clip: false` overflow; Auto-Layout inconsistency
(padding/gap/sizing drifting from tokens); duplicated nodes losing parent
fill/stroke/radius/padding; and JSON that disagrees with the real PNG. Check all
of these in the **PNG**, never in metadata. If defects remain after pass 5, do
not ship — keep fixing together with `Kuron Developer` until it is correct and
on-target.

---

## 5. Anti-Assumption Rules

Four assumptions proven wrong by render evidence — do not repeat them:

1. **Stale state.** Never guess IDs/structure from a previous session. Run
   `frames` each session and after `reload`; visual claims require a fresh PNG.
2. **Vectors need `strokes` + `stroke`.** Nodes from `create_vector` must have
   both. A file without `strokes` renders invisibly even with a valid network.
3. **Schema from live `save_file`, not a guess.** Create a node through the live
   API → `save_file` → read `document.json` from the zip. That is the engine's
   rendering contract.
4. **The live canvas shows the first page by default.** The `.figcraft` file and
   every bundled script are multi-page (`pages[0..N]`): reflow and save preserve
   later pages. Use `--page-index` / `--page-name` on `frames`, `export`,
   `export-all`, and `audit_render.py` to verify a specific page. Export of a
   non-zero page uses a read-only temporary projection that promotes it to
   `pages[0]` for the engine and restores the original file afterwards.
5. **`open_file` is cached per path.** Headless edit then reopen the same path =
   stale. Force a reload: open another file first, then reopen the target.
6. **Names carry meaning.** S-15 rejects empty, generic, or non-English node
   names and captions; S-16 rejects card children that escape their parent or
   cards padded far beyond their content. Both run on every page.

---

## 6. Engine Map and Anti-Hallucination

The FigCraft engine is a **closed binary** — every claim about its behaviour
must be proven by rendering, not guessed.

- `figcraft-cli` (when available) is an optional arbiter for headless `export`
  from disk. This skill does **not** depend on it; a bundled headless fallback
  exists in the scripts.
- `.figcraft` format = zip containing `document.json`. Connectivity keys:
  `parent` ↔ `children`, plus `flows`/`prototype`. Layout keys: `mode/wrap/gap/
  cross_gap/padding/main_align/cross_align` (+`grid_*`). Text keys:
  `characters/style/fills`.
- To learn "what is node X connected to": follow the `parent` chain upward and
  list `children` downward — never guess IDs.

**Three iron laws (violating them = hallucination):**

1. **`save()` always reflows.** `resolve_tree_layout` recomputes ALL autolayout
   child positions. Never tune `y` manually — it will revert on the next save.
   Fix structure (layout/padding/sizing).
2. **Pixels > eyes > JSON.** Measure positions via export + glyph rows, not by
   "how it looks" in the PNG and not by JSON numbers.
3. **Live sessions go stale.** `reload --hard` before a claim, or use headless
   reading from disk. When in doubt, build a small probe and measure its pixels.

---

## 7. Name Identity and Living-File Discipline

Numeric node IDs **can shift between app saves** — an old ID map may point to
the wrong node. Rules:

1. **Match nodes by `name`, not ID.** Before mutating, print the fresh
   `id + name` pair from a fresh load and match the intended name.
2. **Do not write while the user's app is open.** Concurrent writes with the app
   erase one side's work. Coordinate: ask for a pause, back up, write, request a
   reload. Always back up before the first save.
3. **Lint + parity on every save catch stray edits.** Drift over 2px or a new
   warning versus the backup baseline means a misdirected edit — revert first,
   investigate afterwards.
