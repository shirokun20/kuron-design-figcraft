# DESIGN.md — Project Design Constitution (MANDATORY, single source of truth)

> Contract: `design-contract/v1` · Compatible with `kuron-design-figcraft` 3.1.0
>
> **This file is a TEMPLATE + SPECIFICATION.** Every consuming project **MUST**
> own a `DESIGN.md` at its project root. Copy this file, fill in the contract
> block below, then adapt the human prose to your project. Every value in the
> example is a **DEFAULT PRESET** — it may be replaced entirely. No colour,
> size, or style in this skill is sacred.

---

## 0. Golden rules

1. **Mandatory.** Without `DESIGN.md`, the agent stops with a clear error —
   silently using the skill's preset as if it were a project decision is
   **forbidden**. A preset is used only when a project explicitly copies or
   accepts it into its own `DESIGN.md`.
2. **Single source of truth.** `DESIGN.md` binds colour, typography, spacing,
   radius, motion, style direction, states, and accessibility behaviour.
   `design-tokens.css` in the same directory is only a **portable preset** for
   consumers who want the defaults — it does not override `DESIGN.md`.
3. **Machine-parseable.** One delimited JSON block (see §2) is read by the
   scripts. Human prose must not contradict the JSON; if it does, the JSON wins
   and the prose must be updated.
4. **Roles, not brands.** `action-primary` is the primary-action role — its
   colour may be red, blue, green, or anything else. `data-technical` is the
   technical-data role — it may be monospace cyan, orange, or grey. Never
   equate a role with a preset colour.
5. **Silence means `DESIGN.md` wins.** A user request overrides this document
   **only** where explicitly stated. If a request conflicts with a role/token,
   follow the user but **record the violation** in the report — do not
   normalise it silently.
6. **Absolute cleanliness.** Private paths, credentials/secrets, CDN URLs, and
   internal engine IDs are forbidden inside `DESIGN.md`. Fonts and assets are
   bundled/offline.
7. **Mandatory theme parity.** Every semantic colour must have a `dark` and a
   `light` value. Derived tints use `color-mix`, not new hex values.

---

## 1. Location, resolution, and failure

- The parser searches for `DESIGN.md` upward from the project working
  directory (stopping at the repo/package root). A custom path can be supplied
  via the `FIGCRAFT_DESIGN_MANIFEST` environment variable.
- If none is found: **fail** with a message naming the searched locations and
  how to create the file from this template. There is no silent fallback.
- The parser reads **only** the text between
  `<!-- design-contract:v1:start -->` and `<!-- design-contract:v1:end -->`,
  then calls `json.loads` (standard library, no extra dependencies).
- Validation is mandatory before scripts consume values: a known `$schema`,
  required keys present, correct types, all `$...` references resolved without
  cycles, complete `dark`/`light` pairs, and contrast meeting `a11y.minContrast`.

---

## 2. Contract block (copy into your project's `DESIGN.md`)

<!-- design-contract:v1:start -->`
  and `<!-- design-contract:v1:end -->

---

## 3. Block specification for scripts (machine contract)

### Required keys

| Key | Type | Meaning |
|---|---|---|
| `$schema` | string | Must be `kuron-design-figcraft/design-contract/v1` (or a known version prefix). |
| `name`, `version` | string | Consuming project identity, not the skill identity. |
| `style_direction` | string enum | `dense_operational` / `bento_modular` / `editorial` / `clean_utility` / `custom`. See `style-directions.md`. |
| `default_theme` | string enum | `dark` or `light`. Other themes must still have complete token pairs. |
| `locale`, `copy_tone` | string | Microcopy guidance; UI text follows these, not the skill's language. |
| `tokens.primitive` | object | Raw values: themed colours + space/radius/type/motion scales. |
| `tokens.semantic` | object | Roles (`bg`, `action-primary`, `data-technical`, `status-*`, …) + role scales. |
| `tokens.component` | object | Component sizes/variants that reference semantic tokens. |
| `a11y` | object | Contrast targets, touch target, focus, reduced motion, non-colour-only rules. |
| `states` | array of strings | States the **project must design** (at least the eight in the example). |

### Value shapes and resolver

1. **Literal** — hex/`rgba`/shadow string, or a number. Used as is.
2. **Reference** — a string such as `"$primitive.color.brand"`,
   `"$semantic.space.sm"`, or `"$a11y.minTouchTargetPx"`. Resolve by splitting
   `.` into key path segments.
   **Scope rule (mandatory for the parser):**
   - a first segment of `primitive` / `semantic` / `component` reads from
     `tokens` (an explicit `tokens` prefix is allowed: `$tokens.primitive...`);
   - any other first segment (`a11y`, `states`, `style_direction`, …) reads
     from the document root;
   - an unknown reference or a cycle is an error.
3. Primitive **colours are always pairs** of `{"dark": ..., "light": ...}`.
   A semantic colour value is a reference to a primitive, or a literal pair
   `{"dark": ..., "light": ...}` when a project wants a direct override.
   Scales (space/radius/type/motion) are not themed.

### Override and parity rules

- **Full override is allowed.** A project may replace the entire `primitive`
  block, add new keys, and remap `semantic` to any keys. What is forbidden:
  deleting roles used by the scripts, leaving an empty theme pair, or dangling
  references.
- **Merge by key.** Project values win on matching keys; unmentioned keys keep
  the copied preset values.
- **One role = one token.** Do not invent `hover-project-x` to replace `hover`;
  change the `hover` value in `DESIGN.md` instead.
- **Tints are always derived**, e.g.
  `color-mix(in srgb, var(--token) 12%, transparent)`.
- **At most three elevation levels.** Needing a fourth usually means a focus
  ring is wanted, not another shadow.

### Failures scripts must report

Missing `DESIGN.md` · missing sentinel · invalid JSON · wrong `$schema` ·
missing required key · unresolved/cyclic `$...` reference · incomplete theme
pair · contrast below `a11y.minContrast` · empty `states`.

---

## 4. Human section (written prose; not for the parser)

### Direction and rationale

Write 3-5 sentences: domain, target user, main problem, measurable outcome, and
why this `style_direction` was chosen. Note if this is a style blend or
`custom`.

### Screen map and flow

List the core screens plus the primary and secondary action flows. **The
example below is not a standard** — replace it with your project's flow:

```text
Example (illustration only): Summary → List → Detail → Edit → Save
```

Optional machine-readable extension: a `screens` array inside the contract
block with `id`, `name`, `x`, `y`, `width`, `height` entries. The bundled
reference generator reads it; consuming projects may ignore it.

### Microcopy and states

- Labels: **action + object** (`Save changes`, not `OK`).
- Errors: **cause + way out** (`Could not save: connection lost. Try again.`).
- Empty state: **offer an action**, not an illustration.
- Every `states` entry in the JSON block must have a real design here or in a
  component module — no hollow screens.
- AI (where relevant): proportionate status (silent → disabled → spinner →
  incremental progress) + cancel/retry controls + transparency without
  overclaiming.

Optional machine-readable extension: a `copy` object keyed by `locale`, mapping
copy keys (e.g. `submit`, `cancel`) to project strings. `quick_design.py` reads
it; a missing key falls back to a neutral title-cased label.

### Accessibility and handoff

- Minimum AA contrast; a AAA target is declared in `a11y.minContrast`.
- Keyboard focus is always visible; `prefers-reduced-motion` is honoured.
- Touch targets ≥ `a11y.minTouchTargetPx` in touch contexts (hit areas may be
  larger than the visual desktop control height).
- Status must not rely on colour alone — include text or an icon.
- FigCraft node order follows a sensible reading order for screen readers.

---

## 5. DESIGN.md acceptance checklist

- [ ] File exists at the project root and the JSON block sits between the two sentinels.
- [ ] JSON passes `json.loads`; `$schema` and all required keys are present.
- [ ] Every `$...` reference resolves; no empty theme pairs.
- [ ] `style_direction` was chosen for the domain (not from laziness).
- [ ] `action-primary` and `data-technical` are mapped deliberately, not left
      at preset colours without a conscious decision.
- [ ] `a11y` and `states` bind real designs, not mere lists.
- [ ] No private path, secret, CDN URL, or internal engine ID.
- [ ] Prose does not contradict the JSON block.

> **Supremacy:** the project's `DESIGN.md` binds every value. The skill provides
> mechanisms and presets, not taste. Silence = `DESIGN.md` wins.
