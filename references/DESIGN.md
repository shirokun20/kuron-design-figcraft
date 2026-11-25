# DESIGN.md — Project Design Constitution (MANDATORY, single source of truth)

> Contract: `design-contract/v1` · Compatible with `kuron-design-figcraft` 3.2.1
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
- The parser reads **only** the text between the `design-contract/v1` start and
  end HTML comments (shown literally in §2), then calls `json.loads` (standard
  library, no extra dependencies). Do not repeat those literal comments in the
  prose above the block.
- Validation is mandatory before scripts consume values: a known `$schema`,
  required keys present, correct types, all `$...` references resolved without
  cycles, complete `dark`/`light` pairs, and contrast meeting `a11y.minContrast`.

---

## 2. Contract block (copy into your project's `DESIGN.md`)

This block is a **valid starter**: copying this file to `./DESIGN.md` passes
`json.loads()` and `validate()` on first run. Replace the values with your
project's decisions, but keep the sentinels and the required keys.

<!-- design-contract:v1:start -->
```json
{
  "$schema": "kuron-design-figcraft/design-contract/v1",
  "name": "FigCraft Reference Preset",
  "version": "1.0.0",
  "style_direction": "dense_operational",
  "default_theme": "dark",
  "locale": "en-US",
  "copy_tone": "direct, action + object",
  "tokens": {
    "primitive": {
      "color": {
        "n0": {"dark": "#0d0d10", "light": "#f7f6f4"},
        "n1": {"dark": "#141418", "light": "#ffffff"},
        "n2": {"dark": "#1a1a20", "light": "#f1f0ed"},
        "n3": {"dark": "#22222a", "light": "#e8e7e3"},
        "n4": {"dark": "#2a2a33", "light": "#deddd8"},
        "n5": {"dark": "#34343f", "light": "#d8d7d1"},
        "l0": {"dark": "#26262e", "light": "#dfdfd9"},
        "l1": {"dark": "#35353f", "light": "#c4c3bc"},
        "ring": {"dark": "#9a9aa8", "light": "#55555f"},
        "i0": {"dark": "#ececf1", "light": "#16161a"},
        "i1": {"dark": "#a5a6b0", "light": "#55555f"},
        "i2": {"dark": "#71727d", "light": "#7c7c86"},
        "brand": {"dark": "#ff6b5a", "light": "#c4342a"},
        "brandHover": {"dark": "#ff8272", "light": "#a62a21"},
        "brandFg": {"dark": "#1a0a08", "light": "#ffffff"},
        "brandSoft": {"dark": "#2e1614", "light": "#fbe9e7"},
        "tech": {"dark": "#35e7f5", "light": "#0b6e78"},
        "techSoft": {"dark": "#0e2a2e", "light": "#e0f2f4"},
        "ok": {"dark": "#5fd99a", "light": "#1f7a4d"},
        "okSoft": {"dark": "#10281d", "light": "#e4f3ea"},
        "warn": {"dark": "#ffc15e", "light": "#8a5a00"},
        "warnSoft": {"dark": "#2b2110", "light": "#fbf0dc"},
        "danger": {"dark": "#ff5c5c", "light": "#b3261e"},
        "dangerSoft": {"dark": "#2e1416", "light": "#fde8e6"},
        "info": {"dark": "#6ba6ff", "light": "#1f5fbf"},
        "infoSoft": {"dark": "#111e33", "light": "#e5eefb"}
      },
      "space": {
        "1": 4,
        "2": 8,
        "3": 12,
        "4": 16,
        "5": 20,
        "6": 24
      },
      "radius": {
        "xs": 6,
        "md": 12,
        "lg": 16,
        "pill": 9999
      },
      "type": {
        "display": 20,
        "heading": 15,
        "body": 13,
        "control": 12,
        "caption": 11,
        "mono": 10
      },
      "motion": {
        "instant": 100,
        "fast": 200,
        "normal": 320,
        "slow": 480
      }
    },
    "semantic": {
      "color": {
        "bg": "$primitive.color.n0",
        "surface": "$primitive.color.n1",
        "surface-2": "$primitive.color.n2",
        "raised": "$primitive.color.n3",
        "hover": "$primitive.color.n4",
        "selected": "$primitive.color.n5",
        "line": "$primitive.color.l0",
        "line-strong": "$primitive.color.l1",
        "ring": "$primitive.color.ring",
        "text": "$primitive.color.i0",
        "text-2": "$primitive.color.i1",
        "text-3": "$primitive.color.i2",
        "action-primary": "$primitive.color.brand",
        "action-primary-hover": "$primitive.color.brandHover",
        "action-primary-fg": "$primitive.color.brandFg",
        "action-primary-soft": "$primitive.color.brandSoft",
        "data-technical": "$primitive.color.tech",
        "data-technical-soft": "$primitive.color.techSoft",
        "status-success": "$primitive.color.ok",
        "status-success-soft": "$primitive.color.okSoft",
        "status-warn": "$primitive.color.warn",
        "status-warn-soft": "$primitive.color.warnSoft",
        "status-danger": "$primitive.color.danger",
        "status-danger-soft": "$primitive.color.dangerSoft",
        "status-info": "$primitive.color.info",
        "status-info-soft": "$primitive.color.infoSoft"
      },
      "space": {
        "xxs": "$primitive.space.1",
        "xs": "$primitive.space.2",
        "sm": "$primitive.space.3",
        "md": "$primitive.space.4",
        "lg": "$primitive.space.5",
        "xl": "$primitive.space.6"
      },
      "radius": {
        "control": "$primitive.radius.xs",
        "card": "$primitive.radius.md",
        "window": "$primitive.radius.lg",
        "pill": "$primitive.radius.pill"
      },
      "type": {
        "display": "$primitive.type.display",
        "heading": "$primitive.type.heading",
        "body": "$primitive.type.body",
        "control": "$primitive.type.control",
        "caption": "$primitive.type.caption",
        "mono": "$primitive.type.mono"
      },
      "motion": {
        "instant": "$primitive.motion.instant",
        "fast": "$primitive.motion.fast",
        "normal": "$primitive.motion.normal",
        "slow": "$primitive.motion.slow"
      }
    },
    "component": {
      "button": {
        "height": {
          "sm": 28,
          "md": 36,
          "lg": 44
        }
      },
      "field": {
        "height": 40
      },
      "badge": {
        "height": 20
      },
      "card": {
        "padding": 16
      }
    }
  },
  "a11y": {
    "minContrast": "AA",
    "minContrastRatio": {
      "normal": 4.5,
      "large": 3.0,
      "aaaNormal": 7.0,
      "aaaLarge": 4.5
    },
    "minTouchTargetPx": 44,
    "focusVisible": {
      "enabled": true,
      "widthPx": 2,
      "offsetPx": 2
    },
    "reducedMotion": true,
    "neverColorOnly": true,
    "screenReaderLabels": true
  },
  "states": [
    "default",
    "hover",
    "focus",
    "disabled",
    "empty",
    "loading",
    "error",
    "success"
  ]
}
```
<!-- design-contract:v1:end -->

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
