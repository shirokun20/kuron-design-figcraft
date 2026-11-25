# Token Architecture — Primitive → Semantic → Component → Theme/State

This module explains one central idea: **raw values are never consumed directly
by components**. Each layer has a single responsibility, so changing a brand
colour, density, or theme never forces edits to every screen.

Authority remains the project's `DESIGN.md`. `design-tokens.css` in the same
directory is a **preset implementation** of this architecture for consumers who
want the defaults immediately.

---

## 1. Four layers

| Layer | Contents | Example (preset) | Changed by |
|---|---|---|---|
| **Primitive** | Raw values with no UI meaning | `--ks-p-n0: #0d0d10`, `--ks-p-brand: #ff6b5a`, `--ks-p-space-2: 8px` | brand owner / project `DESIGN.md` |
| **Semantic** | Roles used by the design | `--ks-bg: var(--ks-p-n0)`, `--ks-accent: var(--ks-p-brand)`, `--ks-space-sm: var(--ks-p-space-2)` | project `DESIGN.md` (role mapping) |
| **Component** | Component sizes/variants derived from semantics | `--ks-c-button-h-md: 32px`, `--ks-c-card-radius: var(--ks-radius-card)` | project `DESIGN.md` via the `tokens.component` block |
| **Theme/State** | Theme pairs + state behaviour | `[data-theme="light"]`, `[data-current="true"]`, `:focus-visible`, `prefers-reduced-motion` | project `DESIGN.md` via `default_theme`, `a11y`, `states` |

Stacking rule: **component → semantic → primitive**. Skipping the semantic
layer (a component calling a primitive directly) is forbidden.

---

## 2. Three iron rules

1. **One role = one token.** Need a darker hover? Change the value of
   `--ks-hover` in `DESIGN.md`; do not invent `--ks-hover-2`.
2. **Tints are derived.** `color-mix(in srgb, var(--token) N%, transparent)` —
   never a new hex value. Dark/light parity is automatic.
3. **No magic numbers in builders.** Spacing, radius, font size, and colour are
   read from tokens. Numbers in scripts are only for engine geometry that has
   no token counterpart (e.g. vector coordinates), and even those are fixed by
   the contract, not by a momentary preference.

---

## 3. Semantic role map — stable names, variable values

These are the roles scripts read; **role names are stable**, colours are freely
overridable.

| Role (JSON key) | CSS alias | Function |
|---|---|---|
| `bg` | `--ks-bg` | deepest canvas |
| `surface` | `--ks-surface` | main working surface |
| `surface-2` | `--ks-surface-2` | header, toolbar, rail |
| `raised` | `--ks-raised` | elevated card/panel |
| `hover` | `--ks-hover` | transient state |
| `selected` | `--ks-selected` | persistent selection |
| `line`, `line-strong` | `--ks-line`, `--ks-line-strong` | 1px divider / contour |
| `ring` | `--ks-ring` | keyboard focus + selection halo |
| `text`, `text-2`, `text-3` | `--ks-text*` | three-level text hierarchy |
| `action-primary` (+`-hover`, `-fg`, `-soft`) | `--ks-accent*` | **one** primary action per screen |
| `data-technical` (+`-soft`) | `--ks-cyan*` | monospace technical data + `tabular-nums` |
| `status-success/warn/danger/info` (+`-soft`) | `--ks-status-*` | status, with companion text/icon |
| `glass-*` | `--ks-glass-*` | floating chrome (optional by style direction) |

> Compatibility note: `--ks-accent` / `--ks-cyan` are retained as preset aliases
> for the `action-primary` / `data-technical` roles. They are **old variable
> names**, not a requirement that the colours be red/cyan.

---

## 4. Scales as tokens, not loose numbers

| Scale | Semantic keys | Preset | Used for |
|---|---|---|---|
| Space | `xxs … xl` | 4 / 8 / 12 / 16 / 20 / 24 | gap, padding, margin |
| Radius | `control / card / window / pill` | 6 / 12 / 16 / 9999 | controls, cards, frames, badges |
| Type | `display / heading / body / control / caption / mono` | 20 / 15 / 13 / 12 / 11 / 10 | typographic hierarchy |
| Motion | `instant / fast / normal / slow` | 100 / 200 / 320 / 480 ms | transitions, spinners, skeletons |

Scales are **ordinal**: use the available rungs rather than inserting `9px` or
`13.5px` because it is "almost right". If a new step is needed, add it to
`primitive` in `DESIGN.md`.

---

## 5. Contract for scripts (summary; details in `DESIGN.md` §3)

1. Find `DESIGN.md`, extract the delimited JSON block, validate it.
2. Resolve `$...` references to literals; detect cycles with a cut-loop guard.
3. Select the theme value per `default_theme` (or an explicit theme override).
4. Map roles → colours/sizes used by builders.
5. Check contrast (`a11y.minContrast`), touch targets, and `states` presence.
6. On validation failure: **actionable error**, never a silent preset.
7. Record every override in the report (`role: preset → project value`).

With this in place, changing a brand colour or style direction only requires
editing `DESIGN.md`; builders, lint, and export stay the same.

---

## 6. Forbidden hardcoding

- Hex/colour, spacing, radius, and font values directly in builders/templates.
- A specific project name, feature title, or narrative flow as the "standard".
- The assumption that `action-primary` is red or `data-technical` is cyan.
- One UI language as mandatory (read `locale` / `copy_tone`).
- One port, path, or binary as a sacred constant (read
  `live-editing-workflow.md`).

---

## 7. One-line summary

`primitive (values) → semantic (roles, from DESIGN.md) → component (sizes) →
theme/state (parity + accessibility)`; components never call a primitive
directly.
