# FigCraft Design Patterns — A Dynamic Layout Grammar

The technical specification for `kuron-design-figcraft`. **Not** a collection of
one project's templates. Every colour, spacing, radius, type, and state value
comes from the project's `DESIGN.md` (mandatory) and `design-tokens.css`
(portable preset). If they conflict, `DESIGN.md` wins.

Companion modules: `DESIGN.md` (contract), `token-architecture.md` (hierarchy),
`style-directions.md` (direction), `dark-artifact-rules.md` (execution),
`light-glass-system.md` (theme/surface), `product-designer-2026.md` (pillars).

---

## 1. Source of Values and Anti-Hardcode

1. **Read `DESIGN.md` first.** Roles `action-primary`, `data-technical`, and
   `status-*` map to project colours. Coral/cyan in the preset are not identity.
2. **Use ladders, not magic numbers.** `semantic.space.*`, `semantic.radius.*`,
   `semantic.type.*`, `component.*` from `DESIGN.md`.
3. **Forbidden:** inventing hex values or "roughly right" margins/font sizes.
4. **Forbidden:** treating one narrative flow (for example import → translate →
   review) as the standard. That is an **example**; the project flow belongs in
   `DESIGN.md`.
5. **Auto-Layout centric.** Every container, button, card, and panel uses
   `mode: horizontal | vertical` with measured padding/gap from tokens.

---

## 2. Layout Grammar (Universal Blocks)

Combine blocks according to the direction in `DESIGN.md`. Blocks are neutral —
density, size, and hierarchy are what change.

| Block | When to use | Tokens that change its character |
|---|---|---|
| `shell` | screen/frame wrapper | `radius.window`, `bg`, `clip: true` |
| `chrome` | window bar / toolbar / breadcrumb | `space.xs`, `type.caption`, `surface-2` |
| `rail` | secondary navigation, list, filters | rail width, `line`, `hover`/`selected` |
| `canvas` | main working area | `bg`, `surface`, `measure` (editorial) |
| `inspector` | contextual detail/properties | `surface-2`, `raised`, `space.sm` |
| `toolbar` | grouped actions + status | `component.button.height`, `gap` |
| `stack` / `cluster` | vertical stack / horizontal cluster | `space.xxs…xl` |
| `grid` / `bento` | module cards, summaries | `radius.card`, `space.lg`, `raised` |
| `table` | dense data, ledger, log | `line`, `hover`, `selected`, `type.mono` |
| `article` | reading, documentation | `type.body`, `measure`, `space.md` |
| `form` | setup, wizard, input | `component.field.height`, focus `ring` |
| `dialog` / `sheet` | confirmation, quick detail | `radius.card`, elevation 3, scrim |
| `empty` / `skeleton` / `error` | mandatory states | see §5 |

**Example (not a standard)** — a three-column workbench:

```text
chrome (32px preset)
rail (196px preset) │ canvas (1fr) │ inspector (268px preset)
```

These numbers are **presets only**. A `bento_modular` project may use an
asymmetric grid; `editorial` may use one measured column; `clean_utility` may use
a single focused form.

---

## 3. Rhythm and Geometry

- Spacing rhythm uses the `semantic.space` **ladder** (preset 4/8/12/16/20/24).
  Do not insert numbers between rungs.
- Radius uses `control / card / window / pill` from `DESIGN.md`.
- Typography has three sweeps: `display`/`heading` → `body` → `mono` +
  `tabular-nums`.
- Elevation is **at most 3 levels** (`component.elevation.maxLevels`); needing a
  fourth usually means the focus ring is what is needed, not another shadow.
- `clip: true` is mandatory on screen-level frames.
- Canvas utilisation ≥60%; more than 150px of dead vertical space at the bottom
  means redistribute.

Responsiveness comes from `DESIGN.md`/project presets (390 / 834 / 1280 are
example breakpoints). Touch targets must be ≥ `a11y.minTouchTargetPx`.

---

## 4. Node Naming and Structure

1. Semantic names: `Chrome`, `Rail_<Role>`, `Canvas`, `Inspector`,
   `Btn_<Action>`, `Card_<Name>`, `Badge_<Type>`, `Empty_<Scope>`.
2. Auto-Layout sizing: main container `sizing_h: "fill"`; sidebar/inspector
   `sizing_h: "fixed"`, `sizing_v: "fill"`; button/badge `sizing_h: "hug"`,
   `sizing_v: "fixed"`; text `hug`/`hug`.
3. **Match nodes by `name`, not ID** — numeric IDs shift between saves.
4. Build base components first; create new screens with **Duplicate → Refine**,
   not by assembling raw nodes per screen (`product-designer-2026.md`).
5. **Smart reuse:** call `ensure_board()` and `find_or_reuse_component()` before
   creating anything. If a board or component already exists, copy it with
   `duplicate_node()` (fresh unique IDs, zero collisions) and override only the
   needed properties, text, or coordinates. Never rebuild a repeated item.
6. Node order follows a sensible reading order for screen readers.

### 4.1 Three-Board Container

In multi-page mode a design system gives each board its own named page:
`pages[0]` = `00_Foundations` (colour, type, spacing, radius from `DESIGN.md`),
`pages[1]` = `01_Components` (bases and variants), `pages[2]` = `02_Screens`
(screens whose repeated items duplicate nodes from `01_Components`), with
optional exhibits such as `01_Reference` at `pages[3]`. Use
`quick_design.py --preset three-pages` or `doc.ensure_named_pages([...])`.
The legacy `--preset three-board --page-index N` / `--page-name NAME` keeps the
three adjacent frames separated by `BOARD_GAP` on one page. `audit_render.py`
checks every board on every page independently.

---

## 5. Mandatory States (no "hollow" screens)

Every entry in `DESIGN.md`'s `states` must have a real design. Preset minimum:
`default`, `hover`, `focus`, `disabled`, `empty`, `loading`, `error`, `success`.

| State | Treatment |
|---|---|
| `default` | normal view / base surface; clear three-sweep hierarchy |
| `hover` | temporary `hover` token; gone when the pointer leaves |
| `focus` | `ring` 2px, offset 2px; always visible |
| `disabled` | `opacity: 0.45`, never a new colour; action blocked immediately |
| `empty` | heading + description + **action**; no illustration |
| `loading` | ≤1s disable controls; >1s spinner; >3s staged progress labels |
| `error` | cause + way out; inline and persistent when it must be read/retried |
| `success` | concise confirmation; no unfounded claims |

Three list states **must differ**: hover / keyboard cursor / persistent selection.

---

## 6. Concise Microcopy (details in `product-designer-2026.md`)

- Buttons: **action + object** — `Save changes`, not `OK`.
- Helpers: explain the expected format.
- Errors: **cause + way out**, including toasts.
- Empty state: offer an action.
- Shortcuts follow the real platform (⌘/⇧ on macOS, Ctrl+/Shift+ elsewhere).
- Text follows `locale` + `copy_tone` in `DESIGN.md`, not the skill's language.

---

## 6.1 Visual Regression Guard (mandatory, not optional)

| Rule | How to preserve it |
|---|---|
| Text must not escape its border/frame | `width`/`sizing` from tokens; verify in the PNG; never truncate text |
| Text must not clip or overlap | one line = one node; reserve room with `width`, not `min-width` |
| Screen frames must set `clip: true` | check every frame before export; keep content in bounds |
| Auto-Layout must stay consistent | `mode`, `padding`, `gap`, `fill/fixed/hug` follow `semantic.space` + `component.*`; no "almost equal" numbers |
| Duplicates must not lose styling | copy fill/stroke/radius/padding from the parent, then `refine`; `diff --id` parent vs duplicate |
| JSON must match the PNG | evidence is the opened PNG; when in doubt, `reload` + export again |

These six defects are the same **visual regression guard** as in
`dark-artifact-rules.md` and `live-editing-workflow.md`. Passing lint alone is
not enough.

---

## 7. "Do Not Hardcode" List

| Forbidden | Use instead |
|---|---|
| `#ff6b5a`, `#0d0d10`, neon `#00e5ff` | `action-primary`, `bg`, `data-technical` |
| Free `28/32/40px` | `component.button.height` |
| `gap: 7px` | `semantic.space` ladder |
| A specific project's title/labels | `locale` + `copy_tone` + `DESIGN.md` prose |
| `Import→Detect→…` as the standard | The project's screen map in `DESIGN.md` |
| "Glass is always required" | `style_direction` (editorial/utility may skip glass) |

---

## 8. One-Line Summary

`DESIGN.md → direction → universal layout blocks → semantic tokens → components
(duplicate → refine) → complete states → 3–5x PNG proof`.
